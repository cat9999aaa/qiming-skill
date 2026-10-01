"""The published behavior corpus is complete, isolated, and observable."""

import json
import re
from pathlib import Path

from tests.behavior.harness import load_cases


CASE_DIR = Path(__file__).parent / "cases"


def _check(cases: list[dict], start: int, end: int) -> None:
    assert [case["id"] for case in cases] == [f"S{i:02}" for i in range(start, end + 1)]
    for case in cases:
        assert case["fixture"]["files"] or case["fixture"]["directories"] or case["id"] == "S01"
        assert isinstance(case["prompt"], str) and len(case["prompt"]) > 30
        assert isinstance(case["authorization"], list) and case["authorization"]
        assert isinstance(case["required_capabilities"], list) and case["required_capabilities"]
        assert isinstance(case["assertions"], list) and case["assertions"]
        assert isinstance(case["trace_requirements"], list) and case["trace_requirements"]
        assert all(isinstance(item.get("operation"), str) and item["operation"] for item in case["trace_requirements"])
        assert all(item["kind"] in {"path_exists", "path_absent", "file_contains", "file_not_contains", "file_sha256", "json_field_equals", "tree_not_contains", "json_fields_equal", "files_sha256_equal"} for item in case["assertions"])
        assert any(item["path"] not in case["fixture"]["files"] for item in case["assertions"])


def test_case_specs_01_17_have_inputs_permissions_and_assertions():
    _check(load_cases(CASE_DIR)[:17], 1, 17)


def test_cases_do_not_embed_real_credentials():
    for path in CASE_DIR.glob("S*.json"):
        raw = path.read_text(encoding="utf-8")
        assert not re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{24,}", raw)
        if "password" in raw.lower() or "token" in raw.lower():
            assert "SYNTHETIC" in raw


def test_all_34_scenarios_have_runner_requirements():
    cases = load_cases(CASE_DIR)
    assert len(cases) == 34
    _check(cases[17:], 18, 34)
    by_id = {case["id"]: case for case in cases}
    assert any(item["kind"] == "tree_not_contains" and item["path"] == ".qiming" for item in by_id["S21"]["assertions"])
    assert any(item["kind"] == "files_sha256_equal" and item["other_path"].startswith("restored/") for item in by_id["S22"]["assertions"])
    assert any(item["kind"] == "json_fields_equal" and item["other_path"].startswith("restored/") for item in by_id["S22"]["assertions"])


def test_matrix_keeps_missing_host_not_run(tmp_path: Path):
    from tests.behavior.run_matrix import run_matrix

    report = run_matrix(None, tmp_path / "report.json")
    assert len(report["runs"]) == 34
    assert set(run["status"] for run in report["runs"]) == {"not-run"}
    assert (tmp_path / "report.json").is_file()


def test_matrix_rejects_duplicate_or_unknown_scenario_id(tmp_path: Path):
    import pytest
    from tests.behavior.run_matrix import run_matrix

    for selection in (["S01", "S01"], ["S00"], ["S35"]):
        config = tmp_path / "runner.json"
        config.write_text(json.dumps({"cases": selection, "hosts": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            run_matrix(config, tmp_path / "report.json")
