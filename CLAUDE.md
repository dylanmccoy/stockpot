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

There is no linter configured. Local dev needs two terminals: backend and frontend.

## Architecture

Two independent apps in one repo; the only contract between them is the JSON HTTP API under `/api`.

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

Vite + React 18 + TS, strict mode, no router, no state library.

- `types.ts` — hand-maintained mirror of the backend Pydantic schemas. Keep in sync when the API changes.
- `api.ts` — the single `fetch` wrapper (`api.list/create/remove`). All network access goes through here; it throws on non-2xx and handles 204. Calls are same-origin `/api/...` — the Vite dev proxy (`vite.config.ts`) forwards to the backend, so no base URL or CORS in dev.
- `App.tsx` — the whole UI: local `useState`, `refresh()` re-fetches the list after every mutation. New screens/components hang off here.

`tsconfig.json` is a solution file referencing `tsconfig.app.json` (src) and `tsconfig.node.json` (vite config).
