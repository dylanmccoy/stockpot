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

Seventeen runbooks, in the order you'll actually need them. Most are the same
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
  only observable change; `scripts/backup_status.py` (runbook 14) reports
  whether the latest success is recent enough and prunes old snapshots.
- **Failure** — a missing source database, an unwritable `--dest-dir`, or a
  copy interrupted partway prints `backup failed: <reason>` to stderr, exits
  1, creates no new file, and leaves every earlier snapshot in `--dest-dir`
  untouched.

There are no migrations in v1, so this is the only thing standing between a
`models.py` schema change (or any other data-affecting maintenance) and total
data loss. Take a backup before every schema change and on whatever cadence
your deployment needs — runbook 14 runs it unattended on a daily schedule.

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
ticket 02b). Replacing the live database in place, with writers stopped, is
runbook 13:

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
manual, un-supervised form — automatic app-process restart is runbook 16
(`deploy/supervise.sh`); keeping WSL itself alive after terminals close is
runbook 17 (`deploy/wsl-keeper.sh`) and starting after a Windows boot is
ticket 06c. Private HTTPS ingress for
household devices is runbook 11 (Tailscale Serve);
without it the app is reachable only on `127.0.0.1` inside WSL. Household
phones enrol against that ingress in runbook 12.

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
  replaces into `RECIPE_DEPLOY_BUILD_ARCHIVE` (default
  `RECIPE_DEPLOY_DATA_DIR/builds`, newest `RECIPE_DEPLOY_BUILD_KEEP` kept) on
  every successful update. To move *forward* again, build and deploy with
  `deploy/update.sh` — rollback is one-directional.
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
- **Not across a schema change.** "Compatible" here means *same schema era* —
  `rollback.sh` validates the build is serveable, but it cannot check the schema.
  An older build must not be run against a newer, migrated schema. Roll back a
  build only while the schema is unchanged. This deployment ships no schema
  change; a future `models.py` change needs a reviewed, data-preserving
  migration (there is none yet — runbook 3 is the dev-only reset, *not* an
  upgrade path), and once household data is migrated forward the older build is
  no longer compatible.
- **Health check.** `deploy/control.sh status`, as in runbook 9.

`backend/tests/test_deploy.py` covers the select / validate / snapshot / abort
logic against disposable data; the `deployment-update` CI run also drives a
browser through update → rollback (above).

### 11. Private HTTPS ingress (Tailscale Serve)

Give household devices one HTTPS address that reaches the deployment, private
to the tailnet — nothing on the LAN or the public internet can connect
(private-household-deployment ticket 05a). The app keeps listening on
`127.0.0.1` only; Tailscale Serve on the **Windows** host proxies its
`localhost:<port>` (which WSL2 forwards to the app) out onto the tailnet over
HTTPS. Funnel and router port-forwarding are never used.

**Prerequisites**

- The deployment is installed and running (runbook 8): `deploy/control.sh
  status` shows it healthy on `127.0.0.1:<port>`.
- Tailscale is installed and signed in on the Windows host, on the household
  tailnet.
- `deploy/deploy.env` sets `RECIPE_DEPLOY_TAILSCALE_BIN` (from WSL:
  `tailscale.exe`) and, if not 443, `RECIPE_DEPLOY_HTTPS_PORT`.

**1 — confirm Windows can reach the WSL app.** WSL2 forwards Windows
`localhost` to listeners inside the distro (`localhostForwarding`, on by
default). From a Windows PowerShell:

```powershell
curl.exe http://127.0.0.1:8000/api/health      # expect {"status":"ok"}
```

If that fails, the localhost forward is off — set `localhostForwarding=true`
in `%UserProfile%\.wslconfig` under `[wsl2]` and `wsl --shutdown`. See
Microsoft's [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).

**2 — configure Serve.** From the WSL checkout:

```bash
deploy/tailscale-serve.sh apply      # tailnet :443 (HTTPS) -> http://127.0.0.1:<port>
deploy/tailscale-serve.sh status     # current mapping + node state + Funnel (must be off)
deploy/tailscale-serve.sh url        # the address household devices open
deploy/tailscale-serve.sh reset      # clear this node's Serve config
```

- `apply` runs `tailscale serve --bg --https=<https-port> http://127.0.0.1:<port>`.
  `--bg` persists the mapping in tailscaled state, so it returns on its own
  after a Tailscale or Windows restart.
- It **refuses** if Funnel is active on the node, or if the local origin is
  not answering `/api/health` — it never fronts a dead port or a public
  exposure.
- It is idempotent: re-running re-asserts the same mapping, which is also how
  you restore the ingress if the persistent config is ever lost.

**3 — restrict the tailnet to household devices.** Serve makes the app
reachable to *every* node on the tailnet; narrowing that to intended
household identities/devices is an admin-console policy step (it needs tailnet
admin, not this host):

- In the [ACL policy](https://login.tailscale.com/admin/acls), grant only the
  household users/devices access to this node (e.g. tag the deployment host
  `tag:recipe` and write a rule allowing only `group:household` → `tag:recipe`
  on `tcp:443`).
- Keep the tailnet's device-approval / sharing settings closed so an
  unrelated device cannot join and reach the tag.
- Tailscale membership and app login are **separate** requirements — a
  permitted device still signs in with its own account, and registration
  stays closed (runbook 6).

**4 — unattended Tailscale operation.** So the ingress survives the Windows
host running with no user signed in, enable Tailscale's
[unattended mode](https://tailscale.com/docs/how-to/run-unattended) on
Windows (Tailscale tray → Preferences → **Run unattended**, or install it as
a system service). Verify after a full reboot without interactive login
(that whole-path check is runbook / ticket 06c).

**5 — verify.**

```bash
deploy/net-check.sh          # 6 checks, exits non-zero on any hard failure
```

- app answers on `127.0.0.1:<port>`; **nothing** is listening on that port on
  a non-loopback address; Tailscale up; Serve points at the local origin;
  Funnel off; the tailnet HTTPS URL resolves.
- `deploy/net-check.sh --local-only` runs just the first two (useful from
  inside WSL where the Windows CLI may be off PATH).

From a **permitted client** with Tailscale connected, open the `url` address
and confirm, per the ticket's acceptance list:

- valid HTTPS (no certificate warning — Tailscale provisions the cert), login,
  read **and** write, and direct-link reload of a nested route (`/recipes/<id>`);
- `curl https://<host>.<tailnet>.ts.net/api/recipes` → `401` (auth still
  required); a direct `POST /api/auth/register` → `403`;
- from a device **not** on the tailnet, the name does not resolve and the
  host cannot be reached — there is no LAN or public listener bypassing this
  ingress.

**6 — recovery after a Tailscale restart.** With `--bg` the mapping is
restored automatically; run `deploy/net-check.sh` to confirm, and
`deploy/tailscale-serve.sh apply` if anything is missing. Restarting Tailscale
with the app running must not require touching the deployment itself.

**Never:** `tailscale funnel` (public), router port-forwarding, or binding the
app to `0.0.0.0` — each is a public/LAN exposure this deployment explicitly
excludes. `deploy/net-check.sh` fails on all three.

`backend/tests/test_deploy.py` covers the deterministic half in the `backend`
CI job — `deploy/net-check.sh` and `deploy/tailscale-serve.sh` driven against
a healthy loopback deployment and a **stub** Tailscale CLI (no credentials):
Serve is pointed at the local origin over background HTTPS, `apply` refuses on
an active Funnel or a dead origin, and `net-check` fails on a non-loopback
listener or an active Funnel. Real Tailscale, Windows-to-WSL forwarding,
tailnet ACLs, and off-tailnet unreachability are the actual-host acceptance
gate — results recorded in
`.scratch/private-household-deployment/host-acceptance-05a.md`.

### 12. Household phone onboarding (iOS / Android)

Get a household member's phone onto the tailnet and into the app, so they can
use it over cellular while away from home
(private-household-deployment ticket 05b). Nothing new runs on the deployment —
this is commissioning the phone against the runbook 11 ingress. The app is the
same responsive browser app; there is no native app, no install step, and **no
offline mode** — the phone always needs working internet (cellular or Wi-Fi)
for Tailscale to carry the connection.

**Two separate things.** Joining the tailnet and signing into the app are
independent:

1. **Tailscale** decides whether the phone can *reach* the private HTTPS
   address at all. The owner adds the person's Tailscale identity/device to the
   household tailnet and it must fall inside the ACL rule from runbook 11 §3.
2. **The app account** is the person's own username/password (runbook 6 to
   provision, runbook 7 for a forgotten password). Registration stays closed —
   there is no sign-up on the phone.

A phone on the tailnet with no app account still cannot read anything; an app
account on a phone that is not on the tailnet cannot load the page.

**Prerequisites**

- Runbook 11 is done and verified: `deploy/tailscale-serve.sh url` prints the
  address, and `deploy/net-check.sh` passes.
- The owner has invited the household member to the tailnet (Tailscale admin
  console → **Users** → invite) and their devices are covered by the
  `group:household` → `tag:recipe` rule.
- The member has an app account.

**1 — install Tailscale on the phone.**

- **iOS:** App Store → *Tailscale* → install. Open it, **Sign in**, choose the
  household tailnet, and accept the "Tailscale would like to add VPN
  configurations" prompt. Toggle the connection **on** (or enable **Connect on
  demand** in the app's settings so it reconnects itself).
- **Android:** Play Store → *Tailscale* → install. Open it, **Sign in**, choose
  the household tailnet, accept the "connection request" (VPN) prompt, and
  toggle the connection **on**. **Settings → Always-on VPN** (Android system
  settings) keeps it connected.

Confirm the phone shows as connected and appears in the tailnet device list.

**2 — open the app.** In **Safari (iOS)** or **Chrome (Android)** go to the
address from `deploy/tailscale-serve.sh url`
(`https://<host>.<tailnet>.ts.net/`). Expect valid HTTPS with **no certificate
warning** — Tailscale provisions the certificate for that name. Add it to the
home screen / bookmarks for convenience; it is a normal browser tab, not an
installed app.

**3 — sign in and use it.** Log in with the member's own app account. From
there the phone behaves exactly like a desktop browser:

- read a recipe, edit and save — writes hit the same household database and are
  visible to every other member;
- a saved direct link to a nested route (`…/recipes/<id>`) opens and reloads
  without a server error page;
- the login session survives a page reload; **Log out** ends it; an expired or
  invalid session returns to the login screen through the normal flow;
- ordinary API errors still render as in-app errors, not a web server page.

**4 — cellular check.** Turn the phone's **Wi-Fi off** so it is on cellular
only, then repeat step 3 — reach the address, log in, read, save, reload a
nested route. Toggle Tailscale **off**: the address stops resolving and the app
is unreachable. Toggle it back **on**: the app loads again and the existing
login session is still there (no re-login needed unless it had genuinely
expired). With **both** cellular data and Wi-Fi off, Tailscale cannot connect
at all — confirming there is no offline capability.

**Troubleshooting**

- *Address does not resolve / "server not found":* Tailscale is off, the phone
  is off the tailnet, or the device is outside the ACL rule (runbook 11 §3).
- *Certificate warning:* not expected — check the host name in the URL matches
  `deploy/tailscale-serve.sh url` exactly; do not bypass the warning.
- *Loads but every API call fails / immediate logout:* the app account or
  session is the problem, not the network — sign in again, or use runbook 7 for
  a forgotten password.

This runbook is phone commissioning of the existing browser app; it has no
CI-provable surface of its own. The app behaviour it exercises is already
covered against the one-origin production serving (no dev proxy) by two
Playwright projects:

- **`deployment`** (`e2e/smoke.deployment.spec.ts`, ticket 04a) — login with
  an adopted account, a write that persists across a reload, `401` without a
  token, registration `403`;
- **`production`** (`e2e/smoke.production.spec.ts`, tickets 01a / 01b) —
  direct load / reload of a nested route (`/inventory`, `/recipes/<id>`),
  session hydration across a full reload, an invalid stored session redirected
  to login, wrong-password inline, logout, and API 404s that stay 404s.

Real iOS/Android hardware on cellular, Tailscale enrolment, and
disconnect/reconnect are the actual-host acceptance gate — results recorded in
`.scratch/private-household-deployment/host-acceptance-05b.md`.

### 13. Restore in place (replace the live database)

Recover a snapshot **over** the configured household database after a data
loss (private-household-deployment ticket 02c). Unlike runbook 5, this touches
the real database — so the application's writers must be **stopped** for the
whole procedure, and the database being replaced is preserved first. The
end-to-end recovery that picks a **scheduled** snapshot (runbook 14) and adds
the restart / access checks and the one-day target is runbook 15.

**stop → preserve → restore → restart:**

```bash
cd backend

# 1. stop writers — nothing may be writing the target database.
deploy/control.sh stop          # or however this host runs the app (runbook 8);
                                # deployment process control is runbook 6 onward.

# 2 + 3. preserve the current database, then replace it with the snapshot.
uv run python scripts/restore.py --replace \
  --snapshot /path/outside/the/checkout/recipe-20260904T153000Z.db \
  --target   "$RECIPE_DEPLOY_DATA_DIR/recipe.db" \
  --preserve-dir /path/outside/the/checkout/pre-restore

# 4. restart against the same explicit database and health-check.
deploy/control.sh start
deploy/control.sh status        # resolved config + GET /api/health
```

- **`--target` must already exist** — it is the live database. Recovering into
  a fresh path is runbook 5; `--replace` is refused without an existing target.
- **Preserve first.** Before anything is replaced, `scripts/backup.py`
  (runbook 2) snapshots the current `--target` into `--preserve-dir` and that
  copy is itself validated. If preserving or validating it fails, the command
  **refuses** — `restore failed: refusing to replace <target> …`, exit 1, the
  live database byte-for-byte unchanged. A copy of what you replaced is always
  kept.
- **Prepare + validate, then swap.** The snapshot is validated (real SQLite,
  `integrity_check`, this app's tables), copied to a temp file beside the
  target, its `sessions` rows cleared, `chmod`ed `0600`, and validated again —
  and only then renamed onto the live path in one atomic step. A failure at
  any point before that rename leaves the target unchanged (`restore failed:
  preparing the recovered database …`, exit 1); the preserved copy stays.
- **Sessions.** Every session in the recovered database is deleted before it
  is served, so a token captured from the snapshot is refused (`401`) and a
  session revoked before the snapshot is not revived — household members sign
  in afresh after the restart.
- **Untouched:** earlier snapshots in `--preserve-dir`, and the `--snapshot`
  file, are only read.
- **Success** prints `restore ok: replaced <target>` and `preserved prior
  database: <path>`, exits 0.

The host-specific stop/start commands above are placeholders — process
supervision and boot ordering are runbooks 6–11 and the actual-host
acceptance gate. `backend/tests/test_replace.py` /
`backend/tests/test_restore_cli.py` run the preserve/prepare/validate/swap
path and its invalid-snapshot, failed-preservation, and failed-preparation
refusals against disposable data in the `backend` CI job.
### 14. Scheduled daily backups (unattended)

Run the backup (runbook 2) once a day with no terminal open and no dependence
on the app process (private-household-deployment ticket 07a). After a
successful snapshot the job also prunes old snapshots to a retained count, and
`scripts/backup_status.py` reports whether backups are meeting the 24-hour
recovery target (ticket 07b, below). Automatic app start-on-boot is **not** a
prerequisite for the backup job.

**The job — `deploy/backup-run.sh`.** This is the one command a scheduler runs:

```bash
deploy/backup-run.sh
```

- Takes **one** live `recipe-<UTC timestamp>.db` snapshot of
  `RECIPE_DEPLOY_DB_FILE` into `RECIPE_DEPLOY_BACKUP_DIR`, via
  `scripts/backup.py` (runbook 2) — SQLite's online backup facility, safe
  whether or not the app is running. It talks to no app, supervisor, or
  Tailscale.
- **Bounded.** The snapshot runs under `timeout $RECIPE_DEPLOY_BACKUP_TIMEOUT`
  (default 300s; coreutils `timeout`) so a stuck database lock cannot leave the
  task running forever.
- **Success** — prints and logs `ok <snapshot path>`, exits 0, then applies
  retention: keep the newest `RECIPE_DEPLOY_BACKUP_KEEP` valid snapshots
  (default 14), delete older ones (`scripts/backup_status.py --prune`). A
  prune problem only warns — the snapshot itself already succeeded.
- **Failure** — a missing database, an unwritable destination, an interrupted
  copy, or the time limit prints and logs `FAIL <reason>`, exits non-zero,
  creates no new file, and leaves every earlier snapshot untouched. A failed
  run publishes no snapshot, so retention never evicts an earlier success
  because a later backup failed.
- **Diagnostics.** One line per run is appended to
  `RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log`
  (`deploy/control.sh status` echoes its path and the time limit):

  ```
  2026-09-05T03:30:01Z ok /home/you/.local/share/recipe-app/backups/recipe-20260905T033001Z.db
  2026-09-06T03:30:00Z FAIL deployment database ... does not exist ...
  ```

**Schedule it — Windows Task Scheduler.** From an elevated-not-required
PowerShell on the Windows host:

```powershell
.\deploy\windows\register-backup-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe
# options: -Time 03:30  -TaskName RecipeAppDailyBackup  -LogonType S4U|Password
.\deploy\windows\register-backup-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -Unregister
.\deploy\windows\register-backup-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -ShowCommand
```

- Registers a task that runs, daily at `-Time` (host local time),
  `wsl.exe -d <Distro> -- bash <Checkout>/deploy/backup-run.sh`.
- **Whether or not a user is signed in.** Principal `LogonType S4U` (no stored
  password). If WSL will not start under S4U on your host, re-run with
  `-LogonType Password` (prompts once).
- **Survives a reboot / catches up.** `-StartWhenAvailable` takes a run missed
  while the machine was off; `MultipleInstances IgnoreNew` and a 1h
  `ExecutionTimeLimit` keep runs from piling up.
- **Idempotent.** Re-running replaces the task of the same name — repeated
  setup never leaves duplicates.
- **Verify:** `Start-ScheduledTask -TaskName RecipeAppDailyBackup`, then check
  the newest file in `RECIPE_DEPLOY_BACKUP_DIR` and the last line of
  `backup-runs.log`. `Get-ScheduledTaskInfo -TaskName RecipeAppDailyBackup`
  shows `LastTaskResult` / `NextRunTime`.

**Check freshness & apply retention — `scripts/backup_status.py`.** Run from
`backend/`; it reads only the snapshot directory and the run log:

```bash
# freshness report — exit 0 fresh, 1 stale / none on disk, 2 bad input
uv run python scripts/backup_status.py \
  --dest-dir "$RECIPE_DEPLOY_BACKUP_DIR" \
  --log "$RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log"

# apply retention by hand (the scheduled job already does this after each success)
uv run python scripts/backup_status.py --dest-dir "$RECIPE_DEPLOY_BACKUP_DIR" --keep 14 --prune
```

- Reports the **latest successful snapshot and its age**, the **latest failed
  attempt** (from the run log), and the count of valid snapshots.
- **Flags** — prints `STALE` to stderr and exits non-zero when there is no
  successful backup on disk, or the latest success is older than
  `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` (default 24). Run it from a wrapper if
  you want an unattended check — the exit status is the whole signal, there is
  no hosted alerting.
- **Incomplete files** — a hidden `.recipe-*.db.tmp` or a `recipe-*.db` that
  will not open as an intact SQLite database is listed but never counted as a
  success and never pruned.
- `--prune` keeps the newest `--keep` valid snapshots and deletes older ones;
  `--dry-run` shows what it would delete. A delete that fails (e.g. a
  read-only directory) is reported and exits non-zero, leaving the retained
  set intact. `--now <UTC ISO8601>` overrides the clock for a what-if check.

**Schedule / destination / retention summary.**

| | |
| --- | --- |
| Schedule | daily at `-Time`, `StartWhenAvailable`, 1h limit, no-pile-up |
| Destination | `RECIPE_DEPLOY_BACKUP_DIR` (default `RECIPE_DEPLOY_DATA_DIR/backups`), outside the checkout and served assets |
| Permissions | `scripts/backup.py` sets `0700` on the directory and `0600` on every snapshot each run (best effort — a `chmod` the operator can't make is skipped; host-verified in acceptance #6) |
| Run log | `RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log`, one `ok`/`FAIL` line per run |
| Time limit | `RECIPE_DEPLOY_BACKUP_TIMEOUT` (default 300s) |
| Retention | `RECIPE_DEPLOY_BACKUP_KEEP` newest valid snapshots (default 14); count-based, so a failed run never evicts an earlier success |
| Freshness target | `RECIPE_DEPLOY_BACKUP_MAX_AGE_HOURS` (default 24) — `scripts/backup_status.py` flags no success / an older success |

**Diagnosis.**

- No new snapshot and a `FAIL` line — read the reason. Missing database: start
  the deployment at least once (runbook 8). Unwritable destination: check the
  backup directory's owner/permissions and free disk.
- No new snapshot and **no** new log line — the task did not fire. Check
  `Get-ScheduledTaskInfo` `LastRunTime` / `LastTaskResult`, that the task is
  Enabled, and that `wsl.exe -d <Distro> -- bash <Checkout>/deploy/backup-run.sh`
  (`-ShowCommand`) runs by hand.
- `scripts/backup_status.py` says `STALE` — the newest good snapshot is past
  the 24-hour target. Fix the cause of the last `FAIL` (above), then re-run
  the job by hand (`deploy/backup-run.sh`, or `Start-ScheduledTask`) and
  re-check; a `FAIL` line is not data loss (earlier snapshots are always kept)
  but it does mean the recovery point is aging.
- `scripts/backup_status.py` warns during `deploy/backup-run.sh` about a
  retention prune problem — the snapshot itself succeeded. Run
  `scripts/backup_status.py --dest-dir "$RECIPE_DEPLOY_BACKUP_DIR"` for the
  detail (usually a snapshot file the operator account cannot delete); fix the
  directory permissions and re-run with `--prune`.

`backend/tests/test_deploy.py` and `backend/tests/test_backup_status.py` cover
the deterministic half in the `backend` CI job — `deploy/backup-run.sh` driven
as a subprocess against disposable data (a snapshot with the app running and
with it stopped, the run log lines, failure leaving earlier snapshots intact,
the time limit terminating a stuck snapshot, and retention pruning after a
success), plus `app.backup_status` / `scripts/backup_status.py` against
disposable snapshot directories with an injected clock (latest-success age,
the no-success and older-than-target flags, incomplete files never counted,
count-based retention, and a failed delete reported without touching the
retained set). Real Windows Task Scheduler registration and the
reboot-without-interactive-login check are the actual-host acceptance gate —
results recorded in
`.scratch/private-household-deployment/host-acceptance-07a.md` and
`host-acceptance-07b.md`.

### 15. Recover the deployment from a scheduled snapshot

The whole-deployment recovery procedure after a data loss: take the newest
good **scheduled** snapshot (runbook 14), replace the live database in place
(runbook 13), restart, and confirm household access — inside the one-day
recovery target (private-household-deployment ticket 07c).

**Depends on** a usable local snapshot and a surviving host disk. Off-machine
backups and recovery from disk or machine loss are out of scope (spec items
13, 30). A snapshot older than 24h is already past the accepted data-loss
target — `scripts/backup_status.py` flags that (runbook 14).

**Rehearse in isolation first.** Before running this against the live
database, run it once against a separate database and app instance (runbook 5,
or the `test_deploy.py` recovery tests) so the steps and the chosen snapshot
are known-good.

**select → stop → preserve → restore → restart → verify:**

```bash
cd "$RECIPE_DEPLOY_CHECKOUT/backend"

# 1. select — the newest `ok` line in the backup run log is the freshest
#    recovery point; confirm it is < 24h old (runbook 14).
tail -n 5 "$RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log"
snapshot=$(awk '$2 == "ok" { p = $3 } END { print p }' \
  "$RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log")
echo "restoring from $snapshot"

# 2. stop writers.
deploy/control.sh stop

# 3 + 4. preserve the current database, then replace it with the snapshot.
uv run python scripts/restore.py --replace \
  --snapshot "$snapshot" \
  --target   "$RECIPE_DEPLOY_DB_FILE" \
  --preserve-dir "$RECIPE_DEPLOY_DATA_DIR/pre-restore"

# 5. restart against the same explicit database.
deploy/control.sh start
deploy/control.sh status          # resolved config + GET /api/health
deploy/net-check.sh --local-only  # listener still loopback-only

# 6. verify household access — a fresh login and a representative read:
curl -fsS "http://127.0.0.1:$RECIPE_DEPLOY_PORT/api/health"
curl -fsS -X POST "http://127.0.0.1:$RECIPE_DEPLOY_PORT/api/auth/login" \
  -H 'content-type: application/json' \
  -d '{"username":"<member>","password":"<password>"}'
```

- **Selecting the snapshot.** `backup-runs.log` carries one `ok <path>` /
  `FAIL <reason>` line per scheduled run (runbook 14). Take the newest `ok`
  path. If it is older than 24h, or the latest lines are `FAIL`, you are
  restoring past the accepted data-loss window — note it and continue with the
  best snapshot you have.
- **stop → preserve → restore → restart** is runbook 13 unchanged: `--target`
  must be the existing live database; the current database is snapshotted into
  `--preserve-dir` and validated *before* anything is replaced, and the
  command refuses (live database byte-for-byte unchanged) if that fails. A
  copy of what you replaced is always kept, so a bad snapshot choice can be
  undone.
- **Sessions.** Every session in the restored snapshot is cleared before the
  app serves it — a login session from before the restore is refused (`401`)
  and a session revoked before the snapshot is not revived. Household members
  sign in again after the restart.
- **What you lose.** Every change committed after the snapshot's timestamp —
  recipes, inventory, cooking history, grocery edits, password changes — is
  rolled back. That is the accepted ≤24h data-loss target (spec item 35);
  completing the restore inside a day is item 36.
- **Verify in a browser** (on a permitted device — this is the host
  rehearsal): fresh login succeeds; a representative recipe / inventory record
  from before the snapshot reads back; a change known to have been made
  *after* the snapshot is absent; an old session returns to the login screen.

`backend/tests/test_deploy.py` runs this whole procedure in the `backend` CI
job against the isolated `deploy_env` deployment — its own port and
data/backup/runtime dirs and app process, so live data is never touched: seed
records, `deploy/backup-run.sh` for the scheduled snapshot, diverge,
`restore.py --replace`, restart, then over real HTTP a fresh login sees the
snapshot's records, the pre-restore session is `401`, and the post-snapshot
change is gone. The **actual-host rehearsal within the one-day target** — real
browser, real deployment, timed — is the acceptance gate recorded in
`.scratch/private-household-deployment/host-acceptance-07c.md`.

### 16. WSL app process supervision (auto-restart)

Keep the app process alive while the WSL distribution is up: if it exits, a
watch loop restarts it (private-household-deployment ticket 06a). This slice
supervises the **app process only** — keeping WSL itself alive is runbook 17,
and starting it after a Windows boot without an interactive login is ticket 06c.
Run `deploy/supervise.sh` under whatever brings WSL up (runbook 17 is that
"whatever" for unattended operation).

```bash
deploy/supervise.sh start     # start the app if needed, then watch it (background)
deploy/supervise.sh status    # supervisor state + restart count, then control.sh status
deploy/supervise.sh stop      # stop the watch loop, then the app
deploy/supervise.sh restart
deploy/supervise.sh run       # watch loop in the FOREGROUND (for a systemd unit /
                              # a test harness that owns the process lifetime)
```

- **What it does.** A loop around `deploy/control.sh`: every
  `RECIPE_DEPLOY_SUPERVISE_INTERVAL` seconds (default 3) it checks the app pid;
  if the process is gone it runs `deploy/control.sh start`, which brings the app
  back on the one configured absolute `RECIPE_DATABASE_URL`. Nothing about the
  database, build, or port changes on a restart.
- **No duplicate instances.** `supervise.sh start` refuses if a supervisor is
  already running (its own pidfile, `RECIPE_DEPLOY_RUNTIME_DIR/recipe-supervisor.pid`),
  and it never launches a second app — it adopts an app that is already running
  (e.g. started via runbook 8) and supervises it in place. `control.sh start`
  itself still refuses a second app, so a repeated `install`/`start` cannot
  double-run the deployment.
- **Crash-loop damping.** A one-off crash is restarted immediately. But if
  `control.sh start` fails (bad build, port in use), or the app comes back and
  then exits again within `RECIPE_DEPLOY_SUPERVISE_BACKOFF_MAX` seconds
  (default 60), the loop waits a delay that doubles each time — capped at that
  value — before the next restart, and resets once the app holds. It never
  gives up, and recovers on its own once the fault is fixed.
- **Diagnostics.** `supervise.sh status` prints the supervisor state, the
  running restart count and last-restart time, and the tail of the supervisor
  log (`RECIPE_DEPLOY_RUNTIME_DIR/recipe-supervisor.log`), then defers to
  `deploy/control.sh status` (its exit code — `3` when the app is stopped — is
  the command's exit code). Application/startup output is still
  `RECIPE_DEPLOY_RUNTIME_DIR/recipe.log`.
- **Stopping.** `supervise.sh stop` (or a `SIGTERM` to `supervise.sh run`) stops
  the watch loop *and* the app together. Use it instead of a bare
  `deploy/control.sh stop`, which the supervisor would immediately undo.

**Verify** (on the target host — do this while WSL stays up):

```bash
deploy/supervise.sh start
deploy/control.sh status                       # healthy on 127.0.0.1:<port>
kill "$(cat "$RECIPE_DEPLOY_DATA_DIR/run/recipe.pid")"   # simulate a crash
sleep 5
deploy/supervise.sh status                     # app restarts >= 1, health OK again
# open the app / re-read a recipe — previously saved records are still there
deploy/supervise.sh stop
```

`backend/tests/test_deploy.py` covers the mechanism deterministically in the
`backend` CI job: a terminated app is restarted and pre-existing records stay
usable, a second `supervise.sh start` is refused and never duplicates the app,
an already-running app is adopted without a restart, `run` supervises until it
is signalled, and a failed restart is retried and then recovers. Real
Windows/WSL process recovery (with the actual WSL distribution and no
interactive shell) is the actual-host acceptance gate — results recorded in
`.scratch/private-household-deployment/host-acceptance-06a.md`.

### 17. Keep WSL serving after terminals close

Keep the WSL distribution — and the app supervisor (runbook 16) above it —
alive with no development shell open, and bring it back after a controlled
`wsl --shutdown` (private-household-deployment ticket 06b). A WSL distro stops
when its last process exits, so a systemd service *inside* WSL cannot hold it
open; the lifetime owner has to be on the Windows side. Starting this before an
interactive Windows login (a full reboot) and running Tailscale ingress
unattended are ticket 06c.

**The keeper — `deploy/wsl-keeper.sh`.** One long-lived foreground process:

```bash
deploy/wsl-keeper.sh run      # hold WSL up + keep supervise.sh (and the app) alive
deploy/wsl-keeper.sh status   # keeper state + keeper log, then supervise.sh status
deploy/wsl-keeper.sh stop     # stop the keeper, the supervisor, and the app
```

- **What it does.** While `run` is alive the distribution stays up. It starts
  `deploy/supervise.sh` if none is running, adopts one that already is (e.g. you
  started it by hand per runbook 16), and re-launches it on the next heartbeat
  (`RECIPE_DEPLOY_KEEPER_HEARTBEAT`, default 30s) if it ever disappears. The
  supervisor in turn keeps the app process up. Nothing about the database,
  build, or port changes.
- **No duplicate instances.** `run` refuses if a keeper is already running (its
  own pidfile, `RECIPE_DEPLOY_RUNTIME_DIR/recipe-keeper.pid`); `supervise.sh`
  still refuses a second supervisor and `control.sh` a second app. A stale
  pidfile left by an abrupt `wsl --shutdown` names a dead pid and is ignored, so
  the next launch starts clean — repeated setup or a retried start never
  double-runs anything.
- **Stopping.** `wsl-keeper.sh stop` (or a `SIGTERM` to `run` — Task Scheduler's
  "End task") stops the keeper, and with it the supervisor it started and the
  app. A keeper that only *adopted* an operator-started supervisor leaves it
  running. A clean stop stays stopped; only a non-zero exit (a crash, or
  `wsl.exe` returning after `wsl --shutdown`) is auto-restarted.
- **Diagnostics.** `wsl-keeper.sh status` prints the keeper state, the tail of
  the keeper log (`RECIPE_DEPLOY_RUNTIME_DIR/recipe-keeper.log` — one heartbeat
  line while healthy, a line whenever it re-launches the supervisor), then
  `deploy/supervise.sh status` (whose exit code — `3` when the app is stopped —
  is the command's exit code). Supervisor and app logs are unchanged
  (`recipe-supervisor.log`, `recipe.log`).

**Run it unattended — Windows Task Scheduler.** From an
elevated-not-required PowerShell on the Windows host:

```powershell
.\deploy\windows\register-keeper-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe
# options: -TaskName RecipeAppWslKeeper  -RepetitionMinutes 5  -LogonType S4U|Password
.\deploy\windows\register-keeper-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -Unregister
.\deploy\windows\register-keeper-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -ShowCommand
```

- Registers a task whose action is
  `wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh run`.
- **Independent of a dev shell.** Principal `LogonType S4U` (no stored
  password); triggers are **AtLogOn** for the invoking user plus a **5-minute
  repetition that runs indefinitely**. The repetition is the recovery path
  after a controlled `wsl --shutdown` while you stay logged in — within five
  minutes the task re-runs, WSL boots, and the keeper restores the supervisor
  and app. `MultipleInstances IgnoreNew` makes a tick a no-op while the keeper
  is up.
- **Restart on failure.** `wsl.exe` exiting non-zero (e.g. after
  `wsl --shutdown`) restarts the action after 1 minute, up to 999 times.
  `ExecutionTimeLimit` is 0 — the keeper runs forever.
- **Idempotent.** Re-running replaces the task of the same name (`-Force`) —
  repeated setup never leaves a second keeper.
- **Verify:** `Start-ScheduledTask -TaskName RecipeAppWslKeeper`, then
  `wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh status` shows the
  keeper running and the app healthy. `Get-ScheduledTaskInfo` shows
  `LastTaskResult` / `NextRunTime`.

**Host power — this task cannot serve a sleeping machine.** The task starts and
keeps running on battery and is not stopped when the machine leaves idle, but
sleep/hibernate still stops everything (spec item 24). Configure the host to
stay awake during expected availability, e.g. on AC power:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
# a laptop also needs Settings > System > Power > "lid close action" = Do nothing (plugged in)
```

**Diagnosis.**

- App unreachable, `wsl-keeper.sh status` says `keeper : stopped` — the task did
  not run or exited. Check `Get-ScheduledTaskInfo -TaskName RecipeAppWslKeeper`
  (`LastRunTime` / `LastTaskResult`), that it is Enabled, and run
  `wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh status`
  (`-ShowCommand`) by hand. `LastTaskResult` non-zero with the task Running
  again is the restart-on-failure loop — read `recipe-keeper.log` /
  `recipe.log` for why the keeper or app will not stay up.
- `keeper : running` but the app is down — this is a supervisor/app fault, not a
  lifetime one. `recipe-keeper.log` shows the re-launch attempts; drop to
  runbook 16's diagnosis (`recipe-supervisor.log`, then `recipe.log` — bad
  build, port in use).
- Access lost after the machine was idle — check it did not sleep (the powercfg
  settings above); the task itself is not idle-stopped.
- Recovery after a `wsl --shutdown` is taking minutes — expected: the 1-minute
  restart-on-failure and the 5-minute repetition are the recovery paths while
  logged in. Lower `-RepetitionMinutes` if you need it tighter.

`backend/tests/test_deploy.py` covers the mechanism deterministically in the
`backend` CI job: `wsl-keeper.sh run` holds the app up and a `SIGTERM` takes the
keeper, supervisor, and app down together; a second `run` is refused and
duplicates nothing; a terminated supervisor is re-launched on the next
heartbeat and adopts the still-running app rather than starting a second one;
and `stop` is clean when nothing is up. The actual `wsl.exe` invocation, the
Windows task and its power settings, closing the IDE/terminals and idling, and
recovery across a real `wsl --shutdown` are the actual-host acceptance gate —
results recorded in
`.scratch/private-household-deployment/host-acceptance-06b.md`.

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
