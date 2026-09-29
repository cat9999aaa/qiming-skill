"""Export selected user-owned resources with byte hashes and explicit omissions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .codec import load_record
from .index import authority_records
from .profile import load_profile
from .scan import _relative_path, _root
from .secrets import validate_account_ref


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(code: str, message: str) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": code, "message": message, "locator": None, "retryable": False, "details": {}}], "changed": []}


def bundle(manifest_path: Path, selection: dict[str, object], destination: Path, include_history: bool, *, _test_before_copy: Callable[[Path], None] | None = None) -> dict[str, object]:
    manifest_path = manifest_path.resolve()
    destination = destination.resolve()
    manifest, _ = load_record(manifest_path, "json")
    profile = load_profile(manifest_path)
    roots = {alias: _root(manifest_path, alias) for alias in manifest.get("roots", {})}
    if destination.exists():
        return _fail("WRITE_CONFLICT", "Bundle destination already exists")
    if any(destination.is_relative_to(root) for root in roots.values()):
        return _fail("PATH_ESCAPE", "Bundle destination is inside an input root")
    scopes = selection.get("scope_ids", ["workspace"])
    if not isinstance(scopes, list):
        return _fail("INVALID_INPUT", "scope_ids must be a list")
    selected: list[tuple[Path, str, str, dict[str, object] | None, str]] = []
    omissions: list[dict[str, object]] = []
    source_root = manifest_path.parent.parent
    control = manifest_path.parent
    for name in ("workspace.json", str(manifest.get("profile", "profile.json")), str(manifest.get("workspace_entry", "")), str(manifest.get("conventions", "")), str(manifest.get("init_journal", ""))):
        if not name:
            continue
        path = control / name
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(control):
            selected.append((path, f"workspace/{path.relative_to(source_root)}", "management", None, "workspace"))
    instance = manifest.get("instance")
    if isinstance(instance, dict):
        instance_manifest = control / str(instance.get("manifest", ""))
        if instance_manifest.is_file():
            instance_doc, _ = load_record(instance_manifest, "json")
            selected.append((instance_manifest, f"workspace/{instance_manifest.relative_to(source_root)}", "instance-manifest", None, "workspace"))
            for resource in instance_doc.get("resources", []):
                path = instance_manifest.parent / str(resource.get("path", ""))
                if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(instance_manifest.parent.resolve()):
                    selected.append((path, f"workspace/{path.relative_to(source_root)}", "instance-resource", None, "workspace"))
                elif resource.get("required"):
                    omissions.append({"reason": "required-instance-resource-missing", "path": str(resource.get("path"))})
        else:
            omissions.append({"reason": "instance-manifest-missing"})
    else:
        omissions.append({"reason": "instance-not-materialized"})
    rows, coverage = authority_records(manifest_path, selection.get("collections", []))
    excluded_count = 0
    for row in rows:
        if row.get("scope") not in scopes or (not include_history and row.get("lifecycle") in {"retired", "archived"}):
            excluded_count += 1
            continue
        locator = row["record_locator"]
        root = roots[locator["root"]]
        path = _relative_path(root, locator["path"])
        if path.suffix.lower() in {".env", ".key", ".pem", ".p12"} or path.name.startswith(".env"):
            omissions.append({"reason": "sensitive-file-excluded", "record_ref": row["ref"]})
            continue
        collection = profile["collections"][locator["collection"]]
        record, _ = load_record(path, str(collection.get("codec", "json")))
        if validate_account_ref(record):
            omissions.append({"reason": "credential-value-in-record", "record_ref": row["ref"]})
            continue
        if not path.is_relative_to(source_root):
            omissions.append({"reason": "external-root-not-selected", "root": locator["root"], "path": locator["path"]})
            continue
        selected.append((path, f"workspace/{path.relative_to(source_root)}", "authority", row["ref"], str(row.get("scope"))))
    if excluded_count:
        omissions.append({"reason": "scope-or-history-excluded", "count": excluded_count})
    for locator in selection.get("business_paths", []):
        alias = locator.get("root")
        if alias not in roots:
            omissions.append({"reason": "unknown-root", "root": alias})
            continue
        root = roots[alias]
        path = _relative_path(root, str(locator.get("path", "")))
        if not path.is_relative_to(source_root):
            omissions.append({"reason": "external-root-not-selected", "root": alias, "path": locator.get("path")})
            continue
        if path.is_file() and not path.is_symlink():
            selected.append((path, f"workspace/{path.relative_to(source_root)}", "business-content", None, "selected"))
        else:
            omissions.append({"reason": "business-content-missing", "root": alias, "path": locator.get("path")})
    unique: dict[str, tuple[Path, str, str, dict[str, object] | None, str]] = {item[1]: item for item in selected}
    stage = Path(tempfile.mkdtemp(prefix=".qiming-bundle-", dir=destination.parent))
    files: list[dict[str, object]] = []
    try:
        for path, bundle_path, role, record_ref, scope in unique.values():
            data = path.read_bytes()
            if _test_before_copy:
                _test_before_copy(path)
            if _sha(path.read_bytes()) != _sha(data):
                return _fail("STALE_SOURCE", "Source changed during export")
            output = stage / bundle_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            files.append({"bundle_path": bundle_path, "bytes": len(data), "sha256": _sha(data), "role": role, "scope": scope, "record_ref": record_ref})
        for item in files:
            if _sha((stage / item["bundle_path"]).read_bytes()) != item["sha256"]:
                return _fail("IO_ERROR", "Bundle verification failed")
        descriptor = {"protocol": "qiming.bundle/1", "workspace_id": manifest.get("workspace_id"), "created_at": datetime.now(timezone.utc).isoformat(), "files": files, "omissions": omissions, "coverage": coverage, "root_aliases": list(roots), "credential_recovery": "external-provider-required"}
        (stage / "bundle.json").write_text(json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"status": "partial" if omissions or coverage["errors"] or coverage["truncated"] else "ok", "result": {"bundle_manifest": str(destination / "bundle.json"), "omissions": omissions, "verification": {"files": len(files), "hashes_match": True}}, "diagnostics": [], "changed": [{"path": str(destination), "action": "created-bundle"}]}
