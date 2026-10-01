"""Run declared cases through an explicitly configured real Agent adapter."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tests.behavior.harness import load_cases, run_case
from tests.behavior.report import summarize_runs


CASE_DIR = Path(__file__).parent / "cases"


class CommandRunner:
    """Adapter protocol: stdin JSON request; stdout one JSON outcome with trace_ref."""

    def __init__(self, host: dict[str, object]):
        command = host.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("runner command must be a nonempty argument array")
        self.command = command
        self.host = str(host["name"])
        self.model = str(host["model"])
        self.timeout = int(host.get("timeout_seconds", 600))
        if self.timeout < 1 or self.timeout > 3600:
            raise ValueError("runner timeout must be 1..3600 seconds")

    def run(self, prompt: str, workspace: Path, capabilities: dict[str, object]) -> dict[str, object]:
        payload = {"prompt": prompt, "workspace": str(workspace), "host": self.host, "model": self.model, **capabilities}
        completed = subprocess.run(self.command, input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, cwd=workspace, timeout=self.timeout, check=False)
        if completed.returncode:
            return {"status": "fail", "host": self.host, "model": self.model, "reason": f"runner exited {completed.returncode}"}
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"status": "fail", "host": self.host, "model": self.model, "reason": "runner did not return JSON"}
        if not isinstance(result, dict) or result.get("host") != self.host or result.get("model") != self.model:
            return {"status": "fail", "host": self.host, "model": self.model, "reason": "runner identity mismatch"}
        return result


def _selection(config: dict[str, object], known: set[str]) -> list[str]:
    selected = config.get("cases", sorted(known))
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise ValueError("cases must be a list of scenario IDs")
    if len(selected) != len(set(selected)) or not set(selected).issubset(known):
        raise ValueError("duplicate or unknown scenario ID")
    return selected


def run_matrix(config_path: Path | None, report_path: Path) -> dict[str, object]:
    cases = {case["id"]: case for case in load_cases(CASE_DIR)}
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path else {"hosts": [], "cases": sorted(cases)}
    if not isinstance(config, dict):
        raise ValueError("runner config must be an object")
    selected = _selection(config, set(cases))
    hosts = config.get("hosts", [])
    if not isinstance(hosts, list):
        raise ValueError("hosts must be an array")
    runs: list[dict[str, object]] = []
    if not hosts:
        for identifier in selected:
            runs.append(run_case(CASE_DIR / f"{identifier}.json", None))
    else:
        for host in hosts:
            if not isinstance(host, dict) or not isinstance(host.get("name"), str) or not isinstance(host.get("model"), str):
                raise ValueError("host must declare name and model")
            capabilities = set(host.get("capabilities", []))
            runner = CommandRunner(host) if host.get("command") else None
            for identifier in selected:
                case = cases[identifier]
                missing = set(case["required_capabilities"]) - capabilities
                if runner is None:
                    result = run_case(CASE_DIR / f"{identifier}.json", None)
                    result.update(host=host["name"], model=host["model"], reason="No real Agent command configured")
                    runs.append(result)
                    continue
                if missing:
                    result = run_case(CASE_DIR / f"{identifier}.json", None)
                    result.update(status="blocked", host=host["name"], model=host["model"], reason=f"Missing capabilities: {', '.join(sorted(missing))}")
                    runs.append(result)
                    continue
                for repeat in range(1, 4):
                    try:
                        result = run_case(CASE_DIR / f"{identifier}.json", runner)
                    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
                        result = run_case(CASE_DIR / f"{identifier}.json", None)
                        result.update(status="fail", host=host["name"], model=host["model"], reason=f"Runner error: {type(error).__name__}: {error}")
                    result["repeat"] = repeat
                    runs.append(result)
    report = summarize_runs(runs)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["config_ref"] = str(config_path) if config_path else None
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Qiming real-Agent behavior matrix")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    options = parser.parse_args()
    report = run_matrix(options.config, options.report)
    print(json.dumps({"counts": report["counts"], "report": str(options.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
