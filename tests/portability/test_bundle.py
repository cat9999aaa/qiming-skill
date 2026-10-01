import hashlib
import json
from pathlib import Path


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    control = root / ".qiming"
    control.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (external / "photo.bin").write_bytes(b"external content")
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}, "outside": {"location": str(external), "access": "read-only"}}}), encoding="utf-8")
    profile = {"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}, "scope": {"source": "/scope"}, "type": {"source": "/type"}}}}
    (control / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "public.json").write_text(json.dumps({"id": "rec_public", "name": "Public", "scope": "public", "type": "knowledge"}), encoding="utf-8")
    return manifest


def test_bundle_rejects_nested_destination(tmp_path: Path):
    from qiming_core.bundle import bundle

    manifest = _workspace(tmp_path)
    destination = manifest.parent.parent / "exports"
    result = bundle(manifest, {"scope_ids": ["public"], "collections": ["assets"]}, destination, False)
    assert result["status"] == "conflict"
    assert not destination.exists()


def test_bundle_lists_external_omissions_and_hashes(tmp_path: Path):
    from qiming_core.bundle import bundle

    manifest = _workspace(tmp_path)
    destination = tmp_path / "bundle"
    result = bundle(manifest, {"scope_ids": ["public"], "collections": ["assets"], "business_paths": [{"root": "outside", "path": "photo.bin"}]}, destination, False)
    assert result["status"] == "partial"
    contents = json.loads((destination / "bundle.json").read_text())
    assert any(item["reason"] == "external-root-not-selected" for item in contents["omissions"])
    for item in contents["files"]:
        assert hashlib.sha256((destination / item["bundle_path"]).read_bytes()).hexdigest() == item["sha256"]


def test_bundle_excludes_secret_values_and_private_out_of_scope_files(tmp_path: Path):
    from qiming_core.bundle import bundle

    manifest = _workspace(tmp_path)
    root = manifest.parent.parent
    (root / "assets" / "private.json").write_text(json.dumps({"id": "rec_private", "name": "private title", "scope": "private", "type": "knowledge"}), encoding="utf-8")
    (root / "assets" / "account.json").write_text(json.dumps({"id": "rec_account", "name": "Account", "scope": "public", "type": "account", "password": "not-in-bundle"}), encoding="utf-8")
    destination = tmp_path / "bundle"
    result = bundle(manifest, {"scope_ids": ["public"], "collections": ["assets"]}, destination, False)
    assert result["status"] == "partial"
    raw = "\n".join(path.read_text(errors="ignore") for path in destination.rglob("*") if path.is_file())
    assert "not-in-bundle" not in raw
    assert "private title" not in raw


def test_bundle_detects_source_change_during_export(tmp_path: Path):
    from qiming_core.bundle import bundle

    manifest = _workspace(tmp_path)
    source = manifest.parent.parent / "assets" / "public.json"
    destination = tmp_path / "bundle"

    def change(path: Path) -> None:
        if path == source:
            path.write_text("changed during export", encoding="utf-8")

    result = bundle(manifest, {"scope_ids": ["public"], "collections": ["assets"]}, destination, False, _test_before_copy=change)
    assert result["status"] == "conflict"
    assert not destination.exists()

def test_default_bundle_keeps_startup_rules(tmp_path):
    from qiming_core.initialize import initialize
    from qiming_core.bundle import bundle
    root=tmp_path/'project';root.mkdir()
    assert initialize(root,goal='continue')['status']=='ok'
    result=bundle(root/'.qiming/workspace.json',{},tmp_path/'export',False)
    assert result['status']=='ok',result
    assert (tmp_path/'export/workspace/.qiming/startup.md').is_file()
    assert (tmp_path/'export/workspace/.qiming/project-entrypoints.json').is_file()
    assert (tmp_path/'export/workspace/AGENTS.md').is_file()
