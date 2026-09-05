# 04a: Install the WSL app with existing household data

**What to build:** The owner can install and run the production app in WSL while retaining their existing household records.

**Blocked by:** 01a: Open and use the built app at its entry address; 02a: Take a usable live SQLite snapshot.

**Status:** ready-for-agent

- [ ] Provide repeatable installation and local start/stop/status controls with explicit WSL distribution, executables, build location, loopback port, and absolute database location.

- [ ] Keep SQLite on persistent WSL Linux storage outside the checkout and disposable builds. Use the snapshot operation to preserve existing data before adopting it; re-running setup must not overwrite an existing deployment database.

- [ ] Run the installed production app, log in, and read/write records. Verify app restart and invocation from another working directory still use the same database.

- [ ] Exercise installation and data adoption with disposable data through the production browser harness; document target inputs, diagnostics, and manual process controls. Automatic supervision is a later feature.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

