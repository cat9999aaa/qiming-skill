"""Validate work state changes against real, current evidence."""

from __future__ import annotations


def _diag(code: str, message: str) -> dict[str, object]:
    return {"code": code, "message": message, "locator": None, "retryable": False, "details": {}}


def check_work_transition(work: dict[str, object], target_status: str, evidence_by_ref: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if target_status not in {"open", "active", "blocked", "done", "cancelled"}:
        return [_diag("SCHEMA_INVALID", "Unknown work status")]
    if target_status == "blocked":
        if not isinstance(work.get("next_action"), str) or not work["next_action"].strip():
            issues.append(_diag("NEXT_ACTION_REQUIRED", "Blocked work needs a concrete next action"))
        if not isinstance(work.get("blocked_on"), str) or not work["blocked_on"].strip():
            issues.append(_diag("BLOCKER_REQUIRED", "Blocked work needs a specific external condition"))
    if target_status == "done":
        acceptance = work.get("acceptance")
        if not isinstance(acceptance, list) or not acceptance:
            issues.append(_diag("ACCEPTANCE_REQUIRED", "Completed work needs observable acceptance conditions"))
            return issues
        for condition in acceptance:
            refs = condition.get("evidence_refs", []) if isinstance(condition, dict) else []
            if not refs:
                issues.append(_diag("EVIDENCE_MISSING", "Acceptance condition has no evidence"))
                continue
            for ref in refs:
                evidence = evidence_by_ref.get(ref)
                if not evidence:
                    issues.append(_diag("EVIDENCE_MISSING", f"Evidence reference is missing: {ref}"))
                    continue
                if evidence.get("subject", {}).get("fingerprint") != condition.get("subject_fingerprint"):
                    issues.append(_diag("EVIDENCE_STALE", f"Evidence subject changed: {ref}"))
                if evidence.get("coverage", {}).get("scope") != condition.get("scope"):
                    issues.append(_diag("EVIDENCE_SCOPE", f"Evidence scope does not cover condition: {ref}"))
                if evidence.get("result", {}).get("status") != "pass":
                    issues.append(_diag("EVIDENCE_FAILED", f"Evidence did not pass: {ref}"))
    return issues
