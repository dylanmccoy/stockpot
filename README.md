# Recipe App

Barebones full-stack scaffold: FastAPI + SQLAlchemy + SQLite backend, React + TypeScript (Vite) frontend.

## Layout

- `backend/` — FastAPI app (`app/`), pytest suite (`tests/`), managed with `uv`.
- `frontend/` — Vite + React + TypeScript SPA, managed with `npm`.

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
```

Run the backend and frontend in separate terminals during development.

## API

`/api/health` and CRUD under `/api/recipes` (`GET`, `POST`, `GET/{id}`, `PUT/{id}`, `DELETE/{id}`).
