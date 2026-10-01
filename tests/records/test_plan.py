import hashlib
import json
import os
from pathlib import Path


def _setup(tmp_path: Path) -> tuple[Path, str]:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "ready", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    profile = control / "profile.json"
    profile.write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}), encoding="utf-8")
    return manifest, hashlib.sha256(profile.read_bytes()).hexdigest()


def _change(path: str, expected: str | None, content: str) -> dict:
    return {"action": "create" if expected is None else "replace", "target": {"kind": "file", "root": "work", "path": path}, "expected_sha256": expected, "content_ref": content, "desired_sha256": hashlib.sha256(b"new").hexdigest(), "extensions": {"mine": 1}}


def test_plan_rejects_stale_profile_and_source(tmp_path: Path):
    from qiming_core.plan import plan_changes

    manifest, profile_sha = _setup(tmp_path)
    target = tmp_path / "old.json"
    target.write_bytes(b"old")
    staged = manifest.parent / "stage"
    staged.write_bytes(b"new")
    change = _change("old.json", "0" * 64, "stage")
    assert plan_changes(manifest, [change], "intent", "0" * 64)["diagnostics"][0]["code"] == "WRITE_CONFLICT"
    assert plan_changes(manifest, [change], "intent", profile_sha)["diagnostics"][0]["code"] == "WRITE_CONFLICT"
    assert target.read_bytes() == b"old"


def test_plan_rejects_dotdot_symlink_hardlink_and_absolute_member_path(tmp_path: Path):
    from qiming_core.plan import plan_changes

    manifest, profile_sha = _setup(tmp_path)
    (manifest.parent / "stage").write_bytes(b"new")
    target = tmp_path / "target.json"
    target.write_bytes(b"old")
    (tmp_path / "link.json").symlink_to(target)
    os.link(target, tmp_path / "hard.json")
    for path in ("../outside.json", str(target), "link.json", "hard.json"):
        result = plan_changes(manifest, [_change(path, hashlib.sha256(b"old").hexdigest(), "stage")], "intent", profile_sha)
        assert result["status"] == "conflict"
        assert result["diagnostics"][0]["code"] == "PATH_ESCAPE"


def test_plan_creates_no_target_or_parent(tmp_path: Path):
    from qiming_core.plan import plan_changes

    manifest, profile_sha = _setup(tmp_path)
    (manifest.parent / "stage").write_bytes(b"new")
    result = plan_changes(manifest, [_change("new/sub/asset.json", None, "stage")], "intent", profile_sha)
    assert result["status"] == "ok"
    assert result["result"]["protocol"] == "qiming.plan/1"
    assert result["result"]["changes"][0]["extensions"] == {"mine": 1}
    assert result["result"]["parents_to_create"]
    assert not (tmp_path / "new").exists()
