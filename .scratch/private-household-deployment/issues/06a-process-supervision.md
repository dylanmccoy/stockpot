# 06a: Restart a failed app inside a running WSL distribution

**What to build:** The app recovers from an application-process failure while its WSL distribution remains running.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** ready-for-agent

- [ ] Provide process supervision using the installed deployment configuration, with operator start/stop/status and useful application/startup diagnostics.

- [ ] Restart a terminated app process automatically and prevent duplicate instances on repeated setup or start attempts.

- [ ] While WSL is running, terminate the app, verify local browser/API access returns, and confirm previously saved records remain usable.

- [ ] Document that this slice supervises the app process only; independently maintaining WSL lifetime and starting after Windows boot follow separately. Record the target-host process-recovery result.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

