# Conversation lifecycle design

Users need visible topic conversations to remain in the intended workspace and finish with durable handoffs. A host thread, an internal worker, a managed work record and a service session are distinct objects.

Keep the project-local Skill small. Add an on-demand reference and a read-only Python policy helper. The helper consumes explicit host observations and the authoritative workspace manifest; it recommends reuse/create/fork/archive but never calls host tools, reads credentials, mutates records or treats supplied citations as proven evidence. The host remains responsible for authorization, truthful observations and actual execution/readback.

Prefer existing suitable conversations. Creation requires task-specific split authorization. A registered root project may use project creation; subdirectory work or unresolved host projects use same-directory fork. A child ID is not successful placement. Verify cwd, manifest identity and formal host membership independently; an explicit-null project is an unregistered directory workspace, never a formal project. If sidebar placement is requested, verify that separately and repair a suitable conversation's placement rather than duplicating it.

Archive only completed non-coordinator conversations with outcome, validation, remaining-work handoff and preserved worktree changes, plus explicit archive authorization. Paused, active, awaiting-user and current conversations remain open. No permanent deletion.

Alternatives: prose alone cannot check repeated identity mistakes; a host controller would add credentials, destructive capabilities and host coupling. The selected reference + deterministic recommendation is small, self-contained and independently testable. No new daemon or automatic session creation on ordinary chat. Long-context continuation uses a concise handoff where supported instead of unconditional full-history forks.

Validation uses synthetic temporary projects, subprocess CLI tests, instance materialization and upgrade preservation. Existing field failures motivate the change; they do not prove all models or hosts will follow the guidance. No private field records enter this repository.
