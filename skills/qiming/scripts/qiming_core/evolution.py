"""Preflight local profile migrations and guard mixed intermediate states."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .codec import load_record
from .index import authority_records
from .plan import plan_changes
from .profile import load_profile, normalize_fields
from .scan import _relative_path, _root


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _diag(code: str, message: str, locator: str | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "locator": locator, "retryable": False, "details": {}}


def _conflict(code: str, message: str, locator: str | None = None) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [_diag(code, message, locator)], "changed": []}


def migration_guard(manifest_path: Path, collections: list[str]) -> list[dict[str, object]]:
    marker = manifest_path.parent / "migration.json"
    if not marker.exists():
        return []
    try:
        value, _ = load_record(marker, "json")
    except (OSError, ValueError):
        return [_diag("RECOVERY_REQUIRED", "Migration marker cannot be read", str(marker))]
    affected = value.get("affected_collections", [])
    if not collections or set(collections).intersection(affected):
        return [_diag("RECOVERY_REQUIRED", "A profile migration is incomplete; inspect its operation journal", str(value.get("journal_ref", marker)))]
    return []


def _put_simple_pointer(record: dict[str, object], pointer: str, value: object) -> bool:
    if not pointer.startswith("/") or "/" in pointer[1:]:
        return False
    key = pointer[1:].replace("~1", "/").replace("~0", "~")
    if key in record and record[key] != value:
        return False
    record[key] = copy.deepcopy(value)
    return True


def plan_profile_migration(manifest_path: Path, new_profile_ref: Path, affected_collections: list[str], intent_ref: str) -> dict[str, object]:
    manifest, _ = load_record(manifest_path, "json")
    old_profile = load_profile(manifest_path)
    old_profile_path = (manifest_path.parent / str(manifest["profile"])).resolve()
    candidate = new_profile_ref.resolve()
    if not candidate.is_relative_to(manifest_path.parent.resolve()) or not candidate.is_file() or candidate == old_profile_path:
        return _conflict("PATH_ESCAPE", "New profile must be a distinct staged control file", str(new_profile_ref))
    try:
        new_profile, new_raw = load_record(candidate, "json")
    except (OSError, ValueError) as exc:
        return _conflict("SCHEMA_INVALID", str(exc), str(candidate))
    if new_profile.get("protocol") != "qiming.profile/1":
        return _conflict("UNSUPPORTED_PROTOCOL", "New profile protocol unsupported", str(candidate))
    if not affected_collections:
        return _conflict("INVALID_INPUT", "Affected collections must be explicit")
    for name in affected_collections:
        if name not in old_profile.get("collections", {}) or name not in new_profile.get("collections", {}):
            return _conflict("SCHEMA_INVALID", "Affected collection missing in old or new profile", name)
        old_collection = old_profile["collections"][name]
        new_collection = new_profile["collections"][name]
        if any(old_collection.get(field) != new_collection.get(field) for field in ("root", "directory", "pattern", "codec")):
            return _conflict("SCHEMA_INVALID", "Collection relocation needs an explicit file move plan", name)
        if old_collection.get("codec") != "json":
            return _conflict("SCHEMA_INVALID", "Existing codec cannot safely rewrite records", name)
    rows, coverage = authority_records(manifest_path, affected_collections)
    if coverage["errors"] or coverage["truncated"]:
        return _conflict("SCHEMA_INVALID", "Cannot migrate with incomplete source coverage")
    stage = manifest_path.parent / "migrations"
    proposed: list[tuple[Path, bytes, dict[str, object]]] = []
    affected_ids: list[str] = []
    for row in rows:
        locator = row["record_locator"]
        collection_id = locator["collection"]
        collection = new_profile["collections"][collection_id]
        mapping = new_profile["mappings"].get(collection.get("mapping"))
        if not isinstance(mapping, dict):
            return _conflict("SCHEMA_INVALID", "New collection mapping is missing", collection_id)
        path = _relative_path(_root(manifest_path, locator["root"]), locator["path"])
        source, raw = load_record(path, "json")
        updated = copy.deepcopy(source)
        old_fields = {key: row.get(key) for key in ("name", "lifecycle", "scope", "type")}
        old_fields["id"] = row["ref"]["id"]
        for field in ("id", "name", "scope", "type"):
            rule = mapping.get(field)
            if not isinstance(rule, dict) or field not in old_fields or old_fields[field] is None:
                continue
            current = normalize_fields(updated, {field: rule}).get(field)
            if current is None:
                if not _put_simple_pointer(updated, str(rule.get("source", "")), old_fields[field]):
                    return _conflict("SCHEMA_INVALID", f"Ambiguous field mapping: {field}", str(path))
                if field == "name" and source.get("name") == old_fields[field]:
                    aliases = updated.get("aliases", [])
                    if not isinstance(aliases, list):
                        return _conflict("SCHEMA_INVALID", "Existing aliases is not a list", str(path))
                    if old_fields[field] not in aliases:
                        updated["aliases"] = aliases + [old_fields[field]]
            elif current != old_fields[field]:
                return _conflict("SCHEMA_INVALID", f"New mapping changes {field} meaning", str(path))
        new_fields = normalize_fields(updated, mapping)
        if new_fields.get("id", source.get("id")) != row["ref"]["id"]:
            return _conflict("SCHEMA_INVALID", "Migration changes member ID", str(path))
        if old_fields["lifecycle"] is not None and new_fields.get("lifecycle") != old_fields["lifecycle"]:
            return _conflict("SCHEMA_INVALID", "Ambiguous lifecycle value mapping", str(path))
        if updated != source:
            data = (json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            proposed.append((path, data, locator))
        affected_ids.append(str(row["ref"]["id"]))
    changes = []
    stage.mkdir(exist_ok=True)
    for path, data, locator in proposed:
        staged = stage / f"{_sha(str(path).encode())}.json"
        staged.write_bytes(data)
        changes.append({"action": "replace", "target": {"kind": "file", "root": locator["root"], "path": locator["path"]}, "expected_sha256": _sha(path.read_bytes()), "content_ref": str(staged.relative_to(manifest_path.parent)), "desired_sha256": _sha(data)})
    # The profile is switched after records; the marker prevents mixed reads.
    root_alias = None
    root_path = None
    for alias, binding in manifest.get("roots", {}).items():
        if binding.get("access") == "read-write":
            root = (manifest_path.parent / str(binding.get("location", ""))).resolve()
            if old_profile_path.is_relative_to(root):
                root_alias, root_path = alias, root
                break
    if root_alias is None:
        return _conflict("PATH_ESCAPE", "No writable root contains profile")
    old_raw = old_profile_path.read_bytes()
    changes.append({"action": "replace", "target": {"kind": "file", "root": root_alias, "path": str(old_profile_path.relative_to(root_path))}, "expected_sha256": _sha(old_raw), "content_ref": str(candidate.relative_to(manifest_path.parent)), "desired_sha256": _sha(new_raw)})
    planned = plan_changes(manifest_path, changes, intent_ref, _sha(old_raw))
    if planned["status"] != "ok":
        return planned
    planned["result"]["migration"] = {"old_profile_sha256": _sha(old_raw), "new_profile_sha256": _sha(new_raw), "affected_collections": affected_collections, "affected_ids": affected_ids, "marker": "migration.json", "postconditions": {"ids_preserved": True, "new_profile_valid": True}}
    return planned
