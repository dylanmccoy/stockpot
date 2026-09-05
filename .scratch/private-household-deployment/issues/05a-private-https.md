# 05a: Reach the app from a permitted private-network client

**What to build:** A household member can use one private HTTPS address from a permitted computer, while other devices cannot reach the deployment.

**Blocked by:** 04a: Install the WSL app with existing household data; 01b: Reload bookmarked pages without breaking API errors.

**Status:** ready-for-agent

- [ ] Inspect Windows-to-WSL localhost connectivity and configure Windows Tailscale Serve to proxy the local production origin. Configure persistent Serve and unattended Tailscale operation.

- [ ] Restrict access to intended household identities/devices from the start. Keep application listeners local; do not enable Funnel, public port forwarding, or a LAN/public bypass.

- [ ] From a permitted client, verify valid HTTPS, login, read/write, and direct-link reload. Verify rejected unauthenticated API access, closed registration, and inability to connect from outside the permitted private network.

- [ ] Verify recovery after restarting Tailscale with the app running. Supply repeatable setup and connectivity diagnostics, and record actual-host results.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

