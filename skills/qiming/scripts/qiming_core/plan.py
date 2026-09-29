"""Prepare bounded file changes without changing target files or directories."""

from __future__ import annotations

import hashlib
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .codec import load_record
from .scan import _root


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _conflict(code: str, message: str, locator: str | None = None) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": code, "message": message, "locator": locator, "retryable": False, "details": {}}], "changed": []}


def resolve_target(manifest_path: Path, locator: dict[str, object], *, writable: bool = True) -> Path:
    if locator.get("kind") != "file" or not isinstance(locator.get("root"), str) or not isinstance(locator.get("path"), str):
        raise ValueError("invalid file locator")
    relative = str(locator["path"])
    fragment = Path(relative)
    if fragment.is_absolute() or relative in {"", "."} or ".." in fragment.parts or "\x00" in relative:
        raise ValueError("file path must be relative inside registered root")
    manifest, _ = load_record(manifest_path, "json")
    root_config = manifest.get("roots", {}).get(locator["root"])
    if not isinstance(root_config, dict) or (writable and root_config.get("access") != "read-write"):
        raise ValueError("root is unavailable or read-only")
    root = _root(manifest_path, str(locator["root"]))
    target = root / fragment
    if not target.resolve(strict=False).is_relative_to(root):
        raise ValueError("file path escapes registered root")
    current = root
    for component in fragment.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("symlink in file path")
    if target.exists() and (not target.is_file() or target.stat().st_nlink > 1):
        raise ValueError("target is not an unshared regular file")
    return target


def plan_changes(manifest_path: Path, changes: list[dict[str, object]], intent_ref: str, expected_profile_sha256: str) -> dict[str, object]:
    manifest, _ = load_record(manifest_path, "json")
    if manifest.get("protocol") != "qiming.workspace/1":
        return _conflict("UNSUPPORTED_PROTOCOL", "Unsupported workspace protocol")
    if manifest.get("state") == "repair_required":
        return _conflict("RECOVERY_REQUIRED", "Workspace requires repair")
    profile_relative = manifest.get("profile")
    if not isinstance(profile_relative, str):
        return _conflict("SCHEMA_INVALID", "Profile path missing")
    profile_path = (manifest_path.parent / profile_relative).resolve()
    if not profile_path.is_relative_to(manifest_path.parent.resolve()):
        return _conflict("PATH_ESCAPE", "Profile path escapes control directory")
    if _sha(profile_path) != expected_profile_sha256:
        return _conflict("WRITE_CONFLICT", "Profile fingerprint changed", str(profile_path))
    if not isinstance(changes, list) or not changes:
        return _conflict("INVALID_INPUT", "At least one change is required")
    parents: set[str] = set()
    seen: set[str] = set()
    for change in changes:
        try:
            target = resolve_target(manifest_path, change["target"])
        except (ValueError, KeyError) as exc:
            return _conflict("PATH_ESCAPE", str(exc))
        if str(target) in seen:
            return _conflict("WRITE_CONFLICT", "Plan repeats one target", str(target))
        seen.add(str(target))
        action = change.get("action")
        expected = change.get("expected_sha256")
        current = _sha(target) if target.exists() else None
        if action not in {"create", "replace", "remove"}:
            return _conflict("INVALID_INPUT", "Unsupported change action", str(target))
        if current != expected or (action == "create" and current is not None) or (action != "create" and current is None):
            return _conflict("WRITE_CONFLICT", "Target fingerprint changed", str(target))
        if action == "remove":
            if change.get("content_ref") is not None or change.get("desired_sha256") is not None:
                return _conflict("INVALID_INPUT", "Remove cannot have desired content", str(target))
        else:
            content_ref = change.get("content_ref")
            if not isinstance(content_ref, str):
                return _conflict("INVALID_INPUT", "Staged content path missing", str(target))
            staged = (manifest_path.parent / content_ref).resolve()
            if not staged.is_relative_to(manifest_path.parent.resolve()) or not staged.is_file() or staged.is_symlink():
                return _conflict("PATH_ESCAPE", "Staged content must be a control-directory file", content_ref)
            if _sha(staged) != change.get("desired_sha256"):
                return _conflict("WRITE_CONFLICT", "Staged content fingerprint changed", content_ref)
        parent = target.parent
        while not parent.exists():
            parents.add(str(parent))
            parent = parent.parent
    plan = {
        "protocol": "qiming.plan/1",
        "plan_id": f"plan_{uuid.uuid4()}",
        "workspace_id": manifest["workspace_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_sha256": expected_profile_sha256,
        "intent_ref": intent_ref,
        "changes": changes,
        "parents_to_create": sorted(parents, key=lambda path: (len(Path(path).parts), path)),
        "expected_outcome": None,
    }
    return {"status": "ok", "result": plan, "diagnostics": [], "changed": []}
