# 02a: Take a usable live SQLite snapshot

**What to build:** The owner can create a consistent timestamped local snapshot without interrupting normal app use.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Provide a backup operation with explicit source and destination inputs using SQLite's online backup facility. Store snapshots outside the checkout and served assets with operator-only access.

- [ ] Publish a completed snapshot only after success. Missing sources, unwritable destinations, and interrupted writes report failure without creating a misleading successful backup or damaging earlier snapshots.

- [ ] Seed disposable file-backed SQLite through real APIs, run the real backup while the app is available, then open an isolated copy of the snapshot with the existing app factory and verify representative records through fresh login and API reads.

- [ ] Put deterministic backup checks in CI and document the backup command, result, and destination. Scheduling and replacement of an existing database are outside this slice.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

