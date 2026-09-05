# backend/CLAUDE.md

Layered FastAPI app. Import direction is one-way:
`config → database → models → schemas/routers → main`.
Full architecture and the command table are in the root `CLAUDE.md`; this file is
the navigation map that keeps each `/implement` inside the smart zone.

## Read only what the ticket cites

`docs/spec.md` is ~1700 lines. Do **not** read it whole. Every feature area maps
to 2–3 sections and one test file — read those, nothing else. The ticket's
**Spec:** field names the exact anchors.

To read one section: `grep -nE '^#{1,6} ' docs/spec.md` for the line-numbered
heading list, then `Read` with `offset`/`limit` bounded to the cited section.

| Area | `docs/spec.md` §§ | Test file |
| --- | --- | --- |
| `normalize.py` (food-name canonicalization) | 2.1 | `tests/test_normalize.py` |
| `units.py` (unit tokens, buckets, to/from base, `Quantity`) | 2.2 | `tests/test_units.py` |
| `services/ingredient_parse.py` (pasted line → structured) | 2.3 | `tests/test_ingredient_parse.py` |
| `config.py` / `database.py` / `main.py` / `security.py` | 3.1–3.4 | `tests/test_config.py`, `test_engine_listeners.py`, `test_exception_handlers.py` |
| `services/inventory_math.py` — `aggregate`, `check_availability`, `generate_lines`, `add_to_inventory_calc`, `deduct_calc` | 4, 4.1–4.5 | `tests/test_inventory_math.py` |
| Auth API (`routers/auth.py`) | 5.1 | `tests/test_auth.py` |
| Recipes CRUD (`routers/recipes.py`) | 5.2 | `tests/test_recipes.py` |
| Availability endpoint | 5.3 | `tests/test_recipes.py` |
| Cook + made-history | 5.4 | `tests/test_recipes.py`, `tests/test_cook_logs.py` |
| Inventory API (`routers/inventory.py`) | 5.5 + §1 "inventory_items" | `tests/test_inventory.py` |
| Grocery API (`routers/grocery.py`) | 5.6 + §1 "grocery_*" | `tests/test_grocery.py` |
| Concurrency / transactions | 6 | `tests/test_transactions.py`, `tests/test_concurrency.py` |
| Locked contract oracles (R-7) | 7 "Locked contract oracles" | per oracle-lock ticket |

All data-model tables live in `docs/spec.md` §1. Phase checkboxes to tick on
close: `docs/phases/phase-N.md`. Ticket dependency order and the R-7 rules:
`.scratch/backend-v1/issues/README.md`.

## File map (`backend/app/`)

| File | Responsibility |
| --- | --- |
| `config.py` | `Settings` (pydantic-settings). All config from `RECIPE_`-prefixed env / `backend/.env`. Knobs: `database_url`, `cors_origins`, `frontend_dist`. |
| `database.py` | `engine`, `SessionLocal`, `Base`, `get_db()` dependency. SQLite → `check_same_thread=False`. No module-level session. |
| `models.py` | Every ORM table (SQLAlchemy 2.0 `Mapped[...]`). |
| `normalize.py` | Pure: food-name normalization. |
| `units.py` | Pure: `normalize_unit_token`, `bucket_of`, `to_base`/`from_base`, `Quantity`. |
| `security.py` | Password hashing, session-token mint/verify, `get_current_user`. |
| `backup.py` | `create_backup()` — live SQLite snapshot via the online backup API (private-household-deployment ticket 02a). CLI wrapper: `scripts/backup.py`. |
| `schemas/` | Pydantic request/response models, one module per resource, re-exported from `schemas/__init__.py`. `*Read` uses `from_attributes=True`. |
| `routers/` | One `APIRouter` per resource, each with its own `/api/<x>` prefix. Register in `main.py` via `app.include_router(...)`. |
| `services/ingredient_parse.py` | Pure: pasted-line → structured ingredient. |
| `services/inventory_math.py` | Pure calc layer for inventory / availability / grocery / cook (spec §4). |
| `main.py` | Builds the `FastAPI` app, CORS, `include_router`; opt-in built-frontend serving when `Settings.frontend_dist` is set (`_mount_frontend`: entry doc + assets in ticket 01a, client-side-route fallback in 01b). Schema = a lifespan `Base.metadata.create_all()` — no migrations. |

## Invariants agents keep re-deriving

- **No migrations.** Any `models.py` change → delete `backend/recipe.db` before the run.
- Mutating routers carry `route_class=TransactionRoute` and `Depends(get_current_user)`.
  The `tests/test_transactions.py` route-class guard must stay green.
- Handlers commit explicitly, then `db.refresh()` before returning. Missing row → `HTTPException(404)`.
- `TransactionRoute` owns the commit; `get_db` owns session lifetime. A Core
  `UPDATE` does **not** fire the ORM `onupdate` — bind `_utcnow()` explicitly.
- The three R-7 oracle-lock tickets (`phase-4a`, `-5a`, `-6a`) deliver an
  **accepted, locked, non-green** black-box suite. They do not go green. Every
  other ticket ends `cd backend && uv run pytest` green.
- `docs/spec.md` is edited only via a paired spec+test change when a locked
  oracle proves it wrong (`docs/plan.md` §Independent contract-test gate).
- Do not read `docs/frontend/` — it is not backend implementation authority
  (`docs/plan.md` §"Phase scope fence").

## Commands

Full table in root `CLAUDE.md`. From `backend/`: `uv run pytest` (all),
`uv run pytest tests/test_inventory.py::test_name` (one).
