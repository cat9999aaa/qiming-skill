# Cross-device integration and version checks implementation plan

Goal: merge PR #1/#2 and publish v0.3.0 with read-only update discovery.
Architecture: preserve project-local instances; standard-library version/check_update helper behind existing JSON CLI, explicit official GitHub release lookup.
Spec: ../specs/2026-10-24-version-check-design.md

- [x] Merge both contribution heads locally, retain ancestry, run baseline tests and review independently.
- [ ] Test installed-versus-runtime version, semantic ordering/channel filtering, same-version source drift, offline/rate-limit errors, invalid metadata and byte-preserving read-only behavior.
- [ ] Implement qiming_core/updates.py and CLI/API entry points; link upgrade and English operational docs.
- [ ] Add public change notes, site update instructions and current release metadata in four locales; rebuild.
- [ ] Compare and synchronize approved public sources into development checkout without touching private records; run local/public checks and nine CI jobs.
- [ ] Review final changes, merge/publish GitHub, deploy and compare official site, test public install/update command and preserve-upgrade the owning instance.
- [ ] Record sources, tests, remaining host limits and handoff through the owning instance.

Review focus: no network in version; no path/credential leakage into HTTP; unknown cannot become up-to-date; prerelease channels remain explicit; old instance versions stay distinguishable from the downloaded seed; user-edited rules survive upgrade.
