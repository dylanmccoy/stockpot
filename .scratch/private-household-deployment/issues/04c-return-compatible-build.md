# 04c: Return to a previous compatible app build

**What to build:** The owner can recover from an unsuitable application update by selecting a previous compatible build without rolling back household records.

**Blocked by:** 04b: Deploy a schema-preserving application update.

**Status:** ready-for-agent

- [ ] Retain or identify a previous compatible build and provide an operator operation to switch the app back using the existing deployment controls and current persistent database.

- [ ] Validate the selected build and compatibility before switching; a missing or unusable selection must not destroy the running build or data.

- [ ] Create a record after an update, return to the previous compatible build, and verify that record remains readable and editable through the production browser.

- [ ] Document application-build rollback separately from snapshot data restore. Do not imply that an older build can safely run against an incompatible future schema.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

