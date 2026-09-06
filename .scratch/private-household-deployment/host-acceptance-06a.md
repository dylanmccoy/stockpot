# 06a — actual-host acceptance results

Ticket: `issues/06a-process-supervision.md` — restart a failed app inside a
running WSL distribution (`deploy/supervise.sh`).

Linux CI proves the mechanism deterministically (`backend/tests/test_deploy.py`,
the `test_supervise_*` cases). The checks below need the real Windows/WSL host —
the actual WSL distribution, the app started with no interactive shell attached,
and a real process kill — and are **not** satisfied by CI. Fill in
`Result` / `Date` / `By` / `Notes` on the target machine and commit this file.

Runbook: README "Operating the server" #15. Tool: `deploy/supervise.sh`.

Scope: this slice supervises the **app process only**. Keeping the WSL
distribution alive after terminals close is ticket 06b; starting it after a
Windows boot without an interactive login is 06c. Those are separate acceptance
files.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution | _pending_ |
| `RECIPE_DEPLOY_CHECKOUT` | _pending_ |
| `RECIPE_DEPLOY_PORT` | _pending_ |
| `RECIPE_DEPLOY_DATA_DIR` | _pending_ |
| `RECIPE_DEPLOY_SUPERVISE_INTERVAL` (if not default 3) | _pending_ |
| `RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX` (if not default 60) | _pending_ |
| How `supervise.sh` is launched on the host (shell / systemd unit / other) | _pending_ |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `deploy/supervise.sh start` on the installed deployment | exit 0; `deploy/control.sh status` healthy on `127.0.0.1:<port>` | PENDING | | | |
| 2 | `deploy/supervise.sh status` | supervisor running; `app restarts : 0`; then the `control.sh status` block | PENDING | | | |
| 3 | Terminate the app process while WSL stays up (`kill $(cat $RECIPE_DEPLOY_DATA_DIR/run/recipe.pid)`) | within a few seconds the app is running again on a new pid; `GET /api/health` returns; `supervise.sh status` shows `app restarts : 1` and a last-restart time | PENDING | | | |
| 4 | `kill -9` the app process group (hard crash) | same as #3 — supervisor restarts it | PENDING | | | |
| 5 | Local browser / API access after the restart | app loads; a household account signs in; a previously saved recipe/inventory record is readable and a new write persists on reload | PENDING | | | |
| 6 | Run `deploy/install.sh` again, then `deploy/supervise.sh start` again, with the deployment already up | neither creates a second app or a second supervisor; `supervise.sh start` reports "already supervising" / "supervising it in place"; exactly one uvicorn on `<port>` | PENDING | | | |
| 7 | `deploy/supervise.sh stop` | watch loop stops **and** the app stops; `deploy/control.sh status` exits 3 (stopped) | PENDING | | | |
| 8 | Supervisor running with no interactive shell attached (close the terminal it was started from, or start it via the host's boot mechanism) then repeat #3 | the app still restarts — supervision does not depend on the launching shell staying open | PENDING | | | |
| 9 | Diagnostics are useful: inspect `RECIPE_DEPLOY_DATA_DIR/run/recipe-supervisor.log` and `recipe.log` after a restart | supervisor log shows the detection + restart lines with timestamps; app log shows the app's own startup output; a connectivity / process / data fault is distinguishable | PENDING | | | |

## Result summary

- Target-host process-recovery result (checks 3–5, 8): _pending_
- Deviations from the documented behaviour (if any): _pending_

## Sign-off

- Commissioned by: _pending_
- Date: _pending_
