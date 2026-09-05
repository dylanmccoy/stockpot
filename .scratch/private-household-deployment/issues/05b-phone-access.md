# 05b: Connect a household phone over cellular

**What to build:** A household member can enroll their phone, connect Tailscale, and use the private app while away from home.

**Blocked by:** 05a: Reach the app from a permitted private-network client.

**Status:** ready-for-agent

- [ ] Provide household phone onboarding for iOS and Android, distinguishing private-network connection from application login and explaining that internet connectivity is required.

- [ ] On an actual household phone, turn off Wi-Fi, connect through Tailscale, open the private HTTPS address, log in, read a recipe, save a change, and reload a nested route.

- [ ] Verify the change from another permitted client and exercise disconnect/reconnect followed by another successful read. Retain the existing session and error behavior.

- [ ] Record the actual mobile platform tested and any unperformed device checks. This is mobile onboarding and network commissioning of the existing browser app, not a native app or offline feature.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

