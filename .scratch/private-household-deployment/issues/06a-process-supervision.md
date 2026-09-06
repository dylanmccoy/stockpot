# 06a: Restart a failed app inside a running WSL distribution

**What to build:** The app recovers from an application-process failure while its WSL distribution remains running.

**Blocked by:** 04a: Install the WSL app with existing household data.

**Status:** in-review

- [x] Provide process supervision using the installed deployment configuration, with operator start/stop/status and useful application/startup diagnostics.

- [x] Restart a terminated app process automatically and prevent duplicate instances on repeated setup or start attempts.

- [x] While WSL is running, terminate the app, verify local browser/API access returns, and confirm previously saved records remain usable.
  <br>`test_supervise_restarts_a_terminated_app_and_records_stay_usable`: a
  signed-in member is using the app through the origin; the app process group is
  `SIGKILL`ed; the supervisor brings it back on a new pid; the same session then
  reads the pre-existing recipe and writes a new one through the HTTP API, and
  the write is confirmed in the one explicit database. Real-host browser
  verification is checks 3–5 of `host-acceptance-06a.md`.

- [x] Document that this slice supervises the app process only; independently maintaining WSL lifetime and starting after Windows boot follow separately. Record the target-host process-recovery result.
  <br>README runbook 15 and every code comment scope this to the app process
  (06b = WSL lifetime, 06c = start-on-boot). Target-host result is recorded in
  `.scratch/private-household-deployment/host-acceptance-06a.md` (PENDING until
  run on the Windows/WSL machine — Linux CI is not evidence of it).

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-06a`, worktree
  `.claude/worktrees/private-household-deployment-06a`.

- **`deploy/supervise.sh`** (new) — a watch loop around `deploy/control.sh`:
  - `start` — start the app if it is not already up, then launch the loop in
    the background (`setsid`, its own pidfile `recipe-supervisor.pid`). Refuses
    a second supervisor; adopts an already-running app instead of starting a
    duplicate.
  - `stop` — stop the loop, then the app (a bare `control.sh stop` would be
    undone by the supervisor).
  - `restart`, `status` (supervisor state + running restart count + last-restart
    time + supervisor-log tail, then `control.sh status`; its exit 3 = app
    stopped is propagated).
  - `run` — the loop in the FOREGROUND for a systemd unit (06b) or a test
    harness; `SIGTERM`/`SIGINT` stops the app and exits 0.
  - The loop restarts a gone app via `control.sh start` (same one explicit
    absolute `RECIPE_DATABASE_URL`); a failed restart is logged and retried with
    a doubling delay capped at `RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX`, never
    giving up. The in-flight `control.sh` child is signal-interruptible so a
    stop mid-restart leaves nothing orphaned.

- **`deploy/lib.sh`** — added `RECIPE_DEPLOY_SUPERVISE_INTERVAL` (default 3) and
  `RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX` (default 60), the supervisor
  pidfile/log/state paths, and `deploy_supervisor_pid_if_running` (mirror of
  `deploy_pid_if_running`, with the same recycled-pid guard).

- **`deploy/deploy.env.example`** — documents the two supervision knobs.

- **Tests** — `backend/tests/test_deploy.py`, new `test_supervise_*` section (in
  the `backend` CI job): terminated app is restarted and records stay usable; a
  second `start` is refused and never duplicates the app; an already-running app
  is adopted without a restart; `stop` with nothing running is clean; `run`
  supervises until signalled and stops the app with it; a failed restart is
  retried and then recovers. The `deploy_env` fixture teardown now stops the
  supervisor before the app.

- **Docs** — root `README.md` runbook 15 ("WSL app process supervision");
  runbook 8's "un-supervised" note now points at it; `docs/deployment.md`
  outline item 3; intro count → `Fifteen`.

- **Host acceptance** — `.scratch/private-household-deployment/host-acceptance-06a.md`
  (new). Not run: no Windows/WSL host in this session. Real-host process
  recovery (checks 3–5, 8) is still PENDING per the spec's actual-host gate.

- Rebased onto `main` after 05b/02c/07a merged (README runbook renumber, one
  `test_deploy.py` append conflict — both new sections kept).

### Review findings actioned (`/code-review`, Standards + Spec)

- **Diagnostics no longer lost in the backgrounded case.** The per-restart
  app-log excerpt was written to the loop's stderr, which `start` sends to
  `/dev/null`; it now appends to the supervisor log like every other line.
- **`RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX` wording corrected + made true.** It
  was described as backing off "between consecutive failed restarts" but a
  healthy-then-crashing app restarted every interval forever. The loop now also
  damps a crash loop: an app that exits again within the cap window grows the
  same doubling delay, reset once it holds. A one-off crash still restarts at
  once.
- **`deploy_supervisor_pid_if_running` / `deploy_pid_if_running` de-duplicated**
  behind `_deploy_pid_from_file <pidfile> <marker>` in `lib.sh`.
- **Supervisor pidfile has one writer.** `start` no longer pre-writes it; the
  spawned loop owns it (via the shared `_own_and_watch`), closing the
  child-`_deploy_die` → stale-recreate window.
- **`_supervised_call` bare calls now `|| true`** so a non-signal non-zero from
  `wait` can't silently abort the loop.
- **Tests hardened:** the supervise cases run on their own port (8763), so a
  detached watch loop can't collide with the other `test_deploy.py` cases or a
  parallel worktree on the shared `PORT`; the fragile system-wide
  `/proc`-scan duplicate assertion is replaced with a tmp-scoped pidfile check;
  `_wait_for` treats a raising predicate as not-ready; and the restart test now
  signs in and reads/writes through the deployed origin (not just a direct
  SQLite read), and confirms the session survives the supervised restart.

Deliberately not changed:

- **`run` subcommand keeps its "systemd unit (06b)" framing.** No unit file is
  added here; `run` is the foreground seam a test harness (and later 06b) needs,
  and is exercised as such. It stays in lane.
- **Repeated `install.sh` against a live supervised deployment** has no new
  automated case — `install.sh` starts nothing, its non-overwrite guarantees
  are already covered by 04a's tests, and the supervision duplicate guard
  (second `supervise.sh start`) is tested. Host acceptance check 6 covers the
  end-to-end.
- **Browser-origin (Playwright) coverage** — the mechanism is driven through
  the real HTTP origin in `test_deploy.py`; a dedicated Playwright project for a
  kill-and-recover flow would fight the detached supervisor's process-group
  lifetime (the `deployment` project uses `control.sh run` foreground for
  exactly that reason). Real browser recovery is host-acceptance checks 3–5.
