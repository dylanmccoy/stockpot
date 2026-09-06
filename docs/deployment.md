# Private household deployment

The first deployment serves the owner's household from an existing Windows
machine running WSL. This outline records the 2026-09-05 deployment interview.
The [ready-for-agent deployment spec](../.scratch/private-household-deployment/spec.md)
owns implementation scope and acceptance checks.

## Agreed scope

- Household devices connect through Tailscale and open the app in a browser.
- Individual app logins have equal editing access. Registration is closed after
  provisioning; the operator handles forgotten passwords.
- Backups stay on the local disk for now. Up to 24 hours of lost changes and
  one day to restore service are acceptable when the host disk survives.
  Disk or machine loss is outside that recovery coverage.
- Current work serves one household. Multiple-household support and overlapping
  membership decisions wait until that expansion begins.
- Later hosting around $5/month is acceptable, with ordinary browser access
  that requires no private-network client. No cloud provider is selected.

## Implementation outline

1. Build the React frontend and serve it with the FastAPI API under one origin.
   Configure static assets, direct navigation to frontend routes, and `/api`
   routing. Run the backend as a production process without development reload.
2. Expose that origin through private Tailscale Serve with HTTPS. Keep backend
   services bound locally, restrict tailnet access to household devices, and
   retain application login. Funnel and router port forwarding are unnecessary
   for this private deployment. Delivered by `deploy/tailscale-serve.sh`
   (apply/status/url/reset) and `deploy/net-check.sh` (connectivity
   diagnostics); operator steps and the actual-host acceptance list are
   README "Operating the server" runbook 11. Household phone (iOS / Android)
   onboarding against that ingress is runbook 12.
3. Configure Windows/WSL startup, process restart, and host power settings for
   unattended operation. Verify behavior after a full Windows reboot; starting
   an app service inside an already running WSL session is not sufficient.
   App-process restart (only, while WSL stays up) is delivered by
   `deploy/supervise.sh` (start/stop/status/restart/run); operator steps and
   the actual-host recovery check are README "Operating the server" runbook 16.
   Keeping the WSL distribution alive independent of a development shell, and
   bringing it back after a controlled `wsl --shutdown`, is `deploy/wsl-keeper.sh`
   run unattended by a Windows Scheduled Task
   (`deploy/windows/register-keeper-task.ps1`) — README runbook 17, with host
   power settings paired alongside. Restoring the whole deployment — WSL, the
   app, and the private HTTPS ingress — after a full Windows reboot with nobody
   signed in is the same task's at-boot trigger plus `RECIPE_DEPLOY_KEEPER_SERVE`
   (the keeper re-asserts Tailscale Serve itself) — README runbook 18, with the
   reboot-without-login acceptance recorded in
   `.scratch/private-household-deployment/host-acceptance-06c.md`.
4. Keep SQLite on persistent WSL Linux storage, outside disposable build
   output. Carry existing household data forward and use an explicit database
   path. Establish data-preserving migrations before any schema-changing
   upgrade; deleting the database is not an upgrade procedure.
5. Schedule daily timestamped SQLite online backups into a dedicated local
   backup directory outside the application checkout. Record backup failures
   and document how to restore while the app is stopped. Test a restore into a
   separate database before relying on the procedure. The unattended job is
   `deploy/backup-run.sh` (one bounded online-backup snapshot, `ok`/`FAIL`
   line per run in the backup run log, earlier snapshots kept on failure),
   scheduled on the Windows host by `deploy/windows/register-backup-task.ps1`
   (daily, runs with no interactive logon). After a successful snapshot the job
   prunes to the newest `RECIPE_DEPLOY_BACKUP_KEEP` valid snapshots (count-based,
   so a failed run never evicts an earlier success), and
   `scripts/backup_status.py` reports the latest success, its age, and the
   latest failure — flagging no success or a success older than the 24-hour
   recovery target with a non-zero exit, no hosted alerting. Operator steps and
   actual-host acceptance lists are README "Operating the server" runbook 14.
   Restore steps are runbook 5 (isolated rehearsal) and runbook 13 (replace the
   live database in place, writers stopped); runbook 15 is the end-to-end
   recovery from a scheduled snapshot within the one-day target (ticket 07c),
   with a timed actual-host rehearsal as its acceptance gate.
6. Document account provisioning, operator password recovery, updates, logs,
   restart, and restore so ongoing use does not depend on a development shell.

Exact service configuration and paths follow inspection of the target Windows
and WSL installation during implementation.

The proposed network path is Windows Tailscale Serve proxying to a Windows
localhost port forwarded to the WSL app. This combines documented
[WSL localhost access](https://learn.microsoft.com/en-us/windows/wsl/networking)
and [Serve localhost proxying](https://tailscale.com/docs/reference/examples/serve);
the composition must be verified on the target host. Configure Tailscale
[Run Unattended](https://tailscale.com/docs/how-to/run-unattended) and persistent
Serve operation. WSL needs its own startup/lifetime arrangement:
[systemd services do not keep a WSL instance alive](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Acceptance checks

- A household phone on cellular data with Tailscale connected can sign in,
  read recipes, and save a change; a non-tailnet device cannot reach the service.
- Reloading a nested frontend URL works and API failures remain API responses.
- Registration is closed after provisioning; existing session/logout behavior
  works through the deployed HTTPS origin.
- Data survives app restart, deployment of an update, and Windows reboot.
- Service returns after Windows reboot without manually opening a development
  terminal; automatic restart works after an app-process failure.
- Access continues after closing terminals and the IDE and leaving the host
  idle. Verify recovery after WSL restart and Tailscale restart. Configure the
  host to stay awake during expected availability; it cannot serve while asleep.
- A scheduled backup is created and restored successfully into a separate
  test database; the documented recovery can be completed within one day.

## Later public deployment

Before exposing an ordinary internet-facing website, revisit authentication
hardening, abuse controls, off-machine backups, account recovery, and hosting
operations. Before admitting unrelated households to the same service, implement
household ownership, membership, scoped authorization and uniqueness rules,
and cross-household isolation tests. Opening registration alone is insufficient.
See [ADR 0001](adr/0001-independent-households.md) and the
[earlier deployment exploration](features.md#remote-deployment-exploration-informational-2026-09-04).
