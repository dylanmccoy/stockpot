# Plan: Household Recipe + Food Inventory App (Core-Loop Backend v1)

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
stock; submitting a checked grocery list adds stock. There is **no meal
planning** — the unit of work is "make *this* recipe now".

**v1 is backend-only** (user's choice): the core-loop backend features + tests,
delivered in testable phases. The full frontend is a separate later effort; the
existing `App.tsx`/`api.ts`/`types.ts` will not function against the new API and
are left untouched until then. The v1 interaction surface is the OpenAPI docs
(`/docs`) and the test suite.

**De-scope decision (2026-08-31).** An earlier revision of this plan (committed at
`5144c25`, 1117 lines) also carried photo upload, grocery-receipt OCR, URL
import, cross-recipe ingredient research, and per-cook reviews, with two
adversarial-review passes and a hardening pass folded in (22 findings). That was
roughly **2x the scope a v1 needs** for a LAN-only SQLite app: it bundled four
independent features, each with its own dependency and failure surface, onto the
core loop. v1 is now trimmed to the cooking loop alone; the five cut features
move to **§Deferred to v2** below with their full specs intact. **The complete
pre-trim plan and all 22 review findings are preserved verbatim at
`git show 5144c25:docs/plan.md`** — nothing is lost, only deferred.

## Constraints

- **Planning task only — no code is written as part of this goal.** Deliverable
  is this plan.
- Extend the existing repo. Keep the one-way import layering
  (`config → database → models → schemas/routers → main`) and the test seam
  (`create_app(test_settings, test_engine)` builds an app wired entirely to the
  injected engine — no `dependency_overrides`, #P2 — real HTTP through
  `TestClient`).
- No new heavy infrastructure: still SQLite, still `create_all` (no Alembic yet),
  still `uv` + `npm`. LAN-only — no HTTPS-in-app, email flows, or third-party IdP.
- **No LLM / AI services anywhere.**
- Minimal-ethos: smallest thing that works; a new dependency needs a stated
  justification.
- `types.ts` stays a hand-maintained mirror of the Pydantic schemas (relevant to
  the later frontend effort).
- v1 excludes: meal planning; "what can we make now"; staples / low-stock
  alerts; **photo upload; grocery-receipt OCR; URL import; recipe research;
  per-cook reviews**. The data model must not preclude any of them — see
  **§Deferred to v2**, which carries the execution-ready spec for each.

## Revisions — adversarial review pass 2 (historical record)

A second adversarial review of the pre-trim plan raised 17 findings. The table is
kept as the record of what was already reasoned through. After the de-scope, the
findings split:

- **Still live in v1** (core-loop features): #2, #4, #6, #7, #8, #9, #13, #14,
  #16 (the cook-log half).
- **Moved to v2 with their feature**: #1, #3, #5, #10a, #10b, #11, #12, #15
  (registration — *stays in v1*, see Auth), #16 (the review-nesting half), #17.

| # | Finding | Decision |
|---|---|---|
| 1 | Google Custom Search JSON API is closed to new customers (EOL 2027-01-01). | **De-scoped.** `query` mode removed; `research` (v2) takes `urls` only. |
| 2 + 7 | One `inventory_items` row per normalized name silently merges incompatible units / prep-adjective mismatches (`diced tomatoes` ≠ `tomato`). | **Fixed (v1).** Composite `(match_name, unit_bucket)` uniqueness; drop the blind `+=` fallback; descriptor-stripping in `normalize.py`; editable `match_name` on inventory rows. `FoodItem` still deferred. |
| 3 | `recipe_research` reads `ing.normalized_name`, absent from the preview ingredient shape. | **Fixed (v2).** New `ImportIngredient` DTO carries `normalized_name` + `raw_text`. |
| 4 | Availability compares each ingredient line against the full stock row (double-spend) and `all_available` ignores `have_uncertain`. | **Fixed (v1).** Aggregate requirements by `(match_name, dimension)`; `all_available` true only when every quantified line is `ok`. |
| 5 | Receipt apply silently skips included lines with no quantity, then locks the receipt; `applied` is a bare bool. | **Fixed (v2).** Reject apply when any included line lacks a finite positive quantity; apply in one transaction; snapshot `applied_quantity`/`applied_unit` per line. |
| 6 | Grocery check/uncheck mutates inventory per-line and reverses using post-edit field values → drift. | **Fixed (v1, user-directed).** Check-off no longer touches inventory. `POST /api/grocery/{id}/submit` adds every checked, quantified, not-yet-applied line in one transaction and **freezes** those lines (forward-only). No uncheck-reversal. |
| 8 | No atomicity / concurrency contract for read-modify-write on `quantity`. | **Fixed (v1, light).** SQLite `UPSERT` for `add_to_inventory`; `PRAGMA busy_timeout`; `UPDATE ... WHERE status=<expected>` guards on one-shot transitions. No dedicated concurrency test suite. |
| 9 | COUNT dimension treats `jar`/`can`/`package`/`clove`/… as 1:1 with `each`. | **Fixed (v1).** COUNT keeps only `unit`/`each`/`""`, `dozen`, `pair`; the rest move to UNKNOWN (opaque, exact-string match). |
| 10a | `_fetch_and_scrape` never returns `html`, so the `wild_mode=True` retry is dead code. | **Fixed (v2).** Split the fetch (`fetch_bytes`) from `scrape_preview(html, url)`; the route holds `html` for the retry. |
| 10b | Fetch is unbounded (no size cap, no status check). | **Fixed (v2).** Streamed byte cap + `raise_for_status` + SSRF guard. |
| 11 | Public `/uploads` would also serve receipt images (PII); `StaticFiles` mounts before the dir exists. | **Fixed (v2).** Receipts stored under a private dir, served only via an auth'd `FileResponse` route. |
| 12 | OCR has no decoded-pixel / time / concurrency limit; every test monkeypatches `_ocr_image`, so a missing binary ships green. | **Fixed (v2).** Pillow validation + `pytesseract` `timeout` + process semaphore; `/api/health` reports tesseract; one non-mocked CI smoke test. |
| 13 | Recipe/grocery quantities and multipliers accept negative and non-finite floats. | **Fixed (v1).** `gt=0` when non-null + `allow_inf_nan=False` on every quantity/multiplier; inventory stays `ge=0` finite. |
| 14 | `database.py unchanged` — SQLite ignores declared cascades / `SET NULL` without `PRAGMA foreign_keys=ON`. | **Fixed (v1).** Connect-time `PRAGMA foreign_keys=ON` (+ `busy_timeout`) in `database.py` and the test engine; `passive_deletes=True` where DB cascade is relied on. |
| 15 | Registration on by default; no `code` field; every account has full mutation access. | **Fixed (v1).** `RECIPE_ALLOW_REGISTRATION` defaults **false**; when true a configured `RECIPE_REGISTRATION_CODE` is required; `code` added to `RegisterRequest`. Single shared household / full-trust members stated explicitly. |
| 16 | `CookLog.deductions` records the requested amount, not the actual clamped delta; review responses lack their cook event's context. | **Fixed.** v1: each deduction records `requested` / `deducted` / `before` / `after`. v2: `RecipeReviewRead` nests `CookEventMini`. *(Refined by #P7: all four are canonical, `deducted_unit` added.)* |
| 17 | Receipt items use PUT full-replace; the replacement payload loses OCR evidence. | **Fixed (v2).** Per-item `PATCH .../items/{item_id}` with stable ids; OCR rows (`raw_text`, `price_cents`) never destroyed. |

## Revisions — hardening pass 3 (historical record)

Five treatments lifted from a parallel review branch. Post-trim:

| # | Change | v1 / v2 |
|---|---|---|
| H1 | **SSRF-guarded `fetch_bytes`** as the single network primitive: scheme allowlist, resolve host and reject private/loopback/link-local/ULA/multicast/`169.254.169.254`, `follow_redirects=False`, `raise_for_status`, `Content-Type` allowlist, stream to a byte cap. | **v2** — v1 makes no outbound HTTP calls at all. |
| H2 | **App factory** `create_app(settings, engine) -> FastAPI` + `make_engine(url)` / `make_session_factory(engine)` in `database.py`; module-level `app = create_app(settings, engine)` for uvicorn. | **v1** — kept. It is a clean testing seam (conftest passes a settings object + test engine, no global mutation, no import-order hack), not scope bloat. |
| H3 | **Concurrency contract.** Pure `services/` **propose** an adjustment DTO; the **router performs** the atomic write and owns the single transaction. On `IntegrityError` or lock/`busy_timeout` timeout the endpoint returns **409**, not 500. | **v1** — kept. Governs cook + grocery submit. |
| H4 | **Validation completeness.** `GroceryListCreate.recipe_ids` non-empty, unique, all exist (else 422); `multipliers` keys ⊆ `recipe_ids` (else 422). A dedicated `test_validation.py` covers negative/`0`/`inf`/`nan` on every numeric field. | **v1** — kept. |
| H5 | **Global cook-log reads.** New `routers/cook_logs.py`: `GET /api/cook-logs` (all recipes, newest-first, paginated) and `GET /api/cook-logs/{log_id}`. | **v1** — kept. A cook log survives its recipe's deletion; without these endpoints it is unreachable afterward. |

Judgement calls that stand: grocery `submit` is forward-only, no per-line
`/undo` (the Deferred "undo for forward-only actions" covers it uniformly);
`match_name` is editable on inventory rows only, not on recipe ingredients
(`FoodItem` is the real fix); `AvailabilityLine` stays one-per-ingredient (now
with group-level fields, #R7).

**Recipe-side match divergence — residual v1 limitation (#R4).** With one
inventory row per `(match_name, unit_bucket)` and `match_name` editable on the
inventory row only, two recipe labels that *should* map to one stock item but
`normalize_name` to different strings (`flour` vs `all-purpose flour` vs `plain
flour`) cannot both be matched by editing the inventory row — fixing one label
breaks the other. The v1 lever is **`normalize.py` tuning** (add such tokens to
the leading-descriptor stoplist so they collapse to a common form). The complete
fix — recipe-ingredient-side aliasing or a shared `FoodItem` identity — is
**v2** (see §Deferred, `FoodItem` upgrade path). v1 does not add an
`ingredient_aliases` table.

## Revisions — review pass 4 (2026-08-31)

A post-de-scope adversarial review (`NO-SHIP`) raised 8 core-loop findings; all
8 are folded in here. Full adjudication (failure scenarios, risk trade-offs) in
`/home/dylan/.claude/plans/reviewed-updated-plan-here-abstract-tome.md`.

| # | Finding | Treatment |
|---|---|---|
| R1 | Opaque units (`can`, `jar`, `bag`, `clove`) had no arithmetic model — `to_base()` returns `None` for them, so availability/cook/grocery `to_base(...).amt` crashed and identical opaque stock never netted. | **Fixed.** Availability, `deduct`, and `generate_lines` branch on `bucket is opaque` **before** any `to_base` call and do arithmetic directly on the stored amount. `add_quantities` merges opaque `Quantity`s whose unit strings are equal. Same-unit opaque now nets (`2 can` need − `1 can` stock = `1 can` short). Cross-unit opaque (`can` vs `jar`, `clove` vs `bulb`) stays `nettable=false` / `have_uncertain`. |
| R2 | The `ON CONFLICT … SET quantity = quantity + convert(…)` upsert invoked a `convert()` SQLite does not have — the #8/#H3 atomicity guarantee was not actually delivered. | **Fixed.** `inventory_items` stores `quantity_base` (canonical: g / ml / count / exact opaque amount) as the source of truth; the pure service converts the incoming amount to base *before* the INSERT (no DB-state dependency, no race). The upsert is the valid atomic `SET quantity_base = quantity_base + excluded.quantity_base`. `quantity` / `unit` become display-only. *(Refined by #P1: replaced by a single `display_unit` preference; the display quantity is recomputed from `quantity_base` on read.)* |
| R3 | Concurrent cooks could lose a deduction despite "one transaction": `BEGIN DEFERRED` + a shared read → both compute from the same stale value → the second commits over the first. `busy_timeout` only waits. | **Fixed.** Mutating transactions (cook, grocery `submit`) run `BEGIN IMMEDIATE` (write lock acquired before the first read) via a `database.py` hook. Adds `test_concurrency.py` (file-backed SQLite, two connections: one cook-race, one submit-race) — the in-memory `StaticPool` fixture cannot exercise this. #H3's 409-on-`busy_timeout` stands. |
| R4 | Stripping `fresh`/`dried`/`ground` in `normalize.py` silently merged identity-distinct foods; and one inventory `match_name` cannot express two recipe labels. | **Partially fixed.** `normalize.py` stoplist keeps cut-style (`diced`, `chopped`, …) and size/quality (`large`, `ripe`, …) descriptors but **no longer strips state/process words** (`fresh`, `dried`, `ground`, and none of `cooked`/`raw`/`smoked` added) — those are identity-bearing. Recipe-side aliasing stays a documented v1 limitation (see above); `FoodItem` is the v2 fix. |
| R5 | `submit` auto-archived when "every line applied or unchecked" — but the same list was promised to accept a later `submit` of newly-checked lines, which the `status='active'` guard would 409. A no-op `submit` also archived. | **Fixed.** `submit` never changes list status. A list stays `active` until an explicit `POST /api/grocery/{id}/archive` (guarded `WHERE status='active'`). `submit` with nothing checked is an explicit no-op (200, empty result), not a state change. |
| R6 | Availability filtered inventory to the required bucket only, so `clove`-need vs `bulb`-stock returned `missing`, never `have_uncertain` — that status was near-unreachable. | **Fixed.** Availability and `deduct` load **all** inventory rows for the `match_name`, then partition: compatible-bucket rows → do the math; else if any other-bucket row exists → `have_uncertain` + `nettable=false`; `missing` only when no row for the name exists at all. *(Refined by #P4: only **positive-stock** rows count; a row at `quantity_base = 0` is treated as absent, so `missing` also covers "only zero rows".)* |
| R7 | Aggregated availability emitted one line per member ingredient, each carrying the *group's* `need`/`have`/`short` — a client summing per-line `need` double-counts. | **Fixed.** One line per ingredient still, but per-line `need`/`need_unit` = that row's own quantity ×M; group totals move to new `group_key` / `group_need` / `group_have` / `group_short` fields (identical across members). `status` and `all_available` unchanged. *(Refined by #P5: all figures canonical, `group_unit` added, legacy per-line `have`/`have_unit`/`short` removed.)* |
| R8 | The verification script starts a default server (registration disabled) and calls `/register` — a guaranteed 403 — and omits the `code`. | **Fixed.** Verification step 1 sets `RECIPE_ALLOW_REGISTRATION=true` + `RECIPE_REGISTRATION_CODE=devcode`, passes `code`, and restarts without those vars afterward. |

Deferred-block wording tightened (#R-def): the Research URL-list cap, the OCR
CI-fatal-tesseract rule, OCR upload-failure cleanup, review-read reachability
after recipe deletion, and the URL-import streaming contract are each stated
explicitly in §Deferred rather than delegated to the archived revision.

## Revisions — review pass 5 (2026-08-31)

A further pass on the core-loop v1 raised 7 findings (`#P1`–`#P7`), all folded in
here. **Cross-cutting outcome:** every quantity in every v1 response is expressed
in the bucket's **canonical unit** and carries an explicit unit label — `g` /
`ml` / `unit` for known dimensions, the opaque unit string for opaque buckets.
Only recipe-ingredient rows (the author's own words) and request bodies
(converted on write) keep arbitrary units.

| # | Finding | Treatment |
|---|---|---|
| P1 | `inventory_items.quantity` / `unit` stored "the amount+unit of the most recent add" — a value with no meaning after the next cook — and `POST` vs `PATCH` semantics were never distinguished. | **Fixed.** A row stores `quantity_base` (source of truth) + `display_unit` (a *preferred unit only*); the human-facing quantity is `from_base(quantity_base, dim, display_unit)` recomputed on **every read**, never persisted. `POST /api/inventory` = **additive upsert** (`quantity_base += …` within the `(match_name, unit_bucket)` row). `PATCH /api/inventory/{id}` = **absolute replacement** of that row (sets `quantity_base` outright from the given amount+unit). `PATCH` is **within-bucket only** — a `unit` that would change `unit_bucket` → **422** ("remove and re-add"). A `PATCH` that sets `match_name` such that the row's new `(match_name, unit_bucket)` is already held by another row → **409** (no auto-merge in v1); `POST` cannot collide (it upserts on that key by definition). Tests: add → cook → GET (display recomputed from base), `PATCH` absolute reduction, `PATCH` display-unit change within a bucket, 409 collision. |
| P2 | `conftest.py` needed a second, independent DB-wiring mechanism (`dependency_overrides[get_db]`) on top of the injected `test_engine` — two ways to point the app at a database, kept in sync by hand. | **Fixed.** `create_app(settings, engine)` **derives and installs an app-local session dependency** closed over the injected `engine` (on `app.state`, exposed as `get_db` / `SessionDep`); there is no importable module-global session factory to override. Injected settings are reachable via a `get_settings(request)` dependency (`request.app.state.settings`) and directly as `app.state.settings`. `security.py` / `get_current_user` consume **those** dependencies, not module globals. `conftest.py` builds the app with `create_app(test_settings, test_engine)` and **overrides nothing** — the injected engine is the only DB wiring. |
| P3 | Only `cook` + grocery `submit` ran `BEGIN IMMEDIATE`; every other request (auth `last_used_at` bump, GETs, inventory/recipe CRUD) used `BEGIN DEFERRED`. A DEFERRED transaction that lazily upgrades to a write (a GET that also bumps `last_used_at`) can still deadlock a concurrent writer, and the policy was left implicit. | **Fixed (explicit simple policy).** **All** request-scoped SQLite transactions `BEGIN IMMEDIATE` — auth and GETs included — via the `database.py` hook. The "short auth session, then a mutation session" alternative is rejected as unnecessary complexity for a two-user LAN app. **Trade-off documented:** every request now serializes on the single SQLite write lock; for the intended concurrency (≤2 members) the added contention is immaterial and lost updates are impossible everywhere, not just on the two mutating paths. Exercised through authenticated HTTP requests in `test_concurrency.py` (not only the low-level races). |
| P4 | Availability / deduct partitioned inventory into compatible vs. other-bucket by **row existence**, so a row cooked down to `quantity_base = 0` still forced `have_uncertain` (incompatible bucket) or blocked `missing` (compatible bucket) — a stale empty row poisoned the result. | **Fixed.** Only **positive-stock** rows (`quantity_base > 0`) are considered. Partition: positive-compatible rows → do the math (`ok` / `short`); else any positive-incompatible row → `have_uncertain` + `nettable=false`; otherwise → `missing`. A zero-stock row is treated exactly as if it did not exist, so `cook`-to-zero yields `missing` in availability and a full-need grocery line. Test: cook a food to `quantity_base = 0`, then assert availability `missing` and a grocery line for the whole requirement. |
| P5 | `AvailabilityLine.group_need` / `group_have` / `group_short` were converted "`from_base` back to `g.unit`" — an undefined per-group unit — and shipped as bare floats with no unit field; the pre-#R7 per-line `have` / `have_unit` / `short` fields survived in the schema with no writer. | **Fixed.** Add **`group_unit`**; `group_need` / `group_have` / `group_short` are in that canonical unit (`g` / `ml` / `unit` / opaque string), identical across every member line. **Remove** per-line `have` / `have_unit` / `short`. Per-line `need` / `need_unit` are also canonical now — the row's own `quantity × M` converted to base — so `need_unit == group_unit` and a client summing per-line `need` still gets the group total (the #R7 double-count fix holds; only its unit changes). |
| P6 | `get_current_user(authorization: str = Header(...))` made the header **required**, so a missing token returned FastAPI's 422, and malformed / wrong-scheme / expired tokens had no stated handling. | **Fixed.** `authorization: str \| None = Header(default=None)`. The dependency returns **401** explicitly for all five: missing header, malformed value (not exactly `<scheme> <token>`), wrong scheme (not `Bearer`, case-insensitive), token not found, token row past `expires_at`. All five are asserted in `test_auth.py`. |
| P7 | `CookLog.deductions[].deducted` was the canonical delta converted back to the undefined per-group `unit`, while `before` / `after` stayed canonical — mixed scales in one dict, no `deducted_unit`, and `requested` undefined for a group whose members use different units. | **Fixed.** `requested` and `deducted` are both in the bucket's **canonical unit**; add **`deducted_unit`**, with `requested_unit == deducted_unit == inventory_unit`. `requested` = the group's summed need in canonical units (order-independent, hence deterministic regardless of member unit mix). `before − deducted == after` now holds within every entry. Test: stock held in `g`, recipe asks in `kg` (and vice versa) — assert the recorded `requested` / `deducted` / `before` / `after` are all canonical and self-consistent. |

## Done criteria

**Backend v1 is done** when, verified through `/docs` and `uv run pytest`:

1. **Auth.** A user can register (only while `RECIPE_ALLOW_REGISTRATION=true`, and
   only with the correct `RECIPE_REGISTRATION_CODE` when one is configured — see
   #15) and log in, receiving a bearer token. Every data endpoint except
   `/api/health` and the public auth routes returns **401** for a missing,
   malformed, wrong-scheme, unknown, or expired token (#P6).
2. **Structured recipes.** `POST/PUT /api/recipes` accept nested ingredient rows
   (`quantity` nullable, `unit` nullable, `item`, `note`), ordered `steps`,
   `tags`, `cuisine`, `prep_time`, `cook_time`, `servings`, `source_url`,
   `notes`. `GET` returns them nested and ordered. PUT fully replaces nested rows.
   `normalized_name` is computed server-side on every ingredient.
3. **Inventory.** `/api/inventory` supports list / add / edit / remove of
   `{item, quantity ≥ 0, unit}` items, one row per `(match_name, unit_bucket)`
   (#2); `match_name` is editable to correct matching. `POST` is an **additive
   upsert** into the matching `(match_name, unit_bucket)` row; `PATCH /{id}` is an
   **absolute replacement** of that row — within its bucket only (a
   bucket-changing `unit` → 422; a colliding `match_name` → 409) (#P1). Each row
   stores `quantity_base` + a `display_unit`; the shown quantity is computed from
   base on every read (#P1).
4. **Missing-ingredient check.** `GET /api/recipes/{id}/availability?multiplier=M`
   returns per-ingredient `status` in
   `{ok, short, missing, to_taste, have_uncertain}` with unit conversion applied
   when units are compatible and an explicit uncertain state otherwise. Multiple
   lines for the same food are aggregated before comparison (#4); each line
   carries its **own** `need` / `need_unit` plus the group totals in `group_need`
   / `group_have` / `group_short` / `group_unit` / `group_key` (#R7/#P5) — all in
   the bucket's **canonical unit** (#P5). `have_uncertain` is returned whenever
   the food is in **positive** stock only in an incompatible bucket; a row at
   `quantity_base = 0` counts as absent, so cook-to-zero → `missing` (#R6/#P4).
   `all_available` is true only when every quantified line is `ok`.
5. **Cook deducts stock, or just logs it.** `POST /api/recipes/{id}/cook
   {multiplier, deduct?}` — `deduct=true` (default) subtracts ingredients from
   inventory (converting units, clamping at 0, skipping unmatched); `deduct=false`
   skips inventory entirely. Either way it writes an auditable `CookLog` row,
   so **every** made-event is recorded. `GET /api/recipes/{id}/cook-logs`
   lists them newest-first — the made-history — and `GET /api/cook-logs` /
   `GET /api/cook-logs/{log_id}` read across all recipes and still resolve a log
   after its recipe is deleted (#H5).
6. **Grocery list.** `POST /api/grocery {recipe_ids, multipliers?}` creates a
   persisted list whose lines are consolidated requirements across the selected
   recipes minus current stock; only shortfalls appear; unit-incompatible lines
   are flagged `nettable=false`, not dropped. Manual one-off items can be added.
   `PATCH` on a line toggles `checked` and edits its fields — **no inventory
   effect** (#6). `POST /api/grocery/{id}/submit` adds every checked, quantified,
   not-yet-applied line to inventory in one `BEGIN IMMEDIATE` transaction (#R3)
   and freezes those lines (forward-only; a later `PATCH` on a frozen line →
   409). `submit` **never archives** the list (#R5); re-submitting picks up only
   newly-checked lines, and a `submit` with nothing checked is a 200 no-op. A
   list stays `active` until an explicit `POST /api/grocery/{id}/archive`.
7. **Unit conversion** is a standalone pure module with a documented supported-
   unit set and defined behavior for unknown / incompatible pairs.
8. **Tests green.** `uv run pytest` passes: units, ingredient parser, inventory
   math, auth gating (incl. the five 401 cases — missing / malformed /
   wrong-scheme / invalid / expired, #P6), input validation (#H4), recipe CRUD
   with nested rows, availability (incl. cook-to-zero → `missing`, #P4), cook
   (both `deduct` modes; canonical `requested` / `deducted` / `deducted_unit`,
   kg-from-g stock, #P7) + cook-log reads (#H5), inventory CRUD (additive `POST`
   vs absolute `PATCH`, bucket-change 422, collision 409, #P1), grocery
   generation + submit.
9. **Docs.** `README.md`, `CLAUDE.md`, `backend/.env.example` updated for the
   new architecture, env vars, and the `rm backend/recipe.db` reset procedure.

## Data model (`backend/app/models.py`, one file)

Layering with new modules:
`config → database → normalize/units → models → security/services → schemas/routers → main`.

| Table | Columns (type — notes) |
| --- | --- |
| **users** | `id` PK · `username` str(50) unique, regex `^[A-Za-z0-9_.-]{3,50}$` · `password_hash` str(255) argon2 · `created_at` dt(tz) |
| **sessions** | `id` PK · `token` str(64) unique indexed (`secrets.token_urlsafe(32)`) · `user_id` FK users CASCADE · `created_at` · `last_used_at` · `expires_at` (= created + `SESSION_TTL_DAYS`, default 30) |
| **recipes** | `id` PK · `title` str(200) min_len 1 · `notes` Text="" · `prep_time` int? ≥0 · `cook_time` int? ≥0 · `servings` float? >0 · `cuisine` str(100)? · `source_url` str(500)? · `photo_path` str(500)? *(reserved for v2 photo upload — nullable, unused in v1)* · `tags` JSON `list[str]`=[] · `steps` JSON `list[str]`=[] · `created_at` · `updated_at` (`onupdate`) · `created_by_id` FK users? (no cascade) |
| **recipe_ingredients** | `id` PK · `recipe_id` FK recipes CASCADE · `position` int 0-based · `quantity` float? (null = to taste) · `unit` str(30)? · `item` str(200) · `note` str(200)? · `normalized_name` str(200) indexed, **server-computed** · `raw_text` str(300)? *(reserved for v2 import — nullable, unused in v1)* · index `(recipe_id, position)` |
| **inventory_items** | `id` PK · `item` str(200) display · `normalized_name` str(200) indexed, server-computed · `match_name` str(200) indexed (defaults to `normalized_name`, **user-editable** — the recipe↔inventory match key, #2/#7) · `unit_bucket` str(20) (`mass`/`volume`/`count`/`opaque:<canonical unit>`, #2) · `quantity_base` float ≥0 finite default 0, `CHECK(quantity_base >= 0)` — **source of truth**, in the bucket's canonical unit (g / ml / count / exact opaque amount), #R2 · `display_unit` str(30)? — a **preferred display unit only** (#P1); the shown quantity is `from_base(quantity_base, dim, display_unit)` computed on every read, never stored; `None`/opaque → canonical unit · `updated_at` · `created_by_id` FK users? · **unique `(match_name, unit_bucket)`** (`POST` add = atomic `quantity_base += excluded.quantity_base` upsert within a bucket; `PATCH /{id}` = absolute set of `quantity_base`, within-bucket only, #P1) |
| **grocery_lists** | `id` PK · `name` str(200) default `"Groceries <date>"` · `status` str(20) `active`/`archived` · `source_recipe_ids` JSON `list[int]`=[] (informational, no FK) · `created_at` · `created_by_id` FK users? |
| **grocery_list_items** | `id` PK · `grocery_list_id` FK CASCADE · `item` str(200) · `normalized_name` str(200) indexed · `quantity` float? >0 finite when set · `unit` str(30)? · `checked` bool=false · `checked_at` dt? · `submitted_at` dt? (#6) · `source` str(20) `generated`/`manual` · `nettable` bool=true · `added_to_inventory` bool=false (idempotency guard + freeze flag, #6) · `applied_quantity` float? · `applied_unit` str(30)? (snapshot of what `submit` actually added, #6) |
| **cook_logs** | `id` PK · `recipe_id` FK recipes SET NULL · `recipe_title` str(200) snapshot · `multiplier` float=1 >0 · `deducted` bool=true (false = logged without touching stock) · `cooked_at` · `cooked_by_id` FK users? · `deductions` JSON=[] (`[{item, normalized_name, requested, requested_unit, deducted, deducted_unit, inventory_unit, before, after, applied, reason}]` — `requested`/`deducted`/`before`/`after` all in the bucket's canonical unit, `requested_unit == deducted_unit == inventory_unit`; empty when `deducted=false`; #16/#P7) |

Relationships: `Recipe.ingredients` → ordered by `position`,
`cascade="all, delete-orphan"`; read paths use `selectinload(Recipe.ingredients)`.
`GroceryList.items` cascade. Users are never deleted in v1 (nullable
`created_by_id`, no cascade).

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
  never an arithmetic merge of `1 + 500 → 501`. All inventory lookups fetch
  **every** row for a `match_name` and partition into compatible vs.
  other-bucket at the call site (#R6) — the "no compatible row but stock exists
  elsewhere" case is what surfaces `have_uncertain`.
- **Stored quantity is canonical (`quantity_base`), #R2.** Each row keeps its
  amount in the bucket's base unit — g for `mass`, ml for `volume`, count for
  `count`, the exact numeric amount for `opaque:<unit>` (unit equality is
  guaranteed by the composite key there). The incoming add is converted to base
  in the pure service *before* the write, so the upsert increment
  (`quantity_base = quantity_base + excluded.quantity_base`) is a genuine atomic
  SQL expression with no `convert()` and no read-modify-write. The row also
  stores a `display_unit` — a preferred unit **only**; the human-facing quantity
  is recomputed from `quantity_base` on every read and never persisted (#P1).
  There is no stored "last-add amount".
- **Opaque buckets do arithmetic too (#R1).** Within `opaque:can`, `2 need − 1
  stock = 1 short` — the composite key guarantees the unit string is identical,
  so the numbers add and subtract directly (no `to_base`). Only *cross-unit*
  opaque comparisons (`can` vs `jar`) are non-nettable.

**`backend/app/normalize.py`** (pure, no dep): `normalize_name(raw)` = strip →
lower → drop punctuation (keep spaces/hyphens) → collapse whitespace → **strip
leading prep/size descriptors** (a small stoplist: `diced`, `chopped`, `minced`,
`sliced`, `large`, `small`, `medium`, `boneless`, `skinless`, `ripe`, … —
documented tuning knob, #7) → naive singularize (irregular map
`{tomatoes→tomato, potatoes→potato, leaves→leaf, …}`, then `-ies→-y`,
`-ses/-xes/-oes→ -e`, trailing `-s` → drop). Remaining false matches are
corrected per-row via the editable `match_name`; no `inflect` dependency.

**State/process descriptors are NOT stripped (#R4).** `fresh`, `dried`,
`ground`, `cooked`, `raw`, `smoked` and the like change a food's identity and
its quantity semantics (`fresh yeast` ≠ `active-dry yeast`; dried herbs are
~3× the potency of fresh) — stripping them would silently merge distinct stock
items into one bucket. Only cut-style (`diced`, `chopped`, …) and size/quality
(`large`, `ripe`, …) descriptors, which do not change identity, are in the
stoplist. The stoplist remains a documented tuning knob; recipe-side match
divergence (`flour` vs `all-purpose flour`) is tuned here, with the residual
limitation noted in §Revisions — hardening pass 3.

## Module / router layout (`backend/app/`)

```
config.py     + allow_registration (default false, #15), registration_code?, session_ttl_days
database.py   make_engine(url) + make_session_factory(engine) helpers (#H2); default module-level
                engine/SessionLocal kept for the default app; on-connect listener:
                PRAGMA foreign_keys=ON, PRAGMA busy_timeout=5000 (#14/#8);
                BEGIN IMMEDIATE emitted for EVERY request-scoped transaction (#P3)
normalize.py  normalize_name()  (incl. descriptor stripping, #7)  [pure]
units.py      unit table + conversions                           [pure, no deps]
security.py   hash/verify_password (pwdlib), issue_token, get_current_user dep (consumes the
                app-local session + get_settings deps, #P2; optional header, 5 explicit 401s, #P6),
                CurrentUser alias
models.py     all tables
schemas/      package: common.py, auth.py, recipe.py, inventory.py, grocery.py  (__init__ re-exports)
services/
  ingredient_parse.py   parse_ingredient(text) -> row dict       [pure]
  inventory_math.py     check_availability, generate_lines, add_to_inventory_calc, deduct_calc  [pure, dataclasses in/out — PROPOSE an adjustment, never mutate, #H3]
routers/
  auth.py       /api/auth      register, login, logout, me
  recipes.py    /api/recipes   CRUD + /{id}/availability + /{id}/cook + /{id}/cook-logs
  cook_logs.py  /api/cook-logs  list (paginated, all recipes) + get by id (#H5)
  inventory.py  /api/inventory  CRUD — POST additive upsert, PATCH /{id} absolute replace (#P1)
  grocery.py    /api/grocery    lists + items (PATCH state only) + /{id}/submit (#6) + /{id}/archive (#R5) + delete
main.py       create_app(settings, engine) -> FastAPI (#H2): derive & install an app-local session
              dependency from the injected engine + stash settings on app.state / get_settings (#P2);
              include 5 routers; /api/health; lifespan create_all on the injected engine.
              Module-level `app = create_app(settings, engine)` for uvicorn.
```

**Rule (documented in CLAUDE.md):** `services/` functions take/return plain
dataclasses or dicts, **never ORM objects**; routers marshal ORM ↔ dataclass.
That is the unit-test seam. `services/inventory_math.py` imports only `units`,
`normalize`, stdlib. **A service proposes an adjustment DTO; the router performs
the atomic write and owns the single transaction (#H3).**

**Auth gating:** every router is
`APIRouter(..., dependencies=[Depends(get_current_user)])` except `auth`
(register/login public; logout/me protected) and inline `/api/health`. v1 mounts
**no** StaticFiles and serves **no** files — there is no `/uploads`.

## Unit conversion — `backend/app/units.py` (pure Python, no `pint`)

Dimensions: `MASS` (base **g**), `VOLUME` (base **ml**), `COUNT` (base **unit**).

Static synonym table `str → (Dimension, factor_to_base)`:
- **mass:** g/gram(s) 1 · kg 1000 · mg 0.001 · oz/ounce 28.3495 · lb/lbs/pound(s) 453.592
- **volume:** ml 1 · l/litre/liter 1000 · tsp/teaspoon 4.92892 · tbsp/tablespoon 14.7868 · cup(s) 236.588 · fl-oz 29.5735 · pint 473.176 · quart 946.353 · gallon 3785.41
- **count:** unit/each/"" 1 · dozen 12 · pair 2  — **only genuinely countable units** (#9)
- **left UNKNOWN on purpose** (→ opaque: exact-string match only, never
  *cross-unit* converted; **same-unit opaque still nets**, #R1):
  clove, slice, piece, stick, can, package, pkg, jar, bottle, box, bag, head, bulb,
  bunch, sprig, pinch, handful, dash, splash, "to taste" (#9). Within one
  `opaque:<unit>` bucket the amounts add/subtract directly (`2 can − 1 can = 1
  can`). Documented tuning knob — a food-specific *cross-unit* conversion (e.g.
  `1 can tomatoes ≈ 400 g`) can be added later, per pair, deliberately.

Unit-string normalization: lower → strip trailing `.` → naive-singularize → map
via synonym dict.

API:
```
@dataclass Quantity: amount: float | None; unit: str | None
parse_unit(s)                 -> UnitDef | None            # None = unknown
to_base(amount, unit)         -> (float, Dimension) | None # None = opaque/unknown unit
from_base(amount, dim, unit)  -> float | None
compatible(a, b)              -> bool                       # both known + same dimension
add_quantities(list[Quantity]) -> list[Quantity]           # merge known units by dimension;
                                                           # merge opaque units when the unit STRING is equal (#R1);
                                                           # None-unit merges as COUNT; distinct otherwise
bucket_of(unit)               -> "mass"|"volume"|"count"|"opaque:<canon>"   # None -> "count"
```

Incompatible/unknown behavior — **never drop a line:**
- both units `None` → treat as COUNT (so "3 onions" vs "2 onions" nets).
- **same opaque unit both sides** ("2 cans" vs "1 can") → nets directly:
  `nettable=true`, arithmetic on the raw amounts, no `to_base` (#R1).
- one side a *known* unit and the other opaque, or two *different* opaque units
  ("2 cloves garlic" vs "1 bulb garlic"), or different known dimensions →
  `compatible()` false → line surfaced with `nettable=false`, need = recipe
  requirement as written.

## Netting & deduction algorithms (`services/inventory_math.py`, pure)

### availability — `GET /api/recipes/{id}/availability?multiplier=M`

**Aggregate first (#4):** group the recipe's ingredient rows by
`(normalized_name, bucket)` where `bucket` = `bucket_of(unit)` — a known unit's
dimension, else `opaque:<canonical unit>` (None unit → COUNT). Sum `need` per
group **in canonical units** (g / ml / `unit`; raw amount for opaque). Compare
each group once against the *sum* of matching inventory rows — so a recipe that
lists flour twice can't see full stock twice. Every figure below (`need`,
`group_*`) is canonical and labelled with `group_unit` (#P5).
```
canon  = canon_unit(g.bucket)   # "g" | "ml" | "unit" | "<opaque unit>"
groups = aggregate(recipe.ingredients, M)   # -> {(norm, bucket): {need_base, members:[(ing_id, own_qty_base)]}}
for g in groups:
    to_taste members -> one line(status="to_taste", need=None) each; skip quantified math for those
    pos    = [r for r in inventory if r.match_name == g.norm and r.quantity_base > 0]   # POSITIVE stock only (#P4)
    compat = [r for r in pos if r.unit_bucket == g.bucket]                              # same bucket
    if compat:
        stock = sum(r.quantity_base for r in compat)          # already canonical — NO to_base (#R1/#R2)
        short = g.need_base - stock
        group_status = "ok" if short <= 0 else "short"
        group_have, group_short = stock, max(short, 0)
    elif pos:                          -> group_status = "have_uncertain", nettable=false,          # positive stock, wrong bucket (#R6/#P4)
                                          group_have = 0, group_short = g.need_base
    else:                              -> group_status = "missing", group_have = 0,                 # no row, or only zero rows (#P4)
                                          group_short = g.need_base
    # one AvailabilityLine per member ingredient_id:
    #   need / need_unit  = THAT member's own quantity * M, in canonical units (#R7/#P5)
    #   group_key         = f"{g.norm}|{g.bucket}"        ;   group_unit = canon
    #   group_need / group_have / group_short = the canonical group figures above (NO from_base)
    #   status            = group_status ;  nettable per above
    #   (legacy per-line have / have_unit / short are GONE, #P5)
report.all_available = every quantified line's group_status == "ok"
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
    for q in add_quantities(r.quantities):        # consolidated per dimension/bucket; opaque merged by unit string (#R1)
        bucket = bucket_of(q.unit)
        canon  = canon_unit(bucket)               # "g" | "ml" | "unit" | "<opaque unit>"
        pos    = [iv for iv in inventory if iv.match_name == norm and iv.quantity_base > 0]   # POSITIVE only (#P4)
        compat = [iv for iv in pos if iv.unit_bucket == bucket]
        need_base = (q.amount if bucket.startswith("opaque:") or q.unit is None
                     else to_base(q.amount, q.unit).amt)         # canonical; opaque = raw amount (#R1)
        if q.amount is None:                                     # opaque/None with no amount -> surface as written
            emit, nettable = Quantity(None, canon), false
        elif not compat:                                         # nothing positive in this bucket
            emit, nettable = Quantity(need_base, canon), (not pos)   # non-nettable iff positive stock sits in another bucket (#R6/#P4)
        else:
            stock = sum(iv.quantity_base for iv in compat)       # already canonical — NO to_base (#R2)
            short = need_base - stock
            if short <= 0: continue                              # fully in stock -> no line
            emit, nettable = Quantity(short, canon), true        # shortfall in canonical units (#P5)
        items.append(GLItem(item=r.display_item, normalized_name=norm,
                            quantity=emit.amount, unit=emit.unit, nettable=nettable, source="generated"))
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
Checking is pure list state. Nothing reaches inventory until `submit`, so a
line can be freely checked, edited, and unchecked with no drift.

### submit a grocery list — `POST /api/grocery/{list}/submit`
```
if list.status != "active": 409
with ONE transaction (BEGIN IMMEDIATE, #R3):
    for item in list.items:
        if not item.checked or item.added_to_inventory or item.quantity is None: continue
        applied = add_to_inventory(item.normalized_name, item.item, item.quantity, item.unit)
        item.applied_quantity, item.applied_unit = applied.amount, applied.unit   # canonical snapshot (#6/#P7)
        item.added_to_inventory = true
        item.submitted_at = now
    # NO status change here (#R5) — the list stays "active"
return updated list        # 200 even if nothing was checked (explicit no-op)
```
Forward-only, matching Cook — **no unapply**. Re-submitting is safe:
already-`added_to_inventory` lines are skipped, so only newly-checked lines are
added; a `submit` with nothing checked is a harmless 200 no-op (#R5). An
accidental submit is corrected with a manual `/api/inventory` adjustment. This
is what resolves #6: because checking has no inventory effect and submitted
lines are frozen, the "edit-after-check then uncheck" desync cannot occur; the
stored `applied_quantity`/`applied_unit` snapshot keeps the audit record honest.

### archive a grocery list — `POST /api/grocery/{list}/archive` (#R5)
```
UPDATE grocery_lists SET status='archived' WHERE id=? AND status='active'   # guarded, idempotent
-> 200 GroceryListRead ; 404 if the list does not exist
```
The **only** path to `archived`. `submit` never triggers it, so incremental
submit (shop today, finish tomorrow) works: the list is still `active` when the
second `submit` lands. Archiving is terminal — a `PATCH` / `submit` on an
archived list → 409.

### add_to_inventory(match_name, display, amount, unit) -> Quantity actually added (canonical)
`POST /api/inventory` and grocery `submit` both go through here — the
**additive** path (#P1).
```
bucket = bucket_of(unit)                    # dim for a known unit, else opaque:<canonical>, None -> count
canon  = canon_unit(bucket)                 # "g" | "ml" | "unit" | "<opaque unit>"
# convert to canonical base IN PYTHON, before the write — depends only on the
# input, not on any current DB value, so there is no race (#R2):
amt_base = max(amount, 0) if bucket.startswith("opaque:") or unit is None \
           else to_base(max(amount, 0), unit).amt          # opaque: raw amount; known: g/ml/count

# genuinely-atomic upsert within the (match_name, unit_bucket) row (#2, #8, #R2):
INSERT INTO inventory_items (item, normalized_name, match_name, unit_bucket, quantity_base, display_unit)
     VALUES (display, normalize_name(display), match_name, bucket, :amt_base, :unit)
ON CONFLICT (match_name, unit_bucket) DO UPDATE SET
     quantity_base = inventory_items.quantity_base + excluded.quantity_base,        # plain SQL, no convert()
     display_unit  = COALESCE(excluded.display_unit, inventory_items.display_unit), # keep a set preference
     updated_at    = now
RETURNING quantity_base
# No cross-bucket / best-effort '+=' path — incompatible units are just
# different rows (#2). quantity_base stays >= 0 and finite (CHECK).
return Quantity(amt_base, canon)            # canonical contribution (for the grocery applied_* snapshot, #P7)
```

### edit an inventory row — `PATCH /api/inventory/{id} {item?, match_name?, quantity?, unit?}` (#P1)
Absolute replacement of the addressed row — **not** additive.
```
row      = get_or_404(id)
cur_unit = unit if "unit" in body else (row.display_unit or canon_unit(row.unit_bucket))
if bucket_of(cur_unit) != row.unit_bucket: 422      # bucket change not allowed here — remove the row and re-add (#P1)
if "match_name" in body and exists_other_row(body.match_name, row.unit_bucket, exclude=id): 409   # collision, no merge (#P1)
if "quantity" in body:
    row.quantity_base = (max(body.quantity, 0) if row.unit_bucket.startswith("opaque:") or cur_unit is None
                         else to_base(max(body.quantity, 0), cur_unit).amt)   # ABSOLUTE set, canonical
if "unit" in body:        row.display_unit = cur_unit        # preference only; quantity_base already set above (or unchanged)
if "match_name" in body:  row.match_name  = body.match_name
if "item" in body:        row.item = body.item; row.normalized_name = normalize_name(body.item)
row.updated_at = now
# one BEGIN IMMEDIATE transaction like every request (#P3); IntegrityError on the composite unique -> 409 (#H3)
return InventoryItemRead(row)               # display quantity recomputed from quantity_base
```

### mark as cooked — `POST /api/recipes/{id}/cook {multiplier, deduct=true}`
```
log = CookLog(recipe_id, recipe_title=recipe.title, multiplier=M, deducted=deduct, cooked_by=user)
if not deduct:
    save(log); return log         # made-event recorded, stock untouched, deductions=[]
with ONE transaction (BEGIN IMMEDIATE — write lock before the first read, #R3):
  for (norm, bucket), need_base in aggregate(recipe.ingredients, M):   # aggregate like availability (#4)
    canon = canon_unit(bucket)   # "g" | "ml" | "unit" | "<opaque unit>"  (#P7)
    #   need_base is canonical: g/ml/count for known dims, raw amount for opaque (#R1)
    to_taste members -> log.deductions += {item, requested:null, requested_unit:null, applied:false, reason:"to taste"}
    pos    = [r for r in inventory if r.match_name == norm and r.quantity_base > 0]   # POSITIVE stock only (#P4)
    compat = [r for r in pos if r.unit_bucket == bucket]
    if not compat and not pos:
        log.deductions += {item, requested:need_base, requested_unit:canon, deducted:0, deducted_unit:canon,
                           inventory_unit:canon, applied:false, reason:"not in inventory"}; continue
    if not compat:
        log.deductions += {item, requested:need_base, requested_unit:canon, deducted:0, deducted_unit:canon,
                           inventory_unit:canon, applied:false, reason:"have uncertain (incompatible unit)"}; continue   # (#R6/#P4)
    remaining = need_base
    for r in compat:                                 # draw down compatible rows in order, clamp at 0 (#16)
        before = r.quantity_base
        take   = min(remaining, r.quantity_base)     # all canonical — NO to_base, NO display_amt (#R1/#R2/#P7)
        r.quantity_base = before - take; r.updated_at = now
        remaining -= take
        log.deductions += {item, normalized_name:norm,
                           requested: (need_base if r is compat[0] else null), requested_unit: canon,
                           deducted: take, deducted_unit: canon, inventory_unit: canon,
                           before, after: r.quantity_base,
                           applied: true, reason: ("ok" if remaining <= 0 else "clamped to 0")}
save(log)
```
Every amount in a deduction entry is canonical — `requested`, `deducted`,
`before`, `after` all in `inventory_unit`, so `before − deducted == after` holds
and there is no `display_amt` round-trip (#P7). Cook is intentionally lossy
(clamp at 0, skip incompatible buckets, skip zero-stock rows — #P4).
`deductions` records `requested` vs the **actual** `deducted` amount and
`before`/`after` per row (#16), so a future "undo" = `add_to_inventory` of each
entry's `deducted` amount (already canonical).

### made-history — `GET /api/recipes/{id}/cook-logs` + global `GET /api/cook-logs[/{log_id}]` (#H5)
Per-recipe: plain `list[CookLogRead]`, `order_by(cooked_at.desc())` — every
made-event regardless of `deducted`. This is "recipes I've actually made" and
(for v2) how a caller finds the `cook_log_id` a review will attach to.

`routers/cook_logs.py` adds the cross-recipe reads:
- `GET /api/cook-logs?limit=&offset=` → `CookLogList` (paginated, all recipes,
  newest first) — the "what have we cooked lately" feed.
- `GET /api/cook-logs/{log_id}` → `CookLogRead` (404 if missing) — a log is
  reachable by id alone, and **still resolves after its recipe is deleted**
  (`recipe_id` null, `recipe_title` snapshot stands).

### concurrency & atomicity (#8, #H3)

Two household members can act at once. Contract:
- **Pure service proposes, router performs (#H3).** `services/inventory_math.py`
  takes DTOs and returns a proposed adjustment; it never holds an ORM object or a
  session. The router applies that adjustment and **owns the single
  transaction** — a failure mid-operation rolls the whole thing back (no
  half-applied cook, no partly-submitted grocery list).
- **Every request-scoped transaction opens with `BEGIN IMMEDIATE` (#R3/#P3)** —
  `cook`, grocery `submit`, inventory/recipe CRUD, **and** read-only requests and
  the auth `last_used_at` bump. `database.py` issues it on every pooled
  connection via a transaction hook (SQLAlchemy's pysqlite "emit our own BEGIN"
  pattern), alongside the PRAGMA listener. The connection takes the write
  (RESERVED) lock *before* its first `SELECT`, so a second concurrent actor
  blocks at `BEGIN`, waits out `busy_timeout`, then reads **already-committed**
  state — no read-modify-write lost update anywhere. Plain `BEGIN DEFERRED` +
  `busy_timeout` does **not** prevent the lost update; a DEFERRED transaction
  that lazily upgrades to a write (e.g. a GET that also bumps `last_used_at`) can
  still deadlock a concurrent writer.
- **Trade-off (accepted, #P3):** every request now serializes on the single
  SQLite writer lock. For the intended load — a two-user household LAN — the
  contention is immaterial, and one policy (no "auth session vs mutation
  session" split) is worth more than notional read parallelism. The rejected
  alternative (a short read-only auth transaction, then a separate mutation
  transaction) buys nothing here.
- `add_to_inventory` is the SQLite `INSERT … ON CONFLICT (match_name,
  unit_bucket) DO UPDATE SET quantity_base = quantity_base + excluded.quantity_base`
  upsert above (#R2) — a genuine atomic SQL increment (no `convert()`, no Python
  read-modify-write), and concurrent first-inserts can't raise a duplicate 500.
- One-shot state transitions use a guarded update:
  `UPDATE grocery_lists SET status='archived' WHERE id=? AND status='active'`
  (the `archive` endpoint, #R5); the grocery-item freeze uses
  `added_to_inventory` as the guard.
- `database.py` sets `PRAGMA busy_timeout=5000` per connection (#14), so a brief
  writer overlap waits rather than erroring. **On `IntegrityError` or a lock /
  `busy_timeout` timeout the endpoint returns 409, not 500 (#H3).**
- **In scope (#R3/#P3):** `test_concurrency.py` — a file-backed SQLite DB with two
  independent connections, driving **authenticated HTTP requests** through the
  `TestClient`: one test racing two `cook`s that share an ingredient and one
  racing two `submit`s, asserting stock lands at the correct total (not a lost
  update) and both `CookLog`s report honest, canonical `deducted` amounts. The
  in-memory `StaticPool` fixture shares one connection and cannot exercise this.
  The sequential double-submit idempotency test still runs in `test_grocery.py`.

## Auth approach

- **Hashing:** `pwdlib[argon2]` (`hash_password`/`verify_password` in
  `security.py`). Dummy-verify on unknown username to blunt timing enumeration.
- **Sessions:** opaque `secrets.token_urlsafe(32)` in the `sessions` table, TTL
  `RECIPE_SESSION_TTL_DAYS` (default 30). No JWT, no signing secret to manage.
  `get_current_user(authorization: str | None = Header(default=None))` (optional,
  #P6) splits the value on the first space and returns **401** for every failure
  mode: no header, not exactly `<scheme> <token>` (malformed), scheme ≠ `Bearer`
  (case-insensitive), token not in `sessions`, or the row is past `expires_at`
  (expired). On success it bumps `last_used_at` (a write — hence `BEGIN
  IMMEDIATE` even on GETs, #P3). It resolves its session via the **app-local
  session dependency** installed by `create_app` and reads config via
  `get_settings` — no module globals (#P2).
  `CurrentUser = Annotated[User, Depends(get_current_user)]`.
- **Household model (#15):** v1 is a **single shared household**. Every
  authenticated user has full read/write access to all data — there is no
  per-user ownership or membership layer, by design. `created_by_id` is
  attribution only.
- **Registration (#15):** `RECIPE_ALLOW_REGISTRATION` defaults **`false`**. To
  add accounts, the household sets it `true` (and normally also sets
  `RECIPE_REGISTRATION_CODE`), registers, then sets it back `false`. When
  `RECIPE_REGISTRATION_CODE` is set, `/register` requires a matching `code` or
  returns 403.
- **Endpoints (`/api/auth`):** `POST /register {username, password, code?}` → 201
  `{token,user}` (409 dup / 403 disabled-or-bad-code / 422 short pw); `POST
  /login` (JSON, not OAuth2 form, to keep the fetch wrapper uniform) →
  `{token,user}` (401); `POST /logout` → 204 (deletes the row); `GET /me` →
  `UserRead`.
- **CORS:** no code change (token is a header, not a cookie; `allow_headers=["*"]`
  already passes it). For LAN hosting, add the server origin to
  `RECIPE_CORS_ORIGINS` or set `["*"]` (safe — not credentialed). Doc note only.

## Dependencies

**Backend runtime (`uv add`):**
- `pwdlib[argon2]` — password hashing (no bcrypt 72-byte footgun).

**Not added:** `pint` (units are a bounded pure-Python set) · `python-jose`/`pyjwt`
(opaque tokens) · `passlib` (using `pwdlib`) · `alembic` (staying on
`create_all`) · `inflect` (naive singularize) · `python-multipart` (no file
uploads in v1) · `recipe-scrapers` / `httpx`-as-runtime / `pytesseract` /
`Pillow` (import + OCR are v2) · any web-search API or LLM/AI service.

**Backend dev:** none new. `httpx` stays in the existing dev group for
`TestClient`.

**Frontend:** `react-router-dom` — added during the later frontend effort, not
v1.

## Schema management

Stay on `create_all`:
- **App factory (#H2/#P2).** `create_app(settings, engine)` is the single build
  path. It (a) runs `Base.metadata.create_all(bind=engine)` in its lifespan on
  the **injected** engine; (b) builds a `sessionmaker` bound to that engine and
  installs an **app-local** `get_db` dependency (a generator yielding a
  request-scoped session) on `app.state` — there is no importable module-global
  session factory that tests must monkeypatch; (c) stashes `settings` on
  `app.state.settings`, exposed through a `get_settings(request)` dependency. The
  module-level `app = create_app(settings, engine)` is what uvicorn imports;
  `conftest.py` calls `create_app(test_settings, test_engine)` and **overrides
  nothing further** — the injected engine is the only DB wiring (#P2). No "set
  env vars before importing `app`" ordering hack.
- `database.py` exposes `make_engine(url)` / `make_session_factory(engine)` and
  registers a `connect` event listener issuing `PRAGMA foreign_keys=ON` and
  `PRAGMA busy_timeout=5000` on every SQLite connection (#14/#8) — without it
  SQLite ignores the declared `CASCADE` / `SET NULL` — **plus a `begin`
  transaction hook that emits `BEGIN IMMEDIATE` for every request-scoped
  transaction** (#P3). The test engine gets the same listeners. Relationships
  that rely on DB-level cascade set `passive_deletes=True`.
- `create_all` won't ALTER the stale `recipes` table → **delete
  `backend/recipe.db`** in Phase 0 and again after the schema-expanding phases.
- Document in README + CLAUDE.md: "No migrations. After a model change:
  `rm backend/recipe.db` and restart; local data is lost."

**Cost of Alembic now (rejected):** +dep, `alembic/` + `env.py` + `alembic.ini`,
`--autogenerate` + review per change, a new CI step. Buys zero data loss + a real
upgrade path. Revisit at the first schema change *after* the household has
recipes worth keeping.

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
  - `RecipeBase {title 1..200, notes="", prep_time ≥0|None, cook_time ≥0|None,
    servings >0|None, cuisine|None, source_url|None, tags: list[str]=[],
    steps: list[str]=[]}`.
  - `RecipeCreate` / `RecipeUpdate` = `RecipeBase` + `ingredients:
    list[RecipeIngredientIn] = []` — **PUT fully replaces** nested rows.
  - `RecipeRead` = `RecipeBase` + `{id, created_at, updated_at, photo_path,
    created_by: UserMini|None, ingredients: list[RecipeIngredientRead]}`.
  - `AvailabilityLine {ingredient_id, item, need: float|None, need_unit: str,
    group_key: str, group_unit: str, group_need: float|None,
    group_have: float|None, group_short: float|None,
    status: Literal["ok","short","missing","to_taste","have_uncertain"],
    nettable: bool}` (#R7/#P5) — `need`/`need_unit` are **this ingredient row's
    own** quantity ×M, in the bucket's **canonical unit**; `group_*` carry the
    aggregated figures shared by every line with the same `group_key`
    (`"<normalized_name>|<bucket>"`), also canonical and labelled by `group_unit`
    (`"g"`/`"ml"`/`"unit"`/`"<opaque unit>"`). The pre-#R7 per-line
    `have`/`have_unit`/`short` fields are **removed** (#P5). `status` and
    `all_available` are decided on the group. `AvailabilityReport {recipe_id,
    multiplier, lines, all_available}`.
  - `CookRequest {multiplier: float = 1 (gt=0, finite), deduct: bool = True}`;
    `CookLogRead {id, recipe_id, recipe_title, multiplier, deducted, cooked_at,
    cooked_by: UserMini|None, deductions: list[dict]}` — each deduction dict is
    `{item, normalized_name, requested, requested_unit, deducted, deducted_unit,
    inventory_unit, before, after, applied, reason}` where
    `requested`/`deducted`/`before`/`after` are all in the bucket's **canonical
    unit** and `requested_unit == deducted_unit == inventory_unit` (#16/#P7).
    `POST /cook`,
    `GET /api/recipes/{id}/cook-logs`, and `GET /api/cook-logs/{log_id}` all
    return `CookLogRead`; `GET /api/cook-logs` returns
    `CookLogList {items: list[CookLogRead], total, limit, offset}` (#H5).
- `inventory.py` — `InventoryItemIn {item, quantity: float ge=0 (finite),
  unit: str|None, match_name: str|None}` — the human input for **`POST`** (an
  additive upsert into `(match_name, unit_bucket)`) and for **`PATCH /{id}`** (an
  absolute replacement of that row; a bucket-changing `unit` → 422, a
  `match_name` collision → 409, #P1). The server converts `quantity`+`unit` to
  `quantity_base` on write (#R2). `InventoryItemRead {id, item, normalized_name,
  match_name, unit_bucket, quantity_base, display_unit, display_quantity,
  updated_at}` — `quantity_base` is authoritative (canonical); `display_quantity`
  is `from_base(quantity_base, dim, display_unit)` **computed on every read**,
  never stored; `display_unit` `None`/opaque ⇒ `display_quantity` is the
  canonical amount and `display_unit` the canonical unit (#P1).
- `grocery.py` — `GroceryListCreate {name: str|None, recipe_ids: list[int]
  (non-empty, unique, all must exist — else 422), multipliers: dict[int, float] = {}}`
  (each multiplier `gt=0`, finite, #13; **keys must be a subset of `recipe_ids`,
  else 422 — #H4**);
  `GroceryListItemIn {item, quantity: float|None gt=0 (finite), unit: str|None}`;
  `GroceryListItemUpdate {checked: bool|None, quantity, unit, item}` — 409 if the
  target line is `added_to_inventory` (frozen after submit, #6) or the list is
  `archived` (#R5);
  `GroceryListItemRead {id, item, normalized_name, quantity, unit, checked,
  checked_at, submitted_at, source, nettable, added_to_inventory,
  applied_quantity, applied_unit}` (#6) — for `source="generated"` lines
  `quantity`/`unit` are the shortfall in the bucket's **canonical unit** and
  `applied_quantity`/`applied_unit` snapshot what `submit` added, also canonical
  (#P5/#P7); `source="manual"` lines keep the amounts the user typed;
  `GroceryListRead {id, name, status, source_recipe_ids, created_at, created_by,
  items}`. `POST /{id}/submit` and `POST /{id}/archive` both return
  `GroceryListRead`; `submit` on a non-`active` list and `archive` guard on
  `status='active'` (#R5).

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
factory (#H2/#P2): `app = create_app(test_settings, test_engine)` where
`test_settings` has `allow_registration=true` (no code), and `test_engine` is the
in-memory `StaticPool` engine with the `PRAGMA foreign_keys=ON` / `busy_timeout`
/ `BEGIN IMMEDIATE` listeners (#14/#P3) + `create_all`/`drop_all`. **No
`dependency_overrides[get_db]`** — `create_app` derives the session dependency
from `test_engine` itself, so the injected engine is the sole DB wiring (#P2).
`test_concurrency.py` opts out of the shared engine — it builds its own
**file-backed** SQLite DB (`tmp_path`) with two independent engines/connections
and drives authenticated HTTP requests (#R3/#P3).
- `user` — registers a default user via `POST /api/auth/register`.
- `auth_client` — `TestClient` with `Authorization: Bearer <token>` preset;
  **becomes the default**. Existing `test_recipes.py` switches `client` →
  `auth_client`.
- `client` — kept as the **anonymous** client for auth / 401 tests.

New / changed test files:
- `test_units.py` — pure. Both-way conversions, plurals/abbrevs, unknown → None,
  cross-dimension incompatible, count handling, `add_quantities` merge + bucketing
  incl. **same-unit opaque merges (`2 can` + `1 can` → `3 can`), different opaque
  units stay separate** (#R1); `bucket_of`.
- `test_ingredient_parse.py` — pure. `"2 tbsp olive oil"`, `"1 1/2 cups flour"`,
  `"½ tsp salt"`, `"salt to taste"`, `"3 large eggs"`, `"1 (14 oz) can tomatoes"`,
  garbage → raw fallback.
- `test_inventory_math.py` — pure. availability (all 5 statuses; **duplicate
  ingredient rows aggregated** so stock isn't double-counted, #4; per-line `need`
  and `group_*` all canonical, `group_unit` set, #R7/#P5; **`clove` need vs
  `bulb` stock ⇒ `have_uncertain`, not `missing`**, #R6; **row at
  `quantity_base = 0` ⇒ treated as absent: cook-to-zero food ⇒ `missing`, not
  `short`/`have_uncertain`**, #P4; `have_uncertain` ⇒ `all_available` false, #4);
  `generate_lines` (consolidation across 2 recipes, netting against summed
  positive compatible `quantity_base`, **`2 can` need − `1 can` stock ⇒ `1 can`
  line** in canonical units, #R1/#P5, skip in-stock, non-nettable surfaced,
  zero-stock row ignored, #P4); `deduct` (clamp at 0, incompatible bucket ⇒
  `have uncertain` reason not applied, #R6, opaque same-unit deducts, **canonical
  `requested`/`deducted`/`deducted_unit`, `before − deducted == after`**,
  #16/#P7, **kg-from-g: stock `2000` g, recipe `1 kg` ⇒ `deducted 1000`,
  `after 1000`, all `g`**, #P7); `add_to_inventory` (new bucket row,
  **`quantity_base` upsert** with a cross-unit add — `1 kg` row + `500 g` ⇒
  `1500` base, #R2 — **incompatible unit ⇒ a second row, never `1+500→501`**,
  #2; returns a canonical `Quantity`, #P7).
- `test_auth.py` — anonymous `client`. register 201 / 409 dup / 403 when
  `RECIPE_ALLOW_REGISTRATION=false` / 403 wrong `code` when a code is configured /
  422 short pw (#15); login 200+token / 401 bad pw / 401 unknown user; logout
  invalidates. **The five `get_current_user` 401 cases (#P6):** no `Authorization`
  header, malformed value (`"garbage"`, no space), wrong scheme (`"Basic xyz"`),
  unknown token, and a token whose `sessions` row is past `expires_at` — each on a
  gated endpoint (and `/me`); `/me` 200 with a good token.
- `test_validation.py` — negative / `0` / `inf` / `nan` quantity and multiplier
  rejected (422) on recipe ingredient, inventory add/edit, cook, grocery create,
  availability query param (#H4, #13); `recipe_ids` empty or with a duplicate →
  422; a `multipliers` key not in `recipe_ids` → 422.
- `test_cook_logs.py` — `auth_client`. `GET /api/cook-logs` paginates
  newest-first across recipes; `GET /api/cook-logs/{id}` returns one; a log is
  still returned by both endpoints after its recipe is deleted (#H5).
- `test_recipes.py` — expanded, `auth_client`. nested create/read (positions,
  computed `normalized_name`); PUT clears old ingredients; steps/tags round-trip;
  `/availability?multiplier=2` (per-line `need` and `group_*` canonical,
  `group_unit` present, no `have`/`short` on the line, #R7/#P5; cook-to-zero food
  ⇒ `missing`, #P4); `/cook` writes `CookLog` + mutates inventory (clamp,
  incompatible bucket; deduction dict carries canonical
  `requested`/`deducted`/`deducted_unit`/`before`/`after`, #16/#P7); `cook
  {deduct:false}` leaves inventory untouched but still writes a `CookLog`;
  `GET .../cook-logs` newest-first across both modes.
- `test_inventory.py` — `auth_client`. **`POST` = additive upsert** (two `POST`s
  to the same `(match_name, unit_bucket)` sum in `quantity_base`); **`PATCH
  /{id}` = absolute replacement** (sets `quantity_base` outright — "reduce flour
  to 200 g"); **`PATCH` display-unit change** within a bucket (`g`→`kg`) leaves
  `quantity_base` untouched, only `display_quantity` changes; **`PATCH` to a
  bucket-changing `unit` → 422**; **`PATCH match_name` onto an occupied
  `(match_name, unit_bucket)` → 409** (#P1); **add → cook → GET** shows
  `display_quantity` recomputed from the reduced `quantity_base` (#P1);
  `(match_name, unit_bucket)` composite uniqueness; cross-unit add merges via
  `quantity_base` (`1 kg` + `500 g` ⇒ `1500`, #R2); same food in two incompatible
  units → two rows (#2); editing `match_name` re-points matching; negative /
  non-finite qty rejected (#13).
- `test_grocery.py` — generate from 2 selected recipes (consolidation + netting;
  **generated line `quantity`/`unit` in canonical units**, #P5; a food cooked to
  `quantity_base = 0` still produces a full-need line, #P4), manual item add
  (amounts kept as typed), **check off → inventory unchanged** (#6), edit a
  checked line then submit → inventory reflects the edited value, `POST /submit`
  → inventory up + line frozen (`added_to_inventory`, canonical
  `applied_quantity` set), PATCH a frozen line → 409, uncheck before submit →
  no-op, **`submit` does NOT archive; check a further line and re-submit picks it
  up (incremental submit works)** (#R5), **`submit` with nothing checked → 200
  no-op** (#R5), `POST /archive` → `status=archived` and a later PATCH/submit →
  409 (#R5), sequential double-submit idempotency, delete list cascades items,
  non-nettable line present.
- `test_concurrency.py` — **file-backed SQLite, two connections, authenticated
  HTTP** (#R3/#P3). Two `cook`s racing on a shared ingredient → final
  `quantity_base` is the correct total, both `CookLog`s honest (no lost update).
  Two `submit`s racing → each checked line applied exactly once. A read racing a
  write never observes a torn value (every request is `BEGIN IMMEDIATE`, #P3).

`pyproject.toml` `testpaths`/`addopts` unchanged. No mypy/lint added (ethos).

## Build sequence (each phase ends with `uv run pytest` green)

- **Phase 0 — reset & deps.** `uv add pwdlib[argon2]`. Delete `backend/recipe.db`.
  `.gitignore` unchanged (already ignores `*.db`; no `uploads/` / `receipts/` in
  v1). Old tests still green.
- **Phase 1 — pure core.** `normalize.py`, `units.py`,
  `services/ingredient_parse.py` + `test_units.py`, `test_ingredient_parse.py`.
  Nothing else touched.
- **Phase 2 — auth + app factory.** Introduce `create_app(settings, engine)` in
  `main.py` and `make_engine` / `make_session_factory` in `database.py`; the
  module-level `app` calls the factory. `create_app` **derives the app-local
  `get_db` session dependency from the injected engine** and stashes `settings`
  on `app.state` / behind `get_settings` (#P2). Add the `PRAGMA foreign_keys=ON`
  / `busy_timeout` connect listener **and the `BEGIN IMMEDIATE` transaction hook
  for every request-scoped transaction** (prod + test engines,
  #14/#8/#R3/#P3). `User`/`Session` models, `security.py` (`get_current_user` —
  optional header, five explicit 401s, consumes `get_db` + `get_settings`,
  #P2/#P6), `schemas/auth.py` (incl. `code`), `routers/auth.py` (registration
  default off + `code` check, #15), `config` additions (`allow_registration`
  default false). conftest: build via the factory with a test engine — **no
  `dependency_overrides`, no import-order hack** (#H2/#P2); `user` +
  `auth_client`; migrate `test_recipes.py` to `auth_client`; add
  `dependencies=[Depends(get_current_user)]` to the recipes router.
  `test_auth.py` (incl. the five 401 cases). End: existing recipe CRUD works, now
  gated; login works.
- **Phase 3 — structured recipes.** Expand `Recipe` (keep `photo_path` /
  `raw_text` as reserved nullable cols), add `RecipeIngredient`, drop the old
  text cols; `schemas/recipe.py` nested + validation; rewrite `routers/recipes.py`
  for nested create/replace. Expand `test_recipes.py`; add `test_validation.py`
  (#H4). Delete `recipe.db`. End: full structured recipe CRUD. **No photo.**
- **Phase 4 — inventory + math services.** `InventoryItem` model with
  `(match_name, unit_bucket)` composite unique + editable `match_name` +
  **`quantity_base` as source of truth + `CHECK(quantity_base >= 0)`, a
  `display_unit` preference (display quantity recomputed from base on read)**
  (#2/#R2/#P1); `services/inventory_math.py` (`check_availability` with
  aggregation over **positive** stock, cross-bucket `have_uncertain` and
  zero-stock-as-absent (#R6/#P4), canonical per-line `need` + `group_*` +
  `group_unit` (#R7/#P5), opaque arithmetic without `to_base` (#R1);
  `add_to_inventory_calc` converts to base then proposes the `quantity_base += …`
  upsert, returns a canonical `Quantity`, no `convert()` (#R2/#P7);
  `deduct_calc` on `quantity_base`, recording canonical
  `requested`/`deducted`/`deducted_unit`/`before`/`after` #16/#P7);
  `routers/inventory.py` — **`POST` additive upsert, `PATCH /{id}` absolute
  replacement (within-bucket only → 422, collision → 409), PATCH `match_name`**
  (#P1); `GET /api/recipes/{id}/availability`. `test_inventory.py`,
  `test_inventory_math.py`, availability tests (incl. cook-to-zero → `missing`).
  End: inventory CRUD + missing-ingredient check.
- **Phase 5 — cook = deduct + made-tracking.** `CookLog` model (with
  `deducted: bool = True` from the start; deductions carry canonical
  `requested`/`deducted`/`deducted_unit`/`before`/`after`, #16/#P7); `POST
  /api/recipes/{id}/cook {multiplier, deduct=true}` using `deduct_calc` when
  `deduct=true` (service proposes, router applies atomically in one **`BEGIN
  IMMEDIATE`** transaction, #H3/#R3), skipping it (but still logging) when
  `deduct=false`; `GET /api/recipes/{id}/cook-logs` (made-history, newest first);
  `routers/cook_logs.py` — `GET /api/cook-logs` (paginated) +
  `GET /api/cook-logs/{log_id}` (#H5). Cook + made-history tests in
  `test_recipes.py` (incl. kg-from-g stock, #P7); global reads in
  `test_cook_logs.py` (#H5); **`test_concurrency.py` cook-race over authenticated
  HTTP** (#R3/#P3).
- **Phase 6 — grocery lists.** `GroceryList`/`GroceryListItem` models (with
  `submitted_at` + canonical `applied_*` cols, #6/#P7); `generate_lines` in
  `inventory_math.py` (netting against summed **positive** compatible
  `quantity_base`, opaque same-unit nets, canonical line output,
  #R1/#R2/#P4/#P5); `routers/grocery.py` (create-from-recipes, get, list, add
  manual item, **PATCH = state/field edits only, 409 on frozen lines / archived
  list**, `POST /{id}/submit` → one `BEGIN IMMEDIATE` txn `add_to_inventory` +
  freeze, **no status change** (#R5), `POST /{id}/archive` → guarded
  `status='active'→'archived'` (#R5), delete). `test_grocery.py`;
  **`test_concurrency.py` submit-race over authenticated HTTP** (#R3/#P3). End:
  backend feature-complete.
- **Phase 7 — docs.** Update `README.md`, `CLAUDE.md`, `backend/.env.example`
  (new `RECIPE_*` vars: `SESSION_TTL_DAYS`, `ALLOW_REGISTRATION`,
  `REGISTRATION_CODE`; `rm backend/recipe.db` note; new architecture & full v1
  API surface; LAN deploy `uvicorn app.main:app --host 0.0.0.0 --port 8000`; "set
  `RECIPE_ALLOW_REGISTRATION=true` + a `RECIPE_REGISTRATION_CODE` to add
  accounts, then set it back to `false`" (#15); note that cook and grocery
  `submit` are forward-only). Add a pointer to **§Deferred to v2** and the
  `git show 5144c25:docs/plan.md` archive.

## Deferred to v2 — data model already accommodates

See `docs/features.md` for the consolidated roadmap: deferred capabilities,
infrastructure deferrals (Alembic, multi-user, remote hosting), the `FoodItem`
upgrade path, design invariants for extensions, and rejected items. This section
is authoritative for the v1↔v2 boundary and the execution detail; `features.md`
carries the why-deferred and upgrade context.

Each block below is execution-ready **modulo the "before v2" note it carries**
(#R-def) — a handful of details that review pass 4 flagged as still delegated to
the archive. `full spec` points at the section of the pre-trim plan
(`git show 5144c25:docs/plan.md`) that carries the complete detail plus its
adversarial-review findings.

### Photo upload
- **Route:** `POST /api/recipes/{id}/photo` — one image under a public
  `upload_dir`, records the relative path in `recipes.photo_path` (column
  already present), served at `/uploads/...`. Wrong content-type → 415/422,
  oversize → 413.
- **Deps:** `python-multipart` (Starlette needs it for `multipart/form-data`).
- **Factory change:** `create_app` `os.makedirs(settings.upload_dir)` **before**
  mounting `/uploads` StaticFiles; `config` gains `upload_dir`,
  `max_upload_bytes`.
- **Data-model impact:** none — `photo_path` is already a nullable column.
- *full spec: git 5144c25 §"Done criteria" item 3, §"Module / router layout".*

### URL import (fast-follow)
- **Service `services/import_recipe.py`:**
  `fetch_bytes(url, *, limit, allowed_types) -> bytes` — the **only** network
  call, SSRF-guarded (#H1/#10b): HTTP(S) scheme allowlist; resolve host and
  reject private/loopback/link-local/ULA/multicast/`169.254.169.254`;
  `follow_redirects=False` (3xx → 502); `raise_for_status`; `Content-Type`
  allowlist; stream to a byte cap. `RECIPE_IMPORT_ALLOW_PRIVATE=true` re-opens it
  for a trusted LAN. Split from
  `scrape_preview(html, url, wild_mode=False) -> RecipeImportPreview` (pure;
  wraps `recipe-scrapers`, normal then wild mode; the route holds `html` for the
  retry, #10a).
- **Route:** `POST /api/recipes/import {url, save?}` → 200 `RecipeImportPreview`
  (or 201 `RecipeRead` when `save=true`, image downloaded through the same
  `fetch_bytes`). Unsupported site → 422 `unsupported:true`; any fetch failure →
  502.
- **DTO:** `ImportIngredient` = `RecipeIngredientIn` + `{raw_text, normalized_name}`
  (#3) — populates `recipe_ingredients.raw_text` (column already present).
- **Deps:** `recipe-scrapers`; promote `httpx` from dev to runtime.
- **Config:** `import_max_bytes`, `import_fetch_timeout` (10s), `max_image_bytes`
  (~5 MiB), `import_allow_private` (default false).
- **Tests:** `test_import.py` via `httpx.MockTransport` — happy path, wild-mode
  retry, unsupported → 422, non-2xx / redirect / oversize / wrong content-type →
  502, blocked address (`169.254.169.254`, `localhost`) → 502 with no request,
  `save=true` offline.
- **Data-model impact:** none.
- **Before v2 (#R-def):** "stream to a byte cap" must be an actual streaming
  read that aborts once a running byte counter exceeds the cap — **not**
  `resp.content[:N]` after a full download. Also: `httpx.Client(trust_env=False)`
  (ignore ambient `HTTP(S)_PROXY`), and connect to the **pre-resolved, already
  IP-checked address** with the original `Host` header preserved, so a
  DNS-rebind between the check and the fetch cannot redirect it.
- *full spec: git 5144c25 §"URL import approach", §"Lightweight ingredient parser".*

### Recipe research
- **Service `services/recipe_research.py` (pure):**
  `compare_ingredients(previews) -> ResearchReport` — for a batch of scraped
  `RecipeImportPreview`s, report what fraction contain each `normalized_name`
  (one recipe counts an ingredient once). Nothing is persisted.
- **Route `routers/research.py`:** `POST /api/research/compare {urls, limit?}`
  (`limit` capped at `settings.research_max_urls`; empty `urls` → 422). Reuses
  `fetch_bytes` + `scrape_preview`, so the whole batch inherits the SSRF guard
  (#H1). Per-URL fetch/parse failures collected in `failed`, not fatal. **No
  `query` / web-search mode** — Google Custom Search JSON API is closed to new
  customers and ends 2027-01-01 (#1); revisit with Vertex AI Search / Brave /
  Bing.
- **Before v2 (#R-def):** the *URL list itself* must be bounded, not only the
  optional `limit` param — after dedupe, `len(urls) > research_max_urls` → 422,
  and the batch runs under a single total deadline so a pile of slow hosts can't
  hang the request.
- **Schemas:** `ResearchCompareRequest`, `IngredientStatRead`, `ResearchReport`.
- **Config:** `research_max_urls`.
- **Tests:** `test_research.py` via `httpx.MockTransport` — a "100% vs 10%"
  comparison, one failing URL lands in `failed`, a blocked-address URL lands in
  `failed`, empty `urls` → 422, repeated ingredient within one recipe counts
  once.
- **Deps:** none beyond URL import's.
- **Data-model impact:** none — computed per request, no table.
- *full spec: git 5144c25 §"compare ingredients", §"Recipe research" done-criterion.*

### Per-cook reviews
- **Table `recipe_reviews`:** `id` PK · `cook_log_id` FK cook_logs CASCADE, not
  null · `recipe_id` FK recipes SET NULL (denormalized) · `rating` int? 1-5 ·
  `comment` Text="" · `changes_next_time` Text="" · `created_at` ·
  `created_by_id` FK users?.
- **Routes:** `POST /api/recipes/{id}/cook-logs/{log_id}/reviews
  {rating?, comment?, changes_next_time?}` (404 if the cook log isn't this
  recipe's); `GET /api/recipes/{id}/reviews`. `RecipeRead` additionally nests
  `reviews: list[RecipeReviewRead]` newest-first, each nesting a
  `CookEventMini {cook_log_id, cooked_at, multiplier, deducted}` (#16) so the
  reviewed event's date/mode show without a second lookup. Append-only — reviews
  are never edited/deleted in v1's stance.
- **Schemas:** `RecipeReviewIn`, `RecipeReviewRead`, `CookEventMini`.
- **Tests:** create a review against a cook log; 404 on mismatched
  recipe/cook-log; `GET /api/recipes/{id}` nests reviews newest-first with their
  `cook_event`.
- **Deps:** none.
- **Data-model impact:** additive table; `cook_logs` already carries the FK
  target.
- **Before v2 (#R-def):** all review-read routes are recipe-scoped, so a review
  becomes unreachable once its recipe is deleted (its `recipe_id` goes null) —
  the same gap #H5 fixed for cook logs. Add `GET /api/cook-logs/{log_id}/reviews`
  or nest `reviews` in the global cook-log detail so the record stays readable.
- *full spec: git 5144c25 §"add a review", §"Reviews" done-criterion.*

### Grocery-receipt OCR → stock
- **Tables:** `receipt_imports` (`id` · `image_path` under a **private**
  `receipts_dir` · `raw_ocr_text` · `status` `draft`/`applied` · `created_at` ·
  `applied_at?` · `created_by_id?`) and `receipt_items` (`id` · `receipt_id` FK
  CASCADE · `position` · `raw_text` OCR original, **never overwritten** (#17) ·
  `item` editable · `normalized_name` recomputed on edit · `quantity` float? >0
  finite · `unit?` · `price_cents?` OCR original · `include` bool=true ·
  `applied` bool=false · `applied_quantity?` · `applied_unit?` snapshot (#5)).
- **Services:** `receipt_ocr._ocr_image(path)` — the **only** OCR call: Pillow
  format/frame/`MAX_IMAGE_PIXELS` validation (decompression-bomb → reject),
  `pytesseract(timeout=…)` under a `Semaphore` (#12). `receipt_parse.parse_receipt_text`
  — pure heuristic line-guesser (all-caps, broken decimals, drop
  `SUBTOTAL`/`TAX`/`TOTAL` noise).
- **Routes `routers/receipts.py`:** `POST /api/receipts` (photo upload → OCR →
  parse → draft lines); `GET` list/detail; `GET /{id}/image` — auth'd
  `FileResponse`, image **never** under `/uploads` (#11); `PATCH .../items/{item_id}`
  — per-item, draft-only, recomputes `normalized_name`, leaves `raw_text` /
  `price_cents` intact (#17); `POST .../apply` — one transaction; **422 if any
  included line lacks a finite positive quantity** (#5), else adds every included
  line to inventory via `add_to_inventory`, snapshots `applied_*`, receipt →
  `applied` (immutable); `DELETE` (blocked once applied). Double-apply → 409
  (guarded `UPDATE ... WHERE status='draft'`).
- **Health:** `/api/health` reports tesseract availability (#12).
- **Deps:** `pytesseract` + `Pillow` (Python); **`tesseract-ocr` system
  package** on dev/CI/deploy hosts (`apt-get install tesseract-ocr`; add to
  README, CI workflow, Makefile setup target).
- **Config:** `receipts_dir`, `ocr_timeout_seconds`, `ocr_max_concurrency`,
  `max_image_pixels`.
- **Factory change:** `os.makedirs(receipts_dir)` at build; no StaticFiles mount
  for it.
- **Tests:** `test_receipt_parse.py` (pure, canned noisy OCR text);
  `test_receipts.py` (monkeypatch `_ocr_image` for flow tests: draft creation,
  per-item PATCH keeps `raw_text`/`price_cents`, apply writes `applied_quantity`,
  apply with null/≤0 line → 422 and receipt stays draft, double-apply → 409,
  delete blocked once applied, `GET /{id}/image` needs auth and is not under
  `/uploads`, bad content-type / oversize / decompression-bomb rejected) **plus
  one non-mocked smoke test** — Pillow renders text to PNG, real `_ocr_image`
  reads it back, `skipif` tesseract missing (#12).
- **Data-model impact:** additive tables only.
- **Before v2 (#R-def):** (1) the non-mocked smoke test's `skipif` is
  **local-only** — under `CI` a missing `tesseract` binary is a hard failure, so
  a broken install can't ship green. (2) Upload/OCR failure cleanup is explicit:
  stage the image in a temp file, and on any OCR timeout or DB error either
  delete it or persist a visible `status=failed` draft with retry semantics —
  never leave an orphaned receipt image (it is PII).
- *full spec: git 5144c25 §"apply a receipt", §"Grocery receipt → stock"
  done-criterion, findings #5 #11 #12 #17.*

### Other deferred (unchanged from pre-trim)
- **"What can we make now"** — run `check_availability` across all recipes, filter
  `all_available`; add `GET /api/recipes/makeable`.
- **Staples / low-stock alerts** — add `is_staple bool` + `min_quantity float` to
  `inventory_items`; add `GET /api/inventory/low`.
- **Undo for forward-only actions** — cook and grocery `submit` (and, in v2,
  receipt `apply`) are one-shot and forward-only. Each already stores what it
  actually did (`CookLog.deductions`, `GroceryListItem.applied_quantity/unit`),
  so a future "undo" is a uniform reverse-the-snapshot operation.
- **Frontend** — `react-router-dom`; `auth.tsx` + `RequireAuth`; namespaced
  `api.ts` injecting the bearer token; `types.ts` mirroring the new schemas;
  pages: Login, RecipeList (search/filter + multi-select → grocery list),
  RecipeDetail (scale control, availability panel, "mark as cooked" with a
  deduct/no-deduct toggle, made-history), RecipeForm (dynamic ingredient rows),
  Inventory, GroceryLists (check lines, then one "submit" that commits to
  inventory). v2 additions: import-from-URL + photo in RecipeForm, review form +
  nested past reviews in RecipeDetail, ReceiptUpload, Research. Serving scaling is
  frontend-only for display; `availability`/`cook` take an explicit `multiplier`
  so the math stays server-side.

## Verification

- `cd backend && uv sync && uv run pytest` — all suites green (incl.
  `test_concurrency.py`, #R3).
- `cd backend && rm -f recipe.db && RECIPE_ALLOW_REGISTRATION=true
  RECIPE_REGISTRATION_CODE=devcode uv run uvicorn app.main:app --reload`, then at
  `/docs`:
  1. `POST /api/auth/register {username, password, code:"devcode"}` → copy token
     → Authorize. **Then stop the server and restart it without those two env
     vars** (#R8) — a second `POST /api/auth/register` now returns 403.
  2. `POST /api/recipes` with nested ingredients + steps; `GET` it back nested.
  3. `POST /api/inventory` a couple of items (e.g. `500 g flour`, `1 can
     tomatoes`); a second `POST` of `250 g flour` **adds** (flour row
     `quantity_base` = 750); `PATCH /api/inventory/{flour_id} {quantity:200}`
     **replaces** (→ 200 g); `PATCH {unit:"kg"}` just changes the displayed unit;
     `PATCH {unit:"can"}` → 422 (#P1). `GET
     /api/recipes/{id}/availability?multiplier=1` shows ok/short/missing, per-line
     `need` and `group_*` in canonical units with `group_unit` (#R7/#P5), and
     `have_uncertain` only when **positive** stock sits in an incompatible unit
     (#R6/#P4).
  4. `POST /api/recipes/{id}/cook {multiplier:1}` → inventory `quantity_base`
     drops; `CookLog` recorded with canonical
     `requested`/`deducted`/`deducted_unit`/`before`/`after` per line, and
     `before − deducted == after` (#P7). Cook a food down to `0` → a follow-up
     `availability` reports it `missing` (not `short`), and `POST /api/grocery`
     emits a full-need line for it (#P4).
  5. `POST /api/grocery {recipe_ids:[id]}` → list has only shortfalls,
     consolidated (`2 can` need − `1 can` stock ⇒ `1 can` line, #R1), each
     `quantity` in canonical units (#P5); `PATCH` a line `checked:true` →
     **inventory unchanged**; `POST /api/grocery/{id}/submit` → inventory rises,
     line `added_to_inventory` + `applied_quantity` (canonical) set, **list still
     `status:active`** (#R5); check another line and `submit` again → only that
     line is added; `PATCH` a frozen line → 409.
  6. `POST /api/grocery/{id}/archive` → `status:archived`; a further
     `PATCH`/`submit` → 409 (#R5).
  7. `POST /api/recipes/{id}/cook {multiplier:1, deduct:false}` → inventory
     unchanged, entry appears in `GET /api/recipes/{id}/cook-logs`.
  8. `GET /api/cook-logs` lists cook logs across recipes newest-first;
     `GET /api/cook-logs/{id}` returns one; delete that recipe → the log is
     still returned (#H5).
- Confirm `GET` on any data route with **no** `Authorization` header, a malformed
  one (`Authorization: garbage`), a wrong scheme (`Authorization: Basic x`), an
  unknown token, and an expired token all → **401** (#P6).
- Confirm a recipe ingredient `quantity: -1` or `0`, or a grocery
  `multiplier: 0` / `inf` → 422 (#H4).

## Critical files

- `backend/app/models.py` — `User`/`Session`, expanded `Recipe` +
  `RecipeIngredient` (with reserved-nullable `photo_path` / `raw_text`),
  `InventoryItem` composite unique `(match_name, unit_bucket)` (#2) +
  `quantity_base` source-of-truth / `display_unit` preference (#R2/#P1),
  `CookLog.deducted` + richer canonical `deductions` incl. `deducted_unit`
  (#16/#P7), `GroceryList` / `GroceryListItem` with `submitted_at` / canonical
  `applied_*` (#6/#P7), `CHECK` constraints (#13).
- `backend/app/database.py` — `make_engine` / `make_session_factory` helpers
  (#H2) + `PRAGMA foreign_keys=ON` + `busy_timeout` connect listener (#14/#8) +
  `BEGIN IMMEDIATE` transaction hook for **every request-scoped transaction**
  (#R3/#P3).
- `backend/app/main.py` — `create_app(settings, engine)` factory (#H2/#P2):
  derives the app-local `get_db` session dependency from the injected engine,
  stashes `settings` on `app.state` / `get_settings`; 5 routers, `/api/health`,
  lifespan `create_all` on the injected engine. No StaticFiles mount in v1.
- `backend/app/routers/recipes.py` — nested CRUD + `/availability` (canonical
  lines, positive-stock filter, #P4/#P5) + `/cook` (with `deduct`; canonical
  deductions, #P7) + `/cook-logs`.
- `backend/app/routers/cook_logs.py` — `GET /api/cook-logs` (paginated) +
  `GET /api/cook-logs/{log_id}` (#H5) — new router.
- `backend/app/routers/inventory.py` — `POST` additive upsert + `PATCH /{id}`
  absolute replacement (within-bucket → 422, collision → 409) + PATCH
  `match_name` (#P1) — new router.
- `backend/app/routers/grocery.py` — lists + `PATCH` items (state/edit only) +
  `POST /{id}/submit` (#6, no auto-archive #R5) + `POST /{id}/archive` (#R5) +
  delete — new router.
- `backend/app/routers/auth.py` — register/login/logout/me — new router.
- `backend/app/services/inventory_math.py` — `check_availability`,
  `generate_lines`, `add_to_inventory_calc`, `deduct_calc` (pure, propose-only,
  #H3; positive-stock filter #P4, canonical outputs #P5/#P7) — new service.
- `backend/app/services/ingredient_parse.py` — `parse_ingredient` (pure) — new.
- `backend/app/normalize.py`, `backend/app/units.py`, `backend/app/security.py` —
  new pure/util modules (`security.py`: optional header + five 401s, consumes
  `get_db` / `get_settings`, #P2/#P6).
- `backend/app/config.py` — new `RECIPE_*` settings: `session_ttl_days`,
  `allow_registration` (default `false`, #15), `registration_code`.
- `backend/app/schemas.py` → becomes `backend/app/schemas/` package
  (`common`, `auth`, `recipe`, `inventory`, `grocery`).
- `backend/tests/conftest.py` — factory-built app `create_app(test_settings,
  test_engine)` with **no `dependency_overrides`** (#H2/#P2), FK +
  `BEGIN IMMEDIATE` listeners on the test engine (#14/#P3), registration-on
  settings, `auth_client` (new default) + `user`.
- `backend/tests/test_concurrency.py` — file-backed SQLite, two connections,
  authenticated HTTP; cook-race + submit-race assert no lost update (#R3/#P3) —
  new test file.

## Status

- [x] Requirements gathered
- [x] Codebase exploration
- [x] Design pass
- [x] Final plan written and approved (pre-trim)
- [x] Git repo initialised, skeleton pushed, plan committed to `docs/plan.md`
- [x] Adversarial review pass 2 folded in (17 findings)
- [x] Hardening pass 3 folded in (#H1–#H5)
- [x] De-scoped to core-loop v1 (2026-08-31); photo / receipt OCR / URL import /
      recipe research / per-cook reviews → §Deferred to v2. Pre-trim plan
      archived at `git show 5144c25:docs/plan.md`.
- [x] Review pass 4 folded in (2026-08-31): opaque arithmetic (#R1), canonical
      `quantity_base` upsert (#R2), `BEGIN IMMEDIATE` + `test_concurrency.py`
      (#R3), narrowed descriptor stoplist (#R4), no grocery auto-archive +
      `/archive` endpoint (#R5), cross-bucket `have_uncertain` (#R6), per-line
      `need` + `group_*` fields (#R7), verification registration env vars (#R8),
      deferred-block wording (#R-def).
- [x] Review pass 5 folded in (2026-08-31): `display_unit` + additive `POST` /
      absolute `PATCH` + collision 409 (#P1); app-local session + `get_settings`
      deps, no `dependency_overrides` (#P2); `BEGIN IMMEDIATE` on every
      request-scoped transaction (#P3); positive-stock-only uncertainty /
      zero-stock-as-absent (#P4); `group_unit` + canonical availability figures,
      legacy `have`/`short` removed (#P5); optional auth header + five explicit
      401s (#P6); canonical `CookLog` deductions + `deducted_unit` (#P7). Units
      converted to canonical throughout every v1 response.
- [ ] Phase 0 — reset & deps (not started; awaiting go-ahead)
