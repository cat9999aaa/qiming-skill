import json
from pathlib import Path


def _ready(tmp_path: Path) -> Path:
    from qiming_core.bootstrap import bootstrap
    from qiming_core.materialize import materialize

    root = tmp_path / "project"
    root.mkdir()
    control = root / ".qiming"
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"work": {"location": "..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    assert bootstrap(root, control, manifest, profile, "init_host")["status"] == "ok"
    path = control / "workspace.json"
    assert materialize(path, [], {"instance_id": "ins_user"}, "init_host")["status"] == "ok"
    return path


def test_host_report_separates_format_tool_behavior():
    from qiming_core.capabilities import capability_report

    report = capability_report([{"name": "format_recognition", "available": True, "evidence_ref": "e1"}, {"name": "tool_invocation", "available": False, "evidence_ref": "e2"}], "codex", "gpt-6-astra", "2026-09-28T00:00:00Z")
    assert report["compatibility"] == {"format": "pass", "tool": "fail", "behavior": "not-run"}
    assert report["model"] == "gpt-6-astra"


def test_binding_prefers_ready_user_instance_over_seed(tmp_path: Path):
    from qiming_core.host_binding import binding_preview

    manifest = _ready(tmp_path)
    result = binding_preview(manifest, "codex", manifest.parent.parent)
    assert result["status"] == "ok"
    assert result["source_path"].endswith("qiming-user/SKILL.md")
    assert result["binding_path"].endswith(".agents/skills/qiming-user")


def test_binding_cannot_install_project_instance_in_another_root(tmp_path: Path):
    from qiming_core.host_binding import binding_preview

    manifest = _ready(tmp_path)
    other = tmp_path / "unrelated"
    other.mkdir()
    result = binding_preview(manifest, "codex", other)
    assert result["status"] == "conflict"
    assert result["reason"] == "outside-project"
    assert not (other / ".agents").exists()


def test_materialize_creates_project_instruction_entrypoints(tmp_path: Path):
    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        entry = root / name
        assert entry.is_file(), name
        assert any(ref in entry.read_text(encoding="utf-8") for ref in (".qiming/START.md", "@AGENTS.md", "@./AGENTS.md"))
    assert "会员" in (root / "AGENTS.md").read_text(encoding="utf-8")
    user_skill = (root / ".qiming/qiming-user/SKILL.md").read_text(encoding="utf-8")
    assert "不是付费订阅" in user_skill
    assert "会员" in user_skill.split("---", 2)[1]


def test_materialize_keeps_existing_project_instructions(tmp_path: Path):
    from qiming_core.bootstrap import bootstrap
    from qiming_core.materialize import materialize

    root = tmp_path / "project"
    root.mkdir()
    originals = {"AGENTS.md": "# 原有规则\n先检查项目。\n", "CLAUDE.md": "# Claude 原有规则\n", "GEMINI.md": "# Gemini 原有规则\n"}
    for name, content in originals.items():
        (root / name).write_text(content, encoding="utf-8")
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"work": {"location": "..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    assert bootstrap(root, root / ".qiming", manifest, profile, "init_host")["status"] == "ok"
    path = root / ".qiming/workspace.json"
    assert materialize(path, [], {"instance_id": "ins_user"}, "init_host")["status"] == "ok"
    for name, original in originals.items():
        content = (root / name).read_text(encoding="utf-8")
        assert content.startswith(original)
        assert content.count("qiming:entry:start") == 1
    assert materialize(path, [], {"instance_id": "ins_user"}, "init_host")["changed"] == []


def test_ready_instance_repairs_missing_project_instruction_entrypoint(tmp_path: Path):
    from qiming_core.materialize import materialize

    manifest = _ready(tmp_path)
    entry = manifest.parent.parent / "AGENTS.md"
    entry.unlink()
    repaired = materialize(manifest, [], {"instance_id": "ins_user"}, "init_host")
    assert repaired["status"] == "ok"
    assert entry.is_file()
    assert any(change["path"] == str(entry) for change in repaired["changed"])


def test_project_entrypoints_use_registered_root_alias(tmp_path: Path):
    from qiming_core.bootstrap import bootstrap
    from qiming_core.materialize import materialize

    root = tmp_path / "project"
    root.mkdir()
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"project": {"location": "..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}
    assert bootstrap(root, root / ".qiming", manifest, profile, "init_host")["status"] == "ok"
    result = materialize(root / ".qiming/workspace.json", [], {}, "init_host")
    assert result["status"] == "ok", result
    assert (root / "AGENTS.md").is_file()


def test_generated_binding_is_regenerable_without_user_data_loss(tmp_path: Path):
    from qiming_core.host_binding import binding_preview, binding_status

    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    (root / "private.txt").write_text("private user body", encoding="utf-8")
    first = binding_preview(manifest, "gemini", root)
    second = binding_preview(manifest, "gemini", root)
    assert first == second
    assert "private user body" not in str(first)
    assert binding_status(manifest, "gemini")["status"] == "not-bound"
    assert not (root / ".gemini" / "skills").exists()


def test_copied_host_skill_can_call_tools_against_the_owning_workspace(tmp_path: Path):
    import shutil
    import subprocess
    import sys
    from qiming_core.host_binding import binding_preview, binding_status

    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    preview = binding_preview(manifest, "codex", root)
    assert preview.get("workspace_manifest") == str(manifest)
    binding = Path(preview["binding_path"])
    shutil.copytree(preview["source_directory"], binding)
    request = {"protocol": "qiming.tool/1", "request_id": "copy", "op": "scope_check", "workspace_manifest": preview["workspace_manifest"], "args": {"start_dir": str(root)}}
    run = subprocess.run([sys.executable, str(binding / "scripts/qiming.py"), "--stdin"], input=json.dumps(request), text=True, capture_output=True, cwd=root)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["result"]["active"] is True
    assert binding_status(manifest, "codex")["status"] == "bound-copy"


def test_changed_host_copy_is_not_reported_as_bound(tmp_path: Path):
    import shutil
    from qiming_core.host_binding import binding_preview, binding_status

    manifest = _ready(tmp_path)
    preview = binding_preview(manifest, "codex", manifest.parent.parent)
    binding = Path(preview["binding_path"])
    shutil.copytree(preview["source_directory"], binding)
    (binding / "scripts/qiming.py").write_text("raise RuntimeError('not the saved tool')\n")
    assert binding_status(manifest, "codex")["status"] == "stale-or-conflicting"


def test_binding_status_reports_missing_project_instruction(tmp_path: Path):
    from qiming_core.host_binding import binding_preview, binding_status

    manifest = _ready(tmp_path)
    root = manifest.parent.parent
    preview = binding_preview(manifest, "codex", root)
    binding = Path(preview["binding_path"])
    binding.parent.mkdir(parents=True)
    binding.symlink_to(preview["source_directory"], target_is_directory=True)
    (root / "AGENTS.md").unlink()
    status = binding_status(manifest, "codex")
    assert status["status"] == "incomplete"
    assert status["instruction_path"] == str(root / "AGENTS.md")


def test_read_only_host_reports_partial_capability():
    from qiming_core.capabilities import capability_report

    report = capability_report([{"name": "file_read", "available": True, "evidence_ref": "e1"}, {"name": "file_write", "available": False, "evidence_ref": "e2"}], "unknown-host", "unknown", "2026-09-28T00:00:00Z")
    assert report["operation_level"] == "read-only"
    assert report["compatibility"]["behavior"] == "not-run"
    assert report["limitations"]
