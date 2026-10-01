"""Run a declared case only with a real Agent runner and inspect artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(base: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not (base / path).resolve().is_relative_to(base.resolve()):
        raise ValueError("behavior fixture path escapes workspace")
    return base / path


def _assertion(workspace: Path, assertion: dict[str, object]) -> bool:
    target = _safe(workspace, str(assertion.get("path", "")))
    kind = assertion.get("kind")
    if kind == "path_exists":
        return target.exists()
    if kind == "path_absent":
        return not target.exists() and not target.is_symlink()
    if kind == "file_sha256":
        return target.is_file() and _sha(target.read_bytes()) == assertion.get("sha256")
    if kind == "file_contains":
        return target.is_file() and str(assertion.get("text", "")) in target.read_text(encoding="utf-8")
    if kind == "file_not_contains":
        return not target.exists() or (target.is_file() and str(assertion.get("text", "")) not in target.read_text(encoding="utf-8"))
    if kind == "tree_not_contains":
        needle = str(assertion.get("text", "")).encode("utf-8")
        return bool(needle) and (not target.exists() or (target.is_dir() and all(needle not in path.read_bytes() for path in target.rglob("*") if path.is_file() and not path.is_symlink())))
    if kind == "files_sha256_equal":
        other = _safe(workspace, str(assertion.get("other_path", "")))
        return target.is_file() and other.is_file() and _sha(target.read_bytes()) == _sha(other.read_bytes())
    if kind == "json_fields_equal":
        other = _safe(workspace, str(assertion.get("other_path", "")))
        if not target.is_file() or not other.is_file():
            return False
        field = assertion.get("field")
        return json.loads(target.read_text(encoding="utf-8")).get(field) == json.loads(other.read_text(encoding="utf-8")).get(field)
    if kind == "json_field_equals":
        if not target.is_file():
            return False
        data = json.loads(target.read_text(encoding="utf-8"))
        return data.get(assertion.get("field")) == assertion.get("value")
    raise ValueError(f"unsupported behavior assertion: {kind}")


def load_cases(case_dir: Path) -> list[dict[str, object]]:
    """Load unique, ordered scenario declarations without executing them."""
    cases: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in sorted(case_dir.glob("S*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        identifier = case.get("id")
        if not isinstance(identifier, str) or path.stem != identifier or identifier in seen:
            raise ValueError(f"duplicate or mismatched behavior case: {path}")
        seen.add(identifier)
        cases.append(case)
    return cases


def run_case(case_path: Path, runner: object | None) -> dict[str, object]:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    assertions = case.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ValueError("behavior case requires observable assertions")
    trace_requirements = case.get("trace_requirements")
    if not isinstance(trace_requirements, list) or not trace_requirements:
        raise ValueError("behavior case requires independent trace events")
    fixture = case.get("fixture", {})
    fixture_sha = _sha(json.dumps(fixture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    base = {"case_id": case["id"], "fixture_sha256": fixture_sha, "authorization": case.get("authorization", []), "required_capabilities": case.get("required_capabilities", []), "host": None, "model": None, "trace_ref": None, "artifacts": [], "assertions": []}
    if runner is None:
        return {**base, "status": "not-run", "reason": "No real Agent runner configured"}
    workspace = Path(tempfile.mkdtemp(prefix=f"qiming-{case['id']}-"))
    for relative, content in fixture.get("files", {}).items():
        path = _safe(workspace, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")
    for relative in fixture.get("directories", []):
        _safe(workspace, relative).mkdir(parents=True, exist_ok=True)
    outcome = runner.run(case["prompt"], workspace, {"case_id": case["id"], "required": base["required_capabilities"], "authorization": base["authorization"]})
    if not isinstance(outcome, dict):
        raise ValueError("runner must return a structured outcome")
    results = [{"assertion": item, "passed": _assertion(workspace, item)} for item in assertions]
    artifacts = [{"path": str(path.relative_to(workspace)), "sha256": _sha(path.read_bytes())} for path in sorted(workspace.rglob("*")) if path.is_file()]
    trace_ref = outcome.get("trace_ref")
    trace_path = Path(trace_ref).resolve() if isinstance(trace_ref, str) and trace_ref else None
    independent_trace = bool(trace_path and trace_path.is_file() and trace_path.stat().st_size and not trace_path.is_relative_to(workspace.resolve()))
    events: list[dict[str, object]] = []
    if independent_trace:
        try:
            if trace_path.stat().st_size > 10_000_000:
                raise ValueError("trace is too large")
            events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
            if not all(isinstance(event, dict) for event in events):
                raise ValueError("trace events must be objects")
        except (OSError, UnicodeError, ValueError):
            events = []
    trace_results = [{"requirement": requirement, "passed": any(event.get("case_id") == case["id"] and all(event.get(key) == value for key, value in requirement.items()) for event in events)} for requirement in trace_requirements]
    status = "blocked" if outcome.get("status") == "blocked" else "fail" if outcome.get("status") == "fail" or not all(item["passed"] for item in results + trace_results) else "pass" if independent_trace and outcome.get("status") == "completed" else "blocked"
    reason = outcome.get("reason") or ("Missing independent runner trace" if not independent_trace else "Required trace event missing" if not all(item["passed"] for item in trace_results) else None)
    return {**base, "status": status, "host": outcome.get("host"), "model": outcome.get("model"), "trace_ref": trace_ref, "trace_sha256": _sha(trace_path.read_bytes()) if independent_trace else None, "evidence_refs": outcome.get("evidence_refs", []), "artifacts": artifacts, "assertions": results, "trace_assertions": trace_results, "workspace": str(workspace), "reason": reason}
