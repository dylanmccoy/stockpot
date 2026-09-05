# 04a: Install the WSL app with existing household data

**What to build:** The owner can install and run the production app in WSL while retaining their existing household records.

**Blocked by:** 01a: Open and use the built app at its entry address; 02a: Take a usable live SQLite snapshot.

**Status:** in-review

- [x] Provide repeatable installation and local start/stop/status controls with explicit WSL distribution, executables, build location, loopback port, and absolute database location.

- [x] Keep SQLite on persistent WSL Linux storage outside the checkout and disposable builds. Use the snapshot operation to preserve existing data before adopting it; re-running setup must not overwrite an existing deployment database.

- [x] Run the installed production app, log in, and read/write records. Verify app restart and invocation from another working directory still use the same database.

- [x] Exercise installation and data adoption with disposable data through the production browser harness; document target inputs, diagnostics, and manual process controls. Automatic supervision is a later feature.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-04a`, worktree
  `.claude/worktrees/private-household-deployment-04a`.

- **`deploy/`** — new operator surface, outside `backend/`/`frontend/`:
  - `deploy/lib.sh` resolves one config set (WSL distro, `uv`/`npm`
    executables, checkout, built-frontend dir, loopback port, **absolute**
    database path, backup + runtime dirs) from `deploy/deploy.env`
    (git-ignored; `deploy.env.example` documents each input) or the
    environment, and absolutises every path so a different CWD can't shift
    them.
  - `deploy/install.sh` — build the frontend, create the persistent
    data/backup/runtime dirs (refusing a database path inside the checkout or
    `frontend/dist`), and adopt existing data **once**: if the deployment DB
    is absent it snapshots the source (`scripts/backup.py`, default
    `backend/recipe.db`, `--adopt-from` to override) into the backup dir and
    copies it into place; if present it leaves it untouched. `--skip-build`
    for hosts that build separately.
  - `deploy/control.sh` — `start` (setsid + pidfile, waits for
    `/api/health`), `stop` (signals the group, waits), `restart`, `status`
    (echoes resolved config + liveness, exit 3 when stopped), `run`
    (foreground exec for an external supervisor / test harness). Always
    starts uvicorn with `RECIPE_DATABASE_URL` = the configured absolute path;
    no `--reload`, no Vite.

- **Tests**
  - `backend/tests/test_deploy.py` (5, in the `backend` CI job): install
    adopts via snapshot; install never overwrites an existing deployment DB;
    no source → DB creation deferred to first start; DB-inside-checkout
    refused; full `start`/`status`/`stop`/restart lifecycle from unrelated
    working directories against one explicit absolute DB, adopted record
    surviving the restart, second `start` refused.
  - `frontend/e2e/smoke.deployment.spec.ts` + `deployment-server.mjs` +
    `playwright.deployment.config.ts` — new `deployment` Playwright project
    and CI job: seed a throwaway "prior dev" DB (account + recipe), run
    `deploy/install.sh --adopt-from`, serve via `deploy/control.sh run` from
    an unrelated CWD; the adopted account signs in, its carried-over recipe
    is visible, a new write persists on reload, and registration is closed.
  - `frontend/playwright.config.ts` `testIgnore` extended so the visual suite
    skips `*.deployment.spec.ts` (matches the existing integration exclusion).

- **Docs** — root `README.md` runbook 8 ("WSL deployment install (with
  existing household data)") covers config inputs, persistent layout,
  one-time adoption, the one-explicit-database guarantee, `run` mode, and
  diagnostics; CI section lists the new `deployment` job. Supervision
  (06a), WSL/Windows lifetime (06b/06c), and Tailscale ingress (05a) are
  explicitly out of this slice.

- **Host acceptance** — not run: no Windows/WSL/Tailscale host in this
  session. Linux CI (`backend` + `deployment` jobs) is green; real-host
  commissioning of runbook 8 on the target machine is still pending, per the
  spec's actual-host acceptance gate.

- Reviewed with `/code-review` (Standards + Spec axes); findings actioned
  below.
