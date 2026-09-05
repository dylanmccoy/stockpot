# 02b: Recover a snapshot into a separate database

**What to build:** The owner can rehearse recovery in a separate database and sign in to inspect the recovered household without changing live data.

**Blocked by:** 02a: Take a usable live SQLite snapshot.

**Status:** ready-for-agent

- [ ] Validate a selected snapshot and restore into a new explicit target, refusing an already existing target in this slice. Leave the live database and original snapshot unchanged.

- [ ] Invalidate sessions in the recovered database before it is served; a fresh login succeeds and restored tokens are refused.

- [ ] Take a snapshot, make a distinguishable later change, recover into a new disposable target, and use a fresh factory-built app to verify the snapshot's records and absence of the later change.

- [ ] Reject missing or invalid snapshots without exposing an apparently successful recovered database. Document isolated rehearsal and put these real restore checks in CI.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

