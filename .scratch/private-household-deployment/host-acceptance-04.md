# 04 — actual-host acceptance results

Ticket: `issues/04a-install-persistent-app.md`, `04b-update-app.md`,
`04c-return-compatible-build.md` — WSL install + data adoption, schema-preserving
update, and rollback to a previous build.

Linux CI proves the deterministic half only (`backend/tests/test_deploy.py`):
install adoption / non-overwrite, the start/stop/status lifecycle, the update
switch/snapshot/abort logic, and the rollback select/validate/snapshot/abort
logic, all against disposable data. The checks below need the real Windows/WSL
host and the real household database; they are **not** satisfied by CI. Fill
in `Result` / `Date` / `By` / `Notes` on the target machine and commit this
file.

Runbook: README "Operating the server" #8 (install), #9 (update), #10
(rollback). Tools: `deploy/install.sh`, `deploy/control.sh`, `deploy/update.sh`,
`deploy/rollback.sh`.

## Host inputs (record actuals — do not assume dev values)

| Input | Value on target host |
| --- | --- |
| WSL distribution | ubuntu |
| `RECIPE_DEPLOY_CHECKOUT` |  |
| `RECIPE_DEPLOY_PORT` |  |
| `RECIPE_DEPLOY_DATA_DIR` |  |
| `RECIPE_DEPLOY_DB_FILE` |  |
| Source database adopted from (`--adopt-from`, if not `backend/recipe.db`) | _pending_ |
| `RECIPE_DEPLOY_BUILD_ARCHIVE` / `RECIPE_DEPLOY_BUILD_KEEP` |  |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `deploy/install.sh` on first run | builds frontend, creates persistent dirs, adopts the source database via a live snapshot into `RECIPE_DEPLOY_DATA_DIR` | PASS | 2026-09-22 | dylan |  |
| 2 | `deploy/control.sh start` / `status` | healthy on `127.0.0.1:<port>`; log in with a household account; read and write a recipe | PASS | 2026-09-22 | dylan | GET /api/health OK |
| 3 | `deploy/control.sh stop` / `start` again, and start from a different working directory | `control.sh status` shows the same absolute `RECIPE_DATABASE_URL` every time — no second database created | PASS | 2026-09-22 | dylan |  |
| 4 | Re-run `deploy/install.sh` with the deployment database already present | existing database left untouched; no overwrite; the dev reset (runbook 3) is never invoked | PASS | 2026-09-22 | dylan |  |
| 5 | `deploy/update.sh` (schema-preserving) | pre-maintenance snapshot taken; staged build validated before anything is touched; switch + restart against the same database; records from before the update are still there and a new write after it persists | PASS | 2026-09-22 | dylan |  |
| 6 | Induce a failed update (bad staged build or validation failure) | current deployment and its data are completely untouched — nothing stopped, switched, or snapshotted | PASS | 2026-09-22 | dylan | deploy: --staging-dir /tmp/broken-build has no index.html — nothing prepared, current deployment left intact |
| 7 | `deploy/rollback.sh --list`, then `deploy/rollback.sh` (or `--to <build>`) | returns to the selected build; pre-maintenance snapshot taken; household data untouched; records intact | PASS | 2026-09-22 | dylan |  |
| 8 | `deploy/rollback.sh --to <missing-or-bad-build>` | validation refuses before stopping anything; running deployment and its data completely intact | PASS | 2026-09-22 | dylan | deploy: no build 'nothere' — not a build directory and not a name in /home/dylan/.local/share/recipe-app/builds (try deploy/rollback.sh --list); nothing switched, current deployment and data intact |
| 9 | `deploy/control.sh status` after the above, and `RECIPE_DEPLOY_DATA_DIR/run/recipe.log` for any failure | resolved config, DB path, and health all correct; log has enough detail to diagnose a failed start | PASS | 2026-09-22 | dylan |  |

## Sign-off

- Commissioned by: dylan
- Date: 2026-09-22
- Deviations from the documented topology (if any): none
