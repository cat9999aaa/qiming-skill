"""Apply local plans with cooperative locking, journals and byte checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path

from .codec import load_record
from .journal import _sync_directory, plan_fingerprint, read_json, save_backup, write_json
from .locks import LockHeld, operation_lock
from .plan import resolve_target


def _hash_bytes(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _current(path: Path) -> str | None:
    return _hash_bytes(path.read_bytes()) if path.exists() else None


def _problem(code: str, message: str, *, status: str = "conflict", locator: str | None = None, journal_ref: Path | None = None) -> dict[str, object]:
    return {"status": status, "result": {"journal_ref": str(journal_ref)} if journal_ref else None, "diagnostics": [{"code": code, "message": message, "locator": locator, "retryable": False, "details": {}}], "changed": []}


def _paths(manifest_path: Path, plan: dict[str, object]) -> tuple[Path, Path]:
    plan_id = plan.get("plan_id")
    if not isinstance(plan_id, str) or not re.fullmatch(r"plan_[A-Za-z0-9_-]{8,128}", plan_id):
        raise ValueError("invalid plan_id")
    operations = manifest_path.parent / "operations"
    return operations, operations / f"{plan_id}.json"


def _marker(manifest_path: Path) -> Path:
    return manifest_path.parent / "migration.json"


def _mark_migration(manifest_path: Path, plan: dict[str, object], journal_path: Path) -> None:
    migration = plan.get("migration")
    if not isinstance(migration, dict):
        return
    marker = _marker(manifest_path)
    value = {"protocol": "qiming.migration/1", "plan_id": plan["plan_id"], "journal_ref": str(journal_path), "affected_collections": migration.get("affected_collections", []), "old_profile_sha256": migration.get("old_profile_sha256"), "new_profile_sha256": migration.get("new_profile_sha256")}
    save_backup(marker, (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))


def _clear_migration(manifest_path: Path, plan: dict[str, object]) -> None:
    if not isinstance(plan.get("migration"), dict):
        return
    marker = _marker(manifest_path)
    if marker.exists():
        value = read_json(marker)
        if value.get("plan_id") != plan.get("plan_id"):
            raise ValueError("migration marker belongs to another plan")
        marker.unlink()


def _stage(manifest_path: Path, change: dict[str, object]) -> bytes | None:
    if change["action"] == "remove":
        return None
    relative = change.get("content_ref")
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("invalid staged content path")
    original = manifest_path.parent / relative
    if original.is_symlink() or not original.resolve().is_relative_to(manifest_path.parent.resolve()):
        raise ValueError("staged content escapes control directory")
    data = original.read_bytes()
    if _hash_bytes(data) != change.get("desired_sha256"):
        raise ValueError("staged content fingerprint changed")
    return data


def _verify_plan(manifest_path: Path, plan: dict[str, object]) -> tuple[list[Path], list[bytes | None]]:
    manifest, _ = load_record(manifest_path, "json")
    if plan.get("protocol") != "qiming.plan/1" or plan.get("workspace_id") != manifest.get("workspace_id"):
        raise ValueError("plan identity or protocol mismatch")
    profile = manifest_path.parent / str(manifest["profile"])
    if _current(profile) != plan.get("profile_sha256"):
        raise ValueError("profile fingerprint changed")
    paths: list[Path] = []
    data: list[bytes | None] = []
    for change in plan.get("changes", []):
        target = resolve_target(manifest_path, change["target"])
        if _current(target) != change.get("expected_sha256"):
            raise ValueError(f"target fingerprint changed: {target}")
        paths.append(target)
        data.append(_stage(manifest_path, change))
    if len({str(path) for path in paths}) != len(paths):
        raise ValueError("duplicate target in plan")
    return paths, data


def _replace(path: Path, data: bytes | None, old_mode: int | None) -> None:
    if data is None:
        path.unlink()
        _sync_directory(path.parent)
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".qiming-", dir=path.parent)
    try:
        os.fchmod(descriptor, old_mode if old_mode is not None else 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _apply_steps(manifest_path: Path, journal_path: Path, journal: dict[str, object], *, fail_after: int | None = None) -> dict[str, object]:
    changed: list[dict[str, object]] = []
    plan = journal["plan"]
    for index, change in enumerate(plan["changes"]):
        path = resolve_target(manifest_path, change["target"])
        old_sha = change.get("expected_sha256")
        desired_sha = change.get("desired_sha256")
        actual = _current(path)
        if actual == desired_sha:
            journal["steps"][index] = "done"
            continue
        if actual != old_sha:
            journal["state"] = "needs_reconcile"
            write_json(journal_path, journal)
            return _problem("WRITE_CONFLICT", "Current bytes match neither old nor desired content", status="conflict", locator=str(path), journal_ref=journal_path)
        if fail_after is not None and len(changed) >= fail_after:
            journal["state"] = "needs_reconcile"
            write_json(journal_path, journal)
            return {"status": "partial", "result": {"journal_ref": str(journal_path), "steps": journal["steps"]}, "diagnostics": [{"code": "RECOVERY_REQUIRED", "message": "Operation interrupted after a completed step", "locator": str(journal_path), "retryable": True, "details": {}}], "changed": changed}
        for parent in reversed(path.parents):
            if str(parent) in plan.get("parents_to_create", []) and not parent.exists():
                parent.mkdir()
                journal["created_parents"].append(str(parent))
                write_json(journal_path, journal)
        old_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
        _replace(path, _stage(manifest_path, change), old_mode)
        journal["steps"][index] = "done"
        journal["state"] = "applying"
        write_json(journal_path, journal)
        changed.append({"path": str(path), "before_sha256": old_sha, "after_sha256": desired_sha})
    journal["state"] = "completed"
    write_json(journal_path, journal)
    return {"status": "ok", "result": {"journal_ref": str(journal_path), "steps": journal["steps"]}, "diagnostics": [], "changed": changed}


def apply_plan(manifest_path: Path, plan: dict[str, object], *, _test_fail_after: int | None = None) -> dict[str, object]:
    try:
        operations, journal_path = _paths(manifest_path, plan)
        with operation_lock(operations, str(plan["plan_id"])):
            if _marker(manifest_path).exists():
                return _problem("RECOVERY_REQUIRED", "Incomplete migration blocks new writes", locator=str(_marker(manifest_path)))
            fingerprint = plan_fingerprint(plan)
            if journal_path.exists():
                journal = read_json(journal_path)
                if journal.get("plan_fingerprint") != fingerprint:
                    return _problem("WRITE_CONFLICT", "Plan ID was previously used with different contents", locator=str(journal_path))
                if journal.get("state") == "completed":
                    return {"status": "ok", "result": {"journal_ref": str(journal_path), "steps": journal["steps"], "already_completed": True}, "diagnostics": [], "changed": []}
                return _problem("RECOVERY_REQUIRED", "Incomplete plan must be reconciled", locator=str(journal_path), journal_ref=journal_path)
            paths, data = _verify_plan(manifest_path, plan)
            journal = {"protocol": "qiming.journal/1", "plan_fingerprint": fingerprint, "plan": plan, "state": "prepared", "steps": ["pending"] * len(paths), "created_parents": [], "backups": []}
            for index, (path, change) in enumerate(zip(paths, plan["changes"])):
                backup = operations / f"{plan['plan_id']}.bak-{index}"
                if change["action"] != "create":
                    save_backup(backup, path.read_bytes())
                    journal["backups"].append(str(backup))
                else:
                    journal["backups"].append(None)
            write_json(journal_path, journal)
            _mark_migration(manifest_path, plan, journal_path)
            result = _apply_steps(manifest_path, journal_path, journal, fail_after=_test_fail_after)
            if result["status"] == "ok":
                _clear_migration(manifest_path, plan)
            return result
    except LockHeld as exc:
        return _problem("LOCKED", "Operation lock exists and must be inspected", locator=str(exc))
    except (OSError, ValueError, KeyError) as exc:
        if "journal_path" in locals() and journal_path.exists():
            return _problem("RECOVERY_REQUIRED", str(exc), status="partial", journal_ref=journal_path)
        return _problem("WRITE_CONFLICT", str(exc))


def reconcile(manifest_path: Path, journal_ref: Path, mode: str) -> dict[str, object]:
    if mode not in {"inspect", "resume", "rollback"}:
        return _problem("INVALID_INPUT", "Unsupported reconcile mode")
    operations = manifest_path.parent / "operations"
    if journal_ref.resolve().parent != operations.resolve():
        return _problem("PATH_ESCAPE", "Journal is outside workspace operations")
    try:
        if mode == "inspect":
            journal = read_json(journal_ref)
            states = []
            for change in journal["plan"]["changes"]:
                path = resolve_target(manifest_path, change["target"])
                actual = _current(path)
                states.append("old" if actual == change.get("expected_sha256") else "desired" if actual == change.get("desired_sha256") else "changed")
            return {"status": "ok", "result": {"journal_ref": str(journal_ref), "state": journal["state"], "targets": states}, "diagnostics": [], "changed": []}
        with operation_lock(operations, "reconcile"):
            journal = read_json(journal_ref)
            if journal.get("state") == "completed" and mode == "resume":
                return {"status": "ok", "result": {"journal_ref": str(journal_ref), "already_completed": True}, "diagnostics": [], "changed": []}
            changes = journal["plan"]["changes"]
            for change in changes:
                path = resolve_target(manifest_path, change["target"])
                actual = _current(path)
                if actual not in {change.get("expected_sha256"), change.get("desired_sha256")}:
                    return _problem("WRITE_CONFLICT", "A target was edited after interruption", locator=str(path), journal_ref=journal_ref)
            if mode == "resume":
                result = _apply_steps(manifest_path, journal_ref, journal)
                if result["status"] == "ok":
                    _clear_migration(manifest_path, journal["plan"])
                return result
            changed = []
            for index in reversed(range(len(changes))):
                change = changes[index]
                path = resolve_target(manifest_path, change["target"])
                if _current(path) == change.get("expected_sha256"):
                    continue
                backup = journal["backups"][index]
                _replace(path, Path(backup).read_bytes() if backup else None, stat.S_IMODE(path.stat().st_mode) if path.exists() else None)
                changed.append({"path": str(path), "before_sha256": change.get("desired_sha256"), "after_sha256": change.get("expected_sha256")})
            for parent in reversed(journal.get("created_parents", [])):
                path = Path(parent)
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            journal["state"] = "rolled_back"
            write_json(journal_ref, journal)
            _clear_migration(manifest_path, journal["plan"])
            return {"status": "ok", "result": {"journal_ref": str(journal_ref), "state": "rolled_back"}, "diagnostics": [], "changed": changed}
    except LockHeld as exc:
        return _problem("LOCKED", "Operation lock exists and must be inspected", locator=str(exc))
    except (OSError, ValueError, KeyError) as exc:
        return _problem("IO_ERROR", str(exc), status="error", journal_ref=journal_ref)
