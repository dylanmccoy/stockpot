# 03b: Recover one forgotten household password

**What to build:** The owner can restore a member's account access without changing other accounts or household records.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Provide a local recovery operation with an explicit target database, using existing password hashing and revoking all sessions for the recovered account.

- [ ] Verify old credentials and old sessions fail, fresh login with the replacement password succeeds, and other accounts and household records are preserved.

- [ ] Unknown accounts and invalid inputs fail without creating accounts or mutating unrelated data. Keep passwords and tokens out of logs and setup artifacts.

- [ ] Test through existing real authentication APIs and the application factory using disposable data; document the operator procedure. Existing account setup is sufficient, so 03a is not a blocker.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

