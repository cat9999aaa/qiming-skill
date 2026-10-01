import hashlib
import json
import subprocess
import sys
from pathlib import Path


def fixture_workspace(tmp_path: Path) -> tuple[Path, Path]:
    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({
        "protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "ready",
        "profile": "profile.json", "roots": {"project": {"location": "..", "access": "read-write"}},
    }), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({
        "protocol": "qiming.profile/1", "collections": {
            "work": {"root": "project", "directory": "work", "pattern": "*.json", "codec": "json"},
            "members": {"root": "project", "directory": "members", "pattern": "*.json", "codec": "json"},
        }, "mappings": {},
    }), encoding="utf-8")
    work = tmp_path / "work" / "incident.json"
    work.parent.mkdir()
    work.write_text(json.dumps({"id": "rec_1", "type": "work", "name": "Incident"}), encoding="utf-8")
    return manifest, work


def test_log_event_appends_once_and_keeps_work_fields(tmp_path: Path) -> None:
    from qiming_core.quick_log import log_event

    manifest, work = fixture_workspace(tmp_path)
    ref = {"kind": "file", "root": "project", "path": "work/incident.json"}
    event = {"id": "evt-1", "kind": "observation", "summary": "Service was reachable", "observed_at": "2026-10-01T10:00:00Z"}
    first = log_event(manifest, ref, event, "incident-1")
    assert first["status"] == "ok"
    saved = json.loads(work.read_text(encoding="utf-8"))
    assert saved["name"] == "Incident"
    assert saved["events"] == [event]
    assert Path(first["result"]["journal_ref"]).is_file()
    second = log_event(manifest, ref, event, "incident-1")
    assert second["status"] == "ok"
    assert second["result"]["already_recorded"] is True
    assert len(json.loads(work.read_text(encoding="utf-8"))["events"]) == 1
    stale_retry = log_event(manifest, ref, event, "incident-1", hashlib.sha256(json.dumps({"id": "rec_1", "type": "work", "name": "Incident"}).encode()).hexdigest())
    assert stale_retry["result"]["already_recorded"] is True
    changed_fact = {**event, "summary": "Service was unreachable"}
    assert log_event(manifest, ref, changed_fact, "incident-1")["status"] == "conflict"


def test_log_event_rejects_stale_writer_without_losing_first_event(tmp_path: Path) -> None:
    from qiming_core.quick_log import log_event

    manifest, work = fixture_workspace(tmp_path)
    stale = hashlib.sha256(work.read_bytes()).hexdigest()
    ref = {"kind": "file", "root": "project", "path": "work/incident.json"}
    first = log_event(manifest, ref, {"id": "evt-1", "kind": "action", "summary": "First", "observed_at": "2026-10-01T10:00:00Z"}, "task", stale)
    second = log_event(manifest, ref, {"id": "evt-2", "kind": "action", "summary": "Second", "observed_at": "2026-10-01T10:01:00Z"}, "task", stale)
    assert first["status"] == "ok"
    assert second["status"] == "conflict"
    assert [e["id"] for e in json.loads(work.read_text())["events"]] == ["evt-1"]


def test_log_event_rejects_nonwork_and_escape(tmp_path: Path) -> None:
    from qiming_core.quick_log import log_event

    manifest, work = fixture_workspace(tmp_path)
    members = tmp_path / "members"
    members.mkdir()
    (members / "member.json").write_text(json.dumps({"type": "member"}), encoding="utf-8")
    event = {"id": "evt-1", "kind": "action", "summary": "Done", "observed_at": "2026-10-01T10:00:00Z"}
    for path in ("members/member.json", "../work/incident.json", "work/missing.json"):
        result = log_event(manifest, {"kind": "file", "root": "project", "path": path}, event, "task")
        assert result["status"] != "ok"
    assert "events" not in json.loads(work.read_text())


def test_short_log_command_writes_one_event(tmp_path: Path) -> None:
    manifest, work = fixture_workspace(tmp_path)
    script = Path(__file__).resolve().parents[2] / "skills" / "qiming" / "scripts" / "qiming.py"
    command = [sys.executable, str(script), "log", "work/incident.json", "Power restored",
               "--workspace-manifest", str(manifest), "--kind", "observation", "--intent-ref", "incident"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "ok"
    saved = json.loads(work.read_text())
    assert saved["events"][0]["summary"] == "Power restored"
    assert saved["events"][0]["observed_at"]


def test_short_log_retry_with_stable_event_id_keeps_first_observation_time(tmp_path: Path) -> None:
    manifest, work = fixture_workspace(tmp_path)
    script = Path(__file__).resolve().parents[2] / "skills" / "qiming" / "scripts" / "qiming.py"
    command = [sys.executable, str(script), "log", "work/incident.json", "Power restored",
               "--workspace-manifest", str(manifest), "--kind", "observation", "--intent-ref", "incident",
               "--event-id", "evt-retry"]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0
    observed_at = json.loads(work.read_text())["events"][0]["observed_at"]
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode == 0
    assert json.loads(second.stdout)["result"]["already_recorded"] is True
    events = json.loads(work.read_text())["events"]
    assert len(events) == 1
    assert events[0]["observed_at"] == observed_at


def test_short_log_uses_mapped_work_root_not_hardcoded_project(tmp_path: Path) -> None:
    manifest, work = fixture_workspace(tmp_path)
    control = manifest.parent
    data = json.loads(manifest.read_text())
    data["roots"]["records"] = data["roots"].pop("project")
    manifest.write_text(json.dumps(data))
    profile = control / "profile.json"
    mapping = json.loads(profile.read_text())
    mapping["collections"]["work"]["root"] = "records"
    profile.write_text(json.dumps(mapping))
    script = Path(__file__).resolve().parents[2] / "skills" / "qiming" / "scripts" / "qiming.py"
    result = subprocess.run([sys.executable, str(script), "log", "work/incident.json", "Recovered",
                             "--workspace-manifest", str(manifest), "--intent-ref", "incident"], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(work.read_text())["events"][0]["summary"] == "Recovered"


def test_quickstart_relative_manifest_command(tmp_path):
    manifest, work = fixture_workspace(tmp_path)
    script = Path(__file__).resolve().parents[2] / 'skills/qiming/scripts/qiming.py'
    result = subprocess.run([sys.executable, str(script), 'log', 'work/incident.json', 'Quickstart works',
                             '--workspace-manifest', '.qiming/workspace.json', '--intent-ref', 'incident'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert json.loads(work.read_text())['events'][0]['summary'] == 'Quickstart works'
