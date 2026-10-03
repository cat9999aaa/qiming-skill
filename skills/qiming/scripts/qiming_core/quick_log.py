"""Append one work event through the existing plan/apply transaction path."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .codec import load_record
from .plan import plan_changes, resolve_target
from .transactions import apply_plan


KINDS = {"observation", "decision", "action", "handoff"}


def _problem(code: str, message: str, status: str = "conflict") -> dict[str, object]:
    return {"status": status, "result": None, "diagnostics": [
        {"code": code, "message": message, "locator": None, "retryable": False, "details": {}}
    ], "changed": []}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def log_event(
    manifest_path: Path,
    work_ref: dict[str, object],
    event: dict[str, object],
    intent_ref: str | None,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    """Append an idempotent event to an existing mapped work JSON record."""
    manifest_path = manifest_path.resolve()
    if intent_ref is not None and (not isinstance(intent_ref, str) or not intent_ref.strip()):
        return _problem("INVALID_INPUT", "intent_ref is required", "error")
    if not isinstance(event, dict):
        return _problem("INVALID_INPUT", "event must be an object", "error")
    event_id, kind, summary, observed_at = (event.get(key) for key in ("id", "kind", "summary", "observed_at"))
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", event_id):
        return _problem("INVALID_INPUT", "event.id must be a stable simple identifier", "error")
    if kind not in KINDS or not isinstance(summary, str) or not summary.strip() or len(summary) > 2000 or "\n" in summary:
        return _problem("INVALID_INPUT", "event needs a kind and one-line summary (1-2000 chars)", "error")
    if not isinstance(observed_at, str):
        return _problem("INVALID_INPUT", "event.observed_at is required", "error")
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return _problem("INVALID_INPUT", "event.observed_at must be ISO-8601", "error")
    if observed.tzinfo is None:
        return _problem("INVALID_INPUT", "event.observed_at needs a timezone", "error")
    if set(event) != {"id", "kind", "summary", "observed_at"}:
        return _problem("INVALID_INPUT", "event has unsupported fields", "error")
    from .secrets import validate_account_ref
    issues = validate_account_ref(event)
    if issues:
        return {'status':'conflict','result':None,'diagnostics':issues,'changed':[]}
    try:
        manifest, _ = load_record(manifest_path, "json")
        profile_path = manifest_path.parent / manifest["profile"]
        profile, _ = load_record(profile_path, "json")
        work = profile["collections"]["work"]
        if work.get("codec") != "json" or work_ref.get("root") != work.get("root"):
            return _problem("SCOPE_MISMATCH", "This work collection is read-only or has a different root; log requires a mapped JSON work record. Keep Markdown content and map a JSON sidecar explicitly.")
        relative = Path(str(work_ref.get("path", "")))
        directory = Path(str(work["directory"]))
        from .collections import contains
        if not contains(profile, work, relative):
            result = _problem("SCOPE_MISMATCH", "target is outside the mapped work collection")
            result['diagnostics'][0]['hint'] = f"work_ref.path is relative to registered root '{work['root']}', not the collection directory. Include directory '{work['directory']}', e.g. {directory.as_posix()}/w-0001.json; check codec and exclusions too."
            return result
        target = resolve_target(manifest_path, work_ref)
        if not target.is_file():
            return _problem("NOT_FOUND", "work record does not exist")
        original = target.read_bytes()
        old_sha = _sha(original)
        record = json.loads(original)
        if not isinstance(record, dict) or record.get("type") != "work":
            return _problem("SCHEMA_INVALID", "target is not a work record")
        if intent_ref is None:
            intent_ref = record.get("id")
            if not isinstance(intent_ref, str) or not intent_ref.strip():
                return _problem("INVALID_INPUT", "Work record has no id; provide --intent-ref explicitly", "error")
        events = record.get("events", [])
        if not isinstance(events, list):
            return _problem("SCHEMA_INVALID", "work events must be a list")
        for existing in events:
            if isinstance(existing, dict) and existing.get("id") == event_id:
                # The short CLI supplies the current time on every invocation.  A retry
                # with the same event ID and factual content keeps the first timestamp.
                if existing.get("kind") == kind and existing.get("summary") == summary:
                    return {"status": "ok", "result": {"event_id": event_id, "already_recorded": True}, "diagnostics": [], "changed": []}
                return _problem("WRITE_CONFLICT", "event id already has different content")
        if expected_sha256 is not None and expected_sha256 != old_sha:
            return _problem("WRITE_CONFLICT", "work record changed since it was read")
        record["events"] = [*events, event]
        desired = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        staging = manifest_path.parent / ".staging"
        staging.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="log-", suffix=".json", dir=staging, delete=False) as stream:
            stage = Path(stream.name)
            stream.write(desired)
        change = {"action": "replace", "target": work_ref, "expected_sha256": old_sha,
                  "content_ref": str(stage.relative_to(manifest_path.parent)), "desired_sha256": _sha(desired)}
        planned = plan_changes(manifest_path, [change], intent_ref, _sha(profile_path.read_bytes()))
        if planned["status"] != "ok":
            stage.unlink(missing_ok=True)
            return planned
        result = apply_plan(manifest_path, planned["result"])
        if result["status"] == "ok" or not (isinstance(result.get("result"), dict) and result["result"].get("journal_ref")):
            stage.unlink(missing_ok=True)
        if result["status"] == "ok":
            result["result"] = {**result["result"], "event_id": event_id}
        return result
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return _problem("INVALID_INPUT", str(exc), "error")
