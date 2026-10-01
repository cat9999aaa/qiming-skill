import json
from pathlib import Path


def _workspace(tmp_path: Path) -> Path:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    profile = {"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "asset"}}, "mappings": {"asset": {"id": {"source": "/id"}, "name": {"source": "/name"}, "type": {"source": "/type", "default": "custom"}, "lifecycle": {"source": "/status", "values": {"维护中": "maintained"}}}}}
    (control / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (tmp_path / "assets").mkdir()
    return manifest


def test_same_hash_and_common_dir_do_not_merge_ids(tmp_path: Path):
    from qiming_core.members import member_view

    manifest = _workspace(tmp_path)
    for name, value in (("a", "rec_a"), ("b", "rec_b")):
        (tmp_path / "assets" / f"{name}.json").write_text(json.dumps({"id": value, "name": "Same", "type": "script"}), encoding="utf-8")
    views = [member_view(manifest, {"root": "work", "path": f"assets/{name}.json", "collection": "assets"}) for name in ("a", "b")]
    assert views[0]["ref"] != views[1]["ref"]
    assert views[0]["record_locator"] != views[1]["record_locator"]


def test_legacy_member_json_retains_unknown_status(tmp_path: Path):
    from qiming_core.members import member_view

    manifest = _workspace(tmp_path)
    source = tmp_path / "assets" / "MEMBER.json"
    source.write_text(json.dumps({"id": "old-7", "name": "旧工具", "status": "摸索中", "custom": {"hint": "keep"}}), encoding="utf-8")
    view = member_view(manifest, {"root": "work", "path": "assets/MEMBER.json", "collection": "assets"})
    assert view["ref"] == {"workspace_id": "ws_test", "id": "old-7"}
    assert view["lifecycle"] is None
    assert view["extensions"]["custom"] == {"hint": "keep"}
    assert json.loads(source.read_text())["status"] == "摸索中"


def test_part_of_cycle_is_rejected():
    from qiming_core.members import validate_relation_graph

    members = [{"ref": {"workspace_id": "ws", "id": "a"}, "relations": [{"kind": "part_of", "target": {"workspace_id": "ws", "id": "b"}}]}, {"ref": {"workspace_id": "ws", "id": "b"}, "relations": [{"kind": "part_of", "target": {"workspace_id": "ws", "id": "a"}}]}]
    assert any(item["code"] == "RELATION_CYCLE" for item in validate_relation_graph(members))


def test_external_relation_is_unresolved_not_deleted():
    from qiming_core.members import validate_relation_graph

    members = [{"ref": {"workspace_id": "ws", "id": "a"}, "relations": [{"kind": "depends_on", "target": {"workspace_id": "other", "id": "x"}}]}]
    assert any(item["code"] == "REFERENCE_UNRESOLVED" for item in validate_relation_graph(members))
    assert len(members[0]["relations"]) == 1


def test_retained_script_skill_mcp_get_lightweight_membership(tmp_path: Path):
    from qiming_core.members import member_view

    manifest = _workspace(tmp_path)
    for kind in ("script", "skill", "mcp"):
        (tmp_path / "assets" / f"{kind}.json").write_text(json.dumps({"id": f"rec_{kind}", "name": kind, "type": kind, "locators": []}), encoding="utf-8")
        view = member_view(manifest, {"root": "work", "path": f"assets/{kind}.json", "collection": "assets"})
        assert view["type"] == kind
        assert view["verification"] == []
