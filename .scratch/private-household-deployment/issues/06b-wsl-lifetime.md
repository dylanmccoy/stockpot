# 06b: Keep WSL serving after terminals close

**What to build:** The owner can close the IDE and terminals without losing the app, and the app returns after WSL is restarted.

**Blocked by:** 06a: Restart a failed app inside a running WSL distribution.

**Status:** ready-for-agent

- [ ] Provide a Windows-side lifetime arrangement for the intended WSL workload, independent of an interactive development shell. Do not rely on a WSL systemd service alone to keep the distribution alive.

- [ ] Recover the app after controlled WSL termination/restart and avoid duplicate keeper or app instances on repeated setup.

- [ ] On the actual host, close the IDE and all development terminals, leave the machine idle while awake, and verify local application access and saved data remain available. Repeat after restarting WSL.

- [ ] Document lifetime controls and diagnostics, and configure/document power behavior appropriate for expected availability. Boot before interactive Windows login is handled by 06c.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

