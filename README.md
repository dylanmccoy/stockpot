# Recipe App

Barebones full-stack scaffold: FastAPI + SQLAlchemy + SQLite backend, React + TypeScript (Vite) frontend.

> **Direction:** `docs/plan.md` holds the approved implementation plan — a backend-only
> v1 for a household recipe keeper + food-inventory tracker (structured recipes,
> unit-aware inventory netting, cook-deducts-stock, grocery lists, URL import, token
> auth), built in phases. The scaffold below is the starting point for that work.

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
uv sync                        # install deps into .venv
uv run uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
uv run pytest                  # run tests
```

Tables are auto-created on startup. Config is read from environment variables
prefixed with `RECIPE_` (see `backend/.env.example`).

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api -> http://localhost:8000
npm run build      # type-check + production build
npm run typecheck
npm test           # vitest (watch);  npm run test:run for one-shot
```

Run the backend and frontend in separate terminals during development.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:
the backend `pytest` suite and the frontend `vitest` suite + production build.

## API

`/api/health` and CRUD under `/api/recipes` (`GET`, `POST`, `GET/{id}`, `PUT/{id}`, `DELETE/{id}`).
