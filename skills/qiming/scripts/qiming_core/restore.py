"""Inspect a bundle, preview root rebinding, and restore to an empty target."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .bootstrap import bootstrap
from .codec import load_record
from .plan import plan_changes
from .transactions import apply_plan
from .validate import validate


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _failure(code: str, message: str) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": code, "message": message, "locator": None, "retryable": False, "details": {}}], "changed": []}


def _bundle_file(bundle_root: Path, relative: str) -> Path:
    fragment = Path(relative)
    if fragment.is_absolute() or ".." in fragment.parts or not relative.startswith("workspace/"):
        raise ValueError("bundle entry path is unsafe")
    path = bundle_root / fragment
    if path.is_symlink() or not path.resolve().is_relative_to(bundle_root.resolve()):
        raise ValueError("bundle entry escapes bundle root")
    return path


def inspect_bundle(bundle_root: Path) -> dict[str, object]:
    bundle_root = bundle_root.resolve()
    try:
        descriptor_path = bundle_root / "bundle.json"
        descriptor, raw = load_record(descriptor_path, "json")
        if descriptor.get("protocol") != "qiming.bundle/1" or not isinstance(descriptor.get("files"), list):
            return _failure("UNSUPPORTED_PROTOCOL", "Bundle manifest is unsupported")
        seen: set[str] = set()
        for entry in descriptor["files"]:
            relative = str(entry["bundle_path"])
            if relative in seen:
                return _failure("SCHEMA_INVALID", "Duplicate bundle entry")
            seen.add(relative)
            path = _bundle_file(bundle_root, relative)
            data = path.read_bytes()
            if len(data) != entry.get("bytes") or _sha(data) != entry.get("sha256"):
                return _failure("STALE_SOURCE", "Bundle file hash or size mismatch")
        required = "workspace/.qiming/workspace.json"
        if required not in seen:
            return _failure("BROKEN_ENTRY", "Bundle lacks workspace manifest")
        return {"status": "ok", "result": {"bundle_root": str(bundle_root), "bundle_sha256": _sha(raw), "descriptor": descriptor, "verified_files": len(seen)}, "diagnostics": [], "changed": []}
    except (OSError, ValueError, KeyError) as exc:
        return _failure("BROKEN_ENTRY", str(exc))


def restore_preview(bundle_root: Path, target_root: Path, root_bindings: dict[str, str]) -> dict[str, object]:
    checked = inspect_bundle(bundle_root)
    if checked["status"] != "ok":
        return checked
    target = target_root.resolve()
    if target.exists() and any(target.iterdir()):
        return _failure("WRITE_CONFLICT", "Restore target is not empty")
    descriptor = checked["result"]["descriptor"]
    old_manifest, _ = load_record(bundle_root / "workspace" / ".qiming" / "workspace.json", "json")
    rebound = json.loads(json.dumps(old_manifest))
    missing: list[dict[str, object]] = []
    if "work" not in root_bindings:
        return _failure("PATH_ESCAPE", "work root must be bound to restore target")
    for alias, config in rebound.get("roots", {}).items():
        bound = root_bindings.get(alias)
        if bound is None:
            missing.append({"kind": "root-binding", "root": alias})
            config["location"] = f"__UNBOUND__/{alias}"
            config["access"] = "read-only"
            continue
        location = Path(bound).resolve()
        if alias == "work":
            if location != target:
                return _failure("PATH_ESCAPE", "work root must bind to restore target")
            config["location"] = os.path.relpath(location, target / ".qiming")
        else:
            config["location"] = str(location)
    for omission in descriptor.get("omissions", []):
        if omission.get("reason") in {"external-root-not-selected", "business-content-missing", "required-instance-resource-missing"}:
            missing.append({"kind": "business-content", "reason": omission.get("reason"), "root": omission.get("root")})
        elif omission.get("reason") == "instance-not-materialized":
            missing.append({"kind": "instance", "reason": omission.get("reason")})
    missing.append({"kind": "credential-provider", "reason": "Credential values are managed outside the bundle"})
    result = {"bundle_root": str(bundle_root.resolve()), "bundle_sha256": checked["result"]["bundle_sha256"], "target_root": str(target), "workspace_id": descriptor["workspace_id"], "restored_manifest": rebound, "files": descriptor["files"], "missing": missing, "verification": "not-run"}
    return {"status": "partial" if missing else "ok", "result": result, "diagnostics": [], "changed": []}


def apply_restore(preview: dict[str, object]) -> dict[str, object]:
    bundle_root = Path(str(preview["bundle_root"]))
    target = Path(str(preview["target_root"]))
    checked = inspect_bundle(bundle_root)
    if checked["status"] != "ok":
        return checked
    if checked["result"]["bundle_sha256"] != preview.get("bundle_sha256"):
        return _failure("STALE_SOURCE", "Bundle changed since preview")
    if preview.get("files") != checked["result"]["descriptor"].get("files"):
        return _failure("WRITE_CONFLICT", "Restore preview file selection changed")
    if target.exists() and any(target.iterdir()):
        return _failure("WRITE_CONFLICT", "Restore target is not empty")
    rebound = preview["restored_manifest"]
    if rebound.get("workspace_id") != preview.get("workspace_id") or rebound.get("protocol") != "qiming.workspace/1":
        return _failure("SCHEMA_INVALID", "Preview workspace identity mismatch")
    work_binding = rebound.get("roots", {}).get("work", {}).get("location")
    if not isinstance(work_binding, str) or (target / ".qiming" / work_binding).resolve() != target.resolve():
        return _failure("PATH_ESCAPE", "Restored work root does not bind to target")
    if (target / ".qiming" / str(rebound.get("profile", "profile.json"))).resolve().parent != (target / ".qiming").resolve():
        return _failure("PATH_ESCAPE", "Profile path is unsafe")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    control = target / ".qiming"
    profile, _ = load_record(bundle_root / "workspace" / ".qiming" / str(rebound["profile"]), "json")
    initializing = json.loads(json.dumps(rebound))
    initializing["state"] = "initializing"
    initializing["init_journal"] = "init.json"
    initialized = bootstrap(target, control, initializing, profile, f"restore_{preview['workspace_id']}")
    if initialized["status"] != "ok":
        return initialized
    manifest_path = control / "workspace.json"
    profile_sha = _sha((control / "profile.json").read_bytes())
    stage = control / "restore-stage"
    stage.mkdir(exist_ok=True)
    changes = []
    for index, entry in enumerate(preview["files"]):
        relative = str(entry["bundle_path"])
        if relative in {"workspace/.qiming/workspace.json", "workspace/.qiming/profile.json", "workspace/.qiming/init.json"}:
            continue
        source = _bundle_file(bundle_root, relative)
        data = source.read_bytes()
        if _sha(data) != entry.get("sha256"):
            return _failure("STALE_SOURCE", "Bundle file changed during restore")
        destination = target / relative.removeprefix("workspace/")
        if not destination.resolve(strict=False).is_relative_to(target):
            return _failure("PATH_ESCAPE", "Restore path escapes target")
        staged = stage / f"file-{index}"
        staged.write_bytes(data)
        changes.append({"action": "create", "target": {"kind": "file", "root": "work", "path": str(destination.relative_to(target))}, "expected_sha256": None, "content_ref": str(staged.relative_to(control)), "desired_sha256": _sha(data)})
    journals = []
    changed = list(initialized["changed"])
    if changes:
        planned = plan_changes(manifest_path, changes, "restore-bundle-files", profile_sha)
        if planned["status"] != "ok":
            return planned
        applied = apply_plan(manifest_path, planned["result"])
        if applied["status"] != "ok":
            return applied
        journals.append(applied["result"]["journal_ref"])
        changed.extend(applied["changed"])
    final_manifest = json.loads(json.dumps(rebound))
    final_manifest["init_journal"] = "init.json"
    final_bytes = (json.dumps(final_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    final_stage = stage / "final-workspace.json"
    final_stage.write_bytes(final_bytes)
    manifest_change = {"action": "replace", "target": {"kind": "file", "root": "work", "path": ".qiming/workspace.json"}, "expected_sha256": _sha(manifest_path.read_bytes()), "content_ref": str(final_stage.relative_to(control)), "desired_sha256": _sha(final_bytes)}
    planned = plan_changes(manifest_path, [manifest_change], "restore-rebound-manifest", profile_sha)
    if planned["status"] != "ok":
        return planned
    applied = apply_plan(manifest_path, planned["result"])
    if applied["status"] != "ok":
        return applied
    journals.append(applied["result"]["journal_ref"])
    changed.extend(applied["changed"])
    structural = validate(manifest_path, [], False)
    if structural["status"] != "ok":
        return {"status": "partial", "result": {"manifest_path": str(manifest_path), "journals": journals, "validation": structural}, "diagnostics": structural["diagnostics"], "changed": changed}
    shutil.rmtree(stage, ignore_errors=True)
    return {"status": "partial" if preview.get("missing") else "ok", "result": {"manifest_path": str(manifest_path), "journals": journals, "verification": "structural-only", "missing": preview.get("missing", [])}, "diagnostics": [], "changed": changed}


def restore_record(result: dict[str, object], checks: list[dict[str, object]]) -> dict[str, object]:
    evaluated = [check for check in checks if check.get("kind") in {"inspection", "execution", "user-acceptance"} and check.get("result") in {"pass", "fail", "inconclusive"} and check.get("evidence_ref")]
    verification = "not-run" if not evaluated else "pass" if all(check["result"] == "pass" for check in evaluated) and not result.get("missing") else "fail" if any(check["result"] == "fail" for check in evaluated) else "inconclusive"
    return {"protocol": "qiming.restore/1", "workspace_id": result.get("workspace_id"), "target_root": result.get("target_root"), "observed_at": datetime.now(timezone.utc).isoformat(), "checks": evaluated, "missing": result.get("missing", []), "verification": verification, "status": "pass" if verification == "pass" else "partial"}
