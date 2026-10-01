def test_work_completion_requires_current_evidence():
    from qiming_core.work import check_work_transition

    work = {"status": "active", "goal": "Ship", "scope": "project", "acceptance": [{"id": "a", "evidence_refs": ["e1"], "subject_fingerprint": "new", "scope": "project"}]}
    old = {"e1": {"result": {"status": "pass"}, "subject": {"fingerprint": "old"}, "coverage": {"scope": "project"}}}
    assert check_work_transition(work, "done", old)[0]["code"] == "EVIDENCE_STALE"
    current = {"e1": {"result": {"status": "pass"}, "subject": {"fingerprint": "new"}, "coverage": {"scope": "project"}}}
    assert check_work_transition(work, "done", current) == []


def test_failed_command_stays_failed_even_if_file_exists():
    from qiming_core.evidence import make_evidence

    result = make_evidence("run_1", "command", {"path": "output.txt"}, {"command": "build", "exists": True}, {"scope": "project"}, {"exit_code": 1, "status": "fail"})
    assert result["result"]["status"] == "fail"
    assert result["result"]["exit_code"] == 1


def test_interrupted_work_has_specific_next_action():
    from qiming_core.work import check_work_transition

    work = {"status": "active", "goal": "Publish", "scope": "site", "acceptance": [], "next_action": None}
    assert check_work_transition(work, "blocked", {})[0]["code"] == "NEXT_ACTION_REQUIRED"
    work["next_action"] = "Check the deployment receipt"
    work["blocked_on"] = "deployment response unknown"
    assert check_work_transition(work, "blocked", {}) == []


def test_evidence_omits_known_sensitive_fields():
    from qiming_core.evidence import make_evidence

    evidence = make_evidence("run_1", "command", {}, {"command": "login", "password": "supersecret"}, {}, {"status": "fail", "token": "supersecret"})
    assert "supersecret" not in str(evidence)
    assert evidence["limitations"]
