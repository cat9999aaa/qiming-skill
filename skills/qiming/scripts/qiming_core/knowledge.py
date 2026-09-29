"""Check evidence-linked knowledge without rewriting the author's claim."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from .search import search


def _issue(code: str, message: str, ref: str | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "locator": ref, "retryable": False, "details": {}}


def assess_knowledge(entry: dict[str, object], source_fingerprints: dict[str, str], now: str) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for source in entry.get("source_refs", []):
        if not isinstance(source, dict):
            issues.append(_issue("SCHEMA_INVALID", "Source reference is not an object"))
            continue
        ref = str(source.get("ref", ""))
        prior = source.get("fingerprint")
        current = source_fingerprints.get(ref)
        if current is None:
            issues.append(_issue("SOURCE_UNAVAILABLE", "Source cannot be checked in current scope", ref))
        elif current != prior:
            issues.append(_issue("SOURCE_STALE", "Source fingerprint changed; review derived claim and summary", ref))
    review = entry.get("review_after")
    if isinstance(review, str):
        try:
            if datetime.fromisoformat(review) <= datetime.fromisoformat(now):
                issues.append(_issue("REVIEW_DUE", "Review date passed; claim remains unjudged"))
        except ValueError:
            issues.append(_issue("SCHEMA_INVALID", "Invalid review_after time"))
    if any(isinstance(relation, dict) and relation.get("kind") == "knowledge:conflicts-with" for relation in entry.get("relations", [])):
        issues.append(_issue("KNOWLEDGE_CONFLICT", "Conflicting knowledge has a separate scope or unresolved evidence"))
    return issues


def knowledge_candidates(manifest_path: Path, query: str, scope_ids: list[str]) -> dict[str, object]:
    result = search(manifest_path, {"query": query, "scope_ids": scope_ids, "types": ["knowledge", "lesson", "incident"], "limit": 20})
    if result.get("result") is not None:
        result["result"]["guidance"] = "Read candidate authority and evidence before updating or drafting a new conclusion"
    return result


def draft_lesson_from_incident(incident: dict[str, object], claim: str, applies_to: list[str]) -> dict[str, object]:
    if not claim.strip():
        raise ValueError("lesson claim is required")
    return {"id": f"rec_{uuid.uuid4()}", "type": "lesson", "claim": claim, "applies_to": applies_to, "scope": incident.get("scope"), "content_state": "draft", "evidence_refs": list(incident.get("evidence_refs", [])), "source_refs": [], "relations": [{"kind": "derived_from", "target": {"workspace_id": incident.get("workspace_id"), "id": incident.get("id")}, "evidence_refs": list(incident.get("evidence_refs", []))}]}
