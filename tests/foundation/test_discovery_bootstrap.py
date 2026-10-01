import json
from pathlib import Path


def _manifest(path: Path, workspace_id: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": workspace_id, "state": "ready"}), encoding="utf-8")
    return path


def test_bootstrap_interruption_is_resumable(tmp_path: Path):
    from qiming_core.bootstrap import bootstrap

    control = tmp_path / ".qiming"
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "initializing", "profile": "profile.json", "init_journal": "init.json"}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    first = bootstrap(tmp_path, control, manifest, profile, "init_1")
    assert first["status"] == "ok"
    first_bytes = (control / "workspace.json").read_bytes()
    second = bootstrap(tmp_path, control, manifest, profile, "init_1")
    assert second["status"] == "ok"
    assert (control / "workspace.json").read_bytes() == first_bytes
    assert json.loads((control / "init.json").read_text())["initialization_id"] == "init_1"
    assert len(list(control.iterdir())) == 3


def test_discover_reports_scope_conflict(tmp_path: Path):
    from qiming_core.discovery import discover

    parent = _manifest(tmp_path / ".qiming" / "workspace.json", "ws_parent")
    child = _manifest(tmp_path / "nested" / ".qiming" / "workspace.json", "ws_child")
    found = discover(child.parent.parent, parent, tmp_path)
    assert found["status"] == "conflict"
    assert found["diagnostics"][0]["code"] == "AMBIGUOUS_ENTRY"
    assert {str(parent), str(child)} <= set(found["candidates"])


def test_bootstrap_existing_files_are_not_overwritten(tmp_path: Path):
    from qiming_core.bootstrap import bootstrap

    control = tmp_path / ".qiming"
    control.mkdir()
    target = control / "profile.json"
    target.write_text("user content", encoding="utf-8")
    result = bootstrap(tmp_path, control, {"protocol": "qiming.workspace/1", "workspace_id": "ws_1", "state": "initializing", "profile": "profile.json", "init_journal": "init.json"}, {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}, "init_1")
    assert result["status"] == "conflict"
    assert target.read_text() == "user content"


def test_bootstrap_resumes_an_exact_legacy_manifest(tmp_path: Path):
    from qiming_core.bootstrap import bootstrap, _bytes

    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "old", "state": "initializing", "profile": "profile.json", "init_journal": "init.json"}
    saved = _bytes(manifest)
    (control / "workspace.json").write_bytes(saved)
    result = bootstrap(tmp_path, control, manifest, {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}, "old-init")
    assert result["status"] == "ok"
    assert (control / "workspace.json").read_bytes() == saved


def test_nearest_valid_manifest_wins_within_boundary(tmp_path: Path):
    from qiming_core.discovery import discover

    _manifest(tmp_path / ".qiming" / "workspace.json", "ws_outer")
    inner = _manifest(tmp_path / "project" / ".qiming" / "workspace.json", "ws_inner")
    found = discover(tmp_path / "project" / "src", None, tmp_path)
    assert found["status"] == "ok"
    assert found["manifest_path"] == str(inner)
    assert discover(tmp_path / "project" / "src", None, tmp_path / "project" / "src")["status"] == "none"


def test_non_git_project_children_find_their_local_instance(tmp_path: Path):
    from qiming_core.discovery import discover

    manifest = _manifest(tmp_path / "writing" / ".qiming" / "workspace.json", "writing")
    chapter = tmp_path / "writing" / "chapters"
    chapter.mkdir()
    assert discover(chapter)["manifest_path"] == str(manifest)
    other = tmp_path / "unadopted"
    other.mkdir()
    assert discover(other)["status"] == "none"


def test_nested_git_project_does_not_inherit_outer_qiming(tmp_path: Path):
    from qiming_core.discovery import discover

    _manifest(tmp_path / ".qiming" / "workspace.json", "parent")
    child = tmp_path / "independent"
    (child / ".git").mkdir(parents=True)
    assert discover(child)["status"] == "none"


def test_scope_check_separates_task_root_from_external_resources(tmp_path: Path):
    from qiming_core.discovery import scope_check

    root = tmp_path / "project"
    manifest = _manifest(root / ".qiming/workspace.json", "project")
    child = root / "chapters"
    child.mkdir()
    assert scope_check(manifest, child)["active"] is True
    assert scope_check(manifest, tmp_path)["active"] is False
    nested = child / "independent"
    (nested / ".git").mkdir(parents=True)
    assert scope_check(manifest, nested)["status"] == "nested-project"
    _manifest(child / ".qiming/workspace.json", "other-project")
    assert scope_check(manifest, child)["status"] == "nested-project"
