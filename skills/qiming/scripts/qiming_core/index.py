"""Rebuildable SQLite metadata index; authority remains in source records."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path

from .members import member_view
from .profile import load_profile
from .scan import _relative_path, _root


def authority_records(manifest_path: Path, collections: list[str], *, limit: int | None = None) -> tuple[list[dict[str, object]], dict[str, object]]:
    profile = load_profile(manifest_path)
    selected = collections or list(profile["collections"])
    rows: list[dict[str, object]] = []
    redirects_path = manifest_path.parent / "redirects.json"
    redirects = {}
    if redirects_path.is_file():
        from .codec import load_record

        redirects, _ = load_record(redirects_path, "json")
    errors: list[str] = []
    skipped: list[str] = []
    skipped_files: list[dict] = []
    visited = 0
    truncated = False
    for collection_id in selected:
        collection = profile["collections"].get(collection_id)
        if not isinstance(collection, dict):
            errors.append(f"unknown collection: {collection_id}")
            continue
        root = _root(manifest_path, str(collection["root"]))
        directory = _relative_path(root, str(collection.get("directory", ".")))
        if not directory.is_dir():
            errors.append(f"missing collection directory: {collection_id}")
            continue
        from .collections import collection_paths
        for root, path in collection_paths(manifest_path, profile, collection):
            if limit is not None and visited >= limit:
                truncated = True
                break
            visited += 1
            if path.is_symlink() or not path.is_file():
                continue
            locator = {"root": collection["root"], "path": path.relative_to(root).as_posix(), "collection": collection_id}
            try:
                if collection.get('codec') == 'markdown-frontmatter' and not path.read_bytes().startswith(b'---'):
                    skipped.append(path.relative_to(root).as_posix())
                    skipped_files.append({'path':path.relative_to(root).as_posix(),'root':collection['root'],'collection':collection_id,'reason':'missing-frontmatter'})
                    continue
                view = member_view(manifest_path, locator)
                if f"{view['ref']['workspace_id']}:{view['ref']['id']}" not in redirects:
                    rows.append(view)
            except (OSError, ValueError):
                errors.append(path.relative_to(root).as_posix())
        if truncated:
            break
    return rows, {"collections": selected, "visited": visited, "truncated": truncated, "errors": errors, "skipped": skipped, "skipped_files": skipped_files, "skipped_count": len(skipped_files)}


def coverage_diagnostics(coverage):
    if coverage['errors'] or coverage['truncated'] or coverage['skipped']:
        return [{'code':'INCOMPLETE_COVERAGE','message':f"Search coverage incomplete: {len(coverage['skipped'])} skipped files, {len(coverage['errors'])} errors.",'hint':'Inspect result.coverage.skipped_files and errors. Plain Markdown needs explicit adaptation; no member IDs were invented.'}]
    return []


def source_set_fingerprint(rows: list[dict[str, object]]) -> str:
    tokens = sorted(f"{row['ref']['workspace_id']}:{row['ref']['id']}:{row['record_fingerprint']}" for row in rows)
    return hashlib.sha256("\n".join(tokens).encode("utf-8")).hexdigest()


def _index_path(manifest_path: Path) -> Path:
    profile = load_profile(manifest_path)
    relative = str(profile.get("retrieval", {}).get("index_path", "index.sqlite"))
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("index path must remain in control directory")
    result = (manifest_path.parent / path).resolve()
    if not result.is_relative_to(manifest_path.parent.resolve()):
        raise ValueError("index path escapes control directory")
    return result


def reindex(manifest_path: Path, collections: list[str]) -> dict[str, object]:
    rows, coverage = authority_records(manifest_path, collections)
    destination = _index_path(manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".index-", suffix=".sqlite", dir=destination.parent)
    os.close(descriptor)
    try:
        os.chmod(temporary, 0o600)
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("CREATE TABLE records (workspace_id TEXT, id TEXT, collection_id TEXT, root TEXT, path TEXT, scope TEXT, type TEXT, name TEXT, summary TEXT, fingerprint TEXT)")
            for row in rows:
                connection.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (row["ref"]["workspace_id"], row["ref"]["id"], row["record_locator"]["collection"], row["record_locator"]["root"], row["record_locator"]["path"], row.get("scope"), row.get("type"), row.get("name"), row.get("summary"), row["record_fingerprint"]))
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"status": "partial" if coverage["errors"] or coverage["truncated"] or coverage["skipped"] else "ok", "result": {"index_ref": str(destination), "source_set_fingerprint": source_set_fingerprint(rows), "coverage": coverage}, "diagnostics": coverage_diagnostics(coverage), "changed": [{"path": str(destination), "action": "replaced-derived-index"}]}
