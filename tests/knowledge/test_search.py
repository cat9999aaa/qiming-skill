import json
from pathlib import Path


def _workspace(tmp_path: Path) -> Path:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    profile = {"protocol": "qiming.profile/1", "collections": {"notes": {"purpose": "knowledge", "root": "work", "directory": "notes", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}, "summary": {"source": "/summary"}, "scope": {"source": "/scope"}, "type": {"source": "/type", "default": "knowledge"}}}, "retrieval": {"index_path": "index.sqlite"}}
    (control / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (tmp_path / "notes").mkdir()
    return manifest


def _note(tmp_path: Path, identity: str, name: str, scope: str = "public") -> None:
    (tmp_path / "notes" / f"{identity}.json").write_text(json.dumps({"id": identity, "name": name, "summary": name, "scope": scope, "type": "knowledge"}, ensure_ascii=False), encoding="utf-8")


def test_search_filters_scope_before_candidates(tmp_path: Path):
    from qiming_core.search import search

    manifest = _workspace(tmp_path)
    _note(tmp_path, "one", "ordinary public")
    _note(tmp_path, "two", "private sentinel", "private")
    result = search(manifest, {"scope_ids": ["public"], "query": "sentinel"})
    assert result["status"] == "ok"
    assert result["result"]["items"] == []
    assert "private sentinel" not in str(result)


def test_chinese_substring_fallback_finds_source(tmp_path: Path):
    from qiming_core.search import search

    manifest = _workspace(tmp_path)
    _note(tmp_path, "cn", "重装系统恢复手册")
    result = search(manifest, {"scope_ids": ["public"], "query": "系统恢复"})
    assert [item["id"] for item in result["result"]["items"]] == ["cn"]


def test_cursor_rejects_changed_snapshot_without_duplication(tmp_path: Path):
    from qiming_core.search import search

    manifest = _workspace(tmp_path)
    for name in ("a", "b", "c"):
        _note(tmp_path, name, f"search {name}")
    first = search(manifest, {"scope_ids": ["public"], "query": "search", "limit": 1})
    assert first["result"]["next_cursor"]
    _note(tmp_path, "b", "changed search b")
    next_page = search(manifest, {"scope_ids": ["public"], "query": "search", "limit": 1, "cursor": first["result"]["next_cursor"]})
    assert next_page["status"] == "conflict"
    assert next_page["diagnostics"][0]["code"] == "STALE_CURSOR"


def test_deleted_index_is_rebuilt_from_authoritative_records(tmp_path: Path):
    from qiming_core.index import reindex

    manifest = _workspace(tmp_path)
    _note(tmp_path, "x", "Keep original")
    source = (tmp_path / "notes" / "x.json").read_bytes()
    first = reindex(manifest, ["notes"])
    assert first["status"] == "ok"
    Path(first["result"]["index_ref"]).unlink()
    second = reindex(manifest, ["notes"])
    assert second["status"] == "ok"
    assert Path(second["result"]["index_ref"]).exists()
    assert (tmp_path / "notes" / "x.json").read_bytes() == source
