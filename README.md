# Recipe App

Household recipe manager: structured recipes, unit-aware food inventory, cook
logging with optional stock deduction, and netted grocery lists — served by a
FastAPI + SQLAlchemy + SQLite backend, with a React + TypeScript (Vite)
frontend as its client.

> **Direction:** `docs/plan.md` is the backend-v1 delivery roadmap and
> `docs/spec.md` is its technical contract. Deferred work (v2 and beyond) lives
> in `docs/features.md`.

## Layout

- `backend/` — FastAPI app (`app/`), pytest suite (`tests/`), managed with `uv`.
- `frontend/` — Vite + React + TypeScript SPA, managed with `npm`.

## Common tasks (Makefile)

A root `Makefile` wraps the everyday commands. `make help` lists them.

```bash
make install        # backend `uv sync` + frontend `npm install`
make test           # backend pytest + frontend vitest
make dev-backend    # backend dev server (separate terminal)
make dev-frontend   # frontend dev server (separate terminal)
make db-reset       # delete backend/recipe.db (no migrations; recreated on startup)
```

The per-app commands below still work directly if you prefer them.

## Backend

```bash
cd backend
uv sync                                 # install deps into .venv
uv run uvicorn app.main:app --reload    # http://localhost:8000  (interactive docs at /docs)
uv run pytest                           # run tests
```

Tables are auto-created on startup — there are no migrations. Config is read
from environment variables prefixed with `RECIPE_` (see `backend/.env.example`
and "Operating the server" below).

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api -> http://localhost:8000
npm run build      # type-check + production build
npm run typecheck
npm test           # vitest (watch);  npm run test:run for one-shot
```

Run the backend and frontend in separate terminals during development. The
frontend is wired against the real backend at runtime (no mock layer; MSW is
test-only, per `frontend/CLAUDE.md`) for auth, recipes, inventory,
availability, cook + history, and grocery lists.

**Current frontend limitation:** there is no screen for
`POST /api/auth/change-password` — password rotation is API-only for now
(`frontend/src/types.ts` carries the type, unused). Registration is gated
behind a build-time flag (`VITE_ENABLE_REGISTER`) and only renders when set,
matching the backend defaulting to registration-closed.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull
request, as parallel jobs:

- **backend** — `uv run pytest`.
- **frontend** — `npm run lint`, `npm run test:run`, `npm run build`.
- **integration** — `npm run test:integration`.
  - The real-backend Playwright suite: real SPA + real FastAPI process through
    the Vite dev proxy, on dedicated ports against a disposable SQLite DB.
  - Local repro: `cd frontend && npm run test:integration` (needs `uv` on PATH).
  - On failure the Playwright report and `test-results/` traces upload as the
    `playwright-integration-report` artifact.
- **production-smoke** — `npm run build && npm run test:e2e:production`.
  - Drives the built single-origin deployment (see "Production entry" below).
  - Its own required check: the dev-proxy `integration` suite never exercises
    `RECIPE_FRONTEND_DIST` or single-origin routing.
- **deployment** — `npm run build && npm run test:e2e:deployment`.
  - Installs and serves the app through the real `deploy/` scripts
    (`deploy/install.sh --adopt-from` + `deploy/control.sh`), carrying an
    existing household database in via a live snapshot (see "WSL deployment
    install" below). Distinct from `production-smoke`, which seeds a fresh
    database in place.
  - On failure uploads the `playwright-deployment-report` artifact.

## Authentication

Sessions are opaque bearer tokens (`Authorization: Bearer <token>`), minted by
`register`/`login` and checked by every other endpoint via
`Depends(get_current_user)`.

- **Registration is disabled by default** (`RECIPE_ALLOW_REGISTRATION=false`).
  This is a single-shared-household app: once the first account exists, leave
  registration off. See "First-user bootstrap" below.
- **No self-service password reset.** `POST /api/auth/change-password` covers
  rotation by someone who already knows the current password (and signs out
  every other device on success). A forgotten password is an operator task
  against the database file — there is no recovery flow.
- Sessions expire on a fixed window from creation
  (`RECIPE_SESSION_TTL_DAYS`, `expires_at = created_at + TTL`); `0` is legal
  and means a token that is already expired the moment it's issued.
- Accepted security posture (deliberate, not oversights, for a trusted LAN
  deployment): session tokens are stored in plaintext, there is no HTTPS
  in-app, no login rate-limiting, `/docs` is unauthenticated, and every
  authenticated user has full read/write on all data. See `docs/spec.md`
  "Accepted security posture" for the complete list.

## Operating the server

Ten runbooks, in the order you'll actually need them. Most are the same
shape — a human at a terminal, server stopped, doing something irreversible —
so they're kept together here rather than scattered across documents.

### 1. First-user bootstrap

```bash
cd backend
RECIPE_ALLOW_REGISTRATION=true RECIPE_REGISTRATION_CODE=<code> \
  uv run uvicorn app.main:app --reload
```

1. `POST /api/auth/register` with `{"username", "password", "code": "<code>"}`
   (via `/docs` or `curl`) — copy the returned `token`.
2. **Stop the server.** Restart it with neither `RECIPE_ALLOW_REGISTRATION` nor
   `RECIPE_REGISTRATION_CODE` set (i.e. the defaults in `backend/.env.example`).
3. Confirm registration is now closed: a second `POST /api/auth/register`
   returns `403 {"detail": "registration disabled"}`.

To provision several household accounts at once, or to add a member later
without opening registration at all, use runbook 6 instead.

### 2. Backup

Server can stay up — run from `backend/` (private-household-deployment ticket
02a):

```bash
uv run python scripts/backup.py --dest-dir /path/outside/the/checkout
```

`--dest-dir` should be a directory outside the checkout and outside
`frontend/dist` (never inside anything the server serves as static assets),
readable only by the operator — the script `chmod`s a freshly-created
destination directory and every snapshot file to `0700`/`0600`. `--source`
defaults to the configured `RECIPE_DATABASE_URL`; pass it explicitly to back
up a different database file.

Uses SQLite's online backup API, not a raw file copy — a raw copy of a
database mid-write can capture a torn, corrupt snapshot, and `.backup()` is
safe to run against a live, in-use database. A snapshot is written under a
temp name and renamed to its final `recipe-<UTC timestamp>.db` name only after
it completes successfully:

- **Success** — prints `backup ok: <path>` and exits 0. The new file is the
  only observable change; nothing about it is announced elsewhere yet
  (freshness/retention reporting is ticket 07b).
- **Failure** — a missing source database, an unwritable `--dest-dir`, or a
  copy interrupted partway prints `backup failed: <reason>` to stderr, exits
  1, creates no new file, and leaves every earlier snapshot in `--dest-dir`
  untouched.

There are no migrations in v1, so this is the only thing standing between a
`models.py` schema change (or any other data-affecting maintenance) and total
data loss. Take a backup before every schema change and on whatever cadence
your deployment needs — ticket 07a covers running it unattended on a
schedule.

### 3. Schema reset / restore

```bash
# reset (after a models.py change, or to start clean):
#   1. take a backup (above)
#   2. stop the server
rm backend/recipe.db
#   3. restart from backend/ — the lifespan's Base.metadata.create_all()
#      recreates the schema
(cd backend && uv run uvicorn app.main:app --reload)

# restore from a snapshot (rehearse it in isolation first — runbook 5):
#   1. stop the server
cp /path/outside/the/checkout/recipe-20260904T153000Z.db backend/recipe.db
#   2. restart
```

### 4. Production entry (built frontend + API, one origin)

Serves the production frontend build and the API from the same FastAPI
process — no Vite dev server, no dev proxy (private-household-deployment
ticket 01a). Opt-in: unset `RECIPE_FRONTEND_DIST` and the server behaves
exactly as it does today, API-only.

```bash
cd frontend && npm run build          # writes frontend/dist/
cd ../backend
RECIPE_FRONTEND_DIST=$(pwd)/../frontend/dist uv run uvicorn app.main:app
```

`RECIPE_FRONTEND_DIST` must be the built `dist/` directory (`index.html` +
`assets/`) — `create_app` refuses to start with a clear error if it doesn't
look like a real build. `dist/assets/*` is served as static files; every other
GET that isn't `/api/*` falls back to the entry document (ticket 01b), so a
household member can open or reload a bookmarked client-side route directly —
`/recipes/5`, `/login`, `/inventory`, ... — and `react-router` takes over from
there, including redirecting an anonymous or expired session back to
`/login?next=...`. An unmatched `/api/*` path stays a plain JSON 404 and a
missing `dist/assets/*` file stays a plain 404 — neither ever falls back to
the entry document.

A deterministic smoke test exercises this end to end — build, boot with
registration briefly open to seed one account (the shipped build has no
sign-up UI), boot again with registration closed, then drive login, a wrong
password, logout, a recipe write/read, direct-link/reload of a nested route,
session hydration and invalid-session redirection on reload, an unauthenticated
API request, an unknown API path, a missing asset, and the closed-registration
checks through a real browser:

```bash
cd frontend && npm run build && npm run test:e2e:production
```

This runs in CI as the `production-smoke` job. See
`frontend/playwright.production.config.ts` and `frontend/e2e/production-server.mjs`
for how the two-boot seed sequence works.

### 5. Restore rehearsal (isolated database)

Recover a snapshot into a **throwaway** database and inspect it with a
separate app instance, without touching live data (private-household-deployment
ticket 02b; replacing the live database in place, with writers stopped, is
ticket 02c):

```bash
cd backend
uv run python scripts/restore.py \
  --snapshot /path/outside/the/checkout/recipe-20260904T153000Z.db \
  --target /tmp/recipe-rehearsal.db
```

- `--snapshot` is a file produced by `scripts/backup.py` (runbook 2). It is
  validated — real SQLite, passes `integrity_check`, has the application's
  tables — and only ever read.
- `--target` must **not** already exist: this step never overwrites a
  database. Recovering onto a live database in place is out of scope here.
- Before the recovered database is published, every row in `sessions` is
  deleted. A session token captured from the snapshot is refused (`401`); you
  sign in afresh to inspect the recovered household, and any session revoked
  before the snapshot stays revoked. The recovered file is `chmod`ed to
  `0600`.
- **Success** prints `restore ok: <target>` and exits 0. Point an isolated
  app instance at it on its own port:

  ```bash
  RECIPE_DATABASE_URL=sqlite:////tmp/recipe-rehearsal.db \
    uv run uvicorn app.main:app --port 8001
  ```

- **Failure** — a missing or invalid snapshot, or a target that already
  exists — prints `restore failed: <reason>` to stderr, exits 1, and creates
  no target database. Delete the rehearsal file when you're done.

The `test_restore.py` / `test_restore_cli.py` suites run this whole path
against disposable data in the `backend` CI job: seed a live database,
snapshot it, diverge it, recover into a fresh target, and confirm a factory
app on the target sees the snapshot's records, not the later change, and
refuses the snapshot's tokens.

### 6. Household account provisioning

Create a login for each intended household member, then run the deployment
with registration closed (private-household-deployment ticket 03a). Run this
with the app **stopped** — the script writes straight to the configured
database, so registration is never opened.

```bash
cd backend
uv run python scripts/provision.py --accounts /path/outside/the/checkout/accounts.txt
```

- `--accounts` is a file of `<username> <password>` lines (split on the first
  whitespace; `#` comments and blank lines ignored), or `-` to read the same
  from stdin. The password is taken from the file, never the command line, so
  it stays out of shell history, `ps`, and any log. Keep the file outside the
  checkout, `chmod 600`, and delete it once provisioning succeeds — it is
  never committed. Usernames follow the register rule (3–50 chars,
  `A-Z a-z 0-9 _ . -`); passwords are 8–128 chars.
- `--database-url` defaults to `RECIPE_DATABASE_URL` and is echoed so you can
  confirm which database is being written. The target must already have the
  app's schema — start the deployment once (runbook 4) if it is brand new.
- A username that already exists (case-insensitively) is left untouched and
  reported as `already existed (skipped)`, so adding a member later is the
  same command with one more line.
- No session token is issued and no roles or memberships exist: every member
  signs in themselves and has equal read/write on all household data.
- **Success** prints a `provisioned:` / `already existed (skipped):` summary
  (usernames only) and exits 0. **Failure** — a malformed line, a username or
  password that breaks the register rule, or a database with no schema —
  prints `provision failed: <reason>` to stderr, exits 1, and commits nothing.

Then start the app normally (runbook 4, `RECIPE_ALLOW_REGISTRATION` unset) and
confirm the window is closed: `POST /api/auth/register` returns
`403 {"detail": "registration disabled"}`.

`test_provision.py` / `test_provision_cli.py` run this against disposable data
in the `backend` CI job: provision two accounts, then drive a factory app with
registration closed where both members log in and read/edit the same recipe,
and a direct `register` call is refused.

### 7. Household password recovery

A member forgot their password and there is no email reset. The owner resets
that one account's password and signs every one of its devices out
(private-household-deployment ticket 03b). Run this with the app **stopped** —
the script writes straight to the configured database and is not an
unauthenticated reset endpoint.

```bash
cd backend
uv run python scripts/recover.py \
  --username alice \
  --password-file /path/outside/the/checkout/new-password.txt
```

- `--username` is matched case-insensitively; the stored casing is kept. The
  account must already exist — an unknown name is refused, changing nothing
  (this procedure never creates an account).
- `--password-file` holds only the replacement password, or `-` to read it
  from stdin. It is taken from the file, never the command line, so it stays
  out of shell history, `ps`, and any log. Surrounding whitespace is trimmed.
  Keep the file outside the checkout, `chmod 600`, and delete it afterward —
  it is never committed. The password follows the register rule (8–128
  chars).
- `--database-url` defaults to `RECIPE_DATABASE_URL` and is echoed so you can
  confirm which database is written. It must already have the app's schema.
- The account's password hash is replaced with a fresh argon2 hash (the same
  facility `POST /api/auth/change-password` uses) and **every** session row
  for that account is deleted, so the old password and all previous session
  tokens stop working at once. Other accounts, their sessions, and every
  household record are untouched.
- **Success** prints `recovered: <username> (<n> session(s) revoked)`
  (never the password) and exits 0. **Failure** — an unknown account, a
  password that breaks the register rule, or a database with no schema —
  prints `recover failed: <reason>` to stderr, exits 1, and changes nothing.

Then start the app normally (runbook 4) and have the member sign in with the
new password; their other devices are already signed out.

`test_recover.py` / `test_recover_cli.py` run this against disposable data in
the `backend` CI job: recover one of two provisioned accounts, then confirm
through the real auth API that the old password and old token both fail, the
new password works and sees the same household records, and the other member
is unaffected.

### 8. WSL deployment install (with existing household data)

Install and run the app inside WSL as the household deployment, keeping your
existing records (private-household-deployment ticket 04a). This is the
manual, un-supervised form — automatic process restart is ticket 06a, and
Windows/WSL start-on-boot is 06b/06c. Private HTTPS ingress (Tailscale) is
05a; until then the app is reachable only on `127.0.0.1` inside WSL.

```bash
cp deploy/deploy.env.example deploy/deploy.env
# edit deploy/deploy.env: RECIPE_DEPLOY_CHECKOUT, RECIPE_DEPLOY_DATA_DIR,
# the WSL distribution, executables, port — all explicit host inputs.

deploy/install.sh                    # build frontend + create persistent dirs
                                     #   + adopt backend/recipe.db on first run
deploy/control.sh start             # background; waits for GET /api/health
deploy/control.sh status           # resolved config + running/stopped
deploy/control.sh stop
```

- **Config** (`deploy/deploy.env`, git-ignored, or the environment). Every
  value is echoed by `deploy/control.sh status`: WSL distribution,
  `uv`/`npm` executables, checkout, built-frontend location, loopback port,
  and the **absolute** database path. `deploy/deploy.env.example` documents
  each one.
- **Persistent data** lives under `RECIPE_DEPLOY_DATA_DIR` (default
  `~/.local/share/recipe-app`) — the SQLite database, the pre-adoption
  backup directory, and the pidfile/log — outside the checkout and outside
  the disposable `frontend/dist`. `install.sh` refuses a database path
  inside either.
- **Data adoption** happens once. If the deployment database does not exist,
  `install.sh` takes a live snapshot of the source database (default
  `backend/recipe.db`, override with `--adopt-from <file>`) via
  `scripts/backup.py` and copies it into place. If it already exists,
  `install.sh` leaves it untouched — re-running to pick up a new build never
  overwrites household data, and it never invokes the dev reset in runbook 3.
- **One explicit database.** `deploy/control.sh` always starts uvicorn with
  `RECIPE_DATABASE_URL` set to the configured absolute path, so starting
  from a different working directory, or restarting, cannot create a second
  household database. `--reload` and the Vite dev server are not used.
- **`deploy/control.sh run`** execs uvicorn in the foreground with no
  pidfile — for running under an external supervisor (ticket 06a) or a test
  harness that owns the process lifetime.
- **Diagnostics.** `deploy/control.sh status` reports resolved config plus
  liveness; application/startup output goes to
  `RECIPE_DEPLOY_DATA_DIR/run/recipe.log`; a `start` that never becomes
  healthy prints the tail of that log and exits non-zero.

`backend/tests/test_deploy.py` covers install adoption / non-overwrite and
the `start`/`stop`/`status` lifecycle against disposable data; the
`deployment` CI job (`npm run test:e2e:deployment`) drives the installed,
adopted deployment through a real browser — the seeded account signs in, its
carried-over recipe is there, and a new write persists.

### 9. WSL deployment update (schema-preserving)

Deploy a new application build while the household keeps using the same
database (private-household-deployment ticket 04b). The build is prepared and
validated *before* the running deployment is touched, a snapshot is taken
first, and the app restarts against the same explicit database.

```bash
deploy/update.sh                     # build + validate → snapshot → switch → restart
deploy/update.sh --staging-dir DIR   # use a build produced elsewhere, skip building

deploy/control.sh status             # resolved config + running/stopped + health
deploy/control.sh stop / start / restart
```

- **Prepare + validate first.** `update.sh` builds the frontend into
  `<frontend-dist>.staging` (sibling of the live build), runs `uv sync`, and
  does a backend import smoke against the staged assets. **A failed build or
  validation leaves the current deployment and its data completely
  untouched** — nothing is stopped, switched, or snapshotted.
- **Pre-maintenance snapshot.** Before the switch, `update.sh` takes a live
  snapshot of the deployment database into `RECIPE_DEPLOY_BACKUP_DIR` via
  `scripts/backup.py` (runbook 2). A snapshot failure also aborts before the
  switch.
- **Switch + restart.** The deployment is stopped, the staged build moved into
  place, and `deploy/control.sh start` brings it back on the configured
  absolute `RECIPE_DATABASE_URL`. The outgoing build is held aside as
  `<frontend-dist>.prev` only for the duration of the switch: if the new build
  fails to start, `update.sh` restores it and restarts. On success the build it
  replaced is copied into the build archive (`RECIPE_DEPLOY_BUILD_ARCHIVE`,
  default `RECIPE_DEPLOY_DATA_DIR/builds`, newest `RECIPE_DEPLOY_BUILD_KEEP`
  kept) so runbook 10 can return to it on demand.
- **No schema changes here.** This procedure never resets the database and
  never runs a schema-changing upgrade. A future `models.py` change needs a
  reviewed, data-preserving migration (runbook 3 is the dev-only reset, *not*
  an upgrade path) before it can be installed against household data.
- **Health check.** `deploy/control.sh status` reports the resolved config,
  whether the app is running, the database file, and `GET /api/health`
  liveness; `start` that never becomes healthy prints the tail of
  `RECIPE_DEPLOY_DATA_DIR/run/recipe.log` and exits non-zero.

`backend/tests/test_deploy.py` covers the switch/snapshot/abort logic against
disposable data; the `deployment-update` CI run
(`npm run test:e2e:deployment-update`) drives a real browser through an update
**and** a rollback (runbook 10): records written against each build — and the
adopted ones — survive both switches, and later writes persist.

### 10. WSL deployment rollback (return to a previous build)

Step the deployment back to an earlier application build after an unsuitable
update (private-household-deployment ticket 04c). This is a **build** operation,
not a data operation — it is not how you recover household *records* (that is
runbook 5, restore from a snapshot). The app restarts against the **same**
explicit database; household data is never touched, and a pre-maintenance
snapshot is taken first.

```bash
deploy/rollback.sh --list            # retained builds, newest first
deploy/rollback.sh                   # return to the most recently retained build
deploy/rollback.sh --to 20260905T231233Z   # a specific retained build (by name)
deploy/rollback.sh --to /path/to/build     # a build directory you identified yourself
```

- **Where retained builds come from.** `deploy/update.sh` copies the build it
  replaces into `RECIPE_DEPLOY_BUILD_ARCHIVE` on every successful update. A
  successful `rollback.sh` likewise retains the build it switched *away* from,
  so you can roll forward again.
- **Validate first.** `rollback.sh` checks the selected build has `index.html`
  and that the backend imports cleanly against it **before** stopping anything.
  A missing, unknown, or unusable selection aborts with the running deployment
  and its data completely intact — nothing is stopped, switched, or snapshotted.
- **Pre-maintenance snapshot.** Before the switch, a live snapshot of the
  deployment database is taken into `RECIPE_DEPLOY_BACKUP_DIR` via
  `scripts/backup.py` (runbook 2). A snapshot failure aborts before the switch.
- **Switch + restart.** Stop, swap the selected build in, `deploy/control.sh
  start` on the configured absolute `RECIPE_DATABASE_URL`. If the selected build
  fails to start, the build that was running is put back and restarted.
- **Not across a schema change.** An older build must not be run against a
  newer, incompatible schema. Roll back a build only while the schema is
  unchanged. This deployment ships no schema change; a future `models.py` change
  needs the reviewed, data-preserving migration from runbook 9 first, and once
  household data is migrated forward the older build is no longer compatible.
- **Health check.** `deploy/control.sh status`, as in runbook 9.

`backend/tests/test_deploy.py` covers the select/validate/snapshot/abort and
roll-forward retention logic against disposable data; the `deployment-update` CI
run also drives a browser through update → rollback (above).

## v1 workflows

The full contract lives in `docs/spec.md`; this is the shape of it.

- **Recipes** — structured ingredients (each either a parsed line or a
  pasted-string line the parser resolves), steps, tags. Full CRUD.
- **Inventory** — food items with a canonical quantity + unit; `POST` is
  additive (adds into an existing `(match_name, unit_bucket)` row), `PATCH`
  sets an absolute quantity.
- **Availability** — `GET /api/recipes/{id}/availability?multiplier=` checks a
  recipe's ingredients against current stock, unit-aware, flagging
  `have_uncertain` stock sitting in an incompatible unit.
- **Cook** — `POST /api/recipes/{id}/cook` logs a cook and, unless
  `deduct:false`, deducts stock. Deduction is **forward-only**: there is no
  undo endpoint for a cook or its stock changes.
- **Grocery lists** — generated from selected recipes' shortfalls (netted
  against stock), with manual line add/edit, checking off lines, and
  **forward-only** submit (checked lines get added back into inventory) and
  archive. A submitted or archived list's lines are frozen (`409` on further
  edits).

## API surface

Full request/response contract, including every status code and validation
rule, is the live OpenAPI UI at `/docs` (unauthenticated — see "Accepted
security posture" above) once the server is running. Routers:

| Prefix | Covers |
| --- | --- |
| `/api/auth` | register, login, logout, `me`, change-password |
| `/api/recipes` | recipe CRUD, availability, cook, per-recipe cook-logs |
| `/api/inventory` | inventory CRUD |
| `/api/grocery` | grocery list CRUD, lines, submit, archive |
| `/api/cook-logs` | global (cross-recipe) cook-log reads |
| `/api/health` | unauthenticated liveness check |

## LAN serving

This is a single-shared-household app meant for a trusted LAN, not the public
internet (see "Accepted security posture"). To serve the frontend from another
device on the LAN, add its origin to `RECIPE_CORS_ORIGINS` (a JSON list, e.g.
`["http://192.168.1.50:5173"]`), or set it to `["*"]` — acceptable only for a
trusted, non-credentialed LAN deployment, since a wildcard origin combined
with real sessions is otherwise a CSRF-shaped risk.

## Deferred work

Anything not listed above — meal planning, staples/low-stock alerts, photo
upload, URL import, recipe research, per-cook reviews, receipt OCR, migrations
support, multi-user ownership, and more — is intentionally out of v1 scope.
See `docs/features.md` for the complete deferred/excluded list and rationale.
The pre-trim, full planning record (nine phases, wider v1 scope) is preserved
at `git show 5144c25:docs/plan.md`.
