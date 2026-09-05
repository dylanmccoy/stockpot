# 02c: Restore an existing database safely while stopped

**What to build:** The owner can replace a stopped household database with a validated recovery copy while retaining the database they are replacing.

**Blocked by:** 02b: Recover a snapshot into a separate database.

**Status:** ready-for-agent

- [ ] Extend recovery to an explicitly selected existing database with application writers stopped. Preserve a valid copy of the current database before replacement and refuse to replace it if preservation or validation fails.

- [ ] Prepare and validate the recovered database, including restored-session invalidation, before replacing the configured target. Keep earlier snapshots and the original source untouched.

- [ ] Using test-owned processes and disposable data, stop writers, execute the recovery procedure, restart the app against the target, and verify recovered records through fresh login and API reads.

- [ ] Test invalid snapshot, failed preservation, and failed preparation paths without destroying the usable target. Document the stop/preserve/restore/restart procedure; deployment-specific process controls are supplied later.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

