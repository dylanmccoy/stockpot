# 06c: Restore private access after Windows boot without login

**What to build:** The private household app returns after a full Windows reboot without the owner signing in or opening a terminal.

**Blocked by:** 06b: Keep WSL serving after terminals close; 05a: Reach the app from a permitted private-network client.

**Status:** ready-for-agent

- [ ] Add repeatable Windows boot startup for the intended user/distribution and existing WSL lifetime arrangement. Ensure private Tailscale ingress also runs unattended.

- [ ] On the target machine, reboot Windows and verify the private HTTPS origin becomes usable from a permitted client before interactive login.

- [ ] Log in to the app, read previously saved records, and save a new change. Verify retries/repeated setup do not launch duplicate instances.

- [ ] Record actual reboot results and document failure diagnosis and manual recovery using existing controls. CI or mocked task configuration cannot substitute for this acceptance check.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

