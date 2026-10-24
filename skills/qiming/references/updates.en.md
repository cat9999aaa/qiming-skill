# Version and update checks

Use when the user asks about versions/updates or is preparing an upgrade. Ordinary sessions do not need automatic network checks.

```sh
python3 .qiming/qiming-user/scripts/qiming.py version --workspace-manifest .qiming/workspace.json
python3 .qiming/qiming-user/scripts/qiming.py check-update --workspace-manifest .qiming/workspace.json
```

Use py -3 on Windows. If an old instance lacks these commands, run the new package's scripts/qiming.py against the original workspace manifest; do not reinitialize. The short CLI can discover the nearest manifest within existing project boundaries. An explicit authoritative manifest is preferred.

version is offline and distinguishes the executing package from the project's installed version/source commit/fingerprint and preserved local resources. A reported seed version does not certify every locally customized file. package_source_differs is true only for equal versions with two known differing source commits, otherwise unknown remains null. Without a selected instance only the package is reported.

check-update explicitly reads the official GitHub releases endpoint (up to the 100 most recent releases, bounded response size, 10-second network timeout). It sends no local paths, records, credentials or IDs, and uses no access token. The default channel comes from package release_channel; this prerelease uses preview. --channel stable excludes prereleases; preview includes both; drafts never count. Valid semantic versions are compared.

result contains current_version, latest (version/release URL/date), channel, update_available, comparison, checked_at. comparison is update_available/current/ahead/unknown. Network/rate-limit errors, malformed responses, no eligible release or an unknown local version keep update_available null and produce diagnostics, never a false current claim. stdout remains one JSON response; stderr gives readable Chinese guidance.

The qiming.tool/1 API exposes version and check_update. workspace_manifest is optional; args.channel is optional for check_update. API calls without a manifest inspect only the executing package. Checks are read-only; they do not download or execute updates. Under user authorization, obtain the official package, inspect upgrade_preview, then apply its exact reviewed plan_id, preserving local rules, profile and member IDs. Source commit metadata and the final release commit are distinct; see the Release for provenance. Host discovery is not a real-session compatibility test.
