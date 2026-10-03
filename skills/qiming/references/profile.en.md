# Map an existing directory with profile.json

`workspace.json.roots` maps aliases to locations relative to that manifest. `profile.json` maps collections to existing files. Keep original names, layouts, IDs and bodies; change mappings deliberately instead of replacing an established profile.

| Field | Meaning |
| --- | --- |
| protocol | qiming.profile/1 |
| collections | Named collections such as work, members, knowledge |
| root | Alias registered in workspace roots |
| directory | Path relative to that registered root; no parent traversal |
| pattern | Glob relative to directory; **/*.json includes nested folders |
| codec | json supports structured logging; yaml and markdown-frontmatter are preservation-oriented read-only parsing |
| mapping | Name of an entry in mappings |
| exclude | Collection exclusions combined with scope_rules.exclude |
| scope_rules.exclude | Root-relative patterns or directory names |
| retrieval.max_candidates | Optional candidate cap; truncation reports partial |
| retrieval.index_path | Rebuildable index inside the control directory |
| record_rules, extensions | Local conventions/extensions, not an automatic policy engine |

Mappings use JSON Pointer, e.g. `"name":{"source":"/title","writable":false}`. Escape slash as ~1 and tilde as ~0. values can translate local status names. writable describes mapping support, not filesystem authorization or a general field setter. log appends events to standard JSON work records; plan/apply writes fingerprint-protected bytes.

## Nested categories

Existing members/00-foundation, members/20-models and members/99-archive can stay as they are; use directory=members and pattern=**/*.json. These are examples, not required folders. Add optional category to a record, or map it from an existing field: `"category":{"source":"/group","writable":false}`. Search returns it and accepts args.categories. Uncategorized records remain searchable. A directory/category does not grant permission, establish dependency direction, or retire a record; lifecycle and relations remain explicit. Keep one authoritative record and its stable ID when moving it.

## Markdown and legacy data

```json
{"purpose":"drafts","root":"project","directory":"chapters","pattern":"**/*.md","codec":"markdown-frontmatter","mapping":"draft","exclude":["archive/**"]}
```

Map a title through mappings.draft, e.g. `{"name":{"source":"/title","writable":false}}`. Each authoritative record requires a stable ID in its source frontmatter. Ordinary Markdown without frontmatter is reported in coverage.skipped_files with reason=missing-frontmatter; coverage.skipped_count and partial expose the gap. Malformed frontmatter is an error. A filename fallback is not currently implemented. Use read-only text search for unadapted notes; only add frontmatter or an explicit JSON sidecar after reviewing ownership and preserving original content. Install the locked PyYAML dependency only for YAML/frontmatter, with the interpreter actually running the tools.

Default presets general/dev/writing use JSON collections; dev adds incidents, writing leaves manuscripts untouched. Infrastructure fields can extend existing records without a new mandatory preset; see the Chinese [template](infrastructure.md).

Before changing an established profile, use plan_migration with new_profile_ref, affected_collections and intent_ref. Review the returned plan then apply it, preserving IDs and unknown fields. See [tools](tools.en.md) for response/coverage semantics and [adaptation](adapt.en.md) for project boundaries.
