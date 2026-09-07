# 08: Commission the deployment on the target Windows/WSL host

**What to build:** The owner runs every remaining manual host action on the
real always-on machine and records the results, turning the CI-green build
into a verified live household deployment.

**Blocked by:** 03a, 03b, 04a, 04b, 04c, 05a, 05b, 06a, 06b, 06c, 07a, 07b, 07c
(every implementation slice — this is their shared actual-host acceptance gate).

**Status:** ready-for-human

This ticket does not add runtime code. It is the spec's separate completion
gate — *"Treat real-host acceptance as a separate completion gate; Linux CI
success does not substitute for it"* (spec, Testing Decisions) — collecting the
manual host actions that are still `PENDING` across the feature. Nothing here is
runnable in CI: each item needs the real Windows machine, the real tailnet, a
household phone, Task Scheduler, host power settings, or a full reboot.

## Where the pending actions live

| Source | Commissions | Record sheet | Rows |
| --- | --- | --- | --- |
| 04a | Runbook 8 — WSL install, persistent DB layout, one-time data adoption, `control.sh` run/diagnostics | **needs `host-acceptance-04.md`** (create it) | — |
| 04b | Runbook 9 — schema-preserving update on the host | **needs `host-acceptance-04.md`** | — |
| 04c | Runbook 10 — return to a previous compatible build | **needs `host-acceptance-04.md`** | — |
| 05a | Runbook 11 — Windows→WSL localhost, Tailscale Serve, `net-check.sh`, tailnet ACL, HTTPS cert, Tailscale-restart recovery, unattended Tailscale | `host-acceptance-05a.md` | #1–#14 |
| 05b | Runbook 12 — phone enrol, cellular-only HTTPS, login/read/write, disconnect/reconnect, session behaviour, platform coverage | `host-acceptance-05b.md` | #1–#12 |
| 06a | Runbook 15/16 — `supervise.sh`, app-process kill + restart, no-shell supervision, idempotent re-install, diagnostics | `host-acceptance-06a.md` | #1–#9 |
| 06b | Runbook 17 — keeper Scheduled Task, close IDE/terminals + idle, kill supervisor, `wsl --shutdown` recovery, no-duplicate, `powercfg`, sleep limitation | `host-acceptance-06b.md` | #1–#12 |
| 06c | Runbook 18 — at-boot trigger, full reboot with **no interactive login**, pre-login HTTPS + login/edit, off-tailnet, no-duplicate on logon trigger, failure rehearsal | `host-acceptance-06c.md` | #1–#14 |
| 07a | Runbook 14 — daily backup Scheduled Task, `Start-ScheduledTask` app-up and app-stopped, snapshot permissions, failure preserves prior, reboot-no-login run, bounded job | `host-acceptance-07a.md` | #1–#12 |
| 07b | Runbook 14 — `backup_status.py` OK/STALE, FAIL preserves prior, count retention prune, incomplete files not counted, undeletable-file exit 2, `control.sh status` lines | `host-acceptance-07b.md` | #1–#7 |
| 07c | Runbook 15 — **timed** one-day restore rehearsal from a real scheduled snapshot, verified through a real browser | `host-acceptance-07c.md` | #1–#12 |

03a / 03b (account provisioning, password recovery) have no host-only surface —
their runbooks 6 / 7 are exercised in CI against a real backend. Run them once on
the host while adopting real accounts, but they need no acceptance sheet.

## Canonical host inputs (record actuals once — never assume dev values)

Fill this in first; every record sheet repeats a subset of it.

| Input | Value on target host |
| --- | --- |
| Windows version / Task Scheduler version | _pending_ |
| Tailscale version (Windows) | _pending_ |
| WSL distribution | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` (path inside WSL) | _pending_ |
| `RECIPE_DEPLOY_PORT` (loopback app port) | _pending_ |
| `RECIPE_DEPLOY_HTTPS_PORT` | _pending_ |
| `RECIPE_DEPLOY_DATA_DIR` / `RECIPE_DEPLOY_RUNTIME_DIR` | _pending_ |
| `RECIPE_DEPLOY_DB_FILE` (explicit persistent DB, outside checkout + builds) | _pending_ |
| `RECIPE_DEPLOY_BACKUP_DIR` | _pending_ |
| `RECIPE_DEPLOY_TAILSCALE_BIN` | _pending_ |
| Tailnet HTTPS URL (`deploy/tailscale-serve.sh url`) | _pending_ |
| Principal `LogonType` for the WSL tasks (`S4U` / `Password`) | _pending_ |
| Host power plan + sleep/hibernate/lid-close settings | _pending_ |

## Acceptance criteria

- [ ] **Install + data (04).** Create `host-acceptance-04.md`; on the host run
      runbook 8 install, adopt the existing household database via a snapshot
      (setup does not overwrite an existing deployment DB, never runs the dev
      reset), start the app, log in, read/write, and confirm restart and a
      different working directory use the same explicit DB. Record inputs and
      diagnostics.

- [ ] **Update + rollback (04b/04c).** In `host-acceptance-04.md`, run runbook 9
      (schema-preserving update: pre-maintenance snapshot, validated build,
      records + subsequent writes survive) and runbook 10 (return to the prior
      compatible build; a bad selection leaves the running build and data
      intact). Records survive both.

- [ ] **Private ingress (05a).** Fill every row of `host-acceptance-05a.md`:
      Windows→WSL localhost reaches `/api/health`; `tailscale-serve.sh apply` +
      `net-check.sh` pass; the tailnet ACL admits only household
      identities/devices; a permitted browser gets valid HTTPS with no cert
      warning, logs in, reads/writes, and reloads a nested link; unauthenticated
      API is `401` and registration `403`; an off-tailnet device cannot reach it
      and no LAN/public listener bypasses the ingress; ingress self-recovers
      after a Tailscale restart; Tailscale runs unattended.

- [ ] **Phone over cellular (05b).** Fill `host-acceptance-05b.md` on a real
      household phone with Wi-Fi off: enrol Tailscale, open the HTTPS URL, log in
      with the member's own account, read a recipe, save a change that survives a
      reload, reload a nested link, cross-check the change from a second client,
      toggle Tailscale off/on, and confirm session/expiry/logout behaviour.
      Record the platform tested and any platform left unverified.

- [ ] **Process supervision (06a).** Fill `host-acceptance-06a.md`:
      `supervise.sh start`; kill the app (`SIGTERM` and `kill -9`) and see it
      restart within seconds with the app usable after; re-running `install.sh` /
      `supervise.sh start` creates no second app or supervisor; supervision
      survives closing the launching shell; `stop` takes the app down;
      supervisor/app logs distinguish a connectivity vs process vs data fault.

- [ ] **WSL lifetime (06b).** Fill `host-acceptance-06b.md`: register the keeper
      Scheduled Task; close the IDE and every terminal, idle while awake, and
      confirm access + data from a permitted device; kill the supervisor and see
      the keeper relaunch it (app adopted, not duplicated); recover after a
      controlled `wsl --shutdown`; repeat setup with no duplicate keeper /
      supervisor / app; apply the `powercfg` settings and confirm the host stays
      awake; record the manual-sleep limitation as expected.

- [ ] **Windows boot without login (06c).** Fill `host-acceptance-06c.md`:
      register the at-boot trigger; full reboot and **stay at the sign-in
      screen**; from a permitted client the HTTPS origin is usable before any
      login — log in, edit, reload a nested route, confirm `401`/`403` and
      off-tailnet unreachability; after logging in, the keeper is healthy and the
      logon trigger duplicated nothing; rehearse the failure-diagnosis + manual
      recovery path from runbook 18.

- [ ] **Scheduled backups (07a).** Fill `host-acceptance-07a.md`: register the
      daily backup Scheduled Task; `Start-ScheduledTask` produces a usable
      timestamped snapshot with the app running and again with it stopped; open a
      snapshot in an isolated instance; snapshot dir `0700` / files `0600` owned
      by the operator and outside the served tree; an induced failure logs `FAIL`
      and preserves every earlier snapshot; a reboot without login still runs the
      job; the job is time-bounded.

- [ ] **Backup health + retention (07b).** Fill `host-acceptance-07b.md`:
      `backup_status.py` reports `OK` with a sub-24h latest success after a real
      run and `STALE` once it ages past the target; a `FAIL` run keeps the prior
      good snapshot as latest success; count-based prune keeps exactly
      `RECIPE_DEPLOY_BACKUP_KEEP` newest; incomplete/truncated files are never
      counted or pruned; an undeletable retained file makes `--prune` exit 2
      without dropping any snapshot; `control.sh status` shows the freshness and
      retention lines.

- [ ] **Timed recovery rehearsal (07c).** Fill `host-acceptance-07c.md`: start a
      clock; make a post-snapshot change; select the newest `ok` scheduled
      snapshot (< 24h old); `control.sh stop` → `restore.py --replace
      --preserve-dir` → `start` → `net-check.sh`; in a real browser on a
      permitted device a fresh login reads back pre-snapshot records, the
      post-snapshot change is absent, and a pre-restore session is `401`;
      registration is still `403`; earlier snapshots and the preserved
      pre-restore DB are intact; stop the clock and record elapsed time within
      one day. Sign off the accepted dependence (usable local snapshot +
      surviving disk) and the deferred scope (off-machine backups, disk-loss
      recovery).

- [ ] **Sign-off.** Every record sheet above has its `Result` / `Date` / `By` /
      `Notes` rows filled and its sign-off block completed, committed to
      `.scratch/private-household-deployment/`. Note any check that could not be
      run and why (e.g. no Android device), per the spec's "keep evidence of
      which checks were actually run".

## Delivery constraints

- This is `ready-for-human`: an agent cannot perform a Windows reboot, a phone
  enrolment, a tailnet ACL edit, or a power-setting change. An agent may prepare
  `host-acceptance-04.md` and tidy the record sheets, but the results must come
  from the target machine.

- Do not weaken or delete a check to make it pass. A check that reveals a
  defect in a shipped slice reopens that slice's ticket; it is not fixed by
  editing this one.

- Preserve the parent spec's scope: one private household, existing domain/API
  behaviour and schema, local SQLite and local backups. No public hosting,
  multi-household work, or authentication redesign enters during commissioning.

## Comments

- Run order on the host follows the blocker chain: **04** install/adopt →
  **05a** ingress → **05b** phone; **06a** supervisor → **06b** keeper →
  **06c** boot-before-login; **07a** backup task → **07b** freshness →
  **07c** timed restore rehearsal. 05a and 06c both need the ingress; 07c needs
  a real scheduled snapshot from 07a.

- Deterministic halves are already green in CI (`backend`, `deployment`,
  `deployment-update`, `production-smoke`, `integration`) via
  `backend/tests/test_deploy.py`, `backend/tests/test_backup_status.py`, and the
  Playwright `deployment` / `production` / `update` projects. This ticket adds
  no CI surface — it closes the acceptance gate CI cannot close.
