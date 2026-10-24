import json
from pathlib import Path

from tests.portability.test_hosts import _ready


def _bound(manifest: Path):
    from qiming_core.host_binding import binding_preview

    preview = binding_preview(manifest, "codex", manifest.parent.parent)
    binding = Path(preview["binding_path"])
    binding.parent.mkdir(parents=True)
    binding.symlink_to(preview["source_directory"], target_is_directory=True)


def test_local_context_refresh_preserves_user_rules_and_is_idempotent(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints, binding_status

    manifest = _ready(tmp_path)
    _bound(manifest)
    entry = manifest.parent.parent / "AGENTS.md"
    entry.write_text("# 手写规则\n保留原件。\n" + entry.read_text() + "\n结尾也保留。\n")
    source = manifest.parent / "startup.md"
    source.write_text("# 周报\n每周从周一开始；费用使用人民币元。\n")
    assert binding_status(manifest, "codex")["status"] == "stale-context"
    result = ensure_project_entrypoints(manifest)
    assert result["status"] == "ok", result
    assert source.read_text() in entry.read_text()
    assert entry.read_text().startswith("# 手写规则\n保留原件。\n")
    assert entry.read_text().endswith("\n结尾也保留。\n")
    assert binding_status(manifest, "codex")["status"] == "bound"
    assert ensure_project_entrypoints(manifest)["changed"] == []
    source.write_text("# 周报\n每周从周日开始。\n")
    assert ensure_project_entrypoints(manifest)["status"] == "ok"
    assert source.read_text() in entry.read_text()
    assert "费用使用人民币元" not in entry.read_text()


def test_refresh_refuses_to_overwrite_locally_edited_generated_block(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints

    manifest = _ready(tmp_path)
    entry = manifest.parent.parent / "AGENTS.md"
    edited = entry.read_text().replace("<!-- qiming:entry:end -->", "用户在这里补了规则。\n<!-- qiming:entry:end -->")
    entry.write_text(edited)
    (manifest.parent / "startup.md").write_text("新摘要。\n")
    result = ensure_project_entrypoints(manifest)
    assert result["status"] == "conflict"
    assert entry.read_text() == edited
    assert result["changed"] == []


def test_codex_override_is_reported_instead_of_claiming_preload(tmp_path):
    from qiming_core.host_binding import binding_status

    manifest = _ready(tmp_path)
    _bound(manifest)
    (manifest.parent.parent / "AGENTS.override.md").write_text("这是独立的启动规则。\n")
    result = binding_status(manifest, "codex")
    assert result["status"] == "incomplete"
    assert result["reason"] == "project-instruction-shadowed"


def test_generated_context_follows_custom_entry_locations(tmp_path):
    from qiming_core.bootstrap import bootstrap
    from qiming_core.materialize import materialize

    root = tmp_path / "writing"
    root.mkdir()
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "writing", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "workspace_entry": "导航.md", "conventions": "偏好.md", "roots": {"project": {"location": "..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    bootstrap(root, root / ".qiming", manifest, profile, "custom")
    assert materialize(root / ".qiming/workspace.json", [], {}, "custom")["status"] == "ok"
    entry = (root / "AGENTS.md").read_text()
    assert ".qiming/导航.md" in entry
    assert ".qiming/偏好.md" in entry
    assert ".qiming/START.md" not in entry


def test_ready_instance_refresh_does_not_require_initialization_journal(tmp_path):
    from qiming_core.materialize import materialize

    manifest = _ready(tmp_path)
    value = json.loads(manifest.read_text())
    value["init_journal"] = None
    manifest.write_text(json.dumps(value))
    result = materialize(manifest, [], {}, "not-needed-for-ready")
    assert result["status"] == "ok", result


def test_context_source_cannot_escape_through_a_symlink(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints

    manifest = _ready(tmp_path)
    source = manifest.parent / "startup.md"
    if source.exists():
        source.unlink()
    outside = tmp_path / "outside.md"
    outside.write_text("outside-private-content")
    source.symlink_to(outside)
    before = (manifest.parent.parent / "AGENTS.md").read_bytes()
    result = ensure_project_entrypoints(manifest)
    assert result["status"] == "conflict"
    assert (manifest.parent.parent / "AGENTS.md").read_bytes() == before


def test_known_legacy_entry_can_upgrade_without_touching_surrounding_rules(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints

    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    # Literal prior release output, independent of the current generator.
    old = '''<!-- qiming:entry:start -->
## 启明工作区入口

这里的“会员”指已接管并持续维护的项目、工具、账户等对象，不是付费订阅。遇到入会、项目或系统管理、工作接续、知识沉淀、恢复等请求，先读 `.qiming/workspace.json` 和 `.qiming/START.md`，再按任务需要读 `.qiming/qiming-user/SKILL.md`、本地约定和目标记录。工作中形成并保留独立脚本、Skill、MCP 或自动化时，按本地规则登记其身份与验证状态。保留本文件原有规则；普通小任务无需加载全库。
<!-- qiming:entry:end -->'''
    (root / "AGENTS.md").write_text("# 旧项目\n" + old + "\n自定义尾部。\n")
    (manifest.parent / "project-entrypoints.json").unlink()
    (manifest.parent / "startup.md").write_text("本项目维护古城周报。\n")
    assert ensure_project_entrypoints(manifest)["status"] == "ok"
    updated = (root / "AGENTS.md").read_text()
    assert updated.startswith("# 旧项目\n")
    assert updated.endswith("\n自定义尾部。\n")
    assert "本项目维护古城周报。" in updated
    assert old not in updated


def test_refresh_does_not_partially_apply_when_another_host_entry_conflicts(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints

    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    (root / "GEMINI.md").write_text("<!-- qiming:entry:start -->broken")
    (manifest.parent / "startup.md").write_text("修改后的摘要。\n")
    before = (root / "AGENTS.md").read_bytes()
    state = (manifest.parent / "project-entrypoints.json").read_bytes()
    result = ensure_project_entrypoints(manifest)
    assert result["status"] == "conflict"
    assert result["changed"] == []
    assert (root / "AGENTS.md").read_bytes() == before
    assert (manifest.parent / "project-entrypoints.json").read_bytes() == state


def test_nested_control_directory_keeps_the_explicit_project_root(tmp_path):
    from qiming_core.bootstrap import bootstrap
    from qiming_core.materialize import materialize
    from qiming_core.host_binding import binding_preview
    from qiming_core.discovery import scope_check

    root = tmp_path / "project"
    root.mkdir()
    control = root / "management" / "qiming"
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "nested-control", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"project": {"location": "../..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    assert bootstrap(root, control, manifest, profile, "nested")["status"] == "ok"
    path = control / "workspace.json"
    assert materialize(path, [], {}, "nested")["status"] == "ok"
    assert (root / "AGENTS.md").is_file()
    assert "management/qiming/START.md" in (root / "AGENTS.md").read_text()
    assert "management/qiming/workspace.json" in (root / "AGENTS.md").read_text()
    assert not (root / "management/AGENTS.md").exists()
    assert binding_preview(path, "codex", root)["status"] == "ok"
    assert scope_check(path, root)["active"] is True


def test_crlf_generated_block_is_not_mistaken_for_user_edit(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints, binding_status

    manifest = _ready(tmp_path)
    _bound(manifest)
    entry = manifest.parent.parent / 'AGENTS.md'
    prefix = b'# user prefix\r\n'
    suffix = b'\r\nuser suffix\r\n'
    entry.write_bytes(prefix + entry.read_bytes().replace(b'\n', b'\r\n') + suffix)
    (manifest.parent / 'startup.md').write_bytes('Updated summary.\r\n'.encode())
    assert binding_status(manifest, 'codex')['status'] == 'stale-context'
    result = ensure_project_entrypoints(manifest)
    assert result['status'] == 'ok', result
    assert entry.read_bytes().startswith(prefix)
    assert entry.read_bytes().endswith(suffix)
    assert ensure_project_entrypoints(manifest)['changed'] == []


def _expected_context_coverage():
    return dict(generated_context='current', short_entry='not_checked',
                linked_records='not_checked', summary_accuracy='not_checked')


def test_refresh_reports_scope_when_navigation_disagrees_with_authority(tmp_path):
    """Rendering the author's startup text must not certify unrelated progress."""
    from qiming_core.host_binding import ensure_project_entrypoints
    manifest = _ready(tmp_path)
    control = manifest.parent
    record = control / 'work.json'
    record.write_text('{"id":"task-synthetic","status":"completed"}', encoding='utf-8')
    entry = control / 'START.md'
    entry.write_text('Task is still running; see [authority](work.json).\n', encoding='utf-8')
    (control / 'startup.md').write_text('Read the navigation entry for current work.\n', encoding='utf-8')
    before = {path: path.read_bytes() for path in (entry, record)}
    result = ensure_project_entrypoints(manifest)
    assert result['status'] == 'ok'
    assert result['result']['context_coverage'] == _expected_context_coverage()
    for path, content in before.items():
        assert path.read_bytes() == content
    again = ensure_project_entrypoints(manifest)
    assert again['changed'] == []
    assert again['result']['context_coverage'] == _expected_context_coverage()


def test_bound_status_exposes_unreviewed_summary_scope(tmp_path):
    from qiming_core.host_binding import binding_status
    manifest = _ready(tmp_path)
    _bound(manifest)
    result = binding_status(manifest, 'codex')
    assert result['status'] == 'bound'
    assert result['context_coverage'] == _expected_context_coverage()


def test_context_coverage_respects_custom_navigation_and_refresh_conflict(tmp_path):
    from qiming_core.host_binding import ensure_project_entrypoints
    manifest = _ready(tmp_path)
    control = manifest.parent
    data = json.loads(manifest.read_text())
    data['workspace_entry'] = 'navigation.md'
    data['startup_context'] = 'policy.md'
    manifest.write_text(json.dumps(data), encoding='utf-8')
    entry = control / 'navigation.md'
    entry.write_text('Keep this user-owned navigation.\n', encoding='utf-8')
    (control / 'policy.md').write_text('Custom startup policy.\n', encoding='utf-8')
    result = ensure_project_entrypoints(manifest)
    assert result['status'] == 'ok'
    assert result['result']['context_coverage'] == _expected_context_coverage()
    assert entry.read_text() == 'Keep this user-owned navigation.\n'
    host = control.parent / 'AGENTS.md'
    host.write_text(host.read_text().replace('Custom startup policy.', 'Locally edited generated block.'))
    before = host.read_bytes()
    conflict = ensure_project_entrypoints(manifest)
    assert conflict['status'] == 'conflict'
    assert conflict['result'] is None
    assert conflict['changed'] == []
    assert host.read_bytes() == before


def test_refresh_disabled_entrypoints_never_claims_current_generated_context(tmp_path):
    from qiming_core.initialize import initialize
    from qiming_core.host_binding import ensure_project_entrypoints
    root = tmp_path / 'manual'
    root.mkdir()
    assert initialize(root, goal='synthetic manual context', entry='none')['status'] == 'ok'
    result = ensure_project_entrypoints(root / '.qiming/workspace.json')
    assert result['result']['entrypoints'] == []
    assert result['result']['context_coverage']['generated_context'] == 'not_configured'
    assert not (root / 'AGENTS.md').exists()


def test_copy_binding_preserves_context_coverage(tmp_path):
    import shutil
    from qiming_core.host_binding import binding_preview, binding_status
    manifest = _ready(tmp_path)
    preview = binding_preview(manifest, 'codex', manifest.parent.parent)
    target = Path(preview['binding_path'])
    target.parent.mkdir(parents=True)
    shutil.copytree(preview['source_directory'], target)
    result = binding_status(manifest, 'codex')
    assert result['status'] == 'bound-copy'
    assert result['context_coverage'] == _expected_context_coverage()
