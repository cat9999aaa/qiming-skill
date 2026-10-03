# Local deterministic tools

Run the authoritative project instance's `scripts/qiming.py --stdin` with one UTF-8 JSON request. Required fields: `protocol: "qiming.tool/1"`, `request_id`, `op`, `args`, and for existing-project operations `workspace_manifest`. This manifest is authoritative even if the host discovers a copied Skill elsewhere.

Typical operations: init for onboarding; scan for mapped metadata; plan → apply for controlled writes; reconcile for interrupted operations; search and reindex for retrieval. Registration, progress and verified behavior are separate facts.

## Paths and quick logging

`work_ref.path` is relative to the registered root named by `profile.collections.work.root` in `workspace.json.roots`. It is NOT relative to collection.directory. For root=project and directory=.qiming/work, pass `.qiming/work/w-0001.json`. For directory=records/tasks, pass `records/tasks/w-0001.json`. The CLI determines the root alias from the work collection. Incorrect paths are rejected rather than guessed.

```sh
python3 .qiming/qiming-user/scripts/qiming.py log .qiming/work/w-0001.json "Service recovered; restart check pending" --workspace-manifest .qiming/workspace.json --kind observation --event-id recovery-1
```

Kinds: observation, decision, action, handoff. The log operation appends to an existing mapped JSON work record only. YAML/frontmatter are read-only; preserve their originals and explicitly map a JSON sidecar if needed. Omitted CLI `--intent-ref` uses the record ID; an explicit ref remains supported. Reusing an event ID with the same kind/content does not duplicate the event. Changed content with that ID conflicts.

For JSON `log_event`, args contain `work_ref` (kind=file, root, path), `event` (id, kind, summary, observed_at with timezone), `intent_ref`, and optional expected_sha256. The summary is a single line. Never put secret values in requests or logs.

## Response fields

`status`, `diagnostics`, `changed`, and `run_id` are TOP-LEVEL fields. Operation-specific output is under `result`. Do not read `result.changed`. A successful refresh_context reports changed files with path, before_sha256 and after_sha256; an unchanged repeat reports `changed: []`.

Exit codes: ok/ok_with_warnings=0, error=2, conflict=3, partial=4. Inspect hints and coverage; partial is not full success.

Search args include query, collections, scope_ids, types, optional categories (exact string list), limit and cursor. Omit categories to include uncategorized records. Search results carry category when present. Categories are navigation metadata, never authorization. `result.coverage` includes errors, truncated, skipped_files (root/collection/path/reason), skipped_count and legacy skipped path list. Missing-frontmatter files cause partial/INCOMPLETE_COVERAGE. Use explicit adaptation rather than inventing member IDs from filenames.

## Scope, entries and upgrade

- `scope_check`: args.start_dir is the current task directory, not a managed external system resource. Continue only if result.active is true.
- `refresh_context`: args={} reads local startup.md and updates tracked generated blocks according to entry_policy. It preserves surrounding user text and refuses locally edited generated blocks.
- `binding_preview`: args.host and args.host_root (this project root).
- `binding_status` and `bind`: args.host. Hosts: codex, claude, gemini, cursor, opencode. An opted-out instruction file reports manual-entry, not proven automatic startup.
- `init`: root, preset, name, goal, hosts, dry_run, entry=all|agents|none. See [quickstart](quickstart.en.md).
- `upgrade_preview`: args.seed_dir points to a complete new package. Pass its complete result to upgrade as args.preview and its plan_id as args.plan_id. Stale previews are rejected. Local modifications/conflicts are preserved; inspect diagnostics and validate afterward.
- `plan_migration`: args.new_profile_ref, affected_collections, intent_ref; preview before applying profile/record migrations.

Credential records hold only provider references. Use project-approved credential storage and the host's authorization mechanisms. The Chinese [security reference](security.md) and [infrastructure template](infrastructure.md) describe optional operating conventions; they do not grant permissions.
