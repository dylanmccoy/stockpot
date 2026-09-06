# 06b: Keep WSL serving after terminals close

**What to build:** The owner can close the IDE and terminals without losing the app, and the app returns after WSL is restarted.

**Blocked by:** 06a: Restart a failed app inside a running WSL distribution.

**Status:** in-review

- [x] Provide a Windows-side lifetime arrangement for the intended WSL workload, independent of an interactive development shell. Do not rely on a WSL systemd service alone to keep the distribution alive. — `deploy/wsl-keeper.sh run` (the long-lived foreground process) + `deploy/windows/register-keeper-task.ps1` (Task Scheduler task running it via `wsl.exe`, AtLogOn + 5-min repetition, restart-on-failure, S4U). The runbook states outright that a WSL systemd service cannot hold the distro open.

- [x] Recover the app after controlled WSL termination/restart and avoid duplicate keeper or app instances on repeated setup. — keeper re-enters WSL via the task's restart/repetition after `wsl --shutdown`; stale pidfiles from an abrupt stop are rejected by the existing recycled-pid guard; `run` refuses a second keeper, `supervise.sh` a second supervisor, `control.sh` a second app; `-Force` keeps task registration idempotent. Deterministic coverage in `backend/tests/test_deploy.py::test_keeper_*`. Real `wsl --shutdown` recovery is host-acceptance-06b.md checks 7–8.

- [ ] On the actual host, close the IDE and all development terminals, leave the machine idle while awake, and verify local application access and saved data remain available. Repeat after restarting WSL. — host-only; checklist in `host-acceptance-06b.md` (checks 4, 7–8). Not runnable in CI.

- [x] Document lifetime controls and diagnostics, and configure/document power behavior appropriate for expected availability. Boot before interactive Windows login is handled by 06c. — README runbook 17 (controls, diagnostics table, diagnosis list, `powercfg` guidance), `deploy/deploy.env.example` keeper section, `docs/deployment.md` item 3. Applying the power settings on the host is host-acceptance-06b.md checks 11–12. 06c owns the boot trigger.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-06b`, worktree
  `.claude/worktrees/private-household-deployment-06b`.

- **`deploy/wsl-keeper.sh`** (new) — the WSL-lifetime layer above
  `deploy/supervise.sh` (06a). One long-lived foreground process:
  - `run` — a Windows Scheduled Task launches this via
    `wsl.exe -d <distro> -- bash <checkout>/deploy/wsl-keeper.sh run`. While it
    runs the distribution stays up. It starts `supervise.sh` if none is
    running (adopting an app the operator started by hand per runbook 8), and
    re-launches it on the next heartbeat (`RECIPE_DEPLOY_KEEPER_HEARTBEAT`,
    default 30s) if it disappears. Refuses a second keeper (own pidfile
    `recipe-keeper.pid`, written under `noclobber`).
  - `stop` / `SIGTERM` — stops the keeper, the supervisor, and the app together
    (runbook 17 supersedes 16 — the keeper owns the whole lifecycle), exits 0.
  - `status` — keeper state + keeper-log tail, then `supervise.sh status`
    (its exit 3 = app stopped is propagated).
- **`deploy/windows/register-keeper-task.ps1`** (new) — register/unregister the
  Task Scheduler task. Principal S4U (no stored password); **two natively-built
  triggers** — AtLogOn + a `-Once` trigger repeating every `-RepetitionMinutes`
  (default 5) indefinitely (the post-`wsl --shutdown` recovery path while logged
  in); `ExecutionTimeLimit` 0; restart-on-failure 1 min × 999;
  `MultipleInstances IgnoreNew`; runs on battery / not idle-stopped; `-Force`
  for idempotency. Reads the task back and warns if the repetition did not
  attach. `-ConfigurePower` opt-in runs `powercfg /change *-ac 0`.
  `-Unregister` / `-ShowCommand` like the 07a backup task script. The
  AtStartup/boot trigger and unattended Tailscale are explicitly left to 06c.
- **`deploy/lib.sh`** — `RECIPE_DEPLOY_KEEPER_HEARTBEAT` (default 30), the
  keeper pidfile/log paths, and `deploy_keeper_pid_if_running` (mirrors the
  supervisor helper — same recycled/stale-pid guard, so an abrupt
  `wsl --shutdown` leaves nothing that blocks the next launch). Also extracted
  the timestamp + activity-log helpers `_deploy_ts` / `_deploy_log` here and
  pointed `supervise.sh`'s `_slog` at them (they were about to be a third copy).
- **`deploy/deploy.env.example`** — new "WSL lifetime keeper (ticket 06b)"
  section; the `RECIPE_DEPLOY_WSL_DISTRO` note now points at the keeper task.
- **Tests** — `backend/tests/test_deploy.py`, new `test_keeper_*` section (in
  the `backend` CI job, on the supervise port with a 1s heartbeat): `run` holds
  the app up and `SIGTERM` takes keeper+supervisor+app down together; a second
  `run` is refused and duplicates nothing; a hard-killed supervisor is
  re-launched on the next heartbeat and adopts the still-running app; `stop` is
  clean with nothing up. The `deploy_env` fixture teardown now stops the keeper
  before the supervisor before the app.
- **Docs** — README runbook renumber (the 07c "Recover from a scheduled
  snapshot" and 06a "WSL app process supervision" runbooks had *both* been
  numbered 15 on `main` — a merge collision between #93 and #95); now 15 =
  recover-from-snapshot, 16 = supervision, **17 = this** ("Keep WSL serving
  after terminals close"); intro count "Fifteen" → "Seventeen"; runbook 8's and
  16's forward-refs fixed; `docs/deployment.md` item 3 extended.
- **Host acceptance** —
  `.scratch/private-household-deployment/host-acceptance-06b.md` (new). Not run:
  no Windows/WSL host in this session. Terminals-closed access, real
  `wsl --shutdown` recovery, no-duplicate-on-repeat, and host power behaviour
  (checks 4, 6–8, 11–12) are the actual-host gate.

- `cd backend && uv run pytest` green (full suite, 903 + 4 new); `shellcheck -x
  deploy/{wsl-keeper,supervise,lib}.sh` clean.

### Review findings actioned (`/code-review`, Standards + Spec)

- **`wsl-keeper.sh stop` no longer contradicts the runbook.** It used to try to
  spare an *adopted* supervisor on shutdown while the doc promised the same and
  the unconditional `supervise.sh stop` sweep killed it anyway. Dropped the
  `_keeper_owns_supervisor` bookkeeping: the keeper owns the whole lifecycle,
  every stop path brings supervisor + app down, and the runbook now says
  "runbook 17 supersedes runbook 16".
- **Keeper pidfile write hardened.** `_keeper_loop` writes it under
  `set -o noclobber` and re-checks for a live peer on a clash, closing the
  TOCTOU between the `_run` guard and the write.
- **PowerShell triggers made version-robust.** Replaced the
  `$logon.Repetition = $throwaway.Repetition` copy (inconsistent across
  PowerShell versions) with two natively-built triggers, and added a
  post-registration read-back that warns if no repetition interval attached
  (spec item 6: inspect the host before trusting exact task settings).
- **Power behaviour is now "configure", not only "document".** New opt-in
  `-ConfigurePower` switch on the PS1 runs `powercfg /change {standby,hibernate}-timeout-ac 0`;
  the runbook documents it and the by-hand form.
- **Duplicated log helpers pulled into `lib.sh`.** `_deploy_ts` / `_deploy_log`
  now live there; `supervise.sh` `_slog` and the keeper's `_klog` are one-line
  wrappers. Magic `300` in the keeper's "ok"-line cadence is a named
  `KEEPER_OK_LOG_EVERY_S`.

Deliberately not changed:

- **`_stop` / `_status` / stale-pidfile blocks still mirror `supervise.sh`'s.**
  The repo already tolerates this shape between `control.sh` and `supervise.sh`;
  a generic "stop a pidfile-managed process" helper would be a cross-ticket
  refactor of 04a/06a code beyond this slice.
- **`register-keeper-task.ps1` still repeats ~40 lines of boilerplate with
  `register-backup-task.ps1`.** No PowerShell dot-source library precedent in
  the repo; a two-file logon-type edit is cheaper than introducing one for two
  scripts. Revisit if a third task script lands.
- **Post-`wsl --shutdown` recovery and the `wsl.exe` non-zero-exit assumption
  stay host-gated.** CI cannot drive Task Scheduler; the read-back warning plus
  host-acceptance checks 1–2 and 7–8 are the verification.
- **`_keeper_run` test context manager vs the sibling inline `try/finally`.**
  Reused 3×; the context manager is the cleaner idiom and the reviewer agreed.

