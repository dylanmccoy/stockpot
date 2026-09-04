# Future Features and Roadmap

This file owns work outside backend v1: deferred product capabilities,
infrastructure upgrades, extension invariants, and deliberately excluded
directions. The shipped v1 boundary and phase order live in [`plan.md`](plan.md);
the normative v1 behavior lives in [`spec.md`](spec.md).

The pre-trim plan and its original review detail remain available at
`git show 5144c25:docs/plan.md`.

## Current v1 boundary

Backend v1 contains authentication, structured recipes, inventory, availability,
cook/deduct history, grocery-list generation and submit, unit conversion, tests,
and LAN operating documentation. It has eight phases numbered 0–7.

It does not contain uploads, outbound HTTP, OCR, a rebuilt frontend, migrations,
meal planning, or multi-household authorization.

## Standing constraints for future work

- Preserve one-way imports and the app-factory test seam.
- Keep live network and subprocess seams narrow and mocked in ordinary tests.
- Keep server-side inventory math canonical and auditable.
- Preserve raw source evidence when imports or OCR create editable records.
- Keep forward-only actions explicit and snapshot what was actually applied.
- Do not introduce an LLM or hosted AI dependency.

## Deferred to v2

| Feature | Hook already present in v1 | Why deferred |
|---|---|---|
| Photo upload | Nullable `recipes.photo_path` | Adds multipart handling, file lifecycle, and a static mount without strengthening the core loop |
| URL import | Active `recipe_ingredients.raw_text` and structured recipe creation | Adds runtime HTTP, scraping, and an SSRF-sensitive fetch boundary |
| Recipe research | URL-import preview DTOs can be reused | Depends on URL import and is exploratory rather than transactional |
| Per-cook reviews | Durable `cook_logs` provide the attachment point | Useful history, but not required to complete the cook/inventory loop |
| Grocery-receipt OCR | Inventory additive upsert is the apply target | Highest operational cost: native OCR, private files, image limits, and concurrency controls |

The specifications below are execution-ready except for the explicit
**Before v2** decisions attached to individual features. The archived pre-trim
plan remains the source for still-earlier exploration, not for missing current
requirements.


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
## Additional deferred features

| Feature | v1 status | Hook already in place | Work to add |
| --- | --- | --- | --- |
| "What can we make now" | Excluded | `check_availability` exists; runs on one recipe | `GET /api/recipes/makeable` — run it across all, filter `all_available` |
| Staples / low-stock alerts | Excluded | `inventory_items` row structure | `is_staple: bool` + `min_quantity: float` columns; `GET /api/inventory/low` |
| Undo for forward-only actions | Excluded | `CookLog.deductions` (requested/deducted/before/after) and `GroceryListItem.applied_quantity/unit` snapshot what was applied; `ReceiptItem.applied_quantity/unit` joins them once receipt OCR lands | One uniform reverse-apply op across cook + grocery (+ receipt in v2); no per-action `/undo` route until designed |
| Frontend (React SPA) | Excluded; v1 backend only | Skeleton in place (`App.tsx` / `api.ts` / `types.ts`); **does not work against v1 API** and was left untouched | `react-router-dom` + pages; auth.tsx + bearer-token injection in api.ts; mirror types.ts to v1 schemas |
| Multi-line ingredient paste | Excluded; caller pre-splits | §5.2 per-line ingredient build; `parse_ingredient` per line | Server-side split of a pasted block on `\n` (blank/header/bullet handling) before the existing per-line build; `issues.md` §Deferred item D2 |
| Availability / grocery uncertainty naming | v1 ships `AvailabilityStatus="have_uncertain"` and a negated `nettable` bool | `check_availability` / `generate_lines` set both; locked oracle tables in §7 | Investigate renaming to a positively-phrased `units_comparable` / `incomparable_units`, and a status enum on grocery lines for parity; raised by the frontend track (`frontend/decisions.md` §Q19 follow-up) — no user-facing effect, frontend copy already covers it |
| Display-unit conversion on output | Excluded; every response is canonical-unit | `inventory_items.display_unit` already stores a per-row preference; `units.from_base` already converts | Apply a display preference when serializing availability / grocery / cook-log quantities, or accept a `?units=` request parameter; see below |

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
- **Hook in v1:** `inventory_items` table; `CHECK(quantity_base >= 0)` constraint;
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

### Multi-line ingredient paste

- **v1 status:** excluded. Each element of `payload.ingredients` is one
  ingredient line by contract; §5.2 does no newline splitting. A `str` element
  with embedded `\n` is parsed as a single line (with R-4 it is first truncated
  to 200 chars, so it cannot overflow a column — it just yields one garbled
  row).
- **Hook in v1:** the per-line build loop in §5.2 and `parse_ingredient`
  already handle a clean array of lines; a splitter would feed that loop.
- **Work to add:** accept a raw pasted block, split on `\n`, `strip()` each
  line, drop blanks, and decide how to treat non-ingredient lines (section
  headers like `"For the sauce:"`, leading bullets `- `/`* `, soft-wrapped
  lines). Natural home is the frontend paste box; a server-side endpoint is
  only needed if an API consumer must POST an unsplit block. No timeline
  (`issues.md` §Deferred item D2).

### Display-unit conversion on output

- **v1 status:** excluded (decision #P5). Every quantity outside a recipe body is
  emitted in its bucket's **canonical unit** — `g`, `ml`, `unit`, or the opaque
  token. `inventory_items.display_unit` is honored on `InventoryItemRead` only;
  availability `need_unit` / `group_unit`, generated grocery-line `unit`, and
  every cook-log quantity/unit are canonical with no preference applied.
- **Consequence a user sees:** add `2 lb` of chicken and the grocery list asks for
  `453.592 g` more; add `1 cup` of stock and availability reports `ml`. Someone
  who types `1 kg flour` never sees `kg` again outside the inventory list.
- **Why deferred, not fixed:** one representation is what makes the netting,
  consolidation, and deduction math auditable — `add_quantities` partitions by
  bucket and sums in base units, and the R-7 locked oracles are all expressed in
  canonical units. Converting at the edge is a serialization concern, but
  choosing *which* preference wins is a real design question (per-row
  `display_unit`? a per-user setting? a request parameter?) and every answer
  multiplies the values a test has to pin.
- **Hook in v1:** `units.from_base(amount, dim, unit)` already does the
  conversion and already returns `None` for a cross-dimension or opaque target.
  `inventory_items.display_unit` already stores a per-row preference, and
  `InventoryItemRead.display_quantity` already demonstrates the pattern.
- **Work to add:** decide the preference source, then apply `from_base` in the
  read-model assembly for availability, grocery, and cook-log responses. Keep the
  canonical value in the payload alongside the converted one so clients and tests
  can still assert on an unambiguous number. Do **not** change what is stored:
  `quantity_base` and the locked service-layer oracles stay canonical.
- **When to revisit:** with the frontend SPA effort, which is where the
  formatting burden actually lands. No timeline.

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

### Hashed session-token storage

- **v1 approach:** register/login returns an opaque bearer token generated with
  `secrets.token_urlsafe(32)`, and `sessions.token` stores that exact token in
  plaintext. Authentication performs an exact lookup. Database read access is
  therefore sufficient to impersonate any user with an unexpired session.
- **Upgrade path:** continue returning the raw random token to the client, but
  store only a SHA-256 digest in the database and look up the digest computed
  from the presented token. These tokens already have 256 bits of CSPRNG entropy,
  so a fast cryptographic digest is appropriate; password hashing would add cost
  without protecting against feasible token guessing. Keep expiry, logout, and
  password-change revocation semantics unchanged.
- **Rollout:** either revoke all existing sessions when the schema changes, or
  temporarily support both representations and replace plaintext rows as users
  authenticate. Revoking all sessions is the simpler and safer option for the
  intended small household deployment.
- **When to add:** before remote/public hosting, before database backups are
  stored outside a trusted machine, or once database compromise becomes part of
  the threat model.
- **Why deferred:** v1 is LAN-only and already documents plaintext token storage
  as an accepted risk. This hardening requires a schema/lookup change and a
  deliberate existing-session migration policy, but no API contract change.

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
lowercase, strip descriptors, `_singularize_token` on the final token — a small
hand ruleset, not a full inflection engine).

Inventory items → `match_name` (user-editable, defaults to their own
`normalized_name`).

Matching: recipe ingredient's `normalized_name` == inventory item's `match_name`
(string equality, no aliases).

**Rough edges:** imperfect singularize (e.g., "feta" stays "feta" after
descriptor stripping, but a recipe says "feta cheese" and inventory says "feta
block"). Editable `match_name` per inventory row lets users correct mismatches
manually, but it does not scale (every item must be corrected independently).

**Deferred: robust name singularization (`issues.md` §Deferred item D1).** `normalize.py`
uses one small hand ruleset (`_singularize_token`: irregular map, `-ies→-y`,
`-es`-group, trailing `-s`). It was pinned in v1 for the *closed* unit-token set
(readiness R-3), where it is provably complete. Ingredient **names** are
open-vocabulary — `cherries`/`berries` (fine), but also `gnocchi`, `biscotti`,
`roux`, mass nouns, and multi-word heads — and the ruleset will mis-handle some.
A library (`inflect`) is a defensible choice for names specifically, since the
vocabulary is genuinely open; it was rejected for units only. Fold this in with
the `FoodItem` upgrade below, or sooner if name mismatches become a real
annoyance. No v1 change.

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
