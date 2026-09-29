"""Find one workspace entry without silently crossing a management boundary."""

from __future__ import annotations

from pathlib import Path

from .codec import load_record


def _diagnostic(code: str, message: str, paths: list[str] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "locator": None, "retryable": False, "details": {"paths": paths or []}}


def _valid(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value, _ = load_record(path, "json")
        if value.get("protocol") != "qiming.workspace/1" or not isinstance(value.get("workspace_id"), str):
            return None
        return value
    except (OSError, ValueError):
        return None


def _default_boundary(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / ".git").exists() or (parent / ".qiming" / "workspace.json").exists():
            return parent
    return start


def project_root(manifest_path: Path, manifest: dict | None = None) -> Path:
    """Resolve the owning project, independently of control-directory depth."""
    control = manifest_path.resolve().parent
    if manifest is None:
        manifest, _ = load_record(manifest_path, "json")
    relative = manifest.get("project_root")
    if relative is not None:
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("project_root must be relative to the control directory")
        root = (control / relative).resolve()
    elif control.name == ".qiming":
        root = control.parent  # Legacy default layout.
    else:
        candidates = {(control / str(config["location"])).resolve()
                      for config in manifest.get("roots", {}).values()
                      if isinstance(config, dict) and isinstance(config.get("location"), str)}
        candidates = {candidate for candidate in candidates if control.is_relative_to(candidate)}
        if len(candidates) != 1:
            raise ValueError("Legacy custom layout requires an explicit project_root")
        root = candidates.pop()
    if not root.is_dir() or not control.is_relative_to(root):
        raise ValueError("Control directory must remain inside its owning project")
    return root


def scope_check(manifest_path: Path, start_dir: Path) -> dict[str, object]:
    """Check the active task directory, not the location of an external resource."""
    manifest_path = manifest_path.resolve()
    manifest = _valid(manifest_path)
    if not manifest or manifest.get("state") != "ready":
        return {"status": "conflict", "active": False, "reason": "instance-not-ready"}
    try:
        root = project_root(manifest_path, manifest)
    except ValueError as error:
        return {"status": "conflict", "active": False, "reason": "invalid-project-root", "detail": str(error)}
    start = start_dir.resolve()
    if not start.is_relative_to(root):
        return {"status": "outside", "active": False, "project_root": str(root)}
    for directory in (start, *start.parents):
        if directory == root:
            break
        candidate = directory / ".qiming" / "workspace.json"
        if candidate.exists() or (directory / ".git").exists():
            return {"status": "nested-project", "active": False, "project_root": str(root), "boundary": str(directory)}
    return {"status": "active", "active": True, "workspace_id": manifest["workspace_id"], "project_root": str(root)}


def discover(start_dir: Path, explicit_manifest: Path | None = None, boundary: Path | None = None) -> dict[str, object]:
    start = start_dir.resolve()
    stop = (boundary or _default_boundary(start)).resolve()
    if not start.is_relative_to(stop):
        raise ValueError("start directory is outside boundary")
    candidates: list[Path] = []
    for directory in (start, *start.parents):
        if not directory.is_relative_to(stop):
            break
        candidate = directory / ".qiming" / "workspace.json"
        if candidate.exists():
            candidates.append(candidate)
        if directory == stop:
            break
    closest = candidates[0] if candidates else None
    chosen = explicit_manifest.resolve() if explicit_manifest else closest
    if chosen is None:
        return {"status": "none", "manifest_path": None, "candidates": [], "diagnostics": []}
    chosen_value = _valid(chosen)
    if chosen_value is None:
        return {"status": "conflict", "manifest_path": None, "candidates": [str(chosen)], "diagnostics": [_diagnostic("BROKEN_ENTRY", "Workspace entry is missing or invalid", [str(chosen)])]}
    if explicit_manifest and closest and closest.resolve() != chosen:
        closest_value = _valid(closest)
        if closest_value and closest_value.get("workspace_id") != chosen_value.get("workspace_id"):
            paths = [str(chosen), str(closest)]
            return {"status": "conflict", "manifest_path": None, "candidates": paths, "diagnostics": [_diagnostic("AMBIGUOUS_ENTRY", "Explicit and local workspace entries differ", paths)]}
    return {"status": "ok", "manifest_path": str(chosen), "candidates": [str(path) for path in candidates], "diagnostics": []}
