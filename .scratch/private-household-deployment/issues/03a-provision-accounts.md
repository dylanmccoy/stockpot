# 03a: Provision household logins and close registration

**What to build:** The owner can add intended household accounts, then operate with registration closed and equal access for those accounts.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Provide a controlled local provisioning procedure using existing registration behavior and an explicit target configuration; close the registration window afterward.

- [ ] Verify two individual accounts can read and edit the same household records, and a further direct registration attempt is refused after closure.

- [ ] Use existing API and auth-test seams with disposable data. Verify the normal frontend build does not advertise signup using existing frontend coverage.

- [ ] Document the provisioning and closure steps without logging credentials or adding roles, memberships, or a new account UI.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

