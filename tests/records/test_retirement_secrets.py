import json
from pathlib import Path


def _workspace(tmp_path: Path) -> Path:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}}}, "retrieval": {"index_path": "index.sqlite"}, "scope_rules": {"known_exports": ["exports/archive.zip"], "known_backups": ["backup-usb"]}}), encoding="utf-8")
    (tmp_path / "assets").mkdir()
    return manifest


def test_account_card_rejects_secret_values():
    from qiming_core.secrets import validate_account_ref

    record = {"type": "account", "name": "Site", "credential_ref": {"provider": "password-manager", "id": "site-login"}, "password": "dontshowme"}
    result = validate_account_ref(record)
    assert result and result[0]["code"] == "SECRET_VALUE_FORBIDDEN"
    assert "dontshowme" not in str(result)
    assert validate_account_ref({"type": "account", "credential_ref": {"provider": "password-manager", "id": "site-login"}}) == []


def test_retirement_shows_callers_before_change(tmp_path: Path):
    from qiming_core.retirement import retirement_impact

    manifest = _workspace(tmp_path)
    (tmp_path / "assets" / "a.json").write_text(json.dumps({"id": "a", "name": "A"}), encoding="utf-8")
    (tmp_path / "assets" / "b.json").write_text(json.dumps({"id": "b", "name": "B", "relations": [{"kind": "uses", "target": {"workspace_id": "ws", "id": "a"}}]}), encoding="utf-8")
    impact = retirement_impact(manifest, {"workspace_id": "ws", "id": "a"})
    assert impact["status"] == "ok"
    assert impact["callers"][0]["ref"]["id"] == "b"
    assert (tmp_path / "assets" / "a.json").exists()


def test_merge_keeps_old_id_redirect_without_cycle():
    from qiming_core.retirement import retirement_changes, resolve_redirect

    impact = {"status": "ok", "member": {"ref": {"workspace_id": "ws", "id": "old"}, "record_locator": {"kind": "file", "root": "work", "path": "old.json"}}, "merge_target": {"workspace_id": "ws", "id": "new"}, "redirects": {}}
    changes = retirement_changes(impact, "merge")
    assert changes[0]["redirect"]["from"]["id"] == "old"
    assert resolve_redirect({"workspace_id": "ws", "id": "old"}, {"ws:old": {"workspace_id": "ws", "id": "new"}})["id"] == "new"
    assert resolve_redirect({"workspace_id": "ws", "id": "old"}, {"ws:old": {"workspace_id": "ws", "id": "new"}, "ws:new": {"workspace_id": "ws", "id": "old"}}) is None


def test_delete_plan_lists_derived_copies_and_limits(tmp_path: Path):
    from qiming_core.retirement import retirement_changes, retirement_impact

    manifest = _workspace(tmp_path)
    (tmp_path / "assets" / "a.json").write_text(json.dumps({"id": "a", "name": "A"}), encoding="utf-8")
    impact = retirement_impact(manifest, {"workspace_id": "ws", "id": "a"})
    changes = retirement_changes(impact, "delete")
    assert any(item["scope"] == "authority" for item in changes)
    assert any(item["scope"] == "derived-index" for item in changes)
    assert any(item["scope"] == "known-export" for item in changes)
    assert "backup-usb" in str(changes)
    assert (tmp_path / "assets" / "a.json").exists()
