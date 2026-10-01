import json
from pathlib import Path


def _workspace(tmp_path: Path, *, secret: bool = False) -> Path:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    profile = {"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}, "scope": {"source": "/scope"}}}, "retrieval": {"index_path": "index.sqlite"}, "scope_rules": {"known_exports": ["exports/a.json"], "known_backups": ["offsite-backup"]}}
    (control / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "exports").mkdir()
    record = {"id": "rec_a", "name": "Asset A", "scope": "public", "locators": [{"kind": "file", "root": "work", "path": "script.py"}]}
    if secret:
        record["notes"] = "private-secret"
    (tmp_path / "assets" / "a.json").write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "exports" / "a.json").write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "script.py").write_text("print('keep original')", encoding="utf-8")
    return manifest


def test_delete_clears_controllable_copies_and_reports_backup(tmp_path: Path):
    from qiming_core.deletion import apply_deletion, deletion_preview
    from qiming_core.index import reindex
    from qiming_core.search import search

    manifest = _workspace(tmp_path)
    assert reindex(manifest, ["assets"])["status"] == "ok"
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True, "derived_index": True, "known_exports": True})
    assert preview["status"] == "ok"
    assert any(item["kind"] == "known-backup" for item in preview["result"]["limitations"])
    deleted = apply_deletion(preview["result"], preview["result"]["plan_id"])
    assert deleted["status"] == "ok", deleted
    assert not (tmp_path / "assets" / "a.json").exists()
    assert not (tmp_path / "exports" / "a.json").exists()
    assert search(manifest, {"scope_ids": ["public"], "query": "Asset A"})["result"]["items"] == []


def test_delete_does_not_remove_business_original_without_scope(tmp_path: Path):
    from qiming_core.deletion import apply_deletion, deletion_preview

    manifest = _workspace(tmp_path)
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True})
    assert apply_deletion(preview["result"], preview["result"]["plan_id"])["status"] == "ok"
    assert (tmp_path / "script.py").read_text() == "print('keep original')"


def test_delete_log_does_not_repeat_private_body(tmp_path: Path):
    from qiming_core.deletion import apply_deletion, deletion_preview

    manifest = _workspace(tmp_path, secret=True)
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True, "erase_identity": True})
    result = apply_deletion(preview["result"], preview["result"]["plan_id"])
    assert result["status"] == "ok"
    all_logs = "\n".join(path.read_text(errors="ignore") for path in manifest.parent.rglob("*") if path.is_file() and path.suffix in {".json", ".bak"})
    assert "private-secret" not in all_logs


def test_delete_purges_prior_operation_backups_for_private_record(tmp_path: Path):
    import hashlib
    from qiming_core.deletion import apply_deletion, deletion_preview
    from qiming_core.plan import plan_changes
    from qiming_core.transactions import apply_plan

    manifest = _workspace(tmp_path, secret=True)
    target = tmp_path / "assets/a.json"
    old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    replacement = json.loads(target.read_text())
    replacement["notes"] = "private-new"
    stage = manifest.parent / "replacement.stage"
    stage.write_text(json.dumps(replacement), encoding="utf-8")
    profile_hash = hashlib.sha256((manifest.parent / "profile.json").read_bytes()).hexdigest()
    planned = plan_changes(manifest, [{"action": "replace", "target": {"kind": "file", "root": "work", "path": "assets/a.json"}, "expected_sha256": old_hash, "content_ref": stage.name, "desired_sha256": hashlib.sha256(stage.read_bytes()).hexdigest()}], "edit-private", profile_hash)
    assert apply_plan(manifest, planned["result"])["status"] == "ok"
    assert any(b"private-secret" in path.read_bytes() for path in (manifest.parent / "operations").glob("*.bak-*"))
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True})
    assert apply_deletion(preview["result"], preview["result"]["plan_id"])["status"] == "ok"
    assert all(b"private-secret" not in path.read_bytes() and b"private-new" not in path.read_bytes() for path in manifest.parent.rglob("*") if path.is_file() and path != stage)


def test_delete_waits_for_incomplete_edit_of_same_member(tmp_path: Path):
    import hashlib
    from qiming_core.deletion import deletion_preview
    from qiming_core.plan import plan_changes
    from qiming_core.transactions import apply_plan

    manifest = _workspace(tmp_path, secret=True)
    target = tmp_path / "assets/a.json"
    stage = manifest.parent / "next.stage"
    stage.write_text(json.dumps({"id": "rec_a", "name": "next"}), encoding="utf-8")
    profile_hash = hashlib.sha256((manifest.parent / "profile.json").read_bytes()).hexdigest()
    planned = plan_changes(manifest, [{"action": "replace", "target": {"kind": "file", "root": "work", "path": "assets/a.json"}, "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "content_ref": stage.name, "desired_sha256": hashlib.sha256(stage.read_bytes()).hexdigest()}], "edit-private", profile_hash)
    assert apply_plan(manifest, planned["result"], _test_fail_after=0)["status"] == "partial"
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True})
    assert preview["status"] == "conflict"
    assert preview["diagnostics"][0]["code"] == "RECOVERY_REQUIRED"


def test_merge_redirect_survives_index_rebuild(tmp_path: Path):
    from qiming_core.index import reindex
    from qiming_core.members import resolve_member_ref
    from qiming_core.retirement import record_redirect

    manifest = _workspace(tmp_path)
    (tmp_path / "assets" / "b.json").write_text(json.dumps({"id": "rec_b", "name": "Asset B", "scope": "public"}), encoding="utf-8")
    merged = record_redirect(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"workspace_id": "ws", "id": "rec_b"})
    assert merged["status"] == "ok"
    reindex(manifest, ["assets"])
    result = resolve_member_ref(manifest, {"workspace_id": "ws", "id": "rec_a"})
    assert result["status"] == "ok"
    assert result["view"]["ref"]["id"] == "rec_b"


def test_tampered_delete_preview_is_rejected(tmp_path: Path):
    from qiming_core.deletion import apply_deletion, deletion_preview

    manifest = _workspace(tmp_path)
    preview = deletion_preview(manifest, {"workspace_id": "ws", "id": "rec_a"}, {"authority": True})["result"]
    preview["targets"].append({"scope": "authority", "path": "script.py"})
    result = apply_deletion(preview, preview["plan_id"])
    assert result["status"] == "conflict"
    assert (tmp_path / "assets" / "a.json").exists()
