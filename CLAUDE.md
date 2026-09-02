# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication style

Responses have been too dense to parse quickly — long paragraphs and deep
nesting that bury the actual answer. Fix, without dropping precision:

- **Lead with the answer.** First 1–3 sentences (or a short table) state the
  outcome/conclusion. Supporting detail follows — never make the reader parse
  a paragraph to find the point.
- **Prefer lists and tables to prose.** If a sentence has more than one
  clause of justification or more than one item, it's probably a bullet list.
- **One idea per line.** Avoid stacking qualifiers/parentheticals into a
  single dense sentence — split them into short sentences or sub-bullets.
- **Rationale gets a clause, not a paragraph**, unless the user asks "why" or
  is choosing between options. State *what*, only elaborate *why* on request
  or when it changes a decision.
- **For multi-part work** (a plan, a multi-file change, several findings):
  give a one-line summary per part first (e.g. a table), then full detail
  underneath or on request — don't make the summary and the detail the same
  wall of text.
- Keep all the technical specifics (exact names, numbers, edge cases) — cut
  redundant framing and throat-clearing, not information.

## Commands

All backend commands run from `backend/`; all frontend commands from `frontend/`.

| Task | Command |
| --- | --- |
| Install backend deps | `uv sync` |
| Run backend (dev) | `uv run uvicorn app.main:app --reload` (serves on :8000, OpenAPI at `/docs`) |
| Run all backend tests | `uv run pytest` |
| Run one backend test | `uv run pytest tests/test_recipes.py::test_create_and_list_recipe` |
| Add a backend dep | `uv add <pkg>` (runtime) / `uv add --dev <pkg>` (dev) |
| Install frontend deps | `npm install` |
| Run frontend (dev) | `npm run dev` (serves on :5173, proxies `/api` → `:8000`) |
| Type-check + build frontend | `npm run build` |
| Type-check only | `npm run typecheck` |
| Lint frontend | `npm run lint` (ESLint; `.eslintrc.cjs`) |
| Format frontend | `npm run format` / check with `npm run format:check` (Prettier) |
| Run frontend tests | `npm run test:run` (Vitest + MSW) |

Local dev needs two terminals: backend and frontend.

## Architecture

Two independent apps in one repo; the only contract between them is the JSON HTTP API under `/api`.

**Doc partition.** Backend v1 planning lives in `docs/` (`spec.md`, `plan.md`, `phases/`, `issues.md`, `decisions.md`, `features.md`). Frontend planning lives in `docs/frontend/` and is **not backend implementation authority** — a backend phase must not read it as a requirement source or edit it (`docs/plan.md` §"Phase scope fence"). Frontend work reads `docs/spec.md` as the contract.

### Backend (`backend/app/`)

Layered, import direction is one-way: `config` → `database` → `models` → `schemas`/`routers` → `main`.

- `config.py` — `Settings` (pydantic-settings). All config comes from `RECIPE_`-prefixed env vars or `backend/.env`; `database_url` and `cors_origins` are the knobs.
- `database.py` — the SQLAlchemy `engine`, `SessionLocal`, the `Base` declarative class, and the `get_db()` FastAPI dependency (yields a session, always closes it). SQLite gets `check_same_thread=False`.
- `models.py` — ORM tables (`Base` subclasses, SQLAlchemy 2.0 `Mapped[...]` style).
- `schemas.py` — Pydantic request/response models. `RecipeRead` uses `from_attributes=True` to serialize ORM objects directly.
- `routers/` — one `APIRouter` per resource, each carrying its own path prefix (`/api/recipes`). Register new routers in `main.py` via `app.include_router(...)`.
- `main.py` — builds the `FastAPI` app, adds CORS, includes routers. **Schema management is a lifespan `Base.metadata.create_all()` call** — there are no migrations. Changing a model requires deleting `recipe.db` (or adding Alembic).

Endpoints depend on `get_db` via `Depends`; handlers commit explicitly and `db.refresh()` before returning. Missing rows raise `HTTPException(404)`.

### Backend tests (`backend/tests/`)

pytest + FastAPI `TestClient` (httpx under the hood). `conftest.py`'s `client` fixture is the seam: it builds a fresh in-memory SQLite DB (`StaticPool`) per test, overrides `get_db` through `app.dependency_overrides`, and tears the schema down after. Tests exercise the app through real HTTP calls — no direct DB access. Every test that touches the DB takes the `client` fixture.

### Frontend (`frontend/src/`)

Vite + React 18 + TS strict, `react-router-dom` v6 (classic component routing),
TanStack Query for all server state, CSS Modules + a token layer, MSW for tests.
The normative contract is `docs/frontend/spec.md` (§1 has the module layout);
delivery is phased in `docs/frontend/plan.md` (Phases 0–8). Being built
**mock-first** against MSW and wired to real endpoints as each backend phase lands.

Import direction is one-way: `types → lib → api/client → api/<resource> →
components → pages → app`. Key modules:

- `types.ts` — hand-maintained mirror of `docs/spec.md` §5 (R-1). Update it and
  `docs/frontend/spec.md` §5 together when the API changes.
- `api/client.ts` — the one `fetch` wrapper: `/api` prefix, `Authorization:
  Bearer` from `localStorage`, normalizes both FastAPI error shapes to a thrown
  `ApiError`, handles 204, fires a 401 seam. Same-origin `/api/...` via the Vite
  dev proxy — no base URL or CORS in dev.
- `api/{auth,recipes,inventory,cookLogs,grocery}.ts` — thin typed adapters (R-2).
- `auth/` — `AuthProvider` + `useAuth` (+ `context.ts`): token in `localStorage`
  under `recipe.token`, login/logout, `me` hydration, cache drop on 401.
- `app/` — `router.tsx` (`<Routes>` table), `AppShell.tsx` (responsive nav),
  `RequireAuth.tsx` (→ `/login?next=`).
- `lib/` — pure leaf helpers (`parseIngredients`, `format`, `apiError`) under a
  locked-oracle gate (`docs/frontend/plan.md`).
- `test/` — MSW `server.ts` + `handlers.ts` (happy path per `docs/spec.md` §5) +
  `errorHandlers.ts` (one per `docs/frontend/spec.md` §6 row), wired into
  `setupTests.ts` with `onUnhandledRequest: "error"`.

`tsconfig.json` is a solution file referencing `tsconfig.app.json` (src) and
`tsconfig.node.json` (vite config). `npm run lint` (ESLint + Prettier) joins
`test:run` and `build` in CI.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root (created lazily by `/domain-modeling`). See `docs/agents/domain.md`.
