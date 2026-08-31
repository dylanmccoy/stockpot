# Plan: Household Recipe + Food Inventory App (Backend v1)

## Context

The repo holds a minimal recipe-CRUD skeleton: one `Recipe` table (`title`,
freeform `ingredients` text, freeform `instructions` text, `created_at`), a
FastAPI backend with a single router, no auth, no migrations (`create_all()` in
the lifespan), and a one-file React frontend.

The user wants a **general-purpose recipe keeper + food-inventory tracker for
household use**, whose purpose is to *reduce the friction of cooking at home*.
The organizing idea is a loop: recipes with **structured** ingredients → a
**food inventory** with real quantities → **grocery lists** generated from
hand-picked recipes and netted against what's in stock; cooking a recipe deducts
stock; checking off groceries adds stock. There is **no meal planning** — the
unit of work is "make *this* recipe now".

**v1 is backend-only** (user's choice): all backend features + tests, delivered
in testable phases. The full frontend is a separate later effort; the existing
`App.tsx`/`api.ts`/`types.ts` will not function against the new API and are left
untouched until then. The v1 interaction surface is the OpenAPI docs (`/docs`)
and the test suite.

## Constraints

- **Planning task only — no code is written as part of this goal.** Deliverable
  is this plan; on approval its first step is copying it to `recipe/docs/plan.md`.
- Extend the existing repo. Keep the one-way import layering
  (`config → database → models → schemas/routers → main`) and the test seam (the
  `client` fixture via `app.dependency_overrides[get_db]`, real HTTP through
  `TestClient`).
- No new heavy infrastructure: still SQLite, still `create_all` (no Alembic yet),
  still `uv` + `npm`. LAN-only — no HTTPS-in-app, email flows, or third-party IdP.
- **No LLM / AI services anywhere.** URL import is the `recipe-scrapers` library
  only. Import makes no live network calls in tests.
- Minimal-ethos: smallest thing that works; a new dependency needs a stated
  justification.
- `types.ts` stays a hand-maintained mirror of the Pydantic schemas (relevant to
  the later frontend effort).
- v1 excludes: meal planning; "what can we make now"; staples / low-stock
  alerts. The data model must not preclude them (see Deferred).
- v1 **adds** (approved additions, folded into the phases below): cross-recipe
  ingredient-frequency research (ad-hoc URL **batch only** — see Revisions #1),
  recipe reviews tied to a specific cook/made event, made-history decoupled from
  stock deduction, and grocery-receipt OCR → stock update.

## Revisions — adversarial review pass 2

A second adversarial review raised 17 findings. Dispositions folded into this
plan below. `#n` tags are referenced from the relevant sections.

| # | Finding | Decision |
|---|---|---|
| 1 | Google Custom Search JSON API is closed to new customers (EOL 2027-01-01). | **De-scoped.** `query` mode removed from v1; `research` takes `urls` only. Web-search URL resolution moved to Deferred. |
| 2 + 7 | One `inventory_items` row per normalized name silently merges incompatible units / prep-adjective mismatches (`diced tomatoes` ≠ `tomato`). | **Fixed.** Composite `(match_name, unit_bucket)` uniqueness; drop the blind `+=` fallback; descriptor-stripping in `normalize.py`; editable `match_name` on inventory rows. `FoodItem` still deferred. |
| 3 | `recipe_research` reads `ing.normalized_name`, absent from the `RecipeImportPreview` ingredient shape. | **Fixed.** New `ImportIngredient` DTO carries `normalized_name` + `raw_text`. |
| 4 | Availability compares each ingredient line against the full stock row (double-spend) and `all_available` ignores `have_uncertain`. | **Fixed.** Aggregate requirements by `(match_name, dimension)`; `all_available` true only when every quantified line is `ok`. |
| 5 | Receipt apply silently skips included lines with no quantity, then locks the receipt; `applied` is a bare bool. | **Fixed.** Reject apply when any included line lacks a finite positive quantity; apply in one transaction; snapshot `applied_quantity`/`applied_unit` per line. |
| 6 | Grocery check/uncheck mutates inventory per-line and reverses using post-edit field values → drift. | **Fixed (user-directed).** Check-off no longer touches inventory. New `POST /api/grocery/{id}/submit` adds every checked, quantified, not-yet-applied line in one transaction and **freezes** those lines (forward-only, matching Cook/receipt-apply). No uncheck-reversal. |
| 8 | No atomicity / concurrency contract for read-modify-write on `quantity`. | **Fixed (light).** SQLite `UPSERT` for `add_to_inventory`; `PRAGMA busy_timeout`; `UPDATE ... WHERE status=<expected>` guards on one-shot transitions. No dedicated concurrency test suite. |
| 9 | COUNT dimension treats `jar`/`can`/`package`/`clove`/… as 1:1 with `each`. | **Fixed.** COUNT keeps only `unit`/`each`/`""`, `dozen`, `pair`; the rest move to UNKNOWN (opaque, exact-string match). |
| 10a | `_fetch_and_scrape` never returns `html`, so the `wild_mode=True` retry is dead code. | **Fixed.** Split the fetch (`fetch_bytes`, renamed & SSRF-guarded in #H1) from `scrape_preview(html, url)`; the route holds `html` for the retry. |
| 10b | Fetch is unbounded (no size cap, no status check). | **Fixed.** Streamed byte cap + `raise_for_status` + SSRF guard — see hardening pass 3 below. |
| 11 | Public `/uploads` now also serves receipt images (PII); `StaticFiles` mounts before the dir exists; conftest imports the app before fixtures can redirect the dir. | **Fixed.** Receipts stored under a private dir, served only via an auth'd `FileResponse` route. `os.makedirs` for both dirs at import time before the mount. conftest sets `RECIPE_UPLOAD_DIR` / `RECIPE_RECEIPTS_DIR` before importing `app`. |
| 12 | OCR has no decoded-pixel / time / concurrency limit; every test monkeypatches `_ocr_image`, so a missing binary ships green. | **Fixed.** Pillow format/frame/`MAX_IMAGE_PIXELS` validation (decompression-bomb → reject); `pytesseract` `timeout`; process semaphore; `/api/health` reports tesseract availability; one non-mocked CI smoke test. |
| 13 | Recipe/receipt quantities and grocery multipliers accept negative and non-finite floats. | **Fixed.** `gt=0` when non-null + `allow_inf_nan=False` on every quantity/multiplier; inventory stays `ge=0` finite. |
| 14 | `database.py unchanged` — SQLite ignores declared cascades / `SET NULL` without `PRAGMA foreign_keys=ON`. | **Fixed.** Connect-time `PRAGMA foreign_keys=ON` (+ `busy_timeout`) in `database.py` and the test engine; `passive_deletes=True` where DB cascade is relied on. |
| 15 | Registration on by default; no `code` field; every account has full mutation access. | **Fixed.** `RECIPE_ALLOW_REGISTRATION` defaults **false**; when true a configured `RECIPE_REGISTRATION_CODE` is required; `code` added to `RegisterRequest`. Single shared household / full-trust members stated explicitly. |
| 16 | `CookLog.deductions` records the requested amount, not the actual clamped delta; review responses lack their cook event's context. | **Fixed.** Each deduction records `requested` / `deducted` / `before` / `after`; `RecipeReviewRead` nests `CookEventMini`. |
| 17 | Receipt items use PUT full-replace; the replacement payload has no id / `raw_text` / `price_cents`, so OCR evidence is lost on edit. | **Fixed.** Per-item `PATCH /api/receipts/{id}/items/{item_id}` with stable ids; OCR rows (`raw_text`, `price_cents`) are never destroyed. |

## Revisions — hardening pass 3 (from the parallel review branch)

A concurrent branch revised the *pre-scope-expansion* plan against a separate
design review. Its feature scope is stale (no receipts / research / reviews), so
it is **not merged**, but five of its treatments were stronger and are folded in
here. `#Hn` tags mark them below.

| # | Change | Why |
|---|---|---|
| H1 | **SSRF-guarded `fetch_bytes`** is the single network primitive for `/import` **and** `/research/compare` and `save=true` image download: HTTP(S) scheme allowlist, resolve host and reject private / loopback / link-local / ULA / multicast / `169.254.169.254`, `follow_redirects=False` (a 3xx → 502), `raise_for_status`, `Content-Type` allowlist, stream to a byte cap. `RECIPE_IMPORT_ALLOW_PRIVATE=true` re-opens it for a trusted LAN. | `/research` fetches a *batch* of arbitrary user-supplied URLs — the exposure that made "defer to Phase 7" acceptable for single-URL import no longer holds. Bounded, well-specified, cheap. |
| H2 | **App factory** `create_app(settings, engine) -> FastAPI` + `make_engine(url)` / `make_session_factory(engine)` in `database.py`; module-level `app = create_app(settings, engine)` for uvicorn. `create_app` runs `makedirs` before the StaticFiles mount and the lifespan `create_all` on the injected engine. | Removes the "set `RECIPE_*_DIR` env vars before importing `app`" ordering hack in `conftest.py` (#11) — tests pass a settings object + a test engine, no global mutation, no import-order sensitivity. |
| H3 | **Concurrency contract, tightened.** Explicit rule: pure `services/` **propose** an adjustment DTO; the **router performs** the atomic write and owns the single transaction; a mid-operation failure rolls the whole thing back. On `IntegrityError` or lock / `busy_timeout` timeout the endpoint returns **409**, not 500. | Keeps `inventory_math` genuinely ORM-free and gives the client a defined error instead of a 500 under contention. |
| H4 | **Validation completeness.** `GroceryListCreate.recipe_ids` must be non-empty, unique, and all exist (else 422); `multipliers` keys must be a subset of `recipe_ids` (else 422). A dedicated `test_validation.py` covers negative / `0` / `inf` / `nan` on every numeric field across recipes, inventory, cook, grocery, availability. | Closes the gaps `#13` left (it covered field-level `gt=0` / `allow_inf_nan=False` but not collection-level or a focused test). |
| H5 | **Global cook-log reads.** New `routers/cook_logs.py`: `GET /api/cook-logs` (all recipes, newest-first, paginated) and `GET /api/cook-logs/{log_id}`. | A cook log survives its recipe's deletion (`recipe_id` → null, `recipe_title` snapshot) but `#16` left no endpoint that can return it afterward, and no by-id fetch for a reviewer drilling into `CookEventMini`. |

Judgement calls left **as-is on main** (branch had alternatives; main's choices
stand): grocery `submit` is forward-only, no per-line `/undo` (the Deferred
"undo for forward-only actions" covers all three uniformly); `match_name` is
editable on inventory rows only, not on recipe ingredients (`FoodItem` is the
real fix); `AvailabilityLine` stays one-per-ingredient (frontend renders a
status dot per row).

## Done criteria

**Plan is approved** when this file specifies the data model, module layout,
unit-conversion rules, the netting/deduction algorithms, the auth mechanism, the
import mechanism, dependencies, and the phased build sequence — all below.

**Backend v1 is done** when, verified through `/docs` and `uv run pytest`:

1. **Auth.** A user can register (only while `RECIPE_ALLOW_REGISTRATION=true`, and
   only with the correct `RECIPE_REGISTRATION_CODE` when one is configured — see
   #15) and log in, receiving a bearer token. Every data endpoint except
   `/api/health` and the public auth routes returns 401 without a valid token.
2. **Structured recipes.** `POST/PUT /api/recipes` accept nested ingredient rows
   (`quantity` nullable, `unit` nullable, `item`, `note`), ordered `steps`,
   `tags`, `cuisine`, `prep_time`, `cook_time`, `servings`, `source_url`,
   `notes`. `GET` returns them nested and ordered. PUT fully replaces nested rows.
   `normalized_name` is computed server-side on every ingredient.
3. **Photo.** `POST /api/recipes/{id}/photo` stores one image under the public
   uploads dir and records its relative path; it is served at `/uploads/...`.
   Wrong content-type and oversize are rejected.
4. **Inventory.** `/api/inventory` supports list / add / edit / remove of
   `{item, quantity ≥ 0, unit}` items, one row per `(match_name, unit_bucket)`
   (#2); `match_name` is editable to correct matching.
5. **Grocery receipt → stock.** `POST /api/receipts` (photo upload) OCRs the
   image locally, parses it into draft line items, and returns them for
   review; `PATCH .../items/{item_id}` edits a line (#17); `POST .../apply`
   adds the confirmed quantities to inventory in one transaction and the
   receipt becomes an immutable audit record. Apply is rejected (422) if any
   included line lacks a finite positive quantity (#5). The receipt image is
   retrievable only through an authenticated route, never `/uploads` (#11).
6. **Missing-ingredient check.** `GET /api/recipes/{id}/availability?multiplier=M`
   returns per-ingredient `status` in
   `{ok, short, missing, to_taste, have_uncertain}` with unit conversion applied
   when units are compatible and an explicit uncertain state otherwise. Multiple
   lines for the same food are aggregated before comparison (#4), and
   `all_available` is true only when every quantified line is `ok`.
7. **Cook deducts stock, or just logs it.** `POST /api/recipes/{id}/cook
   {multiplier, deduct?}` — `deduct=true` (default) subtracts ingredients from
   inventory (converting units, clamping at 0, skipping unmatched); `deduct=false`
   skips inventory entirely. Either way it writes an auditable `CookLog` row,
   so **every** made-event is recorded. `GET /api/recipes/{id}/cook-logs`
   lists them newest-first — the made-history — and `GET /api/cook-logs` /
   `GET /api/cook-logs/{log_id}` read across all recipes and still resolve a log
   after its recipe is deleted (#H5).
8. **Reviews.** `POST /api/recipes/{id}/cook-logs/{log_id}/reviews
   {rating?, comment?, changes_next_time?}` attaches a review to a specific
   made-event. `GET /api/recipes/{id}` nests all reviews (newest first) so
   past notes and "what I'd change" are visible whenever the recipe is
   viewed again, without a separate lookup.
9. **Grocery list.** `POST /api/grocery {recipe_ids, multipliers?}` creates a
   persisted list whose lines are consolidated requirements across the selected
   recipes minus current stock; only shortfalls appear; unit-incompatible lines
   are flagged `nettable=false`, not dropped. Manual one-off items can be added.
   `PATCH` on a line toggles `checked` and edits its fields — **no inventory
   effect** (#6). `POST /api/grocery/{id}/submit` adds every checked, quantified,
   not-yet-applied line to inventory in one transaction and freezes those lines
   (forward-only; a later `PATCH` on a frozen line → 409). Re-submitting picks up
   only newly-checked lines.
10. **Unit conversion** is a standalone pure module with a documented supported-
    unit set and defined behavior for unknown / incompatible pairs.
11. **URL import.** `POST /api/recipes/import {url, save?}` fetches through the
    single SSRF-guarded `fetch_bytes` helper (HTTP(S) only, private/loopback/
    link-local/metadata targets rejected, redirects not followed, `Content-Type`
    checked, response streamed to a byte cap; #H1), parses with `recipe-scrapers`
    (normal then wild mode), and returns a structured recipe preview (ingredient
    strings parsed into rows where possible); unsupported sites return 422 with
    `unsupported: true`; fetch failures (transport, blocked address, redirect,
    non-2xx, oversize) return 502. `save=true` downloads the remote image through
    the same helper. No test hits the network.
12. **Recipe research.** `POST /api/research/compare {urls, limit?}` scrapes each
    URL through the same `fetch_bytes` + `scrape_preview` machinery (so the batch
    inherits the SSRF guard; #H1) and reports what fraction of the analyzed
    recipes contain each normalized ingredient — nothing is saved unless
    separately imported. Fetch/parse failures are collected, not fatal. No
    `query` / web-search mode in v1 (#1).
13. **Tests green.** `uv run pytest` passes: units, ingredient parser, inventory
    math, auth gating, input validation (#H4), recipe CRUD with nested rows,
    availability, cook (both `deduct` modes) + cook-log reads (#H5), reviews,
    inventory CRUD, receipt parsing + apply, grocery generation + submit, import
    (`httpx.MockTransport`: success, blocked address, redirect, oversize, non-2xx,
    `save=true` offline; #H1), research (fetch mocked), and one non-mocked OCR
    smoke test (#12).
14. **Docs.** `README.md`, `CLAUDE.md`, `backend/.env.example` updated for the
    new architecture, env vars, and the `rm backend/recipe.db` reset procedure.

## Data model (`backend/app/models.py`, one file)

Layering with new modules:
`config → database → normalize/units → models → security/services → schemas/routers → main`.

| Table | Columns (type — notes) |
| --- | --- |
| **users** | `id` PK · `username` str(50) unique, regex `^[A-Za-z0-9_.-]{3,50}$` · `password_hash` str(255) argon2 · `created_at` dt(tz) |
| **sessions** | `id` PK · `token` str(64) unique indexed (`secrets.token_urlsafe(32)`) · `user_id` FK users CASCADE · `created_at` · `last_used_at` · `expires_at` (= created + `SESSION_TTL_DAYS`, default 30) |
| **recipes** | `id` PK · `title` str(200) min_len 1 · `notes` Text="" · `prep_time` int? ≥0 · `cook_time` int? ≥0 · `servings` float? >0 · `cuisine` str(100)? · `source_url` str(500)? · `photo_path` str(500)? · `tags` JSON `list[str]`=[] · `steps` JSON `list[str]`=[] · `created_at` · `updated_at` (`onupdate`) · `created_by_id` FK users? (no cascade) |
| **recipe_ingredients** | `id` PK · `recipe_id` FK recipes CASCADE · `position` int 0-based · `quantity` float? (null = to taste) · `unit` str(30)? · `item` str(200) · `note` str(200)? · `normalized_name` str(200) indexed, **server-computed** · `raw_text` str(300)? (import original) · index `(recipe_id, position)` |
| **inventory_items** | `id` PK · `item` str(200) display · `normalized_name` str(200) indexed, server-computed · `match_name` str(200) indexed (defaults to `normalized_name`, **user-editable** — the recipe↔inventory match key, #2/#7) · `unit_bucket` str(20) (`mass`/`volume`/`count`/`opaque:<canonical unit>`, #2) · `quantity` float ≥0 finite default 0, `CHECK(quantity >= 0)` · `unit` str(30)? · `updated_at` · `created_by_id` FK users? · **unique `(match_name, unit_bucket)`** (add = upsert within a bucket) |
| **grocery_lists** | `id` PK · `name` str(200) default `"Groceries <date>"` · `status` str(20) `active`/`archived` · `source_recipe_ids` JSON `list[int]`=[] (informational, no FK) · `created_at` · `created_by_id` FK users? |
| **grocery_list_items** | `id` PK · `grocery_list_id` FK CASCADE · `item` str(200) · `normalized_name` str(200) indexed · `quantity` float? >0 finite when set · `unit` str(30)? · `checked` bool=false · `checked_at` dt? · `submitted_at` dt? (#6) · `source` str(20) `generated`/`manual` · `nettable` bool=true · `added_to_inventory` bool=false (idempotency guard + freeze flag, #6) · `applied_quantity` float? · `applied_unit` str(30)? (snapshot of what `submit` actually added, #6) |
| **cook_logs** | `id` PK · `recipe_id` FK recipes SET NULL · `recipe_title` str(200) snapshot · `multiplier` float=1 >0 · `deducted` bool=true (false = logged without touching stock) · `cooked_at` · `cooked_by_id` FK users? · `deductions` JSON=[] (`[{item, normalized_name, requested, requested_unit, deducted, inventory_unit, before, after, applied, reason}]`, empty when `deducted=false`; #16) |
| **recipe_reviews** | `id` PK · `cook_log_id` FK cook_logs CASCADE, not null · `recipe_id` FK recipes SET NULL (denormalized) · `rating` int? 1-5 · `comment` Text="" · `changes_next_time` Text="" · `created_at` · `created_by_id` FK users? |
| **receipt_imports** | `id` PK · `image_path` str(500) (under the **private** receipts dir, #11) · `raw_ocr_text` Text="" · `status` str(20) `draft`/`applied` · `created_at` · `applied_at` dt? · `created_by_id` FK users? |
| **receipt_items** | `id` PK · `receipt_id` FK receipt_imports CASCADE · `position` int · `raw_text` str(300) (OCR original, **never overwritten**, #17) · `item` str(200) (editable) · `normalized_name` str(200) indexed, **server-recomputed on edit** · `quantity` float? >0 finite when set · `unit` str(30)? · `price_cents` int? (OCR original, informational) · `include` bool=true · `applied` bool=false · `applied_quantity` float? · `applied_unit` str(30)? (snapshot of what `apply` added, #5) |

Relationships: `Recipe.ingredients` → ordered by `position`,
`cascade="all, delete-orphan"`; read paths use `selectinload(Recipe.ingredients)`.
`GroceryList.items` cascade. `Recipe.reviews` (via `cook_logs` →
`recipe_reviews`, both `SET NULL`/`CASCADE` as noted) → read path
`selectinload`, newest first. `ReceiptImport.items` cascade. Users are never
deleted in v1 (nullable `created_by_id`, no cascade).

Research (`recipe_research.py`) has **no table** — it's computed per-request
from scraped previews and never persisted; nothing to add here.

**Design choices (recommended, decisive):**
- Steps/tags/`source_recipe_ids`/`deductions` are **JSON columns** — never queried
  individually. Ingredients get a **child table** — queried and matched.
- **No `FoodItem` table in v1.** Matching is string equality between a recipe
  ingredient's `normalized_name` and an inventory row's `match_name` (which
  defaults to its own `normalized_name` but is user-editable). Upgrade path
  unchanged: add `FoodItem` + nullable FKs + backfill by `match_name`.
- **Inventory identity is `(match_name, unit_bucket)`, not a single unique name
  (#2/#7).** `unit_bucket` is the conversion dimension (`mass`/`volume`/`count`)
  for known units, or `opaque:<canonical unit>` for an unknown/opaque unit
  (`bag`, `jar`, …). "Add to stock" upserts *within* a bucket. Stocking the same
  food in two incompatible units (flour in `bag` and in `g`) yields two rows,
  never an arithmetic merge of `1 + 500 → 501`. All inventory lookups return the
  set of compatible rows for a `match_name`, not one row.

**`backend/app/normalize.py`** (pure, no dep): `normalize_name(raw)` = strip →
lower → drop punctuation (keep spaces/hyphens) → collapse whitespace → **strip
leading prep/size descriptors** (a small stoplist: `diced`, `chopped`, `minced`,
`sliced`, `ground`, `fresh`, `dried`, `large`, `small`, `medium`, `boneless`,
`skinless`, `ripe`, … — documented tuning knob, #7) → naive singularize
(irregular map `{tomatoes→tomato, potatoes→potato, leaves→leaf, …}`, then
`-ies→-y`, `-ses/-xes/-oes→ -e`, trailing `-s` → drop). Remaining false
matches are corrected per-row via the editable `match_name`; no `inflect`
dependency.

## Module / router layout (`backend/app/`)

```
config.py     + upload_dir, receipts_dir (private, #11), max_upload_bytes,
                allow_registration (default false, #15), registration_code?, session_ttl_days,
                import_max_bytes, import_fetch_timeout (10s), max_image_bytes (~5 MiB),
                import_allow_private (default false, #H1), ocr_timeout_seconds, ocr_max_concurrency,
                max_image_pixels (#12), research_max_urls
database.py   make_engine(url) + make_session_factory(engine) helpers (#H2); default module-level
                engine/SessionLocal kept for the default app; on-connect listener:
                PRAGMA foreign_keys=ON, PRAGMA busy_timeout=5000 (#14/#8)
normalize.py  normalize_name()  (incl. descriptor stripping, #7)  [pure]
units.py      unit table + conversions                           [pure, no deps]
security.py   hash/verify_password (pwdlib), issue_token, get_current_user dep, CurrentUser alias
models.py     all tables
schemas/      package: common.py, auth.py, recipe.py, inventory.py, grocery.py, receipt.py, research.py  (__init__ re-exports)
services/
  ingredient_parse.py   parse_ingredient(text) -> row dict       [pure]
  import_recipe.py      fetch_bytes(url,*,limit,allowed_types)  [only network fn; SSRF-guarded, #H1/#10b],
                        scrape_preview(html, url, wild=False) -> RecipeImportPreview  [#10a]
  inventory_math.py     check_availability, generate_lines, add_to_inventory_calc, deduct_calc  [pure, dataclasses in/out — PROPOSE an adjustment, never mutate, #H3]
  receipt_ocr.py        _ocr_image(path)  [only OCR call — Pillow validate + pytesseract(timeout=…) under a Semaphore, #12]
  receipt_parse.py      parse_receipt_text(text) -> list[line guess]  [pure]
  recipe_research.py    compare_ingredients(previews) -> ResearchReport  [pure, dataclasses in/out]
routers/
  auth.py       /api/auth      register, login, logout, me
  recipes.py    /api/recipes   CRUD + /import + /{id}/photo + /{id}/availability + /{id}/cook +
                                /{id}/cook-logs + /{id}/cook-logs/{log_id}/reviews + /{id}/reviews
  cook_logs.py  /api/cook-logs  list (paginated, all recipes) + get by id (#H5)
  inventory.py  /api/inventory  CRUD (incl. PATCH match_name)
  grocery.py    /api/grocery    lists + items (PATCH state only) + /{id}/submit (#6) + delete
  receipts.py   /api/receipts   upload (OCR + parse) + get/list + GET /{id}/image (auth'd, #11) +
                                PATCH /{id}/items/{item_id} (#17) + /apply + delete
  research.py   /api/research   /compare (URL batch only, #1)
main.py       create_app(settings, engine) -> FastAPI (#H2): os.makedirs(upload_dir) AND
              os.makedirs(receipts_dir) THEN mount /uploads StaticFiles (#11); include 7 routers;
              /api/health (reports tesseract availability, #12); lifespan create_all on the injected
              engine. Module-level `app = create_app(settings, engine)` for uvicorn.
```

**Rule (documented in CLAUDE.md):** `services/` functions take/return plain
dataclasses or dicts, **never ORM objects**; routers marshal ORM ↔ dataclass.
That is the unit-test seam. `services/inventory_math.py` imports only `units`,
`normalize`, stdlib. **A service proposes an adjustment DTO; the router performs
the atomic write and owns the single transaction (#H3).** `receipt_parse.py` and
`recipe_research.py` follow the pure rule; `import_recipe.fetch_bytes` and
`receipt_ocr._ocr_image` are each a single network/subprocess-touching function
— the one seam each gets monkeypatched in tests (import tests drive `fetch_bytes`
through `httpx.MockTransport`, offline).

**Auth gating:** every router is
`APIRouter(..., dependencies=[Depends(get_current_user)])` except `auth`
(register/login public; logout/me protected) and inline `/api/health`. The
`/uploads` StaticFiles mount is unauthenticated — **recipe photos only**,
acceptable on LAN, noted in docs. **Receipt images are never under `/uploads`**
(#11): they live in the private `receipts_dir` and are served only by
`GET /api/receipts/{id}/image` (`FileResponse`, behind the auth dependency).

## Unit conversion — `backend/app/units.py` (pure Python, no `pint`)

Dimensions: `MASS` (base **g**), `VOLUME` (base **ml**), `COUNT` (base **unit**).

Static synonym table `str → (Dimension, factor_to_base)`:
- **mass:** g/gram(s) 1 · kg 1000 · mg 0.001 · oz/ounce 28.3495 · lb/lbs/pound(s) 453.592
- **volume:** ml 1 · l/litre/liter 1000 · tsp/teaspoon 4.92892 · tbsp/tablespoon 14.7868 · cup(s) 236.588 · fl-oz 29.5735 · pint 473.176 · quart 946.353 · gallon 3785.41
- **count:** unit/each/"" 1 · dozen 12 · pair 2  — **only genuinely countable units** (#9)
- **left UNKNOWN on purpose** (→ opaque, exact-string match only, never converted, non-nettable):
  clove, slice, piece, stick, can, package, pkg, jar, bottle, box, bag, head, bulb,
  bunch, sprig, pinch, handful, dash, splash, "to taste" (#9). Documented tuning knob — a
  food-specific conversion (e.g. `1 can tomatoes ≈ 400 g`) can be added later, per pair, deliberately.

Unit-string normalization: lower → strip trailing `.` → naive-singularize → map
via synonym dict.

API:
```
@dataclass Quantity: amount: float | None; unit: str | None
parse_unit(s)                 -> UnitDef | None            # None = unknown
to_base(amount, unit)         -> (float, Dimension) | None
from_base(amount, dim, unit)  -> float | None
compatible(a, b)              -> bool                       # both known + same dimension
add_quantities(list[Quantity]) -> list[Quantity]           # merge by dimension; unknown/None each stay a bucket
```

Incompatible/unknown behavior — **never drop a line:**
- both units `None` → treat as COUNT (so "3 onions" vs "2 onions" nets).
- one side unknown, or different dimensions ("2 cloves garlic" vs "1 bulb
  garlic") → `compatible()` false → line surfaced with `nettable=false`, need =
  recipe requirement as written.

## Netting & deduction algorithms (`services/inventory_math.py`, pure)

### availability — `GET /api/recipes/{id}/availability?multiplier=M`

**Aggregate first (#4):** group the recipe's ingredient rows by
`(normalized_name, bucket)` where `bucket` = `to_base(need, unit).dim` for a
known unit, else `opaque:<canonical unit>` (None unit → COUNT). Sum `need` per
group in base units. Then compare each group once against the *sum* of matching
inventory rows (`inv.match_name == normalized_name` and same bucket) — so a
recipe that lists flour twice can't see full stock twice.
```
groups = aggregate(recipe.ingredients, M)          # -> {(norm, bucket): summed_need_base, member ingredient_ids, unit}
for g in groups:
    to_taste members -> one line(status="to_taste") each; skip quantified math for those
    stock_base = sum(to_base(r.quantity, r.unit).amt for r in inventory
                     if r.match_name == g.norm and same_bucket(r, g))
    if no matching inventory row:            -> line(need=g.need, have=0, short=g.need, status="missing")
    elif g.bucket is opaque and units differ -> line(need, have=stock, status="have_uncertain", nettable=false)
    else:
        short_base = g.need_base - stock_base
        -> line(status="ok", have=stock) if short_base <= 0
           else line(need, have=stock, short=from_base(short_base, …), status="short")
    (emit one AvailabilityLine per member ingredient_id, carrying the group's status)
report.all_available = every quantified line has status == "ok"
                       (any missing / short / have_uncertain -> false; to_taste is ignored)
```

### grocery generation — `POST /api/grocery {name?, recipe_ids, multipliers?}`
```
reqs = {}   # normalized_name -> {quantities:[Quantity], display_item, sources:set, to_taste:bool}
for rid in recipe_ids:
    M = multipliers.get(rid, 1)
    for ing in recipe(rid).ingredients:
        r = reqs[ing.normalized_name]; r.display_item = ing.item; r.sources.add(recipe.title)
        if ing.quantity is None: r.to_taste = true; continue
        r.quantities.append(Quantity(ing.quantity * M, ing.unit))

items = []
for norm, r in reqs.items():
    for q in add_quantities(r.quantities):                      # consolidated per dimension/bucket
        stock_base = sum_inventory_base(match_name=norm, bucket=bucket_of(q))   # sum of compatible rows in base units, #2/#4
        if stock_base is None:                                   # no compatible row at all
            need, nettable = q, (q.amount is not None and (q.unit is None or parse_unit(q.unit) is not None))
        else:
            nb = to_base(q.amount, q.unit)
            if q.amount is None or nb is None:                   # opaque/unknown recipe unit
                need, nettable = q, false
            else:
                short = nb.amt - stock_base
                if short <= 0: continue                          # fully in stock -> no line
                need, nettable = Quantity(from_base(short, nb.dim, q.unit), q.unit), true
        items.append(GLItem(item=r.display_item, normalized_name=norm,
                            quantity=need.amount, unit=need.unit, nettable=nettable, source="generated"))
    if r.to_taste and norm not already emitted:
        items.append(GLItem(item=r.display_item, quantity=None, unit=None, nettable=false, source="generated"))
persist GroceryList(name or default, source_recipe_ids=recipe_ids, items=items)
```
Consolidation across recipes = keying `reqs` by `normalized_name`.

### edit / check a grocery line — `PATCH /api/grocery/{list}/items/{id} {checked?, quantity?, unit?, item?}`
```
if item.added_to_inventory: 409          # frozen after submit (#6) — no edits, no uncheck
apply the given fields; if item changed, recompute item.normalized_name
if "checked" given:
    item.checked = checked
    item.checked_at = now if checked else null
# NO inventory side effect here (#6)
```
Checking is now pure list state. Nothing reaches inventory until `submit`, so a
line can be freely checked, edited, and unchecked with no drift.

### submit a grocery list — `POST /api/grocery/{list}/submit`
```
with one transaction:
    for item in list.items:
        if not item.checked or item.added_to_inventory or item.quantity is None: continue
        applied = add_to_inventory(item.normalized_name, item.item, item.quantity, item.unit)
        item.applied_quantity, item.applied_unit = applied.amount, applied.unit   # snapshot (#6)
        item.added_to_inventory = true
        item.submitted_at = now
    list.status = "archived" if all items are (added_to_inventory or not checked) else "active"
return updated list
```
Forward-only, matching Cook and receipt apply — **no unapply**. Re-submitting is
safe: already-`added_to_inventory` lines are skipped, so only newly-checked lines
are added. An accidental submit is corrected with a manual `/api/inventory`
adjustment (same escape hatch as Cook). This is what resolves #6: because
checking has no inventory effect and submitted lines are frozen, the
"edit-after-check then uncheck" desync cannot occur; the stored
`applied_quantity`/`applied_unit` snapshot keeps the audit record honest.

### add_to_inventory(match_name, display, amount, unit) -> Quantity actually added
```
bucket = bucket_of(unit)                    # dim for a known unit, else opaque:<canonical>, None -> count
# atomic upsert within the (match_name, unit_bucket) row (#2, #8):
INSERT INTO inventory_items (item, normalized_name, match_name, unit_bucket, quantity, unit)
     VALUES (display, normalize_name(display), match_name, bucket, max(amount,0), unit)
ON CONFLICT (match_name, unit_bucket) DO UPDATE SET
     quantity = quantity + convert(excluded.quantity, excluded.unit -> inventory_items.unit within bucket),
     updated_at = now
RETURNING …
# convert() is identity for an opaque bucket (units are guaranteed equal there);
# for mass/volume/count it is to_base/from_base into the stored row's unit.
# There is NO cross-bucket / best-effort '+=' path — incompatible units are simply
# different rows (#2). Stored quantity stays >= 0 and finite (CHECK).
return Quantity(amount, unit)
```

### mark as cooked — `POST /api/recipes/{id}/cook {multiplier, deduct=true}`
```
log = CookLog(recipe_id, recipe_title=recipe.title, multiplier=M, deducted=deduct, cooked_by=user)
if not deduct:
    save(log); return log         # made-event recorded, stock untouched, deductions=[]
with one transaction:
  for (norm, bucket), need_base, unit in aggregate(recipe.ingredients, M):   # aggregate like availability (#4)
    to_taste members -> log.deductions += {item, requested:null, applied:false, reason:"to taste"}
    rows = [r for r in inventory if r.match_name == norm and same_bucket(r, bucket)]
    if not rows: log.deductions += {item, requested:need, applied:false, reason:"not in inventory"}; continue
    if bucket is opaque and any(r.unit != unit for r in rows):
        log.deductions += {item, requested:need, applied:false, reason:"unit mismatch"}; continue
    remaining = need_base
    for r in rows:                                   # draw down compatible rows in order, clamp at 0 (#16)
        before = r.quantity
        take_base = min(remaining, to_base(r.quantity, r.unit).amt)
        r.quantity = from_base(to_base(r.quantity, r.unit).amt - take_base, bucket, r.unit); r.updated_at = now
        remaining -= take_base
        log.deductions += {item, normalized_name:norm, requested: (need if r is rows[0] else null),
                           requested_unit: unit, deducted: from_base(take_base, bucket, r.unit),
                           inventory_unit: r.unit, before, after: r.quantity,
                           applied: true, reason: ("ok" if remaining <= 0 else "clamped to 0")}
save(log)
```
Cook is intentionally lossy (clamp at 0, skip mismatches). `deductions` now
records `requested` vs the **actual** `deducted` amount and `before`/`after`
per row (#16), so a future "undo" = `add_to_inventory` of each entry's
`deducted` amount.

### made-history — `GET /api/recipes/{id}/cook-logs` + global `GET /api/cook-logs[/{log_id}]` (#H5)
Per-recipe: plain `list[CookLogRead]`, `order_by(cooked_at.desc())` — every
made-event regardless of `deducted`. This is both "recipes I've actually made"
and how a caller finds the `cook_log_id` a review attaches to.

`routers/cook_logs.py` adds the cross-recipe reads:
- `GET /api/cook-logs?limit=&offset=` → `CookLogList` (paginated, all recipes,
  newest first) — the "what have we cooked lately" feed.
- `GET /api/cook-logs/{log_id}` → `CookLogRead` (404 if missing) — a log is
  reachable by id alone, so a reviewer can drill from `CookEventMini` into the
  full deduction detail, and a log **still resolves after its recipe is deleted**
  (`recipe_id` null, `recipe_title` snapshot stands).

### add a review — `POST /api/recipes/{id}/cook-logs/{log_id}/reviews`
```
log = get(CookLog, log_id) or 404
if log.recipe_id != id: 404                     # cook log must belong to this recipe
review = RecipeReview(cook_log_id=log.id, recipe_id=id, created_by=user, **payload)
save(review)
```
`GET /api/recipes/{id}` and `GET /api/recipes/{id}/reviews` both read
`recipe.reviews` (`selectinload` of the review **and its `cook_log`**,
`order_by(created_at.desc())`) — reviews attach once and are never
edited/deleted in v1 (append-only history, same stance as `CookLog`). Each
`RecipeReviewRead` nests a `CookEventMini {cook_log_id, cooked_at, multiplier,
deducted}` (#16) so the reviewed event's date and mode are visible without a
second lookup.

### apply a receipt — `POST /api/receipts/{id}/apply`
```
if receipt.status != "draft": 409                                        # #8 state guard
bad = [it.position for it in receipt.items if it.include and not (it.quantity and isfinite(it.quantity) and it.quantity > 0)]
if bad: 422 {detail:"included lines missing a positive quantity", positions: bad}   # #5 — no silent skip
with one transaction:
    for item in receipt.items:
        if not item.include: continue
        applied = add_to_inventory(item.normalized_name, item.item, item.quantity, item.unit)
        item.applied = true
        item.applied_quantity, item.applied_unit = applied.amount, applied.unit          # snapshot (#5)
    receipt.status = "applied"; receipt.applied_at = now
```
Either every included line applies or none do (single transaction, #5).
One-shot, forward-only, no "unapply" in v1 — matches Cook. Editing is
`PATCH /api/receipts/{id}/items/{item_id}` (#17), draft-only (409 otherwise);
it changes only `item`/`quantity`/`unit`/`include` and recomputes
`normalized_name`, **never** touching the OCR `raw_text` / `price_cents`, so the
receipt stays a faithful record of what was scanned.

### concurrency & atomicity (#8, #H3)

Two household members can act at once. Contract:
- **Pure service proposes, router performs (#H3).** `services/inventory_math.py`
  takes DTOs and returns a proposed adjustment; it never holds an ORM object or a
  session. The router applies that adjustment and **owns the single
  transaction** — a failure mid-operation rolls the whole thing back (no
  half-applied cook, no partly-submitted grocery list).
- Every mutating endpoint (`cook`, receipt `apply`, grocery `submit`, inventory
  CRUD) commits in **one transaction**.
- `add_to_inventory` is the SQLite `INSERT … ON CONFLICT (match_name,
  unit_bucket) DO UPDATE SET quantity = quantity + …` upsert above — the
  increment is atomic and concurrent first-inserts can't raise a duplicate 500.
- One-shot state transitions use a guarded update:
  `UPDATE receipts SET status='applied' WHERE id=? AND status='draft'` (and the
  same for grocery `submit`); zero rows affected → 409.
- `database.py` sets `PRAGMA busy_timeout=5000` per connection (#14), so a brief
  writer overlap waits rather than erroring. **On `IntegrityError` or a lock /
  `busy_timeout` timeout the endpoint returns 409, not 500 (#H3).**
- Not in scope: a multi-process/file-DB concurrency test suite — disproportionate
  at 2 users. One sequential double-submit / double-apply test asserts the
  guard's idempotency; safety otherwise rests on the atomic statements above.

### compare ingredients — `services/recipe_research.py` (pure)
```
def compare_ingredients(previews: list[(source_url, RecipeImportPreview)]) -> ResearchReport:
    total = len(previews)
    tally = {}                                   # normalized_name -> [(source, display_item), ...]
    for source, preview in previews:
        seen = set()
        for ing in preview.ingredients:          # ing is ImportIngredient -> has .normalized_name (#3)
            if ing.normalized_name in seen: continue     # one recipe counts an ingredient once
            seen.add(ing.normalized_name)
            tally.setdefault(ing.normalized_name, []).append((source, ing.item))
    stats = [IngredientStat(norm, most_common_display(v), len(v), len(v) / total * 100, [s for s, _ in v])
             for norm, v in tally.items()]
    stats.sort(key=lambda s: -s.percentage)
    return ResearchReport(analyzed=[...], failed=[...], ingredients=stats, total_recipes=total)
```
`ImportIngredient` (#3) is the ingredient shape inside `RecipeImportPreview`:
`RecipeIngredientIn` + `{raw_text: str|None, normalized_name: str}`, both filled
by `scrape_preview` (`normalized_name = normalize_name(item)`). `compare_ingredients`
therefore never reads a field the preview lacks.

Router (`routers/research.py`, `POST /api/research/compare
{urls: list[str], limit: int=8}`, `limit` capped at `settings.research_max_urls`;
422 if `urls` is empty): dedup URLs; for each, reuse `import_recipe.fetch_bytes`
+ `scrape_preview` (Phase 7) — so **every URL in the batch goes through the same
SSRF guard** as `/import` (#H1) — failures go into `failed`, not a hard error;
**nothing is persisted** (no `Recipe` rows created) — a URL the user likes is
saved separately via `POST /api/recipes/import {url, save:true}`. No `query` /
web-search resolution in v1 (#1); see Deferred.

## Auth approach

- **Hashing:** `pwdlib[argon2]` (`hash_password`/`verify_password` in
  `security.py`). Dummy-verify on unknown username to blunt timing enumeration.
- **Sessions:** opaque `secrets.token_urlsafe(32)` in the `sessions` table, TTL
  `RECIPE_SESSION_TTL_DAYS` (default 30). No JWT, no signing secret to manage.
  `get_current_user(authorization: str = Header(...))` parses `Bearer <token>`,
  looks up a non-expired row, bumps `last_used_at`, else 401.
  `CurrentUser = Annotated[User, Depends(get_current_user)]`.
- **Household model (#15):** v1 is a **single shared household**. Every
  authenticated user has full read/write access to all data — there is no
  per-user ownership or membership layer, by design. `created_by_id` is
  attribution only.
- **Registration (#15):** `RECIPE_ALLOW_REGISTRATION` defaults **`false`**. To
  add accounts, the household sets it `true` (and normally also sets
  `RECIPE_REGISTRATION_CODE`), registers, then sets it back `false`. When
  `RECIPE_REGISTRATION_CODE` is set, `/register` requires a matching `code` or
  returns 403 — so even an open window is not self-serve to a random LAN client.
- **Endpoints (`/api/auth`):** `POST /register {username, password, code?}` → 201
  `{token,user}` (409 dup / 403 disabled-or-bad-code / 422 short pw); `POST
  /login` (JSON, not OAuth2 form, to keep the fetch wrapper uniform) →
  `{token,user}` (401); `POST /logout` → 204 (deletes the row); `GET /me` →
  `UserRead`.
- **CORS:** no code change (token is a header, not a cookie; `allow_headers=["*"]`
  already passes it). For LAN hosting, add the server origin to
  `RECIPE_CORS_ORIGINS` or set `["*"]` (safe — not credentialed). Doc note only.

## URL import approach

`services/import_recipe.py` — fetch and parse are split, and the one network
primitive is **SSRF-guarded** (#H1). It is the only seam tests mock, via
`httpx.MockTransport` (so `save=true`'s image path runs offline too).
```
def fetch_bytes(url, *, limit, allowed_types) -> bytes:      # the ONLY network call
    require url.scheme in ("http", "https")                  # else -> caller 502
    ip = resolve(url.host)
    unless settings.import_allow_private:                    # default false
        reject ip in {private, loopback, link-local, ULA, multicast, 169.254.169.254}
    r = httpx.get(url, timeout=settings.import_fetch_timeout,
                  follow_redirects=False,                    # a 3xx -> 502 "redirect not followed; paste the final URL"
                  headers={"User-Agent": ...})
    r.raise_for_status()                                     # non-2xx -> 502
    require r.headers["content-type"] matches allowed_types  # else -> 502
    read the stream, aborting past `limit` bytes             # oversize -> 502
    return body

def scrape_preview(html, url, wild_mode=False) -> RecipeImportPreview:   # pure; wraps recipe_scrapers + mapping
    scraper = scrape_html(html, org_url=url, wild_mode=wild_mode)
    return map_to_preview(scraper, url)

def map_to_preview(scraper, url) -> RecipeImportPreview:
    title = safe(scraper.title)
    cook  = safe(scraper.total_time)                # -> cook_time; prep_time stays None
    serv  = parse_yields(safe(scraper.yields))      # "4 servings" -> 4.0
    steps = safe(scraper.instructions_list) or (safe(scraper.instructions) or "").split("\n")   # drop blanks
    raws  = flatten(safe(scraper.ingredient_groups)) or safe(scraper.ingredients) or []
    ings  = [ImportIngredient(**parse_ingredient(s), normalized_name=normalize_name(parse_ingredient(s)["item"]))
             for s in raws]                                  # carries raw_text + normalized_name (#3)
    return preview(title, cook_time=cook, servings=serv, steps=[...], ingredients=ings,
                   source_url=url, remote_image_url=safe(scraper.image),
                   cuisine=safe(scraper.cuisine), tags=[], unsupported=False, warnings=[...])
```
Route `POST /api/recipes/import {url, save: bool = false}`:
- `html = fetch_bytes(url, limit=settings.import_max_bytes,
  allowed_types={text/html, application/xhtml+xml}).decode(...)`. Any
  `fetch_bytes` failure (bad scheme, blocked address, redirect, non-2xx, timeout,
  transport error, wrong content-type, oversize) → **502**
  `{detail:"Could not fetch URL"}`.
- `try scrape_preview(html, url)`; on any `recipe_scrapers` failure retry
  `scrape_preview(html, url, wild_mode=True)` (the retry has `html` in scope,
  #10a); still failing → **422** `{detail:"Could not parse this site",
  unsupported:true}`.
- `save=false` (default) → **200** `RecipeImportPreview` (frontend loads it into
  the form later). `save=true` → create the Recipe, then
  `fetch_bytes(remote_image_url, limit=settings.max_image_bytes,
  allowed_types=image/*)` → store via the photo code (any failure leaves
  `photo_path` null, no 5xx) → **201** `RecipeRead`.

**Lightweight ingredient parser** — `services/ingredient_parse.py` (pure):
```
parse_ingredient(text) -> {quantity, unit, item, note, raw_text}:
  raw       = text
  qty, rest = extract_leading_quantity(text)   # int | "1/2" | "1 1/2" | unicode ½¼¾⅓⅔⅛ | "2-3"/"2 to 3" -> upper bound
  unit, rest= extract_leading_unit(rest)       # next token in units.py synonym set -> canonical; else no unit
  note, rest= extract_note(rest)               # "(...)" -> note; first comma -> tail is note; trailing "to taste" -> note
  item      = rest.strip(" ,") or raw
```
Examples: `"1 (14 oz) can diced tomatoes"` → qty 1, note "14 oz", unit "can",
item "diced tomatoes"; `"salt to taste"` → qty None, unit None, item "salt", note
"to taste". Imperfect parses keep `raw_text`; the user fixes them in the form
during the frontend effort.

**Verify at build time** (`recipe-scrapers` API surface): `scrape_html(html,
org_url=...)` signature; `instructions_list()` presence (fallback split);
`ingredient_groups()` shape; exception classes
(`WebsiteNotImplementedError`, `NoSchemaFoundInWildMode`,
`ElementNotFoundInHtml`).

## Dependencies

**Backend runtime (`uv add`):**
- `recipe-scrapers` — URL import.
- `pwdlib[argon2]` — password hashing (no bcrypt 72-byte footgun).
- `python-multipart` — Starlette needs it to accept `multipart/form-data` for the
  photo `UploadFile` endpoint.
- `httpx` — **promote from dev group to runtime**; our own import fetch + remote
  image download (timeout / streamed size cap, offline-testable).
- `pytesseract` — wraps the system `tesseract-ocr` binary to OCR a receipt
  photo into text. Justification: local/offline OCR is the only way to read
  a receipt without sending the photo to a third-party vision API, which
  the household explicitly ruled out. Called with `timeout=` and under a
  `Semaphore` (#12).
- `Pillow` — loads/validates the uploaded image for `pytesseract`: format and
  frame-count check, and `Image.MAX_IMAGE_PIXELS` decompression-bomb guard
  (a bomb warning/error → reject the upload, #12).

**New system package (not a Python dependency):** `tesseract-ocr` must be
installed on dev/CI/deploy hosts (`apt-get install tesseract-ocr`). Documented
in README, CI workflow, and the Makefile setup target.

**Not added:** `pint` (units are a bounded pure-Python set) · `python-jose`/`pyjwt`
(opaque tokens) · `passlib` (using `pwdlib`) · `alembic` (staying on
`create_all`) · `inflect` (naive singularize) · any web-search API or client SDK
— `query` mode is out of v1 (#1) · an LLM/AI service for either research or
receipt parsing (both stay pure heuristics per the no-LLM constraint).

**Backend dev:** none — `test_import.py` and `test_research.py` drive
`import_recipe` through `httpx.MockTransport` (#H1), returning canned HTML with
embedded recipe JSON-LD that `recipe_scrapers` `wild_mode` parses for real (no
stub-scraper mock), and also exercising blocked-address / redirect / oversize /
non-2xx paths; `test_receipts.py` monkeypatches `_ocr_image`, **except** one
non-mocked OCR smoke test that runs the real `tesseract` on a Pillow-generated
image, skipped when the binary is absent (#12).

**Frontend:** `react-router-dom` (confirmed) — added during the later frontend
effort, not v1.

## Schema management

Stay on `create_all`:
- **App factory (#H2).** `create_app(settings, engine)` is the single build path.
  It `os.makedirs(settings.upload_dir)` and `os.makedirs(settings.receipts_dir)`
  **before** mounting `/uploads` StaticFiles (which validates `directory=` at
  construction), and its lifespan runs `Base.metadata.create_all(bind=engine)` on
  the **injected** engine. The module-level `app = create_app(settings, engine)`
  is what uvicorn imports; `conftest.py` calls `create_app(test_settings,
  test_engine)` — no "set env vars before importing `app`" ordering hack.
- `database.py` exposes `make_engine(url)` / `make_session_factory(engine)` and
  registers a `connect` event listener issuing `PRAGMA foreign_keys=ON` and
  `PRAGMA busy_timeout=5000` on every SQLite connection (#14/#8) — without it
  SQLite ignores the declared `CASCADE` / `SET NULL`. The test engine gets the
  same listener. Relationships that rely on DB-level cascade set
  `passive_deletes=True`.
- `create_all` won't ALTER the stale `recipes` table → **delete
  `backend/recipe.db`** in Phase 0 and again after the schema-expanding phases.
- `.gitignore` += `uploads/`, `receipts/` (already ignores `*.db`).
- Document in README + CLAUDE.md: "No migrations. After a model change:
  `rm backend/recipe.db` and restart; local data is lost."

**Cost of Alembic now (rejected):** +dep, `alembic/` + `env.py` wired to
`Base.metadata` / `settings.database_url` + `alembic.ini`, `--autogenerate` +
review per change (SQLite needs batch mode; autogen misses some), a new CI step.
Buys zero data loss + a real upgrade path. Revisit at the first schema change
*after* the household has recipes worth keeping.

## Schemas (`backend/app/schemas/` package)

All `float` fields below are `allow_inf_nan=False` (#13).

- `common.py` — `UserMini {id, username}`.
- `auth.py` — `RegisterRequest {username 3..50 regex, password 8..128, code: str|None}`
  (#15), `LoginRequest`, `TokenResponse {token, user: UserRead}`,
  `UserRead {id, username, created_at}`.
- `recipe.py`:
  - `RecipeIngredientIn {quantity: float|None gt=0, unit: str|None ≤30, item: str 1..200, note: str|None}`
    (#13) — no `position` (array index), no `normalized_name` (server-computed).
  - `RecipeIngredientRead` adds `{id, position, normalized_name}`.
  - `ImportIngredient` = `RecipeIngredientIn` + `{raw_text: str|None, normalized_name: str}`
    — the ingredient shape inside `RecipeImportPreview` (#3).
  - `CookEventMini {cook_log_id, cooked_at, multiplier, deducted}` (#16).
  - `RecipeBase {title 1..200, notes="", prep_time ≥0|None, cook_time ≥0|None,
    servings >0|None, cuisine|None, source_url|None, tags: list[str]=[],
    steps: list[str]=[]}`.
  - `RecipeCreate` / `RecipeUpdate` = `RecipeBase` + `ingredients:
    list[RecipeIngredientIn] = []` — **PUT fully replaces** nested rows.
  - `RecipeRead` = `RecipeBase` + `{id, created_at, updated_at, photo_path,
    created_by: UserMini|None, ingredients: list[RecipeIngredientRead]}`.
  - `RecipeImportPreview` = `RecipeBase` + `{ingredients: list[ImportIngredient],
    source_url, remote_image_url: str|None, unsupported: bool, warnings: list[str]}`
    — like `RecipeCreate` but its ingredient rows carry `normalized_name` +
    `raw_text` (#3).
  - `AvailabilityLine {ingredient_id, item, need: float|None, need_unit,
    have: float|None, have_unit, short: float|None,
    status: Literal["ok","short","missing","to_taste","have_uncertain"],
    nettable: bool}`; `AvailabilityReport {recipe_id, multiplier, lines,
    all_available}`.
  - `CookRequest {multiplier: float = 1 (gt=0, finite), deduct: bool = True}`;
    `CookLogRead {id, recipe_id, recipe_title, multiplier, deducted, cooked_at,
    cooked_by: UserMini|None, deductions: list[dict]}` — each deduction dict is
    `{item, normalized_name, requested, requested_unit, deducted, inventory_unit,
    before, after, applied, reason}` (#16). `POST /cook`,
    `GET /api/recipes/{id}/cook-logs`, and `GET /api/cook-logs/{log_id}` all
    return `CookLogRead`; `GET /api/cook-logs` returns
    `CookLogList {items: list[CookLogRead], total, limit, offset}` (#H5).
  - `RecipeReviewIn {rating: int|None (ge=1,le=5), comment: str="",
    changes_next_time: str=""}`; `RecipeReviewRead` adds
    `{id, cook_log_id, created_at, created_by: UserMini|None,
    cook_event: CookEventMini}` (#16).
  - `RecipeRead` additionally nests `reviews: list[RecipeReviewRead]`
    (newest first).
- `inventory.py` — `InventoryItemIn {item, quantity: float ge=0 (finite),
  unit: str|None, match_name: str|None}` (`match_name` also settable on PATCH, #2);
  `InventoryItemRead` adds `{id, normalized_name, match_name, unit_bucket, updated_at}`.
- `grocery.py` — `GroceryListCreate {name: str|None, recipe_ids: list[int]
  (non-empty, unique, all must exist — else 422), multipliers: dict[int, float] = {}}`
  (each multiplier `gt=0`, finite, #13; **keys must be a subset of `recipe_ids`,
  else 422 — #H4**);
  `GroceryListItemIn {item, quantity: float|None gt=0 (finite), unit: str|None}`;
  `GroceryListItemUpdate {checked: bool|None, quantity, unit, item}` — 409 if the
  target line is `added_to_inventory` (frozen after submit, #6);
  `GroceryListItemRead {id, item, normalized_name, quantity, unit, checked,
  checked_at, submitted_at, source, nettable, added_to_inventory,
  applied_quantity, applied_unit}` (#6);
  `GroceryListRead {id, name, status, source_recipe_ids, created_at, created_by,
  items}`.
- `receipt.py` — `ReceiptItemPatch {item: str 1..200|None, quantity: float|None gt=0
  (finite), unit: str|None, include: bool|None}` — per-item PATCH, all fields
  optional (#17); `ReceiptItemRead` adds `{id, position, raw_text,
  normalized_name, price_cents: int|None, applied, applied_quantity, applied_unit}`;
  `ReceiptImportRead {id, status, created_at, applied_at,
  items: list[ReceiptItemRead]}` — no `image_path` (fetch via the auth'd
  `GET /api/receipts/{id}/image`, #11).
- `research.py` — `ResearchCompareRequest {urls: list[str] (non-empty),
  limit: int = 8}` (#1);
  `IngredientStatRead {normalized_name, display_item, count, percentage,
  sources: list[str]}`; `ResearchReport {analyzed: list[{url, title}],
  failed: list[{url, reason}], ingredients: list[IngredientStatRead],
  total_recipes: int}`.

**PUT nested semantics (full replace):**
```
recipe = get_or_404
apply scalar fields; recipe.tags = payload.tags; recipe.steps = payload.steps
recipe.ingredients.clear()                       # delete-orphan removes old rows
for i, ing in enumerate(payload.ingredients):
    recipe.ingredients.append(RecipeIngredient(position=i,
        normalized_name=normalize_name(ing.item), **ing.model_dump()))
commit; refresh (selectinload)
```
Ingredient `id`s churn per save — harmless (availability is computed fresh;
`CookLog` snapshots its own data).

## Test strategy

**`conftest.py` is the load-bearing change.** It builds the app through the
factory (#H2): `app = create_app(test_settings, test_engine)` where
`test_settings` points `upload_dir` / `receipts_dir` at `tmp_path_factory` dirs
and has `allow_registration=true` (no code), and `test_engine` is the in-memory
`StaticPool` engine with the `PRAGMA foreign_keys=ON` / `busy_timeout` connect
listener (#14) + `create_all`/`drop_all`. `get_db` is still overridden via
`dependency_overrides` for request-scoped sessions. **No "before import"
ordering hack** — the factory takes the dirs and engine as arguments and
`makedirs` them before the StaticFiles mount.
- `user` — registers a default user via `POST /api/auth/register`.
- `auth_client` — `TestClient` with `Authorization: Bearer <token>` preset;
  **becomes the default**. Existing `test_recipes.py` switches `client` →
  `auth_client`.
- `client` — kept as the **anonymous** client for auth / 401 tests.

New / changed test files:
- `test_units.py` — pure. Both-way conversions, plurals/abbrevs, unknown → None,
  cross-dimension incompatible, count handling, `add_quantities` merge + bucketing.
- `test_ingredient_parse.py` — pure. `"2 tbsp olive oil"`, `"1 1/2 cups flour"`,
  `"½ tsp salt"`, `"salt to taste"`, `"3 large eggs"`, `"1 (14 oz) can tomatoes"`,
  garbage → raw fallback.
- `test_inventory_math.py` — pure. availability (all 5 statuses; **duplicate
  ingredient rows aggregated** so stock isn't double-counted, #4; `have_uncertain`
  ⇒ `all_available` false, #4); `generate_lines` (consolidation across 2 recipes,
  netting against summed compatible rows, skip in-stock, non-nettable surfaced);
  `deduct` (clamp at 0, mismatch skipped, cross-unit convert, `requested` vs
  `deducted` recorded, #16); `add_to_inventory` (new bucket row, upsert within a
  bucket, **incompatible unit ⇒ a second row, never `1+500→501`**, #2).
- `test_auth.py` — anonymous `client`. register 201 / 409 dup / 403 when
  `RECIPE_ALLOW_REGISTRATION=false` / 403 wrong `code` when a code is configured /
  422 short pw (#15); login 200+token / 401 bad pw / 401 unknown user; `/me` 200
  with token & 401 without; logout invalidates; a gated endpoint 401 without token.
- `test_validation.py` — negative / `0` / `inf` / `nan` quantity and multiplier
  rejected (422) on recipe ingredient, inventory add/edit, cook, grocery create,
  availability query param (#H4, #13); `recipe_ids` empty or with a duplicate →
  422; a `multipliers` key not in `recipe_ids` → 422.
- `test_cook_logs.py` — `auth_client`. `GET /api/cook-logs` paginates
  newest-first across recipes; `GET /api/cook-logs/{id}` returns one; a log is
  still returned by both endpoints after its recipe is deleted (#H5).
- `test_recipes.py` — expanded, `auth_client`. nested create/read (positions,
  computed `normalized_name`); PUT clears old ingredients; steps/tags round-trip;
  `/availability?multiplier=2`; `/cook` writes `CookLog` + mutates inventory
  (clamp, mismatch; deduction dict carries `requested`/`deducted`/`before`/
  `after`, #16); photo upload (in-memory PNG bytes; wrong content-type
  415/422; oversize 413); `cook {deduct:false}` leaves inventory untouched but
  still writes a `CookLog`; `GET .../cook-logs` newest-first across both
  modes; create a review against a cook log; 404 on mismatched
  recipe/cook-log; `GET /api/recipes/{id}` nests reviews newest-first, each with
  its `cook_event` (#16).
- `test_inventory.py` — CRUD, `(match_name, unit_bucket)` upsert + composite
  uniqueness, same food in two incompatible units → two rows (#2), editing
  `match_name` re-points matching, negative / non-finite qty rejected (#13).
- `test_grocery.py` — generate from 2 selected recipes (consolidation + netting),
  manual item add, **check off → inventory unchanged** (#6), edit a checked line
  then submit → inventory reflects the edited value, `POST /submit` → inventory
  up + line frozen (`added_to_inventory`, `applied_quantity` set), PATCH a frozen
  line → 409, uncheck before submit → no-op, re-submit picks up only newly-checked
  lines, delete list cascades items, non-nettable line present.
- `test_import.py` — **no live HTTP**, `httpx.MockTransport` (#H1). Happy path
  (preview mapping + parser wiring + `ImportIngredient.normalized_name`, #3);
  `recipe_scrapers` failure then `wild_mode` retry (#10a); unparseable → 422
  `unsupported:true`; non-2xx → 502; redirect (3xx) → 502; body over
  `import_max_bytes` → 502; wrong `Content-Type` → 502;
  `http://169.254.169.254/…` and `http://localhost/…` blocked by the guard → 502
  (no request made); `save=true` stores the mocked image, and with a failing
  image response still returns 201 with `photo_path` null.
- `test_receipt_parse.py` — pure. Canned noisy-OCR-style text blocks (all
  caps, broken decimals, store header/footer noise, `SUBTOTAL`/`TAX`/`TOTAL`
  lines) → expected `{item, quantity, unit, price_cents}` guesses; noise
  lines dropped.
- `test_receipts.py` — **OCR mocked except one smoke test.** Monkeypatch
  `app.services.receipt_ocr._ocr_image` for the flow tests: draft creation from
  upload; `PATCH .../items/{item_id}` edits one line, leaves `raw_text`/
  `price_cents` intact (#17); `POST .../apply` updates inventory + writes
  `applied_quantity` (#5); **apply with an included null/≤0-qty line → 422, receipt
  stays draft** (#5); double-apply → 409; delete blocked once applied;
  `GET /{id}/image` needs auth and returns the bytes, image never under `/uploads`
  (#11); wrong content-type / oversize / decompression-bomb image rejected (#12).
  Plus one **non-mocked** test: Pillow renders text to PNG, real `_ocr_image`
  reads it back (`skipif` tesseract missing, #12).
- `test_research.py` — **no live HTTP**, `httpx.MockTransport` (#H1). Canned HTML
  for several recipes reproduces a "100% vs 10% ingredient" comparison; one
  failing URL lands in `failed` without aborting the rest; a blocked-address URL
  in the batch lands in `failed` too (guard, no request); empty `urls` → 422; a
  repeated ingredient within one recipe counts once. No `query` mode (#1).

`pyproject.toml` `testpaths`/`addopts` unchanged. No mypy/lint added (ethos).

## Build sequence (each phase ends with `uv run pytest` green)

- **Phase 0 — reset & deps.** `uv add recipe-scrapers pwdlib[argon2]
  python-multipart httpx pytesseract Pillow`. Install the `tesseract-ocr`
  system package (dev machine, CI, Makefile setup target) — the non-mocked OCR
  smoke test (#12) runs it. Delete `backend/recipe.db`. `.gitignore` +=
  `uploads/`, `receipts/`. Old tests still green.
- **Phase 1 — pure core.** `normalize.py`, `units.py`,
  `services/ingredient_parse.py` + `test_units.py`, `test_ingredient_parse.py`.
  Nothing else touched.
- **Phase 2 — auth + app factory.** Introduce `create_app(settings, engine)` in
  `main.py` and `make_engine` / `make_session_factory` in `database.py`; the
  module-level `app` calls the factory. Add the `PRAGMA foreign_keys=ON` /
  `busy_timeout` connect listener (prod + test engines, #14/#8). `User`/`Session`
  models, `security.py`, `schemas/auth.py` (incl. `code`), `routers/auth.py`
  (registration default off + `code` check, #15), `config` additions
  (`allow_registration` default false). conftest: build via the factory with a
  temp dir + test engine (no import-order hack, #H2); `user` + `auth_client`;
  migrate `test_recipes.py` to `auth_client`; add
  `dependencies=[Depends(get_current_user)]` to the recipes router.
  `test_auth.py`. End: existing recipe CRUD works, now gated; login works; tests
  touch no `recipe.db` / `uploads/`.
- **Phase 3 — structured recipes + photo.** Expand `Recipe`, add
  `RecipeIngredient`, drop the old text cols; `schemas/recipe.py` nested +
  validation; rewrite `routers/recipes.py` for nested create/replace; `config`
  `upload_dir` + `receipts_dir`; `create_app` `makedirs` both dirs before
  mounting `/uploads` (#H2/#11); `POST /{id}/photo`. Expand `test_recipes.py`;
  add `test_validation.py` (#H4). Delete `recipe.db`. End: full structured
  recipe CRUD + photos.
- **Phase 4 — inventory + math services + grocery receipt OCR.**
  `InventoryItem` model with `(match_name, unit_bucket)` composite unique +
  editable `match_name` + `CHECK(quantity >= 0)` (#2); `services/inventory_math.py`
  (`check_availability` with aggregation + `all_available` semantics #4;
  `add_to_inventory_calc` as a bucketed upsert, no blind `+=` #2; `deduct_calc`
  recording `requested`/`deducted`/`before`/`after` #16); `routers/inventory.py`
  CRUD incl. PATCH `match_name`; `GET /api/recipes/{id}/availability`. **Plus:**
  `ReceiptImport`/`ReceiptItem` models (image under `receipts_dir`, `applied_*`
  snapshot cols); `services/receipt_ocr.py` (Pillow validate + `MAX_IMAGE_PIXELS`
  + `pytesseract(timeout=…)` under a `Semaphore`, #12) + `services/receipt_parse.py`;
  `routers/receipts.py` (`POST /api/receipts` upload+OCR+parse, `GET` list/detail,
  `GET /{id}/image` auth'd `FileResponse` #11, `PATCH .../items/{item_id}` #17,
  `POST .../apply` one-txn + null-qty guard #5, `DELETE`); `/api/health` reports
  tesseract availability (#12); registered in `main.py`. `test_inventory.py`,
  `test_inventory_math.py`, availability tests, `test_receipt_parse.py`,
  `test_receipts.py` (incl. the non-mocked OCR smoke test). End: inventory CRUD +
  missing-ingredient check + receipt-driven stock updates.
- **Phase 5 — cook = deduct, made-tracking, and reviews.** `CookLog` model
  (with `deducted: bool = True` from the start; deductions carry
  `requested`/`deducted`/`before`/`after`, #16); `POST /api/recipes/{id}/cook
  {multiplier, deduct=true}` using `deduct_calc` when `deduct=true` (service
  proposes, router applies atomically in one transaction, #H3), skipping it (but
  still logging) when `deduct=false`; `GET /api/recipes/{id}/cook-logs`
  (made-history, newest first). **Plus:** `routers/cook_logs.py` —
  `GET /api/cook-logs` (paginated) + `GET /api/cook-logs/{log_id}` (#H5);
  `RecipeReview` model; `POST /api/recipes/{id}/cook-logs/{log_id}/reviews`;
  `GET /api/recipes/{id}/reviews`; `RecipeRead` nests `reviews`. Cook,
  made-history, and review tests in `test_recipes.py`; global reads in
  `test_cook_logs.py` (#H5).
- **Phase 6 — grocery lists.** `GroceryList`/`GroceryListItem` models (with
  `submitted_at` + `applied_*` cols, #6); `generate_lines` in `inventory_math.py`
  (netting against summed compatible rows); `routers/grocery.py` (create-from-
  recipes, get, list, add manual item, **PATCH = state/field edits only, 409 on
  frozen lines**, `POST /{id}/submit` → one-txn `add_to_inventory` + freeze,
  delete). `test_grocery.py`. End: backend feature-complete.
- **Phase 7 — URL import + recipe research.** `services/import_recipe.py`:
  `fetch_bytes` (scheme allowlist, resolved-address block-list, no redirects,
  `raise_for_status`, `Content-Type` check, byte cap; #H1/#10b) split from
  `scrape_preview` (normal + `wild_mode` retry holding `html`, #10a);
  `ImportIngredient` mapping (#3). `POST /api/recipes/import` in `recipes.py`;
  `save=true` image download reuses `fetch_bytes`. **Plus:**
  `services/recipe_research.py`; `routers/research.py`
  (`POST /api/research/compare {urls, limit?}`, empty `urls` → 422, batch goes
  through `fetch_bytes`, #1/#H1); `config` gains `research_max_urls`,
  `import_max_bytes`, `import_fetch_timeout`, `max_image_bytes`,
  `import_allow_private`. `test_import.py` + `test_research.py` via
  `httpx.MockTransport` (incl. blocked-address / redirect / oversize).
- **Phase 8 — docs.** Update `README.md`, `CLAUDE.md`, `backend/.env.example`
  (new `RECIPE_*` vars: `RECEIPTS_DIR`, `IMPORT_MAX_BYTES`, `IMPORT_FETCH_TIMEOUT`,
  `MAX_IMAGE_BYTES`, `IMPORT_ALLOW_PRIVATE`, `OCR_TIMEOUT_SECONDS`,
  `OCR_MAX_CONCURRENCY`, `MAX_IMAGE_PIXELS`, `RESEARCH_MAX_URLS`,
  `REGISTRATION_CODE`; **no** Google search vars, #1; `tesseract-ocr` system
  requirement; `rm backend/recipe.db` note; new architecture & full API surface
  incl. `/api/receipts` and `/api/research`; LAN deploy
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`; "set
  `RECIPE_ALLOW_REGISTRATION=true` + a `RECIPE_REGISTRATION_CODE` to add
  accounts, then set it back to `false`" (#15); note that research and receipt
  parsing are best-effort by design — review before it's applied/saved; note
  that receipt images are private and grocery `submit` / receipt `apply` / cook
  are forward-only).

## Deferred (post-v1) — data model already accommodates

See `docs/features.md` for a consolidated roadmap: deferred capabilities,
infrastructure deferrals (Alembic, multi-user, remote hosting), the `FoodItem`
upgrade path, design invariants for extensions, and rejected items. The list
below is the source material; `features.md` provides context and upgrade paths.

- **"What can we make now"** — run `check_availability` across all recipes, filter
  `all_available`; add `GET /api/recipes/makeable`.
- **Staples / low-stock alerts** — add `is_staple bool` + `min_quantity float` to
  `inventory_items`; add `GET /api/inventory/low`.
- **Recipe research query mode** (#1) — resolve URLs from a free-text `query`.
  Google Custom Search JSON API is closed to new customers and ends 2027-01-01,
  so v1 ships URL-batch only. Revisit with a currently-available provider
  (Vertex AI Search, Brave, Bing) — one `httpx` call in a new
  `services/web_search.py`, plus `query`/config back on `ResearchCompareRequest`
  and the router.
- **Undo for forward-only actions** — cook, receipt `apply`, and grocery
  `submit` are all one-shot and forward-only in v1. Each already stores what it
  actually did (`CookLog.deductions`, `ReceiptItem.applied_quantity/unit`,
  `GroceryListItem.applied_quantity/unit`), so a future "undo" is a uniform
  reverse-the-snapshot operation across all three.
- **Frontend** — `react-router-dom`; `auth.tsx` + `RequireAuth`; namespaced
  `api.ts` injecting the bearer token; `types.ts` mirroring the new schemas;
  pages: Login, RecipeList (search/filter + multi-select → grocery list),
  RecipeDetail (scale control, availability panel, "mark as cooked" with a
  deduct/no-deduct toggle, made-history + review form, nested past reviews),
  RecipeForm (dynamic ingredient rows, import-from-URL, photo), Inventory,
  GroceryLists (check lines, then one "submit" that commits to inventory),
  ReceiptUpload (photo capture → editable parsed-line preview → apply),
  Research (URL batch → ingredient-frequency table).
  Vite proxy also forwards `/uploads`. Serving scaling is frontend-only for
  display; `availability`/`cook` take an explicit `multiplier` so the math stays
  server-side.

## Verification

- `cd backend && uv sync && uv run pytest` — all suites green.
- `cd backend && rm -f recipe.db && uv run uvicorn app.main:app --reload`, then at
  `/docs`:
  1. `POST /api/auth/register` → copy token → Authorize.
  2. `POST /api/recipes` with nested ingredients + steps; `GET` it back nested.
  3. `POST /api/recipes/{id}/photo` (any small image) → `photo_path` set →
     open `/uploads/<path>`.
  4. `POST /api/inventory` a couple of items; `GET
     /api/recipes/{id}/availability?multiplier=1` shows ok/short/missing.
  5. `POST /api/recipes/{id}/cook {multiplier:1}` → inventory quantities drop;
     `CookLog` recorded with `requested`/`deducted`/`before`/`after` per line.
  6. `POST /api/grocery {recipe_ids:[id]}` → list has only shortfalls,
     consolidated; `PATCH` a line `checked:true` → **inventory unchanged**;
     `POST /api/grocery/{id}/submit` → inventory rises, line `added_to_inventory`
     + `applied_quantity` set; `PATCH` that line again → 409.
  7. `POST /api/recipes/import {url:"<a supported recipe site>"}` → structured
     preview (ingredient rows carry `normalized_name`); a junk URL → 422
     `unsupported:true`; `http://localhost:8000/` or `http://169.254.169.254/`
     → 502 (SSRF guard, #H1).
  8. `POST /api/recipes/{id}/cook {multiplier:1, deduct:false}` → inventory
     unchanged, entry appears in `GET /api/recipes/{id}/cook-logs`; `POST
     .../cook-logs/{log_id}/reviews {rating:4, changes_next_time:"more salt"}`
     → shows up nested in `GET /api/recipes/{id}`.
  9. `POST /api/receipts` with a real receipt photo → draft preview with
     guessed lines; edit one via `PATCH /api/receipts/{id}/items/{item_id}`
     (its `raw_text`/`price_cents` stay put); `POST /api/receipts/{id}/apply` →
     inventory quantities increase, each applied line gets `applied_quantity`;
     re-`apply` → 409; an included line with no quantity → `apply` 422 and the
     receipt stays draft. `GET /api/receipts/{id}/image` returns the photo only
     with a token; it is **not** reachable under `/uploads`.
  10. `POST /api/research/compare {urls:["<3+ links for the same dish>"]}` →
      ingredient percentages match a manual count; `{urls:[]}` → 422.
  11. `GET /api/cook-logs` lists cook logs across recipes newest-first;
      `GET /api/cook-logs/{id}` returns one; delete that recipe → the log is
      still returned (#H5).
- Confirm `GET` on any data route without `Authorization` → 401.
- Confirm a recipe ingredient / receipt item `quantity: -1` or `0`, or a grocery
  `multiplier: 0` / `inf` → 422 (#H4).

## Critical files

- `backend/app/models.py` — all new tables, incl. `InventoryItem` composite
  unique `(match_name, unit_bucket)` (#2), `CookLog.deducted` + richer
  `deductions` (#16), `RecipeReview`, `ReceiptImport`/`ReceiptItem` with
  `applied_*` snapshots (#5), `GroceryListItem.submitted_at`/`applied_*` (#6),
  `CHECK` constraints (#13).
- `backend/app/database.py` — `make_engine` / `make_session_factory` helpers
  (#H2) + `PRAGMA foreign_keys=ON` + `busy_timeout` connect listener (#14/#8).
- `backend/app/main.py` — `create_app(settings, engine)` factory (#H2):
  `makedirs` both dirs then `/uploads` mount (#11), 7 routers, `/api/health`
  reports tesseract (#12), lifespan `create_all` on the injected engine.
- `backend/app/routers/recipes.py` — nested CRUD + `/import` + `/photo` +
  `/availability` + `/cook` (with `deduct`) + `/cook-logs` +
  `/cook-logs/{id}/reviews` + `/reviews`.
- `backend/app/routers/cook_logs.py` — `GET /api/cook-logs` (paginated) +
  `GET /api/cook-logs/{log_id}` (#H5) — new router.
- `backend/app/routers/receipts.py` (incl. auth'd `GET /{id}/image` #11 and
  per-item `PATCH .../items/{item_id}` #17), `routers/research.py` (URL-batch
  only #1) — new routers.
- `backend/app/routers/grocery.py` — `PATCH` items (state/edit only) +
  `POST /{id}/submit` (#6).
- `backend/app/services/receipt_ocr.py` (Pillow validation + `pytesseract`
  timeout + `Semaphore`, #12), `services/receipt_parse.py`,
  `services/recipe_research.py` — new services.
- `backend/app/services/import_recipe.py` — `fetch_bytes` (SSRF guard: scheme +
  resolved-IP block-list + no redirects + content-type + byte cap, #H1/#10b) +
  `scrape_preview` (`wild_mode` retry #10a) + `ImportIngredient` mapping (#3).
- `backend/app/normalize.py` — descriptor stripping (#7).
- `backend/app/config.py` — new `RECIPE_*` settings: `receipts_dir`,
  `import_max_bytes`, `import_fetch_timeout`, `max_image_bytes`,
  `import_allow_private` (#H1), `ocr_timeout_seconds`, `ocr_max_concurrency`,
  `max_image_pixels`, `research_max_urls`, `registration_code`;
  `allow_registration` default `false` (#15). No Google search settings (#1).
- `backend/tests/conftest.py` — factory-built app `create_app(test_settings,
  test_engine)` (#H2), FK-pragma on the test engine (#14), registration-on
  settings, `auth_client` (new default) + `user`.
- `backend/app/schemas.py` → becomes `backend/app/schemas/` package, plus new
  `receipt.py` and `research.py` modules within it.
- New: `backend/app/units.py`, `security.py`,
  `services/{ingredient_parse,import_recipe,inventory_math,receipt_ocr,receipt_parse,recipe_research}.py`,
  `routers/{auth,cook_logs,inventory,grocery,receipts,research}.py`.

## Status

- [x] Requirements gathered
- [x] Codebase exploration
- [x] Design pass
- [x] Final plan written and approved
- [x] Git repo initialised, skeleton pushed, this plan committed to `docs/plan.md`
- [x] Adversarial review pass 2 folded in (see Revisions table; 17 findings dispositioned)
- [x] Hardening pass 3 folded in (5 items lifted from the parallel review branch; #H1–#H5)
- [ ] Phase 0 — reset & deps (not started; awaiting go-ahead)
