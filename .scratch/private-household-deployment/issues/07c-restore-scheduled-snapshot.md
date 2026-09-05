# 07c: Recover the deployed app from a scheduled snapshot

**What to build:** The owner can follow a complete deployment recovery procedure and regain usable household data within one day.

**Blocked by:** 07a: Create daily snapshots without an open terminal; 02c: Restore an existing database safely while stopped.

**Status:** ready-for-agent

- [ ] Combine installed deployment controls and existing validated restore operations into a concrete runbook: select a successful scheduled snapshot, stop writers, preserve the target, restore, restart, and check app access.

- [ ] First execute the procedure against a separate deployment database and isolated production app instance, leaving live household data untouched.

- [ ] Use a scheduled snapshot no more than 24 hours old; verify representative restored records through a fresh browser login, rejection of restored old sessions, and absence of changes made after the snapshot.

- [ ] Record an actual-host recovery rehearsal completed within one day. State the accepted dependence on usable local snapshots and a surviving disk; keep off-machine backups and disk-loss recovery deferred.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

