# Conversation Lifecycle Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task. Preserve user-owned instance customizations.

**Goal:** Make authorized topic-session placement and evidence-before-archive decisions testable.
**Architecture:** On-demand reference plus read-only JSON policy helper bundled into local instances. Actual host actions remain with the calling agent.
**Tech Stack:** Python 3.11+, standard library; existing pytest suite.
**Spec:** ../specs/2026-10-23-conversation-lifecycle-design.md

## Constraints and review focus

No host API calls, background workers, credentials or real project records. Distinguish absent project metadata from explicit null, root from task cwd, formal membership from sidebar grouping, recommendation from execution, and completed from paused/awaiting-user work.

## Task 1: Policy and regression checks

- [x] Add synthetic subprocess tests in tests/portability/test_conversations.py; run before helper exists and record failure.
- [x] Add skills/qiming/scripts/session_policy.py with scope/reuse/create/fork/verify/archive recommendations; run targeted tests.
- [x] Cover wrong cwd/workspace/project/sidebar; explicit-null readbacks; subdirectory fork; evidence, authorization and worktree archive gates; malformed input.

## Task 2: Discoverability and packaging

- [x] Add skills/qiming/references/conversations.md and link from hosts.md and generated local entry in materialize.py.
- [x] Verify generated instance includes reference/helper and upgrade preview preserves local entry changes.
- [x] Run complete pytest suite and site build; inspect public diff for private data.
- [x] Independent review and corrections: initial nine malformed-input regressions failed before fixes; 35 targeted + 193 full tests and 41 independent checks now pass.
- [ ] Commit/push feature branch and open reviewable PR. Attach PR and report actual checks and unverified host behavior.
