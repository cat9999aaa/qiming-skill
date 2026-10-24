# Refresh Coverage Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task; preserve user-owned project records.

**Goal:** Prevent refresh/binding success from being mistaken for verified navigation or progress accuracy.
**Architecture:** Add explicit coverage reporting to existing successful operations and clarify the existing closeout workflow. No automatic summary rewriting.
**Tech Stack:** Python 3.11+, standard library; pytest.
**Spec:** ../specs/2026-10-23-refresh-coverage-design.md

## Constraints and review focus

No business-field assumptions or project-specific paths. Preserve protected regions, custom entry paths, changed lists, budget warnings and idempotence. Never claim generated context current after a failed/conflicting refresh. Coverage is evidence about what the tool checked, not proof that prose is accurate.

## Task 1: Reporting and regressions

- [x] Add synthetic stale-prose, idempotent refresh, custom entry, conflict and binding tests to tests/portability/test_startup.py; observe missing coverage failures.
- [x] Add a shared coverage report in startup.py and preserve it through successful host_binding.py results. No reads of linked records.
- [x] Run targeted and full tests; verify old operation outcomes and changed lists remain intact.

## Task 2: Workflow, review and publication

- [x] Clarify manage.md, tools.md and hosts.md: authority/navigation/startup are separate; refresh only updates generated regions.
- [x] Independent review, correct findings and verify site build/diff checks.
- [ ] Publish a separate reviewable PR; keep local instance customizations and records unchanged. Record actual CI and unverified behavior separately.
