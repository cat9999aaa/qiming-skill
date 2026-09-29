"""Scope-limited member deletion and cleanup of controllable derived copies."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .codec import load_record
from .index import reindex
from .plan import plan_changes
from .profile import load_profile
from .retirement import retirement_impact
from .scan import _root
from .transactions import apply_plan
from .journal import read_json, write_json


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(value: dict[str, object]) -> str:
    safe = {key: item for key, item in value.items() if key != "digest"}
    return _sha(json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _conflict(code: str, message: str) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": code, "message": message, "locator": None, "retryable": False, "details": {}}], "changed": []}


def _historical_copies(manifest_path: Path, targets: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Find operation backups and staged bytes tied to the selected authority paths."""
    control = manifest_path.parent.resolve()
    locators = {(item["target"]["root"], item["target"]["path"]) for item in targets if item.get("scope") in {"authority", "known-export"}}
    copies: list[dict[str, object]] = []
    limitations: list[dict[str, object]] = []
    seen: set[str] = set()
    for journal_path in sorted((control / "operations").glob("plan_*.json")):
        try:
            journal = read_json(journal_path)
            if journal.get("protocol") != "qiming.journal/1":
                continue
            for index, change in enumerate(journal["plan"]["changes"]):
                target = change.get("target", {})
                if (target.get("root"), target.get("path")) not in locators:
                    continue
                if journal.get("state") not in {"completed", "rolled_back"}:
                    limitations.append({"kind": "incomplete-operation", "location": str(journal_path), "reason": "Reconcile this operation before deleting the member"})
                    continue
                candidates = [("backup", journal["backups"][index]), ("staged", change.get("content_ref"))]
                for kind, relative in candidates:
                    if not relative:
                        continue
                    path = Path(relative) if kind == "backup" else control / str(relative)
                    if path.is_symlink() or not path.resolve().is_relative_to(control):
                        limitations.append({"kind": "historical-copy", "location": str(path), "reason": "Outside managed control directory or symlink"})
                        continue
                    if path.is_file() and str(path) not in seen:
                        seen.add(str(path))
                        copies.append({"kind": kind, "path": str(path), "sha256": _sha(path.read_bytes()), "journal_ref": str(journal_path), "index": index})
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            limitations.append({"kind": "historical-copy", "location": str(journal_path), "reason": f"Cannot inspect operation journal: {type(exc).__name__}"})
    return copies, limitations


def deletion_preview(manifest_path: Path, member_ref: dict[str, str], requested_scope: dict[str, object]) -> dict[str, object]:
    impact = retirement_impact(manifest_path, member_ref)
    if impact["status"] != "ok":
        return _conflict("REFERENCE_UNRESOLVED", "Member does not have one authority record")
    if not requested_scope.get("authority"):
        return _conflict("SCOPE_DENIED", "Deletion request must explicitly include authority record")
    manifest, _ = load_record(manifest_path, "json")
    profile = load_profile(manifest_path)
    targets = [{"scope": "authority", "target": impact["member"]["record_locator"], "sha256": impact["member"]["record_fingerprint"]}]
    limitations = [{"kind": "known-backup", "location": item, "reason": "External backup must be handled through its own provider"} for item in impact.get("known_backups", [])]
    if requested_scope.get("known_exports"):
        for relative in impact.get("known_exports", []):
            path = Path(str(relative))
            if path.is_absolute() or ".." in path.parts:
                limitations.append({"kind": "known-export", "location": str(relative), "reason": "Outside managed root"})
                continue
            selected = None
            for alias, config in manifest.get("roots", {}).items():
                root = _root(manifest_path, alias)
                if config.get("access") == "read-write" and (manifest_path.parent.parent / path).resolve().is_relative_to(root):
                    selected = (alias, root)
                    break
            if selected is None:
                limitations.append({"kind": "known-export", "location": str(relative), "reason": "No writable registered root"})
                continue
            candidate = manifest_path.parent.parent / path
            if candidate.is_file() and not candidate.is_symlink():
                targets.append({"scope": "known-export", "target": {"kind": "file", "root": selected[0], "path": str(candidate.relative_to(selected[1]))}, "sha256": _sha(candidate.read_bytes())})
    else:
        limitations.extend({"kind": "known-export", "location": item, "reason": "Not included in requested scope"} for item in impact.get("known_exports", []))
    if requested_scope.get("derived_index") and impact.get("derived_index"):
        targets.append({"scope": "derived-index", "path": str(impact["derived_index"]), "action": "rebuild-after-authority-removal"})
    if not requested_scope.get("business_original"):
        for locator in impact["member"].get("locators", []):
            limitations.append({"kind": "business-original", "location": locator, "reason": "Original content outside requested deletion scope"})
    historical_copies, history_limits = _historical_copies(manifest_path, targets)
    limitations.extend(history_limits)
    if any(item["kind"] == "incomplete-operation" for item in history_limits):
        return _conflict("RECOVERY_REQUIRED", "A related operation must be reconciled before deletion")
    result = {"protocol": "qiming.deletion-preview/1", "plan_id": f"plan_{uuid.uuid4()}", "manifest_path": str(manifest_path.resolve()), "member_ref": member_ref, "requested_scope": requested_scope, "authority_fingerprint": impact["member"]["record_fingerprint"], "targets": targets, "historical_copies": historical_copies, "limitations": limitations, "callers": impact.get("callers", [])}
    result["digest"] = _digest(result)
    return {"status": "ok", "result": result, "diagnostics": [], "changed": []}


def apply_deletion(preview: dict[str, object], plan_id: str) -> dict[str, object]:
    if preview.get("protocol") != "qiming.deletion-preview/1" or preview.get("plan_id") != plan_id or preview.get("digest") != _digest(preview):
        return _conflict("WRITE_CONFLICT", "Deletion preview changed")
    manifest_path = Path(str(preview["manifest_path"]))
    impact = retirement_impact(manifest_path, preview["member_ref"])
    if impact["status"] != "ok" or impact["member"]["record_fingerprint"] != preview.get("authority_fingerprint"):
        return _conflict("STALE_SOURCE", "Member changed since deletion preview")
    fresh = deletion_preview(manifest_path, preview["member_ref"], preview["requested_scope"])
    if fresh["status"] != "ok" or fresh["result"]["targets"] != preview.get("targets") or fresh["result"]["historical_copies"] != preview.get("historical_copies") or fresh["result"]["limitations"] != preview.get("limitations"):
        return _conflict("WRITE_CONFLICT", "Deletion targets differ from current scope")
    manifest, _ = load_record(manifest_path, "json")
    profile_path = manifest_path.parent / str(manifest["profile"])
    profile_sha = _sha(profile_path.read_bytes())
    changes = []
    for target in preview["targets"]:
        if target["scope"] in {"authority", "known-export"}:
            changes.append({"action": "remove", "target": target["target"], "expected_sha256": target["sha256"], "content_ref": None, "desired_sha256": None})
    if preview["callers"] and not preview["requested_scope"].get("erase_identity"):
        tombstone_dir = manifest_path.parent / "tombstones"
        tombstone_dir.mkdir(exist_ok=True)
        record = {"protocol": "qiming.tombstone/1", "ref": preview["member_ref"], "state": "deleted"}
        data = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        staged = manifest_path.parent / "deletion-tombstone.stage"
        staged.write_bytes(data)
        alias = next(alias for alias, config in manifest["roots"].items() if config.get("access") == "read-write" and manifest_path.parent.is_relative_to(_root(manifest_path, alias)))
        root = _root(manifest_path, alias)
        target = tombstone_dir / (_sha(json.dumps(preview["member_ref"], sort_keys=True).encode("utf-8")) + ".json")
        changes.append({"action": "create", "target": {"kind": "file", "root": alias, "path": str(target.relative_to(root))}, "expected_sha256": None, "content_ref": staged.name, "desired_sha256": _sha(data)})
    planned = plan_changes(manifest_path, changes, "delete-member-within-requested-scope", profile_sha)
    if planned["status"] != "ok":
        return planned
    planned["result"]["plan_id"] = plan_id
    applied = apply_plan(manifest_path, planned["result"])
    if applied["status"] != "ok":
        return applied
    # Successful deletion discards private rollback bytes; the journal keeps hashes.
    journal_ref = Path(applied["result"]["journal_ref"])
    journal = read_json(journal_ref)
    for backup in journal.get("backups", []):
        if backup:
            Path(backup).unlink(missing_ok=True)
    journal["backups"] = [None] * len(journal.get("backups", []))
    journal["redacted_after_deletion"] = True
    write_json(journal_ref, journal)
    cleanup_issues = []
    for copy in preview["historical_copies"]:
        path = Path(copy["path"])
        try:
            if path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != copy["sha256"]:
                raise ValueError("historical copy changed before cleanup")
            path.unlink()
            if copy["kind"] == "backup":
                earlier_ref = Path(copy["journal_ref"])
                earlier = read_json(earlier_ref)
                earlier["backups"][copy["index"]] = None
                earlier["redacted_after_deletion"] = True
                write_json(earlier_ref, earlier)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            cleanup_issues.append({"kind": "historical-copy", "location": str(path), "reason": f"Cleanup failed: {type(exc).__name__}"})
    if preview["requested_scope"].get("derived_index"):
        profile = load_profile(manifest_path)
        relative = profile.get("retrieval", {}).get("index_path")
        if relative and (manifest_path.parent / str(relative)).is_file():
            indexed = reindex(manifest_path, [])
            if indexed["status"] != "ok":
                cleanup_issues.append({"kind": "derived-index", "location": str(relative), "reason": "Index rebuild incomplete"})
    return {"status": "partial" if cleanup_issues else "ok", "result": {"journal_ref": str(journal_ref), "limitations": preview["limitations"] + cleanup_issues, "deleted_ref": preview["member_ref"]}, "diagnostics": [], "changed": applied["changed"]}
