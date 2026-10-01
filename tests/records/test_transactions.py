import hashlib
import json
from pathlib import Path


def _plan(tmp_path: Path, names: list[str]) -> tuple[Path, dict]:
    from qiming_core.plan import plan_changes

    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "ready", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    profile = control / "profile.json"
    profile.write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}), encoding="utf-8")
    changes = []
    for name in names:
        target = tmp_path / name
        target.write_text("old", encoding="utf-8")
        stage = control / f"{name}.stage"
        stage.write_text("new", encoding="utf-8")
        changes.append({"action": "replace", "target": {"kind": "file", "root": "work", "path": name}, "expected_sha256": hashlib.sha256(b"old").hexdigest(), "content_ref": stage.name, "desired_sha256": hashlib.sha256(b"new").hexdigest()})
    result = plan_changes(manifest, changes, "current-task", hashlib.sha256(profile.read_bytes()).hexdigest())
    assert result["status"] == "ok"
    return manifest, result["result"]


def test_concurrent_stale_writer_gets_conflict(tmp_path: Path):
    from qiming_core.transactions import apply_plan

    manifest, plan = _plan(tmp_path, ["a.json"])
    (tmp_path / "a.json").write_text("user edit", encoding="utf-8")
    result = apply_plan(manifest, plan)
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "WRITE_CONFLICT"
    assert (tmp_path / "a.json").read_text() == "user edit"


def test_completed_plan_retry_is_idempotent(tmp_path: Path):
    from qiming_core.transactions import apply_plan

    manifest, plan = _plan(tmp_path, ["a.json"])
    first = apply_plan(manifest, plan)
    assert first["status"] == "ok"
    second = apply_plan(manifest, plan)
    assert second["status"] == "ok"
    assert second["result"]["journal_ref"] == first["result"]["journal_ref"]
    assert second["changed"] == []
    assert (tmp_path / "a.json").read_text() == "new"


def test_reconcile_preserves_post_crash_user_edit(tmp_path: Path):
    from qiming_core.transactions import apply_plan, reconcile

    manifest, plan = _plan(tmp_path, ["a.json", "b.json"])
    partial = apply_plan(manifest, plan, _test_fail_after=1)
    assert partial["status"] == "partial"
    (tmp_path / "a.json").write_text("later user edit", encoding="utf-8")
    recovery = reconcile(manifest, Path(partial["result"]["journal_ref"]), "rollback")
    assert recovery["status"] == "conflict"
    assert (tmp_path / "a.json").read_text() == "later user edit"


def test_failed_midway_reports_partial_and_journal(tmp_path: Path):
    from qiming_core.transactions import apply_plan, reconcile

    manifest, plan = _plan(tmp_path, ["a.json", "b.json"])
    partial = apply_plan(manifest, plan, _test_fail_after=1)
    assert partial["status"] == "partial"
    assert Path(partial["result"]["journal_ref"]).exists()
    assert (tmp_path / "a.json").read_text() == "new"
    assert (tmp_path / "b.json").read_text() == "old"
    resumed = reconcile(manifest, Path(partial["result"]["journal_ref"]), "resume")
    assert resumed["status"] == "ok"
    assert (tmp_path / "b.json").read_text() == "new"


def test_stale_lock_requires_inspection(tmp_path: Path):
    from qiming_core.transactions import apply_plan

    manifest, plan = _plan(tmp_path, ["a.json"])
    ops = manifest.parent / "operations"
    ops.mkdir()
    (ops / ".lock").write_text("old process", encoding="utf-8")
    result = apply_plan(manifest, plan)
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "LOCKED"
    assert (ops / ".lock").exists()
