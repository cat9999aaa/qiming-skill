"""Scope-first local search with a Unicode substring fallback."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from .codec import load_record
from .index import authority_records, source_set_fingerprint
from .profile import load_profile
from .scan import _relative_path, _root


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _cursor_decode(cursor: str) -> dict[str, object]:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii") + b"=" * (-len(cursor) % 4)))
        if not isinstance(value, dict):
            raise ValueError("cursor is not an object")
        return value
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid search cursor") from exc


def _stale() -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": "STALE_CURSOR", "message": "Search sources or request changed; restart at first page", "locator": None, "retryable": True, "details": {}}], "changed": []}


def search(manifest_path: Path, request: dict[str, object]) -> dict[str, object]:
    from .evolution import migration_guard

    profile = load_profile(manifest_path)
    scopes = request.get("scope_ids", ["workspace"])
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        raise ValueError("scope_ids must be a list of strings")
    limit = int(request.get("limit", 20))
    if limit < 1 or limit > 100:
        raise ValueError("search limit must be 1..100")
    collections = request.get("collections", list(profile["collections"]))
    blocked = migration_guard(manifest_path, collections)
    if blocked:
        return {"status": "conflict", "result": None, "diagnostics": blocked, "changed": []}
    configured_limit = profile.get("retrieval", {}).get("max_candidates")
    rows, coverage = authority_records(manifest_path, collections, limit=int(configured_limit) if configured_limit is not None else None)
    snapshot = source_set_fingerprint(rows)
    query = str(request.get("query", ""))
    types = request.get("types")
    identity = request.get("ref")
    signature = _fingerprint({"scopes": scopes, "query": query, "types": types, "ref": identity, "collections": collections, "include_history": bool(request.get("include_history", False)), "limit": limit})
    offset = 0
    if request.get("cursor"):
        cursor = _cursor_decode(str(request["cursor"]))
        if cursor.get("snapshot") != snapshot or cursor.get("request") != signature:
            return _stale()
        offset = int(cursor.get("offset", 0))
    matched: list[tuple[int, dict[str, object]]] = []
    # Scope filtering happens before content is read for candidate matching.
    for row in rows:
        if row.get("scope") not in scopes:
            continue
        if types and row.get("type") not in types:
            continue
        if not request.get("include_history") and row.get("lifecycle") in {"retired", "archived"}:
            continue
        locator = row["record_locator"]
        exact = identity and row["ref"] == identity
        path_match = query and query == locator["path"]
        metadata = f"{row.get('name') or ''}\n{row.get('summary') or ''}\n{row['ref']['id']}"
        meta_match = query.casefold() in metadata.casefold() if query else True
        body_match = False
        if query and not exact and not path_match and not meta_match:
            collection = profile["collections"][locator["collection"]]
            path = _relative_path(_root(manifest_path, locator["root"]), locator["path"])
            raw = path.read_text(encoding="utf-8")
            body_match = query.casefold() in raw.casefold()
        if identity and not exact:
            continue
        if not (exact or path_match or meta_match or body_match):
            continue
        rank = 0 if exact or path_match else 1 if meta_match else 2
        matched.append((rank, {"workspace_id": row["ref"]["workspace_id"], "id": row["ref"]["id"], "name": row.get("name"), "summary": row.get("summary"), "type": row.get("type"), "scope": row.get("scope"), "record_locator": locator, "record_fingerprint": row["record_fingerprint"], "match": "exact" if rank == 0 else "metadata" if rank == 1 else "text", "freshness": "source-current"}))
    matched.sort(key=lambda item: (item[0], item[1]["workspace_id"], item[1]["id"]))
    items = [item for _, item in matched[offset:offset + limit]]
    next_offset = offset + len(items)
    next_cursor = None
    if next_offset < len(matched):
        payload = json.dumps({"snapshot": snapshot, "request": signature, "offset": next_offset}, separators=(",", ":"))
        next_cursor = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    result = {"items": items, "next_cursor": next_cursor, "coverage": {**coverage, "source_set_fingerprint": snapshot, "searched_scopes": scopes, "matched": len(matched)}, "warnings": ["Index optional; searched source files"]}
    return {"status": "partial" if coverage["truncated"] or coverage["errors"] else "ok", "result": result, "diagnostics": [], "changed": []}
