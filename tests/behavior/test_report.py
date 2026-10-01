import json
from pathlib import Path


def _case(tmp_path: Path, assertions: list[dict] | None = None) -> Path:
    path = tmp_path / "case.json"
    path.write_text(json.dumps({"id": "S01", "name": "start", "fixture": {"files": {"README.md": "start"}}, "prompt": "Organize this directory", "authorization": ["read", "write"], "required_capabilities": ["file_read"], "trace_requirements": [{"operation": "fixture-observed"}], "assertions": [{"kind": "path_exists", "path": "README.md"}] if assertions is None else assertions}), encoding="utf-8")
    return path


def test_report_keeps_unrun_host_as_not_run(tmp_path: Path):
    from tests.behavior.harness import run_case

    result = run_case(_case(tmp_path), None)
    assert result["status"] == "not-run"
    assert result["trace_ref"] is None


def test_report_fails_when_scenario_has_no_required_assertion(tmp_path: Path):
    import pytest
    from tests.behavior.harness import run_case

    with pytest.raises(ValueError):
        run_case(_case(tmp_path, []), None)


def test_summary_preserves_all_three_behavior_runs():
    from tests.behavior.report import summarize_runs

    runs = [{"case_id": "S01", "status": "pass", "host": "codex", "model": "gpt-6-astra"}, {"case_id": "S01", "status": "fail", "host": "claude", "model": "m"}, {"case_id": "S01", "status": "not-run", "host": "cursor", "model": None}]
    summary = summarize_runs(runs)
    assert summary["counts"] == {"pass": 1, "fail": 1, "blocked": 0, "not-run": 1}
    assert len(summary["runs"]) == 3


def test_baseline_uses_same_fixture_and_permissions():
    import pytest
    from tests.behavior.report import compare_baseline

    baseline = {"case_id": "S01", "fixture_sha256": "aaa", "authorization": ["read"], "status": "fail"}
    current = {"case_id": "S01", "fixture_sha256": "bbb", "authorization": ["read"], "status": "pass"}
    with pytest.raises(ValueError):
        compare_baseline(current, baseline)
    current["fixture_sha256"] = "aaa"
    assert compare_baseline(current, baseline)["outcome"] == "improved"


def test_nonexistent_trace_cannot_make_behavior_pass(tmp_path: Path):
    from tests.behavior.harness import run_case

    class Runner:
        def run(self, prompt, workspace, capabilities):
            (workspace / "README.md").write_text("start", encoding="utf-8")
            return {"status": "completed", "trace_ref": str(tmp_path / "never-written.jsonl")}

    assert run_case(_case(tmp_path), Runner())["status"] != "pass"


def test_unrelated_trace_cannot_make_behavior_pass(tmp_path: Path):
    from tests.behavior.harness import run_case

    case = _case(tmp_path)
    data = json.loads(case.read_text())
    data["trace_requirements"] = [{"operation": "bootstrap"}]
    case.write_text(json.dumps(data), encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({"case_id": "S01", "operation": "unrelated"}) + "\n", encoding="utf-8")

    class Runner:
        def run(self, prompt, workspace, capabilities):
            return {"status": "completed", "trace_ref": str(trace)}

    assert run_case(case, Runner())["status"] != "pass"


def test_correlated_runner_trace_and_artifact_can_pass(tmp_path: Path):
    from tests.behavior.harness import run_case

    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({"case_id": "S01", "operation": "fixture-observed"}) + "\n", encoding="utf-8")

    class Runner:
        def run(self, prompt, workspace, capabilities):
            assert capabilities["case_id"] == "S01"
            return {"status": "completed", "trace_ref": str(trace)}

    result = run_case(_case(tmp_path), Runner())
    assert result["status"] == "pass"
    assert result["trace_sha256"]
