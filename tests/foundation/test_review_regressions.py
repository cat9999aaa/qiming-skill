import json
import subprocess
import sys
from pathlib import Path


def test_cli_handles_json_without_pyyaml_and_malformed_args(tmp_path: Path):
    script = Path(__file__).parents[2] / "skills/qiming/scripts/qiming.py"
    requests = [
        {"protocol": "qiming.tool/1", "request_id": "inspect", "op": "inspect", "args": {"start_dir": str(tmp_path)}},
        {"protocol": "qiming.tool/1", "request_id": "bad", "op": "bootstrap", "args": {}},
    ]
    for request in requests:
        completed = subprocess.run([sys.executable, "-S", str(script), "--stdin"], input=json.dumps(request), text=True, capture_output=True)
        assert not completed.stderr
        output = json.loads(completed.stdout)
        assert output["request_id"] == request["request_id"]
        assert output["status"] == ("ok" if request["request_id"] == "inspect" else "error")


def test_scan_reports_outward_symlink_as_link(tmp_path: Path):
    from qiming_core.scan import scan

    root = tmp_path / "work"
    root.mkdir()
    control = root / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    (root / "outside-link").symlink_to(tmp_path, target_is_directory=True)
    result = scan(manifest, ["work"], ["outside-link"], {"entries": 10, "depth": 1, "seconds": 5})
    assert result["observations"][0]["facts"]["kind"] == "symlink"


def test_validate_references_finds_duplicates_and_cycles(tmp_path: Path):
    from qiming_core.validate import validate

    root = tmp_path / "work"
    control = root / ".qiming"
    control.mkdir(parents=True)
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {"members": {"root": "work", "directory": "members", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}}}}), encoding="utf-8")
    members = root / "members"
    members.mkdir()
    for name, record in {"a": {"id": "a", "relations": [{"kind": "part_of", "target": {"workspace_id": "ws", "id": "b"}}]}, "b": {"id": "b", "relations": [{"kind": "part_of", "target": {"workspace_id": "ws", "id": "a"}}]}, "duplicate": {"id": "a"}}.items():
        (members / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")
    result = validate(manifest, [], True)
    assert {item["code"] for item in result["diagnostics"]} >= {"DUPLICATE_ID", "RELATION_CYCLE"}


def test_search_reaches_exact_id_after_2000_records(tmp_path: Path):
    from qiming_core.search import search

    root = tmp_path / "work"
    control = root / ".qiming"
    control.mkdir(parents=True)
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "workspace_id": "ws", "state": "initializing", "profile": "profile.json", "roots": {"work": {"location": "..", "access": "read-write"}}}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {"members": {"root": "work", "directory": "members", "pattern": "*.json", "codec": "json", "mapping": "m"}}, "mappings": {"m": {"id": {"source": "/id"}}}}), encoding="utf-8")
    members = root / "members"
    members.mkdir()
    for index in range(2001):
        (members / f"{index:04}.json").write_text(json.dumps({"id": f"id-{index:04}"}), encoding="utf-8")
    result = search(manifest, {"scope_ids": ["workspace"], "ref": {"workspace_id": "ws", "id": "id-2000"}})
    assert result["status"] == "ok"
    assert result["result"]["items"][0]["id"] == "id-2000"
