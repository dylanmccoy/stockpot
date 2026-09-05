# 04b: Deploy a schema-preserving application update

**What to build:** The owner can deploy a new application build while continuing to use the same household database.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** ready-for-agent

- [ ] Provide a repeatable update procedure that prepares and validates a build before switching the running deployment, takes a pre-maintenance snapshot, and restarts against the explicit persistent database.

- [ ] A failed build or preparation must leave the current usable deployment and data intact. Do not reset the database or run schema-changing upgrades under this procedure.

- [ ] Through disposable deployment data and the production browser, verify identifiable records survive a replacement build and subsequent writes persist.

- [ ] Document update, stop/start, snapshot, and health checks. Any future schema change requires a data-preserving migration before installation; the convenience operation to return to an older build follows in 04c.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

