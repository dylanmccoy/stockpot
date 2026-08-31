# Features & Roadmap

See `docs/plan.md` for the v1 backend scope (what is shipped). This file
documents deferred capabilities, infrastructure decisions pending v1 scope
expansion, design invariants that extensions must preserve, and features
rejected outright.

**v1 was de-scoped on 2026-08-31** to the core cooking loop only. Five features
that an earlier revision of the plan carried — photo upload, URL import, recipe
research, per-cook reviews, grocery-receipt OCR — moved to v2. Their
execution-ready specs live in `docs/plan.md` §"Deferred to v2"; the pre-trim
plan and its 22 review findings are archived at `git show 5144c25:docs/plan.md`.
This file tracks them under **Deferred to v2** below and does not duplicate the
detail — `plan.md` is authoritative for the v1↔v2 boundary.

**Project:** [github.com/dylanmccoy/stockpot](https://github.com/dylanmccoy/stockpot) (public repo)

**Status:** v1 plan approved & implementation-ready (9-phase build, see `plan.md` §Build sequence). Backend-only: auth, structured recipes, inventory, availability checks, cook-deducts, grocery-list submit, unit conversion (pure). Frontend deferred to later effort.

## What v1 actually ships

Auth (opaque sessions, registration default-off) · structured recipes + nested
ingredient rows · inventory with `(match_name, unit_bucket)` identity ·
`GET /availability` missing-ingredient check · cook = deduct + `CookLog` (both
`deduct` modes) · per-recipe and global cook-log reads · grocery-list generation
(netted against stock) + `POST /submit` (adds checked lines to inventory) · pure
unit-conversion module. 8 build phases (9 with docs). No file uploads, no outbound HTTP, no
OCR.

## What's discussed but not in v1 (deferred or different scope)

| Item | Status | Where it lives |
| --- | --- | --- |
| **Frontend (React SPA)** | Discussed in detail; separate later effort | `docs/features.md` §Deferred features — pages, auth, routing outlined |
| **URL recipe import** | Phase 7 code is backend-ready (in `plan.md`); not shipped in v1 | `docs/plan.md` §URL import approach; backend-ready but user chose backend-only v1 |
| **Photo upload** | Full spec drafted; de-scoped from v1 on 2026-08-31 | `git show 5144c25:docs/plan.md` §Photo upload; `features.md` §Deferred to v2 |
| **Recipe research (URL batch)** | Full spec drafted; depends on URL import; v2 | `git show 5144c25:docs/plan.md` §Recipe research; `features.md` §Deferred to v2 |
| **Per-cook reviews** | Full spec drafted; de-scoped from v1 | `git show 5144c25:docs/plan.md` §Per-cook reviews; `features.md` §Deferred to v2 |
| **Grocery-receipt OCR** | Full spec drafted; highest cost; de-scoped from v1 | `git show 5144c25:docs/plan.md` §Grocery-receipt OCR; `features.md` §Deferred to v2 |
| **Web search query mode** | Outlined; depends on URL import; post-v2 | `docs/features.md` §Recipe research — free-text query mode |

The pre-trim plan at `git show 5144c25:docs/plan.md` (1117 lines, with 22 adversarial-review findings) carries the full execution-ready spec for all five de-scoped features — nothing is lost, only deferred.

## Standing v1 constraints

All future work must preserve these choices:

- **LAN-only, no remote hosting yet** — no in-app HTTPS, no email, no third-party IdP.
- **SQLite + no migrations** — `create_all()` on startup; data loss on schema
  change. Alembic is the next infrastructure step after v1's first schema
  change (see Deferred, **Migrations**).
- **Single full-trust household** — `created_by_id` is attribution only; every
  authed user can read/write all data. Multi-user / per-resource authz is a
  later upgrade.
- **No LLM / AI services** — when research and receipt parsing land in v2 they
  stay pure heuristics.
- **No live network in tests** — v1 makes no outbound calls at all. When
  `fetch_bytes` (URL import + research) and `_ocr_image` (receipt OCR) arrive in
  v2 they are the only network/subprocess seams, both mocked offline.

## Deferred to v2 (carried by the pre-trim plan, cut 2026-08-31)

Full spec for each is in `docs/plan.md` §"Deferred to v2". Summary + why-deferred
only here.

| Feature | Hook already in v1 | Why deferred |
| --- | --- | --- |
| **Photo upload** | `recipes.photo_path` is a reserved nullable column | Isolated and low-risk, but not part of the cooking loop; adds `python-multipart` + a StaticFiles mount + an upload dir |
| **URL import** (`POST /api/recipes/import`) | `recipe_ingredients.raw_text` is a reserved nullable column | Clean fast-follow (`recipe-scrapers` does the parsing), but out of the smallest v1; brings `recipe-scrapers`, promotes `httpx` to runtime, and needs the SSRF-guarded `fetch_bytes` |
| **Recipe research** (`POST /api/research/compare`, URL-batch) | none needed — computed per request, no table | Depends on URL import's `fetch_bytes` + `scrape_preview`; not part of the cook-at-home loop |
| **Per-cook reviews** | `cook_logs` already carries the FK target a review attaches to | Pleasant, not friction-reducing; additive `recipe_reviews` table + `CookEventMini` nesting on `RecipeRead` |
| **Grocery-receipt OCR** (`/api/receipts`) | `add_to_inventory` (the upsert `submit`/`cook` share) is the apply target | Highest cost, most tangential: a `tesseract-ocr` system package, `pytesseract` + `Pillow`, decompression-bomb guards, a process semaphore, private file storage + an auth'd `FileResponse` route, a non-mocked CI smoke test |

### Recipe research — free-text `query` mode (v2+, after URL-batch research lands)

- **v1 status:** excluded (whole research feature is v2).
- **v2 status (planned):** `/api/research/compare` ships URL-batch only.
- **Hook (arrives with URL import in v2):** `fetch_bytes(url, ...)` —
  SSRF-guarded, scheme + resolved-IP blocklist, byte cap, content-type check, no
  redirects; `scrape_preview(html, url)` parses HTML → `RecipeImportPreview`.
- **Work to add on top:**
  - **Service:** `services/web_search.py` — take `query: str` + optional
    `provider: str`, call the search API (Brave Search, Bing, Vertex AI Search —
    Google Custom Search JSON API is closed to new customers and ends
    2027-01-01), return result URLs. One `httpx` call through `fetch_bytes`, same
    SSRF guard. No SDK bundling.
  - **Router:** `POST /api/research/compare` gains optional `query: str`; if
    present, resolve to URLs via `web_search`, then batch-scrape as normal.
    Search failures → land in `failed` or return 502 (implementation choice).
  - **Config:** `RECIPE_WEB_SEARCH_PROVIDER` (default empty/off) and
    `RECIPE_WEB_SEARCH_KEY` (env var).

## v1 build sequence

The backend is built in 9 phases, each ending with `uv run pytest` green:

1. **Phase 0 — reset & deps:** add new dependencies (`recipe-scrapers`, `pwdlib[argon2]`, `python-multipart`, `httpx`), delete old `recipe.db`.
2. **Phase 1 — pure core:** `normalize.py`, `units.py`, ingredient parser + tests (no HTTP).
3. **Phase 2 — auth:** User/Session models, bearer-token login, `auth.py` router, gating. Tests: 401 on missing token.
4. **Phase 3 — structured recipes + photo:** Replace flat `ingredients`/`instructions` with `RecipeIngredient` child table (qty/unit/item/note) + JSON `steps/tags`. Photo upload to `/uploads/`. Tests expand.
5. **Phase 4 — inventory + availability:** `InventoryItem` CRUD, `check_availability` service for per-ingredient status (ok/short/missing/to_taste/have_uncertain). Tests: netting + unit conversion.
6. **Phase 5 — cook deducts stock:** `POST /api/recipes/{id}/cook` + `CookLog` audit trail. Deduction is one-shot (no unwind). Tests: clamp at 0, unit mismatches reported.
7. **Phase 6 — grocery lists:** `GroceryList` + `GroceryListItem` tables. `POST /api/grocery` generates from hand-picked recipes, netted against stock. `POST /api/grocery/{id}/submit` adds checked lines to inventory (one-shot, frozen after). Tests: consolidation, netting, idempotency.
8. **Phase 7 — URL import** (backend-ready, not v1): `services/import_recipe.py` wraps `recipe-scrapers`, lightweight ingredient-string parser. Tests: monkeypatched fetch (no live HTTP).
9. **Phase 8 — docs:** README, CLAUDE.md, `.env.example` updated (new vars, `rm recipe.db` procedure, API surface).

Each phase is independently testable and independently pushable. Phase 7 (URL import) is backend-ready code but not shipped in v1. See `docs/plan.md` §Build sequence for full pseudocode and migration steps.

## Deferred features (post-v2)

| Feature | v1 status | Hook already in place | Work to add |
| --- | --- | --- | --- |
| "What can we make now" | Excluded | `check_availability` exists; runs on one recipe | `GET /api/recipes/makeable` — run it across all, filter `all_available` |
| Staples / low-stock alerts | Excluded | `inventory_items` row structure | `is_staple: bool` + `min_quantity: float` columns; `GET /api/inventory/low` |
| Undo for forward-only actions | Excluded | `CookLog.deductions` (requested/deducted/before/after) and `GroceryListItem.applied_quantity/unit` snapshot what was applied; `ReceiptItem.applied_quantity/unit` joins them once receipt OCR lands | One uniform reverse-apply op across cook + grocery (+ receipt in v2); no per-action `/undo` route until designed |
| Frontend (React SPA) | Excluded; v1 backend only | Skeleton in place (`App.tsx` / `api.ts` / `types.ts`); **does not work against v1 API** and was left untouched | `react-router-dom` + pages; auth.tsx + bearer-token injection in api.ts; mirror types.ts to v1 schemas |

### "What can we make now"

- **v1 status:** excluded.
- **Hook in v1:** `services/inventory_math.check_availability(recipe, multiplier)` computes
  per-ingredient `{ok, short, missing, to_taste, have_uncertain}`; the report
  includes `all_available: bool`.
- **Work to add:** `GET /api/recipes/makeable` in `routers/recipes.py` (or new
  `routers/queries.py` for read-heavy exploratory endpoints). Aggregate
  `check_availability` across all recipes, return `{makeable: [Recipe], count}`.
  No schema change. Optional: add pagination + filtering (cuisine, tag).

### Staples / low-stock alerts

- **v1 status:** excluded; data model accommodates.
- **Hook in v1:** `inventory_items` table; `CHECK(quantity >= 0)` constraint;
  `updated_at` timestamp.
- **Work to add:**
  - **Schema:** add `is_staple: Mapped[bool] = mapped_column(default=False)` and
    `min_quantity: Mapped[float | None]` (finite, ge=0) to `inventory_items`.
    **First real schema change after v1** — pairs with Alembic upgrade.
  - **Endpoint:** `GET /api/inventory/low` → `{items: [InventoryItemRead], count}`.
    Filter to rows where `is_staple=true and quantity < min_quantity` (per
    `unit_bucket`). Optional: return staleness (days since `updated_at`).
  - **UI future:** mark staple items in the inventory view; surface low-stock
    items on the main page.

### Undo for forward-only actions

- **v1 status:** cook and grocery `submit` are one-shot and forward-only (no
  uncheck-reversal, no unsubmit, no uncook). Receipt `apply` joins them in v2.
- **Hook in v1:** Each already snapshots the actual applied state:
  - `CookLog.deductions[]` → each item records `{requested, deducted, before,
    after, reason}`.
  - `GroceryListItem.applied_quantity`, `applied_unit`, `submitted_at`.
  - (v2) `ReceiptItem.applied_quantity`, `applied_unit`.
- **Work to add:** One uniform reverse operation across all of them. Data is
  present to undo: add back the `deducted`/`applied_quantity` to the respective
  inventory row. Design as a single feature, not separate routes. Consider a
  mutation-event audit trail (who reversed it, when) before implementing.

### Frontend (React SPA)

- **v1 status:** backend-only; v1 does not include a frontend.
- **Hook in v1:** Schema definitions (Pydantic in backend) must be hand-mirrored
  to `frontend/src/types.ts` (constraint: keep it manual, not auto-generated).
  Existing `App.tsx` / `api.ts` / `types.ts` were left untouched; they do **not**
  work against v1's API.
- **Work to add:**
  - **Auth:** `auth.tsx` (Login page; register + login forms; session storage for
    bearer token), `RequireAuth` wrapper.
  - **API layer:** `api.ts` → update to inject `Authorization: Bearer <token>`
    header; namespace endpoints by resource.
  - **Pages (v1 backend):** Login, RecipeList (search/filter/sort + multi-select
    to create grocery list), RecipeDetail (ingredient table with availability
    status, multiplier control, "mark as cooked" + deduct/no-deduct toggle,
    made-history), RecipeForm (dynamic ingredient rows), Inventory (CRUD +
    match-name editor), GroceryLists (check/uncheck lines, submit, view applied
    state).
  - **Pages (need v2 backend):** import-from-URL + photo upload in RecipeForm;
    review form + nested past reviews in RecipeDetail; ReceiptUpload (photo →
    OCR preview → edit → apply); Research (URL batch → ingredient-frequency
    table).
  - **Routing:** `react-router-dom`; `/` → Login or RecipeList (guarded);
    `/recipes`, `/recipes/:id`, `/recipes/new`, `/inventory`, `/groceries`
    (`/receipts`, `/research` with v2).
  - **Vite dev proxy:** already forwards `/api` → `:8000`; add a `/uploads`
    forward when photo upload lands (read-only recipe photos).
  - **Build:** TypeScript strict mode; `npm run build` → production bundle.
  - **Tests:** mirror backend patterns — `api` fetch wrapper under test via
    fetch mock / `msw` / plain stubs.

## Excluded by design (not deferred)

### Meal planning

- **What it would be:** a calendar / planner view; mark recipes for specific
  dates; aggregated shopping list across multiple days.
- **Why excluded:** v1's organizing idea is "make *this* recipe now" — a
  transactional, not a planning, model. The data model has no plan/calendar
  entity and was not shaped for temporal aggregation. Adding it is a
  product-direction change, not a backward-compatible extension.
- **If reconsidered later:** start with a requirements pass (how far ahead?
  weekly/monthly/seasonal cycles? shopping coordination?), not a v1 data-model
  hack. It may be a new subsystem, not a table addition.

## Infrastructure deferrals

### Migrations (Alembic)

- **v1 approach:** `create_all()` + manual `rm recipe.db` on schema change (data
  loss; acceptable when recipes are few).
- **Cost of adding now:** new dependency (`alembic`) + `alembic/` folder +
  `env.py` wired to `Base.metadata` + `alembic.ini` + autogenerate review per
  change (SQLite batch mode; autogenerate has gaps) + CI step for migration
  testing + documentation. Complexity for a non-existent problem.
- **When to add:** **at the first schema change after v1 is done**, once there
  are recipes worth not losing. Likely trigger: Staples feature (requires
  `inventory_items` schema change). Cost-benefit flips when data loss is
  unacceptable.
- **Path:** Add `alembic` dependency + autogenerate a base migration from the
  current `Base.metadata`. Then adopt `alembic migrate` for each subsequent
  change. No changes to the app factory or runtime — `create_all()` remains the
  app-startup step (idempotent for dev, and idempotent for prod once the base
  migration is applied).

### Multi-user / per-user ownership / membership

- **v1 approach:** single full-trust household. Every authed user has read/write
  access to all data. `created_by_id` on every table is attribution only (who
  made the recipe, cooked it, added the note).
- **Upgrade path:** Add a `users.household_role` field (or a separate
  `household_members` table) with roles (admin, editor, viewer). Add authz
  checks to every data endpoint: `current_user.household_role >=
  required_role_for_this_op`. Per-resource ownership is not needed (household is
  the unit of ownership). Foreign keys `created_by_id` already exist on every
  table; no new schema required for baseline multi-user.
- **Why deferred:** adds endpoint complexity per router (check membership +
  role). v1 stays simpler; one household works for the initial release.

### Transport security & remote hosting (HTTPS / TLS)

- **v1 approach:** LAN-only. Token auth via `Authorization: Bearer <token>`
  header (not cookies, so no CSRF protection needed for LAN). No in-app HTTPS;
  docs at `/docs` (no auth). v1 serves no files at all. When photo upload lands
  in v2, recipe photos are public at `/uploads` (LAN-safe, not sensitive) and
  receipt images stay private behind an auth'd route.
- **Upgrade path (for remote hosting):** Put a reverse proxy (nginx, Caddy,
  Cloudflare Tunnel, …) in front of the app; it handles HTTPS + TLS termination
  + redirects HTTP → HTTPS. The app sees `X-Forwarded-Proto: https` and can
  trust it (configure the proxy). Update docs to note the proxy requirement and
  link to a HTTPS setup guide.
- **Registration on remote:** if the app is exposed to the internet, set
  `RECIPE_ALLOW_REGISTRATION=false` (default) to close the registration window,
  or set `RECIPE_ALLOW_REGISTRATION=true` + a strong `RECIPE_REGISTRATION_CODE`
  and keep the window brief. Email confirmation is out of scope (no LLM / AI,
  and no email service integration). Single-use registration codes (time-limited)
  are a future refinement.
- **Why deferred:** adds proxy complexity + docs. v1 is self-hosted on LAN;
  remote + public internet is a separate operational decision, not a code feature.

### Postgres / non-SQLite databases

- **v1 approach:** SQLite. `settings.database_url` is the single knob; dev/test
  use an in-memory database.
- **Blockers to Postgres:** SQLite-specific code in a few places:
  - `database.py`: `connect_args={"check_same_thread": False}` (SQLite only);
    connect-time PRAGMAs (`foreign_keys=ON`, `busy_timeout`); Postgres would use
    `psycopg` + different connect config.
  - `services/inventory_math.py`: `add_to_inventory` uses SQL `INSERT … ON
    CONFLICT (match_name, unit_bucket) DO UPDATE SET quantity = quantity + …`
    (SQLite upsert syntax). Postgres has `ON CONFLICT … DO UPDATE` too, but the
    semantics differ slightly; needs review.
  - `tests/conftest.py`: `StaticPool` for in-memory test DB is SQLite-specific;
    Postgres in-memory is not standard (would use Docker container or a real
    test database).
- **Path if needed:** After Alembic is in place (needed for Postgres schema
  versioning anyway), migrate the SQLite-specific bits. Non-trivial but doable.
  Prioritize only if Postgres features (JSON query operators, JSONB, etc.) are
  actually needed — SQLite JSON support is adequate for v1.
- **Why deferred:** SQLite is simpler; Postgres adds operational overhead
  (separate service, backups, upgrades). v1 is single-household LAN; SQLite
  sufficient.

## `FoodItem` — canonical ingredient identity

v1 uses a pragmatic string-matching approach to link recipes and inventory. A
full canonical ingredient / food database is deferred; it is called out here
because several rough edges point at it.

### Current approach (v1)

Recipe ingredients → `normalized_name` (computed server-side via `normalize.py`:
strip descriptors, lowercase, singularize naively).

Inventory items → `match_name` (user-editable, defaults to their own
`normalized_name`).

Matching: recipe ingredient's `normalized_name` == inventory item's `match_name`
(string equality, no aliases).

**Rough edges:** imperfect singularize (e.g., "feta" stays "feta" after
descriptor stripping, but a recipe says "feta cheese" and inventory says "feta
block"). Editable `match_name` per inventory row lets users correct mismatches
manually, but it does not scale (every item must be corrected independently).

### Upgrade path: `FoodItem` table

- **Add:** `FoodItem` table: `{id, canonical_name, aliases: list[str], unit_bucket,
  is_staple, min_quantity, …}`.
- **Add:** nullable `food_item_id` FKs on `recipe_ingredients`,
  `inventory_items`, `grocery_list_items` (and `receipt_items` once receipt OCR
  lands in v2).
- **Backfill:** from `match_name` clusters (all inventory rows with the same
  `match_name` → one `FoodItem`; point all rows to it).
- **Normalization:** `normalize.py` output → lookup in `FoodItem` table; if
  found, use its `id`; if not, create a new `FoodItem` (with `canonical_name`
  from the normalized input).
- **Aliases:** user can add aliases to a `FoodItem` (e.g., "feta cheese" →
  `FoodItem.canonical_name="feta"`). Matching uses alias lookup, not
  `match_name`.
- **Cost:** non-trivial schema migration (new table + backrefs + nullable FKs +
  populate). Pairs with Alembic. Reasonable as a phase after v1, once the
  household has real data.

## Invariants any extension must preserve

Extensions must not break these architectural choices:

1. **One-way import layering:** `config → database → normalize/units →
   models → security/services → schemas/routers → main`. A module never
   imports from something that imports it.

2. **Services are pure and DTO-based.** `services/inventory_math.py` et al.
   take / return plain dataclasses or dicts, never ORM objects. A service
   *proposes* an adjustment DTO; the **router performs the atomic write** and
   owns the single transaction. On `IntegrityError` or lock timeout, the
   endpoint returns **409, not 500**.

3. **No LLM / AI services.** When research and receipt parsing land in v2 they
   stay pure heuristics. If a future feature wants an LLM (e.g., "suggest recipes
   based on inventory"), it is out of scope for this app's ethos; discuss with
   the household before considering it.

4. **No live network in tests.** v1 has no outbound calls. When `fetch_bytes`
   (URL import + research) and `_ocr_image` (receipt OCR) arrive in v2 they are
   the only network/subprocess seams, and both must be mocked offline. New
   network calls follow the same pattern.

5. **`frontend/src/types.ts` stays hand-maintained.** It mirrors the backend
   Pydantic schemas. Do not auto-generate it. When the API changes, update
   `types.ts` manually — it keeps the frontend author aware of contract changes.

6. **Forward-only writes stay forward-only.** Cook and grocery `submit` (v1),
   and receipt `apply` (v2), do not unwind. Until undo is designed as one
   uniform feature (see Deferred), no `POST /{resource}/:id/undo` route.

## Rejected outright (not deferred)

These were considered and rejected. Re-proposing them requires new information
(a blocker has been solved, the use case has changed, or the cost-benefit has
flipped).

| Item | Why rejected |
| --- | --- |
| `pint` (units library) | v1 uses a bounded pure-Python unit table (mass/volume/count); `pint` adds a dependency + external data file. Justified only if we need food-specific conversions (e.g., "1 can tomatoes ≈ 400 g"); do it manually if needed. |
| `passlib` / `bcrypt` | v1 uses `pwdlib[argon2]` (pure Python, no system deps). Simpler, no bcrypt 72-byte password truncation footgun. |
| `python-jose` / `pyjwt` (JWT) | v1 uses opaque session tokens (`secrets.token_urlsafe(32)`) stored in the database. No signing secret to manage; clean revocation (delete the row). JWTs are justified for stateless, multi-service auth; single service + LAN + token revocation = sessions are simpler. |
| `inflect` (singularize library) | v1 uses a naive hand-tuned singularize (irregular map + suffix rules). `inflect` is overkill for this bounded domain; edge cases are fixed manually or via `FoodItem` aliases. |
| Any LLM/AI service (OpenAI API, Anthropic, etc.) | v1's no-LLM constraint (research and receipt parsing are pure heuristics). If a future feature genuinely needs an LLM, it is a separate system; do not bundle it into this app. The household has explicitly opted for on-device / pure-heuristic approaches. |
| Any web-search SDK bundled into the app | Research ships URL-batch only; `query` mode is deferred (v2+). If a web-search service is added later (e.g., Brave Search SDK), add it as a *new* feature, not a bundled dependency. |
