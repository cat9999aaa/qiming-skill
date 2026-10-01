"""Bounded metadata observation; never open the contents of scanned files."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

from .codec import load_record

_EXCLUDE = {".git", ".qiming", "node_modules", ".venv", "__pycache__", ".pytest_cache"}


def _root(manifest_path: Path, alias: str) -> Path:
    manifest, _ = load_record(manifest_path, "json")
    roots = manifest.get("roots")
    if not isinstance(roots, dict) or alias not in roots or not isinstance(roots[alias], dict):
        raise ValueError(f"unknown root alias: {alias}")
    location = roots[alias].get("location")
    if not isinstance(location, str):
        raise ValueError(f"root alias lacks location: {alias}")
    return (manifest_path.parent / location).resolve()


def _relative_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\x00" in relative:
        raise ValueError("relative path escapes registered root")
    target = root / path
    # The link itself is observable; only its parent directories must stay in scope.
    if target != root and not target.parent.resolve().is_relative_to(root):
        raise ValueError("relative path resolves outside registered root")
    return target


def scan(manifest_path: Path, roots: list[str], relative_paths: list[str], budget: dict[str, int]) -> dict[str, object]:
    max_entries = int(budget.get("entries", 2000))
    max_depth = int(budget.get("depth", 2))
    max_seconds = int(budget.get("seconds", 10))
    if min(max_entries, max_depth, max_seconds) < 0:
        raise ValueError("scan budget cannot be negative")
    started = time.monotonic()
    observed_at = datetime.now(timezone.utc).isoformat()
    observations: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    excluded: list[str] = []
    queue: list[tuple[str, Path, Path, int]] = []
    if not roots:
        from .profile import load_profile
        from .collections import collection_paths
        profile=load_profile(manifest_path)
        for collection in profile['collections'].values():
            for root,path in collection_paths(manifest_path,profile,collection):
                if len(queue)>=max_entries: break
                queue.append((collection['root'],root,path,0))
    for alias in roots:
        root = _root(manifest_path, alias)
        for relative in relative_paths or [""]:
            queue.append((alias, root, _relative_path(root, relative), 0))
    visited = 0
    truncated = False
    while queue:
        if visited >= max_entries or time.monotonic() - started >= max_seconds:
            truncated = True
            break
        alias, root, current, depth = queue.pop(0)
        try:
            if current.is_symlink():
                children = [current]
            elif current.is_dir():
                children = sorted(current.iterdir(), key=lambda p: p.name)
            else:
                children = [current]
        except OSError as exc:
            errors.append({"locator": {"kind": "file", "root": alias, "path": str(current.relative_to(root))}, "code": "IO_ERROR", "message": str(exc)})
            continue
        for child in children:
            if visited >= max_entries or time.monotonic() - started >= max_seconds:
                truncated = True
                break
            relative = str(child.relative_to(root))
            if child.name in _EXCLUDE:
                excluded.append(relative)
                continue
            try:
                metadata = child.lstat()
            except OSError as exc:
                errors.append({"locator": {"kind": "file", "root": alias, "path": relative}, "code": "IO_ERROR", "message": str(exc)})
                continue
            kind = "symlink" if stat.S_ISLNK(metadata.st_mode) else "directory" if stat.S_ISDIR(metadata.st_mode) else "file" if stat.S_ISREG(metadata.st_mode) else "other"
            observations.append({"observed_at": observed_at, "locator": {"kind": "file", "root": alias, "path": relative}, "facts": {"kind": kind, "size": metadata.st_size if kind == "file" else None}, "coverage": "metadata-only"})
            visited += 1
            if kind == "directory" and depth < max_depth:
                queue.append((alias, root, child, depth + 1))
        if truncated:
            break
    token = None
    if truncated:
        request = json.dumps({"manifest": str(manifest_path), "roots": roots, "relative_paths": relative_paths, "budget": budget}, sort_keys=True)
        token = {"request_sha256": hashlib.sha256(request.encode()).hexdigest(), "visited": visited, "remaining": [str(item[2]) for item in queue]}
    return {"status": "partial" if truncated or errors else "ok", "observations": observations, "coverage": {"visited": visited, "truncated": truncated, "excluded": excluded, "errors": len(errors)}, "errors": errors, "resume_token": token}
