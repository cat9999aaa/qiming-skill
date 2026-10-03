# Start with one project folder

Use an agent that can read project files and execute commands, with Python 3.11+. A web chat without those capabilities cannot manage your computer's folders automatically. Use `python3` on Linux/macOS or `py -3` on Windows. The default JSON workflow needs only the standard library.

## New project

From the project root explicitly selected by the user, replace the package path if needed:

```sh
python3 .agents/skills/qiming/scripts/qiming.py init --root . --goal "Revise chapter one" --hosts codex,claude --dry-run
```

Review `result.root_entry_files` and `root_file_actions`, then remove `--dry-run`. The default `--entry all` manages Qiming blocks in AGENTS.md, CLAUDE.md and GEMINI.md, preserving existing text. `--entry agents` manages only AGENTS.md. `--entry none` leaves root instruction files untouched and requires manual loading. This choice persists in `workspace.json.extensions.entry_policy`; repeating init or upgrading preserves it. Changing the choice later needs an explicit local configuration review. Disabling a previously managed file does not delete its old content or prevent a host reading it.

`--hosts auto` selects Codex and host directories already present in this project; an explicit comma-separated list can bind other supported hosts. Binding does not prove real-session behavior. With an opted-out entry, the host reports `manual-entry`; read START.md, conventions.md and qiming-user/SKILL.md explicitly each session.

`--preset dev` adds incidents; `writing` leaves manuscripts in place and uses JSON work records. `--name` supplies a project name. Defaults create `.qiming/workspace.json`, `profile.json`, `START.md`, `startup.md`, `conventions.md` and an independent `qiming-user/` instance. Supplying a goal creates `.qiming/work/w-0001.json`. Knowledge and member records grow as needed.

The JSON API equivalent, passed to `qiming.py --stdin`:

```json
{"protocol":"qiming.tool/1","request_id":"init-1","op":"init","args":{"root":"/project","goal":"Revise chapter one","hosts":"codex,claude","entry":"agents","dry_run":true}}
```

stdout is one JSON response; stderr contains readable Chinese guidance. Use returned IDs and fingerprints, never example IDs. Repeating init preserves existing profiles, identities, records and rules; no changes means top-level `changed: []`.

## Append and retrieve

```sh
python3 .qiming/qiming-user/scripts/qiming.py log .qiming/work/w-0001.json "Draft saved; proofreading not run" --workspace-manifest .qiming/workspace.json --event-id chapter-draft-1
```

The record path is relative to the registered root selected by the work collection, normally the project root, NOT the collection directory or arbitrary shell working directory. Include `.qiming/work/`. Omitted `--intent-ref` uses the selected record's ID. The same event ID and content are idempotent; new facts need a new ID.

```json
{"protocol":"qiming.tool/1","request_id":"find-1","op":"search","workspace_manifest":"/project/.qiming/workspace.json","args":{"query":"chapter"}}
```

Matches are in `result.items`. Inspect `result.coverage` and diagnostics before claiming complete coverage. `reindex` rebuilds an optional SQLite index; original records remain authoritative. Plain Markdown without frontmatter is skipped with an explicit reason, not converted into members.

## Existing projects

Read START.md first. Use the new package's `upgrade_preview`, review its resource states, then pass the complete result and its plan_id to `upgrade`. Preserve local changes, profile and member IDs. Never delete `.qiming` or reinitialize over an existing instance. [Adaptation](adapt.en.md) describes scope; [tools](tools.en.md) gives the protocol. The installed seed `qiming` supports adoption/upgrades; daily work uses the project's `qiming-user` instance. Other reference documents and generated guidance are currently primarily Chinese.
