import json
from pathlib import Path


def _workspace(tmp_path: Path, count: int = 1) -> tuple[Path, Path]:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    old = {"protocol": "qiming.profile/1", "collections": {"assets": {"purpose": "members", "root": "work", "directory": "assets", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}, "name": {"source": "/name"}, "lifecycle": {"source": "/status", "values": {"维护中": "maintained"}}, "scope": {"source": "/scope"}}}}
    (control / "profile.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    new = json.loads(json.dumps(old))
    new["mappings"]["m"]["name"]["source"] = "/display_name"
    candidate = control / "new-profile.json"
    candidate.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    for n in range(count):
        (assets / f"{n}.json").write_text(json.dumps({"id": f"rec_{n}", "name": f"Original {n}", "status": "维护中", "scope": "public"}, ensure_ascii=False), encoding="utf-8")
    return manifest, candidate


def test_migration_interruption_blocks_mixed_reads(tmp_path: Path):
    from qiming_core.evolution import plan_profile_migration
    from qiming_core.search import search
    from qiming_core.transactions import apply_plan

    manifest, candidate = _workspace(tmp_path, 2)
    planned = plan_profile_migration(manifest, candidate, ["assets"], "rename name")
    assert planned["status"] == "ok", planned
    partial = apply_plan(manifest, planned["result"], _test_fail_after=1)
    assert partial["status"] == "partial"
    result = search(manifest, {"scope_ids": ["public"], "query": "Original"})
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "RECOVERY_REQUIRED"


def test_rename_keeps_id_and_alias_queries(tmp_path: Path):
    from qiming_core.evolution import plan_profile_migration
    from qiming_core.members import member_view
    from qiming_core.search import search
    from qiming_core.transactions import apply_plan

    manifest, candidate = _workspace(tmp_path)
    planned = plan_profile_migration(manifest, candidate, ["assets"], "rename name")
    assert apply_plan(manifest, planned["result"])["status"] == "ok"
    view = member_view(manifest, {"root": "work", "path": "assets/0.json", "collection": "assets"})
    assert view["ref"]["id"] == "rec_0"
    assert view["name"] == "Original 0"
    assert json.loads((tmp_path / "assets" / "0.json").read_text())["aliases"] == ["Original 0"]
    found = search(manifest, {"scope_ids": ["public"], "query": "Original 0"})
    assert found["result"]["items"][0]["id"] == "rec_0"


def test_ambiguous_status_mapping_blocks_migration(tmp_path: Path):
    from qiming_core.evolution import plan_profile_migration

    manifest, candidate = _workspace(tmp_path)
    new = json.loads(candidate.read_text())
    new["mappings"]["m"]["lifecycle"]["values"] = {"active": "maintained"}
    candidate.write_text(json.dumps(new), encoding="utf-8")
    result = plan_profile_migration(manifest, candidate, ["assets"], "rename and state")
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "SCHEMA_INVALID"
    assert json.loads((tmp_path / "assets" / "0.json").read_text())["status"] == "维护中"


def test_rollback_preserves_later_user_edit(tmp_path: Path):
    from qiming_core.evolution import plan_profile_migration
    from qiming_core.transactions import apply_plan, reconcile

    manifest, candidate = _workspace(tmp_path, 2)
    plan = plan_profile_migration(manifest, candidate, ["assets"], "rename name")["result"]
    partial = apply_plan(manifest, plan, _test_fail_after=1)
    target = tmp_path / "assets" / "0.json"
    target.write_text("later edit", encoding="utf-8")
    recovery = reconcile(manifest, Path(partial["result"]["journal_ref"]), "rollback")
    assert recovery["status"] == "conflict"
    assert target.read_text() == "later edit"
