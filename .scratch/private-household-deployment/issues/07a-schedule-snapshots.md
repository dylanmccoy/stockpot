# 07a: Create daily snapshots without an open terminal

**What to build:** The owner receives automatic daily local snapshots even when no development terminal or app process is running.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** ready-for-agent

- [ ] Schedule the existing real backup operation at least daily for the explicit deployed database and local backup destination. The task can invoke the intended WSL distribution for a bounded backup job independently of app supervision.

- [ ] Exercise the actual scheduler invocation while the app is available and verify a usable timestamped snapshot; also verify a run with the app stopped.

- [ ] Verify the configured task remains available and runs after a Windows reboot without interactive login. Preserve earlier valid snapshots on failure and record the real invocation result.

- [ ] Document schedule, destination, local permissions, and execution diagnostics. Backup freshness reporting and retention controls are added in 07b; automatic app boot is not a blocker.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

