"""Preserve every actual run and keep missing coverage visible."""

from __future__ import annotations


def summarize_runs(runs: list[dict[str, object]]) -> dict[str, object]:
    allowed = {"pass", "fail", "blocked", "not-run"}
    counts = {status: 0 for status in ("pass", "fail", "blocked", "not-run")}
    for run in runs:
        status = run.get("status")
        if status not in allowed:
            raise ValueError(f"invalid run status: {status}")
        counts[status] += 1
    return {"protocol": "qiming.behavior-report/1", "counts": counts, "runs": runs, "coverage": {"executed": len(runs) - counts["not-run"], "declared": len(runs)}}


def compare_baseline(current: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    for field in ("case_id", "fixture_sha256", "authorization", "required_capabilities"):
        if current.get(field) != baseline.get(field):
            raise ValueError(f"baseline differs in {field}")
    old = baseline.get("status")
    new = current.get("status")
    outcome = "improved" if old != "pass" and new == "pass" else "regressed" if old == "pass" and new != "pass" else "unchanged" if old == new else "changed"
    return {"case_id": current.get("case_id"), "baseline_status": old, "current_status": new, "outcome": outcome}
