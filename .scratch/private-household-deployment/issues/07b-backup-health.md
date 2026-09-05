# 07b: Report backup freshness and manage local retention

**What to build:** The owner can tell whether backups meet the 24-hour target and retain useful recovery points on local disk.

**Blocked by:** 07a: Create daily snapshots without an open terminal.

**Status:** ready-for-agent

- [ ] Expose the latest successful snapshot, its age, and the latest failed attempt through an operator-facing status command or report. Explicitly flag no successful backup or a success older than 24 hours.

- [ ] Provide a documented retention policy with explicit configuration. Retention must preserve required valid recovery points and must not remove earlier successes merely because a new backup failed.

- [ ] Exercise unwritable-destination, missed/overdue run, incomplete-snapshot, and failed-retention cases; the report must not count incomplete files as successful backups.

- [ ] Test deterministic status/retention behavior through the real operator operation with controlled disposable snapshots and time inputs, without requiring a live scheduled wait. Document diagnosis and retry; do not add a hosted alerting service.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

