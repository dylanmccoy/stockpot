# CLAUDE.md

## Communication style

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
| Run browser E2E / visual tests | `npm run test:e2e` (Playwright; boots the dev server itself — Vite only, no backend) |
| Run auth integration E2E vs real backend | `npm run test:integration` (needs `uv` on PATH; `playwright.integration.config.ts` boots an isolated throwaway-DB backend + Vite on dedicated ports) |
| Update visual baselines | `npm run test:e2e:update` (regenerate on the same OS CI uses) |
| One-time Playwright browser setup | `npx playwright install --with-deps chromium` (the `--with-deps` half needs root) |

Local dev needs two terminals: backend and frontend.

## Architecture

Two independent apps in one repo; the only contract between them is the JSON HTTP
API under `/api`.

**Per-area maps.** `backend/CLAUDE.md` and `frontend/CLAUDE.md` are the navigation
maps for each app: file map, the feature-area → spec-section → test-file table, and
the invariants agents keep re-deriving. Read the one for the app you're working in
before opening spec files, and let each ticket's **Files:** / **Spec:** / **Tests:**
header point you at the exact sections.

- **Backend** (`backend/app/`) — layered FastAPI, one-way imports
  `config → database → models → schemas/routers → main`. Mutating routers use
  `route_class=TransactionRoute`, which owns the commit; `get_db` only owns
  session lifetime — handlers commit nothing themselves. Tests wire the app
  via `create_app(test_settings, test_engine)`, the only test-database seam
  (real HTTP through `TestClient`, no dependency overrides). No migrations:
  schema is a lifespan `Base.metadata.create_all()`, so a `models.py` change
  means deleting `backend/recipe.db` — see root `README.md` "Operating the
  server" for the full backup/reset/restore procedure.
- **Frontend** (`frontend/src/`) — Vite + React 18 + TS strict, `react-router-dom`
  v6, TanStack Query for all server state, CSS Modules + a token layer, MSW for
  tests. Built mock-first against MSW, wired to real endpoints as each backend
  phase lands.

**Doc partition.**

- Backend v1 planning lives in `docs/` (`spec.md`, `plan.md`, `phases/`,
  `issues.md`, `decisions.md`, `features.md`).
- Frontend planning lives in `docs/frontend/` and is **not backend implementation
  authority** — a backend phase must not read it as a requirement source or edit
  it (`docs/plan.md` §"Phase scope fence").
- Frontend work reads `docs/spec.md` as the contract.

## Agent skills

- **Issue tracker** — issues and specs as markdown files under
  `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.
- **Triage labels** — five canonical roles, each label string equal to its name.
  See `docs/agents/triage-labels.md`.
- **Domain docs** — one `CONTEXT.md` + `docs/adr/` at the repo root, created
  lazily by `/domain-modeling`. See `docs/agents/domain.md`.
