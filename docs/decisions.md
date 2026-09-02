# Decision Log

This file preserves the rationale and review history behind backend v1. It is
not an implementation contract: [`spec.md`](spec.md) wins whenever an old
decision summary and the current specification disagree.

Open findings are tracked only in [`issues.md`](issues.md). Deferred product and
infrastructure choices live in [`features.md`](features.md).

## Product and scope decisions

| Decision | Outcome | Rationale |
|---|---|---|
| Product loop | Recipes → inventory check → cook/deduct → grocery shortfalls → submit purchases | This directly reduces the friction of cooking at home. |
| No meal planning | The unit of work is “make this recipe now” | Calendar planning is a different product model, not an incremental v1 feature. |
| Backend-only v1 | OpenAPI and tests are the v1 interface | Rebuilding the frontend at the same time would obscure validation of the core loop. |
| LAN-only deployment | No in-app HTTPS, email flow, or third-party identity provider | The initial household deployment has at most a couple of trusted users. |
| Shared household | Every authenticated member has full access; creator IDs are attribution only | Per-resource authorization is unnecessary for the initial deployment. |
| SQLite and `create_all()` | No Alembic until the first schema change after v1 | There is no valuable production data to migrate yet. |
| No AI services | Parsing and later research/OCR remain deterministic or on-device | This is an explicit product constraint. |
| v1 de-scope, 2026-08-31 | Photo upload, URL import, recipe research, per-cook reviews, and receipt OCR moved to v2 | They add independent dependencies and failure surfaces without strengthening the core loop. |

The full pre-trim plan is preserved at `git show 5144c25:docs/plan.md`.

### De-scope record (2026-08-31)

The pre-trim plan at `5144c25` was 1,117 lines and carried photo upload,
grocery-receipt OCR, URL import, cross-recipe ingredient research, and per-cook
reviews together with 22 review findings. That was roughly twice the scope
needed for a LAN-only SQLite v1 and bundled several independent dependencies and
failure surfaces onto the core loop. The five features moved to
[`features.md`](features.md), with the original plan retained in Git.

## Specification pass decisions

These identifiers are used by comments in `spec.md`.

| ID | Decision | Rationale |
|---|---|---|
| S1 | Recipe `ingredients` accepts `RecipeIngredientIn \| str`; pasted strings are parsed and preserve `raw_text` | Supports pasted ingredient lists without weakening structured API input. |
| S2 | Inventory PATCH requires `unit` whenever it sets `quantity`; a unit-only PATCH changes display preference | Prevents an unlabeled replacement amount from silently changing physical scale. |
| S3 | Username uniqueness and login lookup are case-insensitive while original casing is preserved | Avoids visually duplicate accounts and surprising login behavior. |
| S4 | Aggregated display labels are stable first-writer-wins in recipe/ingredient order | Removes loop-order nondeterminism. |
| S5 | An unfrozen grocery line can be deleted; frozen or archived lines return 409 | Completes line management without undermining applied snapshots. |
| S6 | `unit_bucket` is `str(30)` | Allows `opaque:` plus a reasonably long unknown unit token. |
| S7 | Archiving an already archived grocery list returns 409 | Keeps the guarded one-way transition explicit. |
| SD1 | `to_taste` availability lines are vacuous and excluded from `all_available` | A quantity-free instruction cannot participate in stock arithmetic. |
| SD2 | Cook deduction draws from compatible inventory rows by ascending row ID | Gives deterministic behavior without implying inventory rows are purchase lots. |
| SD3 | Inventory services accept and return frozen DTOs, never ORM objects or sessions | Keeps calculation pure and transaction ownership in routers. |
| SD4 | `add_quantities` emits partitions in first-seen input order | Keeps generated grocery insertion order deterministic across mixed unit buckets. |

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
| R6 | Availability filtered inventory to the required bucket only, so `clove`-need vs `bulb`-stock returned `missing`, never `have_uncertain` — that status was near-unreachable. | **Fixed.** Availability and `deduct` load **all** inventory rows for the `match_name`, then partition: compatible-bucket rows → do the math; else if any other-bucket row exists → `have_uncertain` + `nettable=false`; `missing` only when no row for the name exists at all. *(Refined by #P4: only **positive-stock** rows count; a row at `quantity_base = 0` is treated as absent, so `missing` also covers "only zero rows". Refined by #N3: a compatible-bucket **partial** short with other-bucket stock also present is now `have_uncertain` + `nettable=false`, not `short` + `nettable=true`.)* |
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
| P1 | `inventory_items.quantity` / `unit` stored "the amount+unit of the most recent add" — a value with no meaning after the next cook — and `POST` vs `PATCH` semantics were never distinguished. | **Fixed.** A row stores `quantity_base` (source of truth) + `display_unit` (a *preferred unit only*); the human-facing quantity is `from_base(quantity_base, dim, display_unit)` recomputed on **every read**, never persisted. `POST /api/inventory` = **additive upsert** (`quantity_base += …` within the `(match_name, unit_bucket)` row). `PATCH /api/inventory/{id}` = **absolute replacement** of that row (sets `quantity_base` outright from the given amount+unit). `PATCH` is **within-bucket only** — a `unit` that would change `unit_bucket` → **422** ("remove and re-add"). A `PATCH` that sets `match_name` such that the row's new `(match_name, unit_bucket)` is already held by another row → **409** (no auto-merge in v1); `POST` cannot collide (it upserts on that key by definition). *(Refined by #S2: a `PATCH` that sets `quantity` must also carry `unit`, else 422.)* Tests: add → cook → GET (display recomputed from base), `PATCH` absolute reduction (with `unit`), `PATCH` display-unit change within a bucket, `PATCH {quantity}` with no `unit` → 422, 409 collision. |
| P2 | `conftest.py` needed a second, independent DB-wiring mechanism (`dependency_overrides[get_db]`) on top of the injected `test_engine` — two ways to point the app at a database, kept in sync by hand. | **Fixed.** `create_app(settings, engine)` **derives and installs an app-local session dependency** closed over the injected `engine` (on `app.state`, exposed as `get_db` / `SessionDep`); there is no importable module-global session factory to override. Injected settings are reachable via a `get_settings(request)` dependency (`request.app.state.settings`) and directly as `app.state.settings`. `security.py` / `get_current_user` consume **those** dependencies, not module globals. `conftest.py` builds the app with `create_app(test_settings, test_engine)` and **overrides nothing** — the injected engine is the only DB wiring. |
| P3 | Only `cook` + grocery `submit` ran `BEGIN IMMEDIATE`; every other request (auth `last_used_at` bump, GETs, inventory/recipe CRUD) used `BEGIN DEFERRED`. A DEFERRED transaction that lazily upgrades to a write (a GET that also bumps `last_used_at`) can still deadlock a concurrent writer, and the policy was left implicit. | **Fixed (explicit simple policy).** **All** request-scoped SQLite transactions `BEGIN IMMEDIATE` — auth and GETs included — via the `database.py` hook. The "short auth session, then a mutation session" alternative is rejected as unnecessary complexity for a two-user LAN app. **Trade-off documented:** every request now serializes on the single SQLite write lock; for the intended concurrency (≤2 members) the added contention is immaterial and lost updates are impossible everywhere, not just on the two mutating paths. Exercised through authenticated HTTP requests in `test_concurrency.py` (not only the low-level races). |
| P4 | Availability / deduct partitioned inventory into compatible vs. other-bucket by **row existence**, so a row cooked down to `quantity_base = 0` still forced `have_uncertain` (incompatible bucket) or blocked `missing` (compatible bucket) — a stale empty row poisoned the result. | **Fixed.** Only **positive-stock** rows (`quantity_base > 0`) are considered. Partition: positive-compatible rows → do the math (`ok` / `short`); else any positive-incompatible row → `have_uncertain` + `nettable=false`; otherwise → `missing`. A zero-stock row is treated exactly as if it did not exist, so `cook`-to-zero yields `missing` in availability and a full-need grocery line. Test: cook a food to `quantity_base = 0`, then assert availability `missing` and a grocery line for the whole requirement. *(Refined by #N3: `short` / `nettable=true` requires that **no** positive incompatible-bucket row exists; with one present a partial short is `have_uncertain` and the emitted grocery line is `nettable=false`.)* |
| P5 | `AvailabilityLine.group_need` / `group_have` / `group_short` were converted "`from_base` back to `g.unit`" — an undefined per-group unit — and shipped as bare floats with no unit field; the pre-#R7 per-line `have` / `have_unit` / `short` fields survived in the schema with no writer. | **Fixed.** Add **`group_unit`**; `group_need` / `group_have` / `group_short` are in that canonical unit (`g` / `ml` / `unit` / opaque string), identical across every member line. **Remove** per-line `have` / `have_unit` / `short`. Per-line `need` / `need_unit` are also canonical now — the row's own `quantity × M` converted to base — so `need_unit == group_unit` and a client summing per-line `need` still gets the group total (the #R7 double-count fix holds; only its unit changes). |
| P6 | `get_current_user(authorization: str = Header(...))` made the header **required**, so a missing token returned FastAPI's 422, and malformed / wrong-scheme / expired tokens had no stated handling. | **Fixed.** `authorization: str \| None = Header(default=None)`. The dependency returns **401** explicitly for all five: missing header, malformed value (not exactly `<scheme> <token>`), wrong scheme (not `Bearer`, case-insensitive), token not found, token row past `expires_at`. All five are asserted in `test_auth.py`. |
| P7 | `CookLog.deductions[].deducted` was the canonical delta converted back to the undefined per-group `unit`, while `before` / `after` stayed canonical — mixed scales in one dict, no `deducted_unit`, and `requested` undefined for a group whose members use different units. | **Fixed.** `requested` and `deducted` are both in the bucket's **canonical unit**; add **`deducted_unit`**, with `requested_unit == deducted_unit == inventory_unit`. `requested` = the group's summed need in canonical units (order-independent, hence deterministic regardless of member unit mix). `before − deducted == after` now holds within every entry. Test: stock held in `g`, recipe asks in `kg` (and vice versa) — assert the recorded `requested` / `deducted` / `before` / `after` are all canonical and self-consistent. |

## Revisions — review pass 6 (2026-08-31)

Review pass 6 (`docs/issues.md`) raised three blockers (`#N1`–`#N3`) plus one
High finding (`#N4`) that is subsumed by the `#N2` fix. All four are folded in
here; `docs/issues.md` is the source record.

| # | Finding | Treatment |
|---|---|---|
| N1 | One `InventoryItemIn {item, quantity, unit, match_name}` was the stated input for **both** `POST` and `PATCH /{id}`. Required `item`/`quantity` ⇒ `PATCH {quantity:200}` and `PATCH {unit:"kg"}` 422; all-nullable ⇒ explicit `item:null` / `match_name:null` reaches non-null columns or the wrong 409, and omission-vs-explicit-null was undefined. | **Fixed.** Two schemas. **`InventoryItemCreate {item (req), quantity: float ≥0 finite (req), unit: str\|None, match_name: str\|None}`** for `POST`. **`InventoryItemUpdate {item: str\|None, match_name: str\|None, quantity: float\|None, unit: str\|None}`** for `PATCH /{id}` — every field omittable; the router uses `body.model_fields_set` to act only on supplied fields. Explicit `null` for `item`, `match_name`, or `quantity` (i.e. name in `model_fields_set` **and** value `None`) → **422**. `unit` may be omitted or explicitly `null`; a supplied `unit` (null included) whose `bucket_of(...)` ≠ the row's `unit_bucket` → **422** ("remove and re-add", so `unit:null` is accepted only on a COUNT row); a `match_name` collision on `(match_name, unit_bucket)` → **409** (#P1). Empty `PATCH {}` → **200** no-op. *(Refined by #S2: `PATCH {quantity:…}` without `unit` → 422.)* Tests: `PATCH {quantity:200, unit:"g"}`, `PATCH {quantity:200}` alone → 422, `PATCH {unit:"kg"}` within bucket, `PATCH {unit:null}` on COUNT vs non-COUNT (422), `PATCH {item:null}` / `{quantity:null}` / `{match_name:null}` → 422, empty body → 200, `POST` missing `item` or `quantity` → 422. |
| N2 | "Module layout" kept a module-level `engine/SessionLocal` while "#P2 / Schema management" said there is no module-global session factory and that `create_app` installs `get_db` on `app.state` — but routers/`CurrentUser` bind `Depends(...)` **statically at import**, so a generator stuffed on `app.state` is never consulted, and a retained global `SessionLocal` points the factory at two databases. | **Fixed.** `database.py` keeps **one** module-level default `engine` (built from `settings`, used only by the uvicorn entrypoint) and **no** `SessionLocal`. It defines the importable `get_db(request: Request)` — reads `request.app.state.session_factory`, opens a session, `yield`s, then `commit()` on clean return / `rollback()` on exception / always close — and `SessionDep = Annotated[Session, Depends(get_db)]`. `create_app(settings, engine)` stores `make_session_factory(engine)` as `app.state.session_factory` and `settings` as `app.state.settings` (+ `get_settings(request)` dep); that is the **only** DB wiring. Static `Depends(get_db)` works because `request` is per-request — `request.app` is the running app. `conftest.py` builds `create_app(test_settings, test_engine)` and overrides nothing. |
| N3 | Once **any** compatible-bucket stock existed, availability/grocery used compatible stock only and reported `short` / `nettable=true`, ignoring positive stock in an incompatible bucket that might cover part of the shortfall (`need 3 can` / have `1 can` + `1 jar` → confident `2 can` buy). | **Fixed.** Three-way partition of **positive** rows for the `match_name`: `compat` (same `unit_bucket`), `incomp` (any other bucket), none. Availability: compat ≥ need → `ok`; compat < need **and** `incomp` non-empty → `have_uncertain` + `nettable=false`, `group_have` = compat stock, `group_short` = the compat-bucket remainder; compat < need with `incomp` empty → `short` + `nettable=true`; no compat but `incomp` non-empty → `have_uncertain` + `nettable=false`, `group_have=0`; nothing → `missing`. Grocery generation mirrors it: emit the compat-bucket remainder with `nettable = (not incomp)`; a pure-incompatible requirement emits full need with `nettable = (not pos)`. Cook is unchanged — it already draws down `compat` only and logs `incomp` as `reason:"have uncertain (incompatible unit)"`, so the audit trail now matches availability. Tests: `need 3 can / have 1 can + 1 jar` → availability `have_uncertain` + `nettable=false` and a grocery line `2 can nettable=false`; `have 1 can` only → `short` + `nettable=true` and `2 can nettable=true`; `need 2 can / have 3 can + 1 jar` → `ok`, no line. |
| N4 | `get_current_user` bumps `last_used_at` (a write) but a read handler never commits, so closing the session rolls it back; if `get_current_user` commits itself, an authenticated mutation spans two transactions. | **Fixed via #N2.** `get_db` owns a single unit of work per request: `commit()` after a clean yield, `rollback()` on any exception. Routers `flush()` for IDs but never commit. The auth bump and the route mutation are therefore one `BEGIN IMMEDIATE` transaction (#P3), and `last_used_at` persists on ordinary authenticated GETs. `IntegrityError` / lock / `busy_timeout` → **409** before `get_db` commits (#H3). |

## Revisions — spec pass 7 (2026-08-31)

`docs/spec.md` (the execution spec derived from this plan) resolved seven points
that diverged from, or were left implicit by, this plan. The plan is updated to
match. **`docs/spec.md` is authoritative for v1 build detail**; this plan retains
rationale and the v2 roadmap.

| # | Change | Rationale |
|---|---|---|
| S1 | **Recipe ingredient input accepts pasted strings.** `RecipeCreate/Update.ingredients` is `list[RecipeIngredientIn \| str]`: a **string** element is run through `services/ingredient_parse.py` and its verbatim text stored in `recipe_ingredients.raw_text`; an **object** element is structured (`raw_text = NULL`). Blank string elements are skipped. `raw_text` is an **active v1 column**, no longer "reserved for v2". `parse_ingredient` is wired into `routers/recipes.py` in Phase 3 (still built + unit-tested pure in Phase 1). | User wants to paste an ingredient list. The parser already existed; only the wiring + the active column are new. |
| S2 | **Inventory `PATCH` with `quantity` requires `unit`** in the same request → else **422** ("unit is required when setting quantity"). Bare `PATCH {quantity: 200}` is no longer valid. `PATCH {unit: "kg"}` alone (display-unit change, `quantity_base` untouched) is still valid. The `(quantity, unit)` pair is converted to canonical base on write. | Removes the "200 could mean 200 kg" ambiguity in the old pseudocode (`cur_unit = row.display_unit or canon`). |
| S3 | **Username uniqueness and login lookup are case-insensitive** — `UNIQUE` index on `lower(username)`; login matches `lower(username) = lower(:input)`. Original casing is preserved in storage and responses. | `Alice` and `alice` must not become two accounts. |
| S4 | **Aggregated display label = first-writer-wins.** When consolidating requirements (availability aggregate, grocery generation), iterate recipes in `recipe_ids` order and ingredients in `position` order; the **first** ingredient row seen for a `normalized_name` sets the display `item`, later rows never overwrite (was `r.display_item = ing.item`, last-writer-wins). | Deterministic given input order. |
| S5 | **New endpoint `DELETE /api/grocery/{list_id}/items/{item_id}`** → **204** on an unfrozen line; **409** if the line is frozen (`added_to_inventory`) or the list is `archived`. | The plan had add + `PATCH` + list-delete but no per-line delete. |
| S6 | **`inventory_items.unit_bucket` widened `str(20)` → `str(30)`.** | `opaque:` + a long unknown unit token can exceed 20 chars. |
| S7 | **Re-archiving a grocery list returns `409`**, not an idempotent `200`. `POST /api/grocery/{id}/archive` runs `UPDATE … WHERE id=? AND status='active'`; `rowcount == 0` → `409 "list is not active"`. | Consistent with "`PATCH` / `submit` on an archived list → 409". |

Gap-fills folded in at the same time (the plan was silent, the spec decided):
`to_taste` availability lines carry `need_unit = <group canonical unit>` and
`group_need`/`group_have`/`group_short` `= null` (`group_key` still set); cook
draws down compatible rows in **ascending inventory-row `id` order**; every
`CookLog.deductions` entry carries the **full key set** (`null` where a branch
does not populate one), though the column stays `list[dict]` (⚠ N7 still open as
a typed schema); manual grocery items are added via `POST /api/grocery/{id}/items`;
`GET /api/grocery` takes an optional `?status=active|archived`; `GET /api/cook-logs`
defaults `limit=50` (`1..200`), `offset=0`; list endpoints have explicit
orderings; the registration `code` is compared with `secrets.compare_digest`;
`IntegrityError` / `database is locked` → `409` via global exception handlers.

## Revisions — phase-gate issue resolutions

Issues raised in review pass 6 that were deferred to their owning phase, now
resolved and folded into `spec.md`. `docs/issues.md` holds only what is still
open.

### N5 — Inventory `match_name` is a canonical server-owned key (2026-08-31)

**Decision:** `match_name` is always canonical, even when its source text comes
from a user. There is no use case in v1 for a deliberately non-canonical match
key.

**Resolution:**

- Every `match_name` — the `normalize_name(item)` default **and** any value
  supplied to `POST` / `PATCH /api/inventory/{id}` — is passed through
  `normalize_name` before store (was `.strip()` only).
- A value that normalizes to `""` (`"  "`, `"!!!"`) → **422**
  (`"match_name normalizes to empty"`).
- Collision detection and the additive-upsert `ON CONFLICT (match_name,
  unit_bucket)` both key off the normalized value. A `PATCH` whose *normalized*
  `match_name` collides with a different row → **409** (no auto-merge in v1 —
  consistent with #P1).
- Display `item` is still stored exactly as typed.

**Consequence:** two `POST`s with `match_name` `"Flour"` then `"flour"` (same
unit) now land on one row additively, instead of creating two logical
duplicates; an edited `match_name` like `" Flour "` matches a recipe ingredient
whose canonical name is `flour`. Descriptor-stripping in `normalize_name` (e.g.
`"large eggs"` → `egg`) applies to `match_name` too — intentional, since recipe
ingredient names are normalized the same way.

**Spec sites:** §1 model notes + `inventory_items` table, §4.4
`add_to_inventory_calc`, §5.5 schemas + `POST` + `PATCH` algorithm + examples,
§7 `test_inventory.py`. **Phase:** `phases/phase-4.md` gate + work + exit.

### N6 — Grocery-line edits: atomic quantity/unit pair + reclassify on content edit (2026-08-31)

**Decision:** On `PATCH /api/grocery/{id}/items/{item_id}`, `quantity` and `unit`
move together, with no server-side conversion; and any edit to the *substance* of
a line (`item` / `quantity` / `unit`) drops the solver's classification.

**Resolution:**

- If exactly one of `quantity` / `unit` is present in the request body
  (`model_fields_set`) → **422** `"quantity and unit must be set together"`.
  Values may be `null`; both keys must appear together. No conversion is done —
  the stored number always matches the unit the caller sent in the same body.
- Any `item` / `quantity` / `unit` edit reclassifies the line: `source →
  "manual"`, `nettable → true`. A generated line is a solver claim ("short
  exactly X, certain/uncertain"); a human override of item/amount/unit voids the
  claim, so the line is treated as hand-entered. A `checked`-only PATCH does
  **not** reclassify.
- Rejected alternatives: auto-converting on a unit-only edit (duplicates
  `to_base`/`from_base` into a new call site and still guesses wrong for the
  "the number is already in the new unit" intent); keeping `source="generated"`
  and only clearing `nettable` (leaves `source` describing data the solver never
  saw); re-running netting on edit (high surprise — user types `2 lb`, row
  silently becomes `907 g`).

**Consequence:** the N6 failure mode is closed — a generated `500 g` line can no
longer become `500 kg` (a 1000× inventory overshoot) via a `{"unit":"kg"}` edit,
and an edited line never carries a stale `generated` / `nettable=false` flag.
`nettable` remains inert in v1 (it informs the shopper; it never gates `submit`),
so reclassification has no algorithmic effect beyond honesty of the stored row.

**Spec sites:** §5.6 `GroceryListItemUpdate` schema + `PATCH` algorithm, §7
`test_grocery.py` + E2E step 5. **Phase:** `phases/phase-6.md` gate + work +
exit.

### N7 — `CookDeductionRead` is an enforced Pydantic model (2026-08-31)

**Decision:** The cook-deduction audit shape is guaranteed at the Pydantic
boundary, not by convention. The spec already designed `CookDeductionRead` (full
11-field table, `list[CookDeductionRead]` on `CookLogRead`); N7 makes it a real
model.

**Resolution:**

- `CookDeductionRead` is a `BaseModel` in `schemas/cook_logs.py` with all 11
  fields typed, nullable exactly where the §5.4 branch table permits (`item`,
  `applied`, `reason` never `null`), `reason` a `Literal` of the 5 allowed
  strings, and `model_config = ConfigDict(extra="forbid")`.
- `CookLogRead.deductions: list[CookDeductionRead]`. FastAPI validates every
  stored dict on read — a malformed, drifted, or extra-key entry is a loud
  `500`, not a silent shape change.
- The `cook_logs.deductions` **DB column is unchanged** — raw `JSON list[dict]`,
  written from `_entry()`.
- `_entry()` keeps returning a dict but its signature names all 11 params as
  **required** (no defaults) — a missing kwarg is a `TypeError` at cook time.
- Rejected: typing the log in the pure `deduct_calc` layer as well (a second
  type to keep in sync with the schema; the read boundary is where the stated
  "response validation cannot enforce it" gap actually lives).

**Consequence:** the promised audit format can no longer vary by branch. Deferred
undo / review features consume a shape the API guarantees. No migration — the
JSON column and `_entry()` writer are untouched.

**Spec sites:** §1 `cook_logs.deductions` note, §4.5 `_entry()` prose, §5.4
`CookDeductionRead` model + `CookLogRead`, §7 `test_recipes.py` +
`test_inventory_math.py`. **Phase:** `phases/phase-5.md` gate + work +
verification + exit.

### Phase 2 close-out — §7 test-seam registration code (2026-09-01)

**Decision:** The §7 test-seam description said `test_settings.allow_registration
= true` "(no code)". That contradicts `phases/phase-2.md` Verification bullet 1,
which requires the suite to exercise "requires the configured code when enabled".
The R-8 seam (`conftest.py`) therefore sets a fixed `registration_code` and the
anonymous `client` fixture passes it on register.

**Resolution:** §7 opening paragraph updated to state the seam configures a fixed
`registration_code` alongside `allow_registration = true`. Behavior-neutral —
the seam already worked this way; only the stale parenthetical changed.

**Spec sites:** §7 opening paragraph. **Phase:** `phases/phase-2.md` R-6 / R-10
close-out.

This subsection preserves the original review verdict, resolution map, and
full N1–N4 failure scenarios. References to sections in `docs/plan.md` describe
the pre-refactor monolith; current normative destinations are in `spec.md`.

Review date: 2026-08-31
Resolution date: 2026-08-31 — **N1, N2, N3 (blockers) and N4 resolved** in
`docs/plan.md` §"Revisions — review pass 6". N5–N7 remain open for their owning
phase. See the Resolution section below.

Scope calibration: this is a local, LAN-only, educational application for at
most a couple of trusted household users. Global SQLite write serialization,
full-trust household access, forward-only cook/grocery actions, and postponing
migrations are therefore **not** treated as blockers.

### Verdict

The plan is close, and Phases 0-1 can start safely. Phases 2-6 should not be
executed unchanged until **N1-N3** are resolved: the inventory PATCH schema
contradicts its documented examples, the app-local database dependency is not
actually defined in a form static FastAPI routers can consume, and mixed
compatible/incompatible stock is still treated as confidently nettable. The
remaining findings should be settled before their owning phase to avoid
ambiguous APIs or misleading audit data.

**Update 2026-08-31:** N1, N2, N3 and N4 are folded into `docs/plan.md` (§Revisions
— review pass 6). Phases 2-6 are now unblocked. N5, N6, N7 stay open for
Phases 4/5/6 respectively.

### Resolution (2026-08-31)

| ID | Status | Where fixed in `docs/plan.md` |
|---|---|---|
| N1 | **Resolved** | §Revisions pass 6 row N1; §Schemas `inventory.py` (`InventoryItemCreate` vs `InventoryItemUpdate`); §"edit an inventory row" pseudocode (`model_fields_set` gate, explicit-null → 422, `PATCH {}` → 200); Phase 4; test strategy `test_inventory.py`. |
| N2 | **Resolved** | §Revisions pass 6 row N2; §Module/router layout (`database.py`, `security.py`, `main.py` lines); §Schema management (importable `get_db(request)` + `SessionDep`, `app.state.session_factory` only, no `SessionLocal`); Phase 2; Critical files. |
| N3 | **Resolved** | §Revisions pass 6 row N3; availability + grocery-generation pseudocode (three-way `compat`/`incomp`/none partition); #R6 and #P4 revision rows (refinement notes); Done criteria items 4 & 6; cook narrative (deliberate non-adoption); test strategy `test_inventory_math.py` / `test_grocery.py`. |
| N4 | **Resolved via N2** | §Revisions pass 6 row N4; §Schema management "Unit of work" bullet — `get_db` commits on clean return / rolls back on exception; routers `flush()` only; auth `last_used_at` bump rides the request's one transaction. |
| N5 | **Resolved 2026-08-31** | §Revisions — phase-gate issue resolutions → N5; `spec.md` §1 / §4.4 / §5.5 / §7; `phases/phase-4.md`. |
| N6 | **Resolved 2026-08-31** | §Revisions — phase-gate issue resolutions → N6; `spec.md` §5.6 + §7; `phases/phase-6.md`. |
| N7 | **Resolved 2026-08-31** | §Revisions — phase-gate issue resolutions → N7; `spec.md` §1 / §4.5 / §5.4 / §7; `phases/phase-5.md`. |

### Findings

| ID | Severity | Title | Plan location / responsible text | Concrete failure scenario | Impact | Required plan change | Confidence |
|---|---|---|---|---|---|---|---:|
| N1 | **Blocker — Phase 4** | Inventory POST and PATCH cannot share the stated input schema | **Schemas → `inventory.py`:** `InventoryItemIn {item, quantity, unit, match_name}` is described as the input for both operations. **Edit algorithm:** `PATCH /api/inventory/{id} {item?, match_name?, quantity?, unit?}`. **Verification:** `PATCH {quantity:200}` and `PATCH {unit:"kg"}`. | If `InventoryItemIn.item` and `quantity` are required as written, both verification PATCHes return 422. Making every field nullable instead allows explicit `item:null` or `match_name:null`, which reaches non-null database columns or produces the wrong 409. | Phase 4 cannot implement both its schema and its acceptance examples. Patch omission versus explicit null is also undefined. | Define `InventoryItemCreate` with required `item` and `quantity`, and a separate `InventoryItemUpdate`: `item`, `match_name`, and `quantity` may be omitted but cannot be null when present; `unit` may be omitted or explicitly null because null is a valid COUNT unit. Use `model_fields_set` to distinguish omission. Add 422 tests for null required fields and for `unit:null` when it would change a non-COUNT row's bucket. | 1.00 |
| N2 | **Blocker — Phase 2** | The app-local session dependency is contradictory and not wired to static routers | **Module layout:** says the default module-level `engine/SessionLocal` is retained. **Review P2 / Schema management:** says there is no importable module-global session factory and that `create_app` installs `get_db` on `app.state`. Routers and `CurrentUser` are nevertheless defined statically with `Depends(...)`. | FastAPI resolves a concrete dependency callable when router functions are defined; putting a newly created generator function on `app.state` does not make existing `Depends` declarations use it. Retaining global `SessionLocal` makes the factory point at two databases again; removing it without a generic dependency leaves routers with nothing importable to depend on. | Phase 2 can either query the wrong engine or require the same manual overrides P2 claims to eliminate. Multiple factory-created apps are especially likely to cross wires. | Make the contract explicit: `create_app` stores only `session_factory` on `app.state`; define one importable `get_db(request: Request)` dependency that reads `request.app.state.session_factory`; define `SessionDep = Annotated[Session, Depends(get_db)]`; have all routers/security use it. Keep a module-level default **engine** only to construct the uvicorn app, but no module-level `SessionLocal`. Update the module-layout contradiction. | 0.98 |
| N3 | **Blocker — Phase 4/6** | A known shortfall is marked nettable even when additional incompatible stock makes the true shortfall uncertain | **Availability:** once any compatible row exists, only compatible stock participates and the result is `ok`/`short`. **Grocery generation:** when compatible stock exists, the emitted shortfall is always `nettable=true`; other positive buckets are ignored. | A recipe needs `3 can tomatoes`; inventory has `1 can` and `1 jar`. The plan subtracts the can, reports `short 2 can`, and generates a confidently nettable `2 can` grocery line. The jar may cover some or all of that need—the exact shortfall is unknown. The same occurs with `1 kg flour` plus `1 bag flour`. | The core grocery feature can overbuy while claiming its result was safely netted, contradicting “unit-incompatible lines are flagged `nettable=false`.” | Partition into positive compatible and positive incompatible rows. If compatible stock fully covers the need, return `ok`. If a positive short remains **and** incompatible stock exists, return `have_uncertain` and emit the known compatible-bucket remainder with `nettable=false`. Only use `short`/`nettable=true` when no positive incompatible stock exists. Add availability and grocery tests for `need 3 can / have 1 can + 1 jar`. | 0.98 |
| N4 | High — Phase 2 | Transaction completion for `last_used_at` and read requests is unspecified | **Auth:** `get_current_user` bumps `last_used_at`. **Concurrency:** every request transaction begins immediately. **Service rule:** routers own and commit transactions. The app-local `get_db` dependency is described only as yielding and closing a session. | On a successful GET, `get_current_user` updates the ORM row, but the read handler has no reason to commit. Closing the session rolls the update back. If `get_current_user` commits itself, an authenticated mutation now spans an auth transaction and a separate router transaction, contrary to the implied single request transaction. | `last_used_at` silently stops working or transaction boundaries vary by endpoint. Lock-timeout handling also becomes harder to place consistently. | Choose one unit-of-work policy. Recommended here: `get_db` commits once after a successful dependency yield and rolls back on any exception; routers `flush` when IDs are needed but do not independently commit. This makes the auth bump and route mutation one transaction. Document where SQLite lock/`IntegrityError` exceptions are translated to 409. Alternatively, drop per-request `last_used_at` updates and update it only on login. | 0.94 |

### Assumptions reviewed in pass 6

- A partially satisfied requirement with additional incompatible stock is
  intended to be uncertain, not a confidently nettable shortfall.
- `match_name` is a canonical server-owned match key even though a user may
  supply its source text.
- A grocery unit-only edit should preserve physical quantity rather than merely
  relabel the existing number.
- `last_used_at` is intended to persist on ordinary authenticated GET requests;
  otherwise the per-request write and its locking cost should be removed.

## Revisions — review pass 8, design grilling (2026-09-01)

An interactive design interview over the whole v1 surface: five rounds, 24
questions, 23 decisions (Q3 was superseded by Q8). Working record and full
rationale: `.scratch/backend-v1-grilling/map.md`. Four of the decisions came
from defects found by reading and running the shipped Phase 2 code, not from an
agenda:

| # | Finding | Evidence |
|---|---|---|
| F1 | `DateTime(timezone=True)` columns come back from SQLite **naive**, so every read path violated §Mechanical defaults' `…+00:00` promise. One column had already been hand-patched. | `security.py` expiry comparison |
| F2 | `issue_token` read `session_ttl_days` from the **module-global** `Settings`, so `create_app(test_settings, …)` could not influence token lifetime; the expired-token test worked around it by rewriting `expires_at` in the database. | `security.py`, `test_auth.py` |
| F3 | `get_db` committed **after** `yield`, which runs after the response is generated. A failing commit returned **`200` with the write silently discarded** — not the `409` §6 promises, and not even a `500`. Reproduced both ways: under the real server configuration the handler was never invoked; with server exceptions raised, Starlette reported `Caught handled exception, but response already started`. | repro during the session |
| F4 | `test_concurrency.py` as specified **cannot fail**: `BEGIN IMMEDIATE` on every transaction makes the lost-update interleave unconstructable, so it passes vacuously. | `database.py` `on_begin` |

Decisions, numbered as asked. Each is now normative in `spec.md`; this table is
rationale only.

| # | Decision | Rationale |
|---|---|---|
| Q1 | **`UtcDateTime` type decorator** in `database.py`, applied to every datetime column; the ad-hoc naive-datetime patch in `security.py` is deleted. | The only fix that holds for every read path including raw-SQL ones, and it removes existing debt instead of adding a second workaround. *Rejected:* per-schema Pydantic validators (miss raw-SQL paths); amending the spec to allow naive output. |
| Q2 | **Account lifecycle:** keep the env-var first-user bootstrap and let Phase 7 document it as *the* procedure; **add `POST /api/auth/change-password`**; accept unbounded `sessions` growth in v1. | Without the endpoint, a rotated credential is a `sqlite3` shell job forever. A household generates a few session rows a month. *Rejected:* session reaping on login or by sweep. |
| Q4 | **Normalize the recipe-ingredient `unit` on both input paths** — lower-case, strip one trailing `.`, **no singularization**. | The only raw consumer of `recipe_ingredients.unit` is `RecipeRead`; every math path already calls `normalize_unit_token`, which singularizes internally. Singularizing on write would change exactly one displayed string while costing a locked R-7 oracle (§2.3 "`cups` stays `cups`") and reading wrong (`2 cup flour`). *Rejected:* singularizing on write; normalizing neither path. |
| Q5 | **Zero-content recipes are permanently legal.** Only `title` is required. | A title-only stub is a legitimate capture-now-fill-later flow, and every downstream case is already total. The explicit §5.2 line stops a later reviewer "fixing" it. *Rejected:* a minimum-content rule. |
| Q6 | **Python-side timestamps everywhere** — `default=_utcnow`, `onupdate=_utcnow`, and an explicitly bound `_utcnow()` in the §5.5 upsert and the §5.4 Core `UPDATE`. §1's "server default `now()`" wording is corrected. | SQLite's `CURRENT_TIMESTAMP` is a naive, second-precision string; it fights Q1 and drops sub-second ordering. One clock. *Rejected:* server defaults as §1 previously specified. |
| Q7 | **`change-password` contract:** `403 {"detail": "incorrect password"}` on a wrong current password; revoke the user's sessions. Phase 2 owns it. | The token is valid and the *action* is refused; `401` would wrongly tell the client to re-authenticate. Revocation is what makes the endpoint worth having. *Rejected:* `401`; leaving other sessions alive; deferring to Phase 7. |
| Q8 | **Rewrite `test_concurrency.py`'s contract** (supersedes Q3): assert serialization, the `409` lock mapping, and post-commit freshness; keep one threaded HTTP smoke test. | Fixes F4 — the test must assert the property that *prevents* the race, since `BEGIN IMMEDIATE` makes the race itself unconstructable. It also exercises `_to_409_if_locked_else_500`, which nothing else covers. *Rejected:* the raw two-`Session` lost-update interleave originally recommended in Q3 (impossible to construct); threaded HTTP alone (flaky, gets skipped). |
| Q9 | **`issue_token(db, user, settings)`.** | Fixes F2; removes the last module-global configuration read from a request path and makes `issue_token` a function of its arguments. Both call sites already have settings injected. *Rejected:* reading `request.app.state` inside `issue_token`. |
| Q10 | **Keep canonical-unit-only responses (#P5)**; record display-unit conversion as v2. | One representation is what makes the netting, consolidation, and deduction math auditable, and every R-7 oracle is expressed in canonical units. Choosing *which* display preference wins is a real design question. Noted in `features.md` with the user-visible consequence (`2 lb` in → `453.592 g` on the grocery list) and the `units.from_base` hook. |
| Q11 | **`ConfigDict(extra="forbid")` on `RecipeIngredientIn` only.** | It is the only schema where a dropped key produces a *successful wrong write* rather than an error: `{"item": "flour", "qty": 500}` would return `201` and silently store a to-taste ingredient. *Rejected:* `extra="forbid"` on every request schema — touches every Phase 3–6 schema; wait for evidence. |
| Q12 | **`change-password` rotates the caller's token too:** delete every session for the user, issue a fresh one, return `200 TokenResponse`. | Makes revocation one unconditional `DELETE WHERE user_id = :me` with no `AND id != current` special case, and a full-window reset is what someone changing a password actually wants. *Rejected:* reusing the caller's row — a session spanning a credential change. |
| Q13 | **`TransactionRoute(APIRoute)` owns the commit**, running it after the endpoint returns but before the response is built. Add a test that fails at `COMMIT` specifically. | Fixes F3. The only option where a client is never told a write succeeded when it did not; silent data loss is the one failure a household recipe box cannot absorb. Verified by prototype during the session: the wrapper returns `409 {"detail": "conflict"}`, and serialization completes before the commit, so `expire_on_commit` needs no change. *Rejected:* mandating a trailing `flush()` in every mutating handler (catches constraint violations only, never a lock at `COMMIT`); accepting the behavior and narrowing §6. |
| Q14 | **Leave the two import-time module globals alone** (`database.engine`, `main.app`). | They are the documented `uvicorn app.main:app` entrypoint. SQLAlchemy engines are lazy, so the test-suite side effect is a file that never gets touched. Revisit only if a test is observed writing `recipe.db`. *Rejected:* a `--factory` entrypoint. |
| Q15 | **Document a backup procedure in Phase 7** — `sqlite3 recipe.db ".backup …"` plus restore. Leave the Alembic trigger where `features.md` puts it. | Schema changes are `rm backend/recipe.db`, Alembic is deferred to the first change *after* v1, and nothing told an operator to take a copy — so the moment data becomes valuable and the moment a tool exists to protect it were separated by an unbounded gap. `.backup`, not `cp`: safe on a live database. *Rejected:* pulling Alembic into v1 (contradicts a deliberate deferral); a `GET /api/export` endpoint. |
| Q17 | **Rewrite §6's transaction-ownership paragraph** to name `TransactionRoute` as owner, keep `rollback()` + `close()` in `get_db`, narrow `flush()` to "call it when you need a generated id", and state that a commit-time conflict or lock now converts to `409`. §3.2/§3.3 get matching edits. | *Unchanged:* a route raising `HTTPException(404)` still rolls back, so `get_current_user`'s `last_used_at` bump is still lost on an error response. |
| Q18 | **One "Operating the server" section in `README.md`** with ordered runbooks: bootstrap, backup, schema reset / restore. Phase 7's checklist points at it. | All three are the same activity — a human at a terminal, server stopped, doing something irreversible — and the ordering that matters is exactly what gets lost when they are scattered across three documents. |
| Q19 | **Commit `docs/frontend/`.** | `plan.md`'s document map has a row for it and `phase-7.md` is told to link to it; not committing it left two documents pointing at nothing. The scope fence already handles the risk in prose, and untracked planning docs rot. |
| Q20 | **One spec-edit PR, then one Phase 2 hardening PR, then Phase 3.** | `plan.md` requires spec edits before the owning phase implements. The Phase 2 items are all infrastructure in the same four modules and want one R-6 reviewer pass. One spec PR is *more* reviewable than five scattered ones, because the decisions interlock — Q1 and Q6 are one paragraph, Q13 and Q17 are one section. *Rejected:* per-phase spec edits; folding the Phase 2 reopen into Phase 3. |
| Q21 | **No new R-7 contract-test gate for Phase 3**; add explicit §7 rows instead. | The gate exists to stop implementation and validation sharing an interpretation error in *arithmetic*. Q4/Q5/Q11 are single-branch rules where a spec sentence and a test row are the same statement. |
| Q22 | **`session_ttl_days: Field(30, ge=0)`**; leave `cors_origins` alone. | Zero is meaningful — it is the clean way to test the expiry branch now that Q9 makes lifetime injectable. Negative is pure misconfiguration. `cors_origins`' default is inert in v1 and Phase 7 owns explaining it. *Rejected:* `ge=1`, which would close the door Q9 just opened. |
| Q23 | **One `decisions.md` entry** (this one); **Phase 2 reverts to "In progress"** until the hardening lands. | The decisions interlock, so scattered entries lose that. Phase 2 was marked Complete while nothing was in version control. |
| Q24 | **`TransactionRoute` lives in `database.py`**; `get_db` stashes `request.state.db`; the route class no-ops when it is absent. **Add a guard test** iterating `app.routes`. | `route_class` is a property of the `APIRouter` a route is *declared* on, and `include_router` cannot apply it retroactively. Phases 4–6 each add a router; a forgotten `route_class=` silently reverts that router to F3 with no test failing. The guard test is the only mechanism that catches it. *Rejected:* `main.py` as the home — routers cannot import `main` without a cycle; relying on a `make_router()` helper alone. |

Not resolved, deliberately: **D1** (open-vocabulary singularization) and **D2**
(multi-line ingredient paste) were not opened; **Alembic** stays deferred to the
first schema change after v1, with Q15 mitigating the data-loss window through
documentation rather than by moving the trigger; **no linter** is configured.

No ADR was written. Nothing here clears hard-to-reverse **and** surprising
**and** a real trade-off. Q13 comes closest, and it is a bug fix with one
sensible answer.

`CONTEXT.md` was created at the repository root during the session — a glossary
only. It pins the vocabulary Q4 forced open, since three distinct things were
all being called "unit": **author's unit**, **canonical unit**, **display
unit**, **unit bucket**, and **opaque unit**.

## Planning status at the refactor boundary

This is the preserved status record from the former monolithic plan. Current
phase status is authoritative in `plan.md`.

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
- [x] Review pass 6 folded in (2026-08-31): the three `docs/issues.md` blockers
      resolved — split `InventoryItemCreate` / `InventoryItemUpdate` with
      `model_fields_set` omission-vs-null semantics (#N1); concrete
      module-`engine`-only + importable `get_db(request)` reading
      `app.state.session_factory` + `SessionDep`, `get_db` owns the commit
      (#N2, subsumes the #N4 transaction-boundary finding); #N3 three-way
      compatible/incompatible/none partition so a shortfall with incompatible
      stock present is `have_uncertain` + `nettable=false`, not confidently
      nettable. Phases 2–6 can now proceed.
- [x] Spec pass 7 folded in (2026-08-31): `docs/spec.md` written; seven
      divergences reconciled into this plan — pasted-string ingredient input +
      active `raw_text` (#S1), inventory `PATCH {quantity}` requires `unit`
      (#S2), case-insensitive usernames (#S3), first-writer-wins aggregate label
      (#S4), `DELETE` grocery line endpoint (#S5), `unit_bucket` `str(30)` (#S6),
      re-archive → 409 (#S7), plus gap-fills. **`docs/spec.md` is authoritative
      for v1 build detail.**
- [x] Phase 0 — reset & deps (complete, 2026-08-31, PR #12). Phase 1 — pure
      core (complete, 2026-09-01, PR #16). Phase 2 — auth and app factory
      (first pass, 2026-09-02, PR #20). See the status table in
      [`plan.md`](plan.md) for live phase state.
- [x] Review pass 8 folded in (2026-09-01): design grilling over the whole v1
      surface — `UtcDateTime` + Python-side timestamps (Q1, Q6), `change-password`
      with full session revocation and token rotation (Q2, Q7, Q12),
      `issue_token(db, user, settings)` + `session_ttl_days` `ge=0` (Q9, Q22),
      `TransactionRoute` owning the commit + the route-class guard test (Q13,
      Q17, Q24), symmetric ingredient-unit normalization + `extra="forbid"` +
      zero-content recipes (Q4, Q5, Q11), the `test_concurrency.py` contract
      rewrite (Q8), and the Phase 7 backup and runbook items (Q15, Q18).
      **Phase 2 reopened for hardening (Q23).**

## Supersession rules

- Later rows refine earlier rows with the same subject.
- Review pass 8 refines the earlier passes where they overlap: it supersedes
  #N2's "`get_db` owns the commit" with `TransactionRoute`, and #R3's
  `test_concurrency.py` contract with the properties in Q8.
- The specification pass refines the review-pass summaries.
- A closed issue must update `spec.md`; closing it only in this log has no
  implementation effect.
- Git history retains verbatim copies of the former monolithic plan; this log
  keeps its complete review findings live without duplicating the normative
  implementation contract.
