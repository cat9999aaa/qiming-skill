"""Derive member views from one authoritative local record."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .codec import load_record
from .profile import load_profile, normalize_fields
from .scan import _relative_path, _root

_LIFECYCLE = {"candidate", "maintained", "paused", "retired", "archived"}


def member_view(manifest_path: Path, record_locator: dict[str, object]) -> dict[str, object]:
    manifest, _ = load_record(manifest_path, "json")
    profile = load_profile(manifest_path)
    collection_id = record_locator.get("collection")
    collection = profile["collections"].get(collection_id)
    if not isinstance(collection, dict):
        raise ValueError(f"unknown collection: {collection_id}")
    if record_locator.get("root") != collection.get("root"):
        raise ValueError("record root does not match collection")
    mapping = profile["mappings"].get(collection.get("mapping"))
    if not isinstance(mapping, dict):
        raise ValueError("collection mapping is missing")
    root = _root(manifest_path, str(record_locator["root"]))
    path = _relative_path(root, str(record_locator["path"]))
    if path.is_symlink():
        raise ValueError("record path is a symlink")
    source, raw = load_record(path, str(collection.get("codec", "json")))
    fields = normalize_fields(source, mapping)
    identity = fields.get("id", source.get("id"))
    if not isinstance(identity, str) or not identity:
        raise ValueError("member requires stable id in authority record")
    lifecycle = fields.get("lifecycle")
    if lifecycle not in _LIFECYCLE:
        lifecycle = None
    mapped_roots = {str(rule.get("source", "")).split("/")[1].replace("~1", "/").replace("~0", "~") for rule in mapping.values() if isinstance(rule, dict) and str(rule.get("source", "")).startswith("/")}
    extensions = {key: value for key, value in source.items() if key not in mapped_roots and key not in {"id", "verification", "locators", "relations", "extensions"}}
    if isinstance(source.get("extensions"), dict):
        extensions.update(source["extensions"])
    return {
        "ref": {"workspace_id": manifest["workspace_id"], "id": identity},
        "record_locator": {"kind": "file", "root": record_locator["root"], "path": record_locator["path"], "collection": collection_id},
        "record_fingerprint": hashlib.sha256(raw).hexdigest(),
        "schema_ref": collection.get("mapping"),
        "name": fields.get("name", source.get("name")),
        "type": fields.get("type", source.get("type", "custom")),
        "summary": fields.get("summary", source.get("summary")),
        "owner": fields.get("owner", source.get("owner")),
        "scope": fields.get("scope", source.get("scope", "workspace")),
        "lifecycle": lifecycle,
        "updated_at": fields.get("updated_at", source.get("updated_at")),
        "review_after": fields.get("review_after", source.get("review_after")),
        "verification": source.get("verification", []),
        "locators": source.get("locators", []),
        "relations": source.get("relations", []),
        "extensions": extensions,
    }


def _key(ref: dict[str, object]) -> tuple[object, object]:
    return ref.get("workspace_id"), ref.get("id")


def validate_relation_graph(members: list[dict[str, object]]) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    by_ref = {_key(member["ref"]): member for member in members}
    edges: dict[tuple[object, object], list[tuple[object, object]]] = {}
    for member in members:
        source = _key(member["ref"])
        edges[source] = []
        for relation in member.get("relations", []):
            target = _key(relation.get("target", {}))
            if target not in by_ref:
                diagnostics.append({"code": "REFERENCE_UNRESOLVED", "message": "Relation target is outside the available member set", "source": source, "target": target})
            if relation.get("kind") == "part_of":
                edges[source].append(target)
    visited: set[tuple[object, object]] = set()
    active: set[tuple[object, object]] = set()

    def walk(node: tuple[object, object]) -> None:
        if node in active:
            diagnostics.append({"code": "RELATION_CYCLE", "message": "part_of relation contains a cycle", "source": node})
            return
        if node in visited:
            return
        active.add(node)
        for target in edges.get(node, []):
            if target in by_ref:
                walk(target)
        active.remove(node)
        visited.add(node)

    for node in edges:
        walk(node)
    return diagnostics


def resolve_member_ref(manifest_path: Path, ref: dict[str, str]) -> dict[str, object]:
    manifest, _ = load_record(manifest_path, "json")
    if ref.get("workspace_id") != manifest.get("workspace_id"):
        return {"status": "unresolved", "ref": ref, "reason": "external-workspace"}
    redirects_path = manifest_path.parent / "redirects.json"
    if redirects_path.is_file():
        from .retirement import resolve_redirect

        redirects, _ = load_record(redirects_path, "json")
        final = resolve_redirect(ref, redirects)
        if final is None:
            return {"status": "conflict", "ref": ref, "reason": "redirect-cycle"}
        if final != ref:
            resolved = resolve_member_ref(manifest_path, final)
            resolved["redirected_from"] = ref
            return resolved
    profile = load_profile(manifest_path)
    matches = []
    for collection_id, collection in profile["collections"].items():
        root = _root(manifest_path, str(collection["root"]))
        directory = _relative_path(root, str(collection.get("directory", ".")))
        for path in directory.glob(str(collection.get("pattern", "*.json"))):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                view = member_view(manifest_path, {"root": collection["root"], "path": str(path.relative_to(root)), "collection": collection_id})
            except (OSError, ValueError):
                continue
            if view["ref"]["id"] == ref.get("id"):
                matches.append(view)
    if len(matches) == 1:
        return {"status": "ok", "view": matches[0]}
    return {"status": "conflict" if matches else "unresolved", "ref": ref, "matches": matches}
