import json
from pathlib import Path
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "qiming" / "SKILL.md"
CLI = ROOT / "skills" / "qiming" / "scripts" / "qiming.py"


def test_skill_frontmatter_matches_directory():
    assert SKILL.is_file()
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == SKILL.parent.name == "qiming"
    assert metadata["description"].startswith("Use when ")
    assert "references/adapt.md" in text


def test_cli_rejects_unknown_op_without_stdout_noise():
    request = {"protocol": "qiming.tool/1", "request_id": "r-invalid", "op": "unknown", "workspace_manifest": None, "args": {}}
    completed = subprocess.run(
        [sys.executable, str(CLI), "--stdin"],
        input=json.dumps(request), text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 2
    output = json.loads(completed.stdout)
    assert output["protocol"] == "qiming.tool/1"
    assert output["request_id"] == "r-invalid"
    assert output["status"] == "error"
    assert output["diagnostics"][0]["code"] == "INVALID_INPUT"
    assert completed.stdout.count("\n") == 1


def test_dispatch_returns_one_json_response():
    from qiming_core.protocol import dispatch

    result = dispatch({"protocol": "qiming.tool/1", "request_id": "r1", "op": "inspect", "workspace_manifest": None, "args": {"start_dir": "."}})
    assert set(result) == {"protocol", "request_id", "status", "result", "diagnostics", "changed", "run_id"}
    assert result["protocol"] == "qiming.tool/1"
    assert result["request_id"] == "r1"
    assert result["status"] in {"ok", "error", "partial", "conflict"}
