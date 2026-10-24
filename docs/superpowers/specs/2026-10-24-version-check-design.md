# Version checks and cross-device integration

User intent: merge the two other-device contributions, publish them with the official site, and let users discover updates without losing project rules or identity.

Use the existing Python 3.11+ standard-library CLI and qiming.tool/1 protocol. Add version (offline) and check_update (explicit network) operations and version/check-update short commands. Runtime package metadata and a project's installed seed_version/seed_commit are distinct; prefer the explicitly selected project instance for comparisons. Existing project rules, member IDs and profile are never written by a check.

Query only the official GitHub releases API with bounded timeout/response size; never send workspace paths, records or credentials. Default channel follows the package release_channel; this pre-1.0 release remains preview. stable excludes prereleases, preview includes them; drafts never count. Compare valid semantic versions, including prerelease ordering. Unknown versions and failed/rate-limited/malformed responses produce an unknown result with diagnostics, never a false up-to-date claim. A different source commit with the same version is reported separately.

Checks do not install, execute downloaded code, mutate local rules, or contact the network during every ordinary session. Expose the operations in the Skill and upgrade guide so the agent uses them when the user asks about versions or updates. After a detected update, obtain the official package, review upgrade_preview and use the existing fingerprinted upgrade flow under user authorization.

Merge each contribution with history retained. Review synthetic host checks separately from real host behavior. Use local/base/remote byte comparisons to sync the accepted public sources into the original development directory, preserving any unrelated local edits and keeping private Qiming files out of the public repository.

Release v0.3.0 preview with four-language update notes and a clear user-facing version-check command. Verify public tests, nine OS/Python CI jobs, actual public installation/check, preserve-upgrade behavior and production site output.
