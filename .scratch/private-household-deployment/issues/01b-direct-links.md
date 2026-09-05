# 01b: Reload bookmarked pages without breaking API errors

**What to build:** A household member can open or reload a bookmarked recipe or inventory page while API failures and missing assets retain correct responses.

**Blocked by:** 01a: Open and use the built app at its entry address.

**Status:** ready-for-agent

- [ ] Add frontend route fallback so direct loading and reloading a nested route, including the login route, works with the production build.

- [ ] Give API routes precedence. Unknown API requests preserve their HTTP status and API response format, and missing static assets return a missing-resource response rather than the SPA document.

- [ ] Through the production browser harness, test direct nested navigation, session hydration after reload, and invalid-session redirection; verify unknown API and missing-asset responses via the same origin.

- [ ] Keep static-file confinement tests green and add focused boundary/traversal cases for the new fallback. Document direct-link behavior as part of the serving instructions.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

