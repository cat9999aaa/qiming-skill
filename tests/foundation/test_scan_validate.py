import hashlib
import json
from pathlib import Path


def _workspace(tmp_path: Path, *, state: str = "initializing") -> Path:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": state, "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}
    if state == "ready":
        manifest["instance"] = {"id": "ins_test", "entry": "qiming-user/SKILL.md", "manifest": "qiming-user/instance.json"}
    path = control / "workspace.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}), encoding="utf-8")
    return path


def test_scan_unicode_path_respects_budget(tmp_path: Path):
    from qiming_core.scan import scan

    manifest = _workspace(tmp_path)
    folder = tmp_path / "中文 项目"
    folder.mkdir()
    for name in ("一.md", "二.md", "三.md"):
        (folder / name).write_text(name, encoding="utf-8")
    found = scan(manifest, ["work"], ["中文 项目"], {"entries": 2, "depth": 2, "seconds": 10})
    assert found["status"] == "partial"
    assert found["coverage"]["visited"] == 2
    assert found["resume_token"]
    assert all("中文 项目" in item["locator"]["path"] for item in found["observations"])


def test_scan_does_not_follow_symlink_or_read_secret_content(tmp_path: Path):
    from qiming_core.scan import scan

    manifest = _workspace(tmp_path)
    secret = tmp_path / "private.secret"
    secret.write_text("should-never-appear", encoding="utf-8")
    (tmp_path / "link").symlink_to(secret)
    found = scan(manifest, ["work"], [], {"entries": 100, "depth": 1, "seconds": 10})
    assert "should-never-appear" not in json.dumps(found)
    assert any(item["facts"]["kind"] == "symlink" for item in found["observations"])


def test_validate_ready_instance_checks_required_hashes(tmp_path: Path):
    from qiming_core.validate import validate

    manifest = _workspace(tmp_path, state="ready")
    folder = manifest.parent / "qiming-user"
    folder.mkdir()
    entry = folder / "SKILL.md"
    entry.write_text("# User instance\n", encoding="utf-8")
    (folder / "instance.json").write_text(json.dumps({"protocol": "qiming.instance/1", "instance_id": "ins_test", "workspace_manifest": "../workspace.json", "resources": [{"path": "SKILL.md", "required": True, "sha256": hashlib.sha256(entry.read_bytes()).hexdigest()}, {"path": "missing.md", "required": True, "sha256": "0" * 64}]}), encoding="utf-8")
    result = validate(manifest, [], False)
    assert result["status"] == "error"
    assert any(d["code"] == "BROKEN_ENTRY" and "missing.md" in d["message"] for d in result["diagnostics"])


def test_validate_does_not_treat_old_observation_as_current_verification(tmp_path: Path):
    from qiming_core.validate import validate

    manifest = _workspace(tmp_path)
    record = tmp_path / "record.json"
    record.write_text(json.dumps({"name": "A", "verification": [{"result": "pass", "subject_fingerprint": "old"}]}), encoding="utf-8")
    result = validate(manifest, [{"root": "work", "path": "record.json", "codec": "json"}], False)
    assert result["status"] == "ok"
    assert result["result"]["records"][0]["structural_valid"] is True
    assert result["result"]["records"][0]["current_verification"] is False
