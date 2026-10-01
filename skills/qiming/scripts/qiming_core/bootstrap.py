"""Resumable, exclusive creation of a workspace control directory."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _conflict(message: str, path: Path) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": "OWNERSHIP_CONFLICT", "message": message, "locator": str(path), "retryable": False, "details": {}}], "changed": []}


def bootstrap(root: Path, control_dir: Path, manifest: dict[str, object], profile: dict[str, object], initialization_id: str) -> dict[str, object]:
    root = root.resolve()
    control = control_dir.resolve()
    if not control.is_relative_to(root) or not root.is_dir():
        raise ValueError("control directory must be inside an existing workspace")
    if not initialization_id or manifest.get("protocol") != "qiming.workspace/1" or profile.get("protocol") != "qiming.profile/1":
        raise ValueError("invalid initialization id or protocol")
    if manifest.get("state") != "initializing":
        raise ValueError("bootstrap requires initializing state")
    from .profile import validate_profile
    validate_profile(profile, manifest)
    original_manifest = manifest
    manifest = dict(manifest)
    declared = manifest.get("project_root")
    if declared is not None and (not isinstance(declared, str) or not declared or Path(declared).is_absolute() or (control / declared).resolve() != root):
        raise ValueError("project_root differs from the explicit bootstrap root")
    manifest["project_root"] = os.path.relpath(root, control)
    existing = control / "workspace.json"
    # Resume an exact old initialization without rewriting its owned bytes.
    if "project_root" not in original_manifest and existing.is_file() and existing.read_bytes() == _bytes(original_manifest):
        from .discovery import project_root
        if project_root(existing, original_manifest) != root:
            return _conflict("Legacy project root differs from explicit root", existing)
        manifest = original_manifest
    profile_path = manifest.get("profile", "profile.json")
    journal_path = manifest.get("init_journal", "init.json")
    if not isinstance(profile_path, str) or not isinstance(journal_path, str):
        raise ValueError("profile and journal paths are required")
    for relative in (profile_path, journal_path):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("bootstrap path must remain in control directory")
    journal = {"protocol": "qiming.initialization/1", "initialization_id": initialization_id, "workspace_id": manifest.get("workspace_id"), "stage": "discovered", "completed": ["bootstrap"], "initial_manifest": manifest, "initial_profile": profile}
    expected = {control / "workspace.json": _bytes(manifest), control / profile_path: _bytes(profile), control / journal_path: _bytes(journal)}
    if len(expected) != 3:
        raise ValueError("bootstrap paths must be distinct")
    for path, data in expected.items():
        if path.exists() and path.read_bytes() != data:
            return _conflict("Existing control file has different content", path)
    control.mkdir(parents=True, exist_ok=True)
    changed = []
    # The journal is the exclusive initialization marker and is created first.
    for path in (control / journal_path, control / profile_path, control / "workspace.json"):
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as target:
                target.write(expected[path])
        except FileExistsError:
            if path.read_bytes() != expected[path]:
                return _conflict("Concurrent initialization changed a control file", path)
        changed.append({"path": str(path), "action": "created"})
    return {"status": "ok", "result": {"manifest_path": str(control / "workspace.json"), "initialization_id": initialization_id}, "diagnostics": [], "changed": changed}
