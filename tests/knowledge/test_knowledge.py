def test_stale_source_invalidates_summary():
    from qiming_core.knowledge import assess_knowledge

    entry = {"id": "rec_k", "source_refs": [{"ref": "file:a", "fingerprint": "old"}], "claim": "Maybe true"}
    issues = assess_knowledge(entry, {"file:a": "new"}, "2026-09-28T00:00:00+00:00")
    assert any(issue["code"] == "SOURCE_STALE" for issue in issues)
    assert entry["claim"] == "Maybe true"


def test_conflicting_versions_keep_scope_and_evidence():
    from qiming_core.knowledge import assess_knowledge

    entry = {"id": "rec_a", "claim": "Use method A", "applies_to": ["system-v1"], "evidence_refs": ["e1"], "relations": [{"kind": "knowledge:conflicts-with", "target": {"workspace_id": "ws", "id": "rec_b"}}]}
    issues = assess_knowledge(entry, {}, "2026-09-28T00:00:00+00:00")
    assert any(issue["code"] == "KNOWLEDGE_CONFLICT" for issue in issues)
    assert entry["applies_to"] == ["system-v1"]
    assert entry["evidence_refs"] == ["e1"]


def test_review_after_does_not_mark_claim_false():
    from qiming_core.knowledge import assess_knowledge

    entry = {"claim": "Works in v1", "review_after": "2026-09-01T00:00:00+00:00", "content_state": "accepted"}
    issues = assess_knowledge(entry, {}, "2026-09-28T00:00:00+00:00")
    assert any(issue["code"] == "REVIEW_DUE" for issue in issues)
    assert not any(issue["code"] == "CLAIM_FALSE" for issue in issues)
    assert entry["content_state"] == "accepted"


def test_incident_and_lesson_keep_distinct_ids():
    from qiming_core.knowledge import draft_lesson_from_incident

    incident = {"id": "rec_incident", "workspace_id": "ws", "evidence_refs": ["e1"], "scope": "project"}
    lesson = draft_lesson_from_incident(incident, "Check the profile version before migration", ["project-v1"])
    assert lesson["id"] != incident["id"]
    assert lesson["relations"][0]["kind"] == "derived_from"
    assert lesson["evidence_refs"] == ["e1"]
    assert lesson["content_state"] == "draft"
