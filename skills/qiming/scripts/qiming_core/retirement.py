"""Read-only impact assessment and proposed member lifecycle changes."""

from __future__ import annotations

from pathlib import Path

from .members import member_view
from .profile import load_profile
from .scan import _relative_path, _root


def record_redirect(manifest_path: Path, old_ref: dict[str, str], new_ref: dict[str, str]) -> dict[str, object]:
    """Persist a merge redirect through the same Plan/Apply path as other edits."""
    import hashlib
    import json
    from .codec import load_record
    from .members import resolve_member_ref
    from .plan import plan_changes
    from .transactions import apply_plan

    if old_ref == new_ref or old_ref.get("workspace_id") != new_ref.get("workspace_id"):
        raise ValueError("merge target must be a distinct member in the same workspace")
    if resolve_member_ref(manifest_path, new_ref).get("status") != "ok":
        raise ValueError("merge target cannot be resolved")
    registry = manifest_path.parent / "redirects.json"
    redirects = load_record(registry, "json")[0] if registry.exists() else {}
    redirects[_key(old_ref)] = new_ref
    if resolve_redirect(old_ref, redirects) is None:
        raise ValueError("redirect cycle")
    data = (json.dumps(redirects, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    staged = manifest_path.parent / "redirects.stage"
    staged.write_bytes(data)
    manifest, _ = load_record(manifest_path, "json")
    alias = next(alias for alias, config in manifest["roots"].items() if config.get("access") == "read-write" and manifest_path.parent.is_relative_to(_root(manifest_path, alias)))
    root = _root(manifest_path, alias)
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    change = {"action": "replace" if registry.exists() else "create", "target": {"kind": "file", "root": alias, "path": str(registry.relative_to(root))}, "expected_sha256": digest(registry.read_bytes()) if registry.exists() else None, "content_ref": staged.name, "desired_sha256": digest(data)}
    profile_sha = digest((manifest_path.parent / str(manifest["profile"])).read_bytes())
    planned = plan_changes(manifest_path, [change], "merge-member-redirect", profile_sha)
    return apply_plan(manifest_path, planned["result"]) if planned["status"] == "ok" else planned


def _key(ref: dict[str, str]) -> str:
    return f"{ref.get('workspace_id')}:{ref.get('id')}"


def resolve_redirect(ref: dict[str, str], redirects: dict[str, dict[str, str]]) -> dict[str, str] | None:
    current = ref
    seen: set[str] = set()
    while _key(current) in redirects:
        marker = _key(current)
        if marker in seen:
            return None
        seen.add(marker)
        current = redirects[marker]
    return current


def retirement_impact(manifest_path: Path, member_ref: dict[str, str]) -> dict[str, object]:
    profile = load_profile(manifest_path)
    members: list[dict[str, object]] = []
    errors: list[str] = []
    for collection_id, collection in profile["collections"].items():
        root = _root(manifest_path, str(collection["root"]))
        directory = _relative_path(root, str(collection.get("directory", ".")))
        if not directory.is_dir():
            continue
        for path in directory.glob(str(collection.get("pattern", "*.json"))):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                members.append(member_view(manifest_path, {"root": collection["root"], "path": str(path.relative_to(root)), "collection": collection_id}))
            except (OSError, ValueError) as exc:
                errors.append(str(path))
    selected = [member for member in members if member["ref"] == member_ref]
    if len(selected) != 1:
        return {"status": "conflict", "member": None, "callers": [], "diagnostics": [{"code": "REFERENCE_UNRESOLVED", "message": "Member is missing or ambiguous", "locator": None, "retryable": False, "details": {}}], "scan_errors": errors}
    callers = []
    for member in members:
        relations = [relation for relation in member.get("relations", []) if relation.get("target") == member_ref]
        if relations:
            callers.append({"ref": member["ref"], "record_locator": member["record_locator"], "relations": relations})
    retrieval = profile.get("retrieval", {})
    scope_rules = profile.get("scope_rules", {})
    return {"status": "ok", "member": selected[0], "callers": callers, "derived_index": retrieval.get("index_path"), "known_exports": scope_rules.get("known_exports", []), "known_backups": scope_rules.get("known_backups", []), "scan_errors": errors, "redirects": {}}


def retirement_changes(impact: dict[str, object], action: str) -> list[dict[str, object]]:
    if impact.get("status") != "ok" or not isinstance(impact.get("member"), dict):
        raise ValueError("retirement impact is unresolved")
    member = impact["member"]
    authority = member["record_locator"]
    if action in {"archive", "retire"}:
        return [{"scope": "authority", "action": "propose-update", "target": authority, "lifecycle": "archived" if action == "archive" else "retired", "callers": impact.get("callers", [])}]
    if action == "merge":
        target = impact.get("merge_target")
        if not isinstance(target, dict) or target == member["ref"]:
            raise ValueError("merge requires a distinct target")
        redirects = dict(impact.get("redirects", {}))
        redirects[_key(member["ref"])] = target
        if resolve_redirect(member["ref"], redirects) is None:
            raise ValueError("redirect cycle")
        return [{"scope": "authority", "action": "propose-redirect", "target": authority, "redirect": {"from": member["ref"], "to": target}, "callers": impact.get("callers", [])}]
    if action == "delete":
        changes = [{"scope": "authority", "action": "propose-remove", "target": authority, "callers": impact.get("callers", [])}]
        if impact.get("derived_index"):
            changes.append({"scope": "derived-index", "action": "rebuild-or-remove", "target": impact["derived_index"]})
        changes.extend({"scope": "known-export", "action": "inspect-copy", "target": item} for item in impact.get("known_exports", []))
        changes.extend({"scope": "known-backup", "action": "external-limitation", "target": item} for item in impact.get("known_backups", []))
        return changes
    raise ValueError("unsupported retirement action")
