import json
from pathlib import Path


def _bundle(tmp_path: Path) -> Path:
    from qiming_core.bundle import bundle

    root = tmp_path / "old-machine" / "project"
    root.mkdir(parents=True)
    control = root / ".qiming"
    control.mkdir()
    external = tmp_path / "old-machine" / "external"
    external.mkdir()
    (external / "data.bin").write_bytes(b"not copied")
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws_permanent", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"work": {"location": "..", "access": "read-write"}, "external": {"location": str(external), "access": "read-only"}}}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}, "scope": {"source": "/scope"}}}}), encoding="utf-8")
    (control / "init.json").write_text(json.dumps({"protocol": "qiming.initialization/1", "initialization_id": "init_old"}), encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "a.json").write_text(json.dumps({"id": "rec_stable", "name": "Asset", "scope": "public"}), encoding="utf-8")
    destination = tmp_path / "export"
    result = bundle(manifest, {"scope_ids": ["public"], "collections": ["assets"], "business_paths": [{"root": "external", "path": "data.bin"}]}, destination, False)
    assert result["status"] == "partial"
    return destination


def test_restore_rebinds_roots_without_changing_ids(tmp_path: Path):
    from qiming_core.restore import apply_restore, restore_preview

    bundle_root = _bundle(tmp_path)
    target = tmp_path / "new-machine" / "project"
    preview = restore_preview(bundle_root, target, {"work": str(target), "external": str(tmp_path / "new-machine" / "external")})
    assert preview["status"] == "partial"
    assert preview["result"]["workspace_id"] == "ws_permanent"
    applied = apply_restore(preview["result"])
    assert applied["status"] in {"ok", "partial"}, applied
    restored = json.loads((target / ".qiming" / "workspace.json").read_text())
    assert restored["workspace_id"] == "ws_permanent"
    assert (target / ".qiming" / restored["roots"]["work"]["location"]).resolve() == target
    assert json.loads((target / "assets" / "a.json").read_text())["id"] == "rec_stable"


def test_restore_fails_on_changed_hash_without_overwrite(tmp_path: Path):
    from qiming_core.restore import restore_preview

    bundle_root = _bundle(tmp_path)
    (bundle_root / "workspace" / "assets" / "a.json").write_text("tampered", encoding="utf-8")
    target = tmp_path / "new-machine" / "project"
    result = restore_preview(bundle_root, target, {"work": str(target)})
    assert result["status"] == "conflict"
    assert not target.exists()


def test_restore_marks_missing_content_and_credential_recovery_separately(tmp_path: Path):
    from qiming_core.restore import restore_preview

    bundle_root = _bundle(tmp_path)
    target = tmp_path / "new-machine" / "project"
    result = restore_preview(bundle_root, target, {"work": str(target)})
    missing = result["result"]["missing"]
    assert any(item["kind"] == "business-content" for item in missing)
    assert any(item["kind"] == "credential-provider" for item in missing)


def test_restore_does_not_claim_pass_before_actual_check():
    from qiming_core.restore import restore_record

    record = restore_record({"workspace_id": "ws", "target_root": "/tmp/project", "status": "partial"}, [])
    assert record["verification"] == "not-run"
    assert record["status"] != "pass"
