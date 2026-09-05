# 01a: Open and use the built app at its entry address

**What to build:** A household member can open the production entry address, sign in, and save a recipe through the real API without development servers.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Add opt-in built-frontend serving through the existing application factory, preserving API-only operation. Use an explicit build location and report missing required build artifacts clearly.

- [ ] Serve the entry document and public build assets beside the existing API. Keep API success/error responses unchanged and confine file serving to the build assets from the first slice; never expose configuration, databases, or checkout contents.

- [ ] Extend the existing Playwright real-backend approach to boot this production mode with a disposable file-backed database and dedicated owned processes. Test login from the entry page, wrong-password rejection, logout, a recipe write/read, and refusal of unauthenticated API access.

- [ ] Seed accounts before closing registration for assertions; the normal frontend build offers no signup. Add the deterministic production smoke scenario to CI and document its local start command. Direct loading of client-side routes is delivered in 01b.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

