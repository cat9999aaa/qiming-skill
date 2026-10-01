# v0.2.0 — reviewed fixes and limits

The October 2026 review correctly identified a broken default record/search/log loop. This release changes defaults for **new projects**, while existing profiles, IDs, records and local customizations remain user-owned.

## Implemented

| Review area | Change |
| --- | --- |
| P0-1 | JSON defaults; recursive collection matching, exclusions, nested event logging; ordinary Markdown without frontmatter skipped |
| P0-2 | CLI/JSON init, dry run, repeat-safe onboarding, first task, startup references, early profile validation, general/dev/writing presets |
| P0-3 | Three-way upgrade_preview / upgrade through plan/apply; local edits preserved and reported; safe copied-binding updates |
| P0-4 | lock_status / lock_break; only a proven dead local owner can be cleared, with matching run ID and fingerprint |
| P1-1 / 9 | Project-only host binding, symlink-to-copy fallback, portable file writes, Windows command guidance |
| P1-2 | Public synthetic tests and Linux/macOS/Windows × Python 3.11–3.13 CI |
| P1-3 / 6 / 11 | Quickstart, profile reference, glossary, numbered workflows; seed vs local instance clarified; author notes removed from runtime |
| P1-4 | Actionable diagnostic hints and ok_with_warnings status |
| P1-5 | Generated .qiming/.gitignore; source records separated from local journals, staging and derived indexes |
| P1-7 | Key and known-token checks on managed writes, including aliases, YAML and event summaries; ordinary tracking URLs allowed |
| P1-8 / 10 | 3000-byte startup warning, 12000-byte limit; default JSON works without PyYAML |
| P2-1 / 3 | Beginner prerequisites, copyable agent request, before/after tree, actual fresh-session smoke results using synthetic records |
| P2-2 / 4 | “会员” retained as the established product term and explained as maintained objects; comparison with simpler approaches |
| P2-5 / 6 | Short active-work entry, explicit archive guidance, overdue knowledge flags; separate data-flow and comparison content on how-it-works |
| P2-7 | Versioned release, CI badge and honest host verification status |

Additional review fixes cover the earliest interrupted initialization, user-modified host copies, resources removed on both sides of an upgrade, and startup/instruction files omitted from backups.

## Deliberate adjustments to the review proposal

- An old lock can still belong to a live process. Time alone never permits removal. Unknown/remote lock owners require investigation.
- Operation journals can contain historical content and machine-specific paths. They are not committed by default. Bundle exports selected source records and project context; it is not a guarantee of cross-machine resumption of an in-flight transaction.
- Generic plan/apply writes bytes. JSON is required for structured event append; YAML and frontmatter parsing does not promise lossless structured rewriting.
- The writing preset does not guess where manuscripts live or move them. Map existing drafts explicitly.
- No automatic deletion of project seeds, arbitrary local-rule overwrite, entropy-only secret rejection or automatic monthly file moves. These can erase user work or misclassify IDs/hashes. Archive decisions remain explicit; stable IDs and paths stay intact.
- No fabricated video or dialogue. The website reports an actual limited smoke check with synthetic task data; a full walkthrough recording and automated archive-summary UI remain future work.

## Verification boundaries

Codex and Claude Code independently recovered a synthetic task and its next step in real fresh CLI sessions on 2026-10-01. Both noted missing acceptance evidence. Gemini CLI required authentication and was not verified. Cursor and OpenCode full behavior runs remain pending. The complete 34-scenario real-agent matrix has not been run.

The public CI result verifies automated tool behavior for each listed OS/Python job. It does not prove universal model or host compatibility. Consult [Actions](https://github.com/cat9999aaa/qiming-skill/actions/workflows/tests.yml) for the actual run state.

## v0.2.1 follow-up

A user relayed a Claude web review of v0.2.0. We reproduced local-edit validation errors, successful-operation staging leftovers, missing embedded source provenance and the mandatory quick-log intent option. The short init command already had a stderr summary; it now explains the project, binding and next step. Local edits warn without claiming verified behavior; missing files and identity errors still fail. Only successful operation-owned staging is removed. Log defaults to the selected work record ID. Release metadata records the source commit before the provenance-only stamp, plus a byte fingerprint for installed copies.
