# Future Features and Roadmap

This file owns work outside the shipped v1 product: deferred capabilities,
infrastructure upgrades, extension invariants, and deliberately excluded
directions. The backend phase order and normative behavior live in
[`plan.md`](plan.md) and [`spec.md`](spec.md); the frontend equivalents live in
[`frontend/plan.md`](frontend/plan.md) and [`frontend/spec.md`](frontend/spec.md).

The pre-trim plan and its original review detail remain available at
`git show 5144c25:docs/plan.md`.

## Current v1 boundary

V1 contains a FastAPI backend and a working React frontend for authentication,
structured recipes, inventory, availability, cook/deduct history, grocery-list
generation and submit, and unit conversion. It includes backend and frontend
tests plus LAN operating documentation.

It does not contain uploads, outbound HTTP, OCR, migrations, meal planning, or
multi-household authorization.

## Post-v1 route (2026-09-05)

The working order for post-v1 work, decided in the
[post-v1-route wayfinding map](../.scratch/post-v1-route/map.md). This section
records **order only** — every track's detail stays in its own section below,
and nothing in this file was removed to make room for it.

| # | Track | What it is | Gate before it can be built |
| --- | --- | --- | --- |
| 1 | Private household deployment | [`spec.md`](../.scratch/private-household-deployment/spec.md), ready-for-agent | Verify the Tailscale → Windows → WSL network path on the target host |
| 2 | Friction pass | Edit-recipe entry point · create grocery list from a recipe · "what can we make now" | — |
| 3 | Recipe entry | URL import — the household's recipes come from websites | `recipe-scrapers` coverage; what happens when a site can't be scraped |
| 4 | Inventory upkeep | One of receipt OCR / staples / undo — which one is still open | Alembic, plus the choice itself |

Selection criteria were daily-use friction and durability/risk. Deployment
leads because no real household data exists yet, which makes both it and
Alembic cheapest right now, and because real use is the only way to replace
guesses about friction with evidence. Tracks 1–3 are all data-model-neutral, so
Alembic is an explicit gate in front of track 4 rather than a track of its own.

**Deliberately not on the route:** multi-household support and photo upload.
Both specifications below are unchanged and remain available; the map's
Out of scope section records why. Everything else in this file is catalogued
and unscheduled — not rejected.

## Standing constraints for future work

- Preserve one-way imports and the app-factory test seam.
- Keep live network and subprocess seams narrow and mocked in ordinary tests.
- Keep server-side inventory math canonical and auditable.
- Preserve raw source evidence when imports or OCR create editable records.
- Keep forward-only actions explicit and snapshot what was actually applied.
- Do not introduce an LLM or hosted AI dependency.

## Larger deferred capabilities

These five were once grouped as "v2". They no longer share a fate, so the
grouping is retained only as a size band — each has its own position on the
[post-v1 route](#post-v1-route-2026-09-05), and "v2" is not used as a release
label anywhere below.

| Feature | Hook already present in v1 | Route position | Why it was deferred |
|---|---|---|---|
| URL import | Active `recipe_ingredients.raw_text` and structured recipe creation | **Track 3** | Adds runtime HTTP, scraping, and an SSRF-sensitive fetch boundary |
| Grocery-receipt OCR | Inventory additive upsert is the apply target | Candidate for **track 4** — ticket 07 decides | Highest operational cost: native OCR, private files, image limits, and concurrency controls |
| Per-cook reviews | Durable `cook_logs` provide the attachment point | Unscheduled | Useful history, but not required to complete the cook/inventory loop |
| Recipe research | URL-import preview DTOs can be reused | Unscheduled | Depends on URL import and is exploratory rather than transactional |
| Photo upload | Nullable `recipes.photo_path` | **Off the route** — owner's decision, photos are not needed | Adds multipart handling, file lifecycle, and a static mount without strengthening the core loop |

The specifications below are execution-ready except for the explicit
**Before implementation** decisions attached to individual features. The archived pre-trim
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

**API shape decided 2026-09-05**, superseding the earlier `save`-flag design.
Sources: [ticket 10](../.scratch/post-v1-route/issues/10-import-endpoint-shape.md)
and the [`recipe-scrapers` findings](../.scratch/post-v1-route/research/recipe-scrapers.md).

- **Service `services/import_recipe.py` — `fetch_bytes(url, *, limit, allowed_types) -> bytes`:**
  the **only** network call, SSRF-guarded (#H1/#10b): HTTP(S) scheme allowlist;
  resolve host and reject private/loopback/link-local/ULA/multicast/`169.254.169.254`;
  `follow_redirects=False` (3xx → 502); `raise_for_status`; `Content-Type`
  allowlist; stream to a byte cap. `RECIPE_IMPORT_ALLOW_PRIVATE=true` re-opens
  it for a trusted LAN. Unchanged from the original spec.
- **Service — `scrape_preview(html, url) -> RecipeImportPreview`:** pure, and
  the parsing half of the split the library's own docs recommend.
  - **One** `scrape_html(html, org_url=url, supported_only=False)` call. It uses
    the dedicated scraper when the host is known and the generic schema.org path
    otherwise. There is **no two-pass "normal then wild mode" retry** — one call
    covers both, so the route no longer holds `html` for a retry (#10a retired).
  - **Do not pass `wild_mode=`.** It is deprecated in 15.x, and passing it
    together with `supported_only` raises `ValueError`.
  - **Every field accessor raises** when its field is absent
    (`SchemaOrgException`, `ElementNotFoundInHtml`, `OpenGraphException`,
    `StaticValueException`). Read each field under its own `try/except`, or set
    `recipe_scrapers.settings.SUPPRESS_EXCEPTIONS`. **A partial result is the
    normal shape of the return value, not an edge case.**
  - Use **`ingredient_groups()`**, not `ingredients()`, so a `For the sauce:`
    header never becomes a false ingredient. Flatten the groups to lines; the
    group `purpose` is a **deliberate loss** — the data model has no group
    concept and adding one is a schema change (see Alembic below).
  - **Retry the generic path when a dedicated scraper returns empty.**
    `scrape_html` dispatches once and never falls back, ~8% of scrapers break
    per year, and the library's CI runs offline fixtures only — so a break
    reaches users first. ~5 lines via `SchemaScraperFactory`.
- **Route:** `POST /api/recipes/import {url?, html?}` — **exactly one**; both or
  neither → 422. **Read-only: it never writes.** Returns 200
  `RecipeImportPreview`. The person corrects the preview, and the app saves it
  through the existing `POST /api/recipes`.
  - **Success = ingredients and steps present.** A missing title, `yields`,
    `total_time`, `ratings` or `author` is *not* a failure. Title is the most
    reliably extracted field (90.0% exact) and is easily typed when absent —
    note `RecipeCreate.title` has `min_length=1`, so the client must require one
    before saving.
  - No recipe found → 422 `unsupported: true` (`NoSchemaFoundInWildMode`,
    `WebsiteNotImplementedError` both map here).
  - Fetch failure → 502. **For 403/503 the message must say the site blocks
    automated access and to paste the page instead** — bot protection was 2 of
    20 live fetches, both on *supported* sites, and no parser can fix it.
- **DTO:** `RecipeImportPreview(RecipeCreate)` — `ingredients` is `list[str]`,
  the scraped lines verbatim. `source_url` is already a `RecipeBase` field, so
  provenance persists with no addition. Advisory fields (which fields were
  absent, the discarded group purposes for display) are safe to add:
  `RecipeCreate` does not set `extra="forbid"`, so the preview posts back
  unchanged.
  - **`ImportIngredient` is removed.** The earlier DTO (`RecipeIngredientIn` +
    `{raw_text, normalized_name}`) **could not be posted back** —
    `RecipeIngredientIn` carries `extra="forbid"`, the only schema in the API
    that does. Plain lines avoid it entirely, and §5.2's string-element path
    already populates `raw_text` and computes `normalized_name` server-side.
- **Deps:** `recipe-scrapers`, **pinned to an exact version** (Mealie pins
  15.12.0, Tandoor 15.11.0). Promote `httpx` from dev to runtime.
- **Config:** `import_max_bytes`, `import_fetch_timeout` (10s),
  `import_allow_private` (default false). `max_image_bytes` is **dropped** —
  nothing downloads an image now that import is read-only and photo upload is
  off the route.
- **Tests:** `test_import.py` via `httpx.MockTransport` — happy path from a
  saved fixture; pasted `html` with no `url`; both or neither → 422; no recipe
  found → 422; non-2xx / redirect / oversize / wrong content-type → 502;
  403 → 502 with the paste-instead message; blocked address
  (`169.254.169.254`, `localhost`) → 502 with no request issued; a page with no
  `total_time` still previews; ingredients absent → 422; a group header is not
  emitted as an ingredient; a preview posts to `POST /api/recipes` unchanged and
  stores `raw_text`. **Retire the "wild-mode retry" case** — there is no retry.
- **Data-model impact:** none. `recipes.source_url` and
  `recipe_ingredients.raw_text` are existing columns, so this track stays in
  front of the Alembic gate.
- **Known limitation:** pasting raw HTML is a desktop gesture (view-source,
  copy). On a phone it is awkward, and rendered page text cannot be parsed
  because the parser needs markup. Accepted for now; revisit if real use shows
  it biting.
- **Measured expectations** (1109 fixture pages, generic path only, scored
  against the dedicated scraper): a parseable recipe on 91.1%, non-empty
  ingredients on 87.7%, byte-identical ingredients on 75.9%. Supported hosts do
  better, because they use their dedicated scraper. Known failure population:
  newsletter/prose sources with no recipe markup, and bot-protected sites.
- **Before implementation (#R-def):** "stream to a byte cap" must be an actual streaming
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
  - **Amended 2026-09-05:** the preview now carries `ingredients` as plain
    lines, so `normalized_name` is no longer a field to read off it. This
    service calls `normalize_name` on each scraped line itself. The removed
    `ImportIngredient` DTO was the only thing that carried it, and computing it
    here is one call — see the URL-import section above.
- **Route `routers/research.py`:** `POST /api/research/compare {urls, limit?}`
  (`limit` capped at `settings.research_max_urls`; empty `urls` → 422). Reuses
  `fetch_bytes` + `scrape_preview`, so the whole batch inherits the SSRF guard
  (#H1). Per-URL fetch/parse failures collected in `failed`, not fatal. **No
  `query` / web-search mode** — Google Custom Search JSON API is closed to new
  customers and ends 2027-01-01 (#1); revisit with Vertex AI Search / Brave /
  Bing.
- **Before implementation (#R-def):** the *URL list itself* must be bounded, not only the
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
- **Before implementation (#R-def):** all review-read routes are recipe-scoped, so a review
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
- **Before implementation (#R-def):** (1) the non-mocked smoke test's `skipif` is
  **local-only** — under `CI` a missing `tesseract` binary is a hard failure, so
  a broken install can't ship green. (2) Upload/OCR failure cleanup is explicit:
  stage the image in a temp file, and on any OCR timeout or DB error either
  delete it or persist a visible `status=failed` draft with retry semantics —
  never leave an orphaned receipt image (it is PII).
- *full spec: git 5144c25 §"apply a receipt", §"Grocery receipt → stock"
  done-criterion, findings #5 #11 #12 #17.*

### Recipe research — free-text `query` mode (after URL-batch research lands)

- **v1 status:** excluded; the whole research feature is unscheduled.
- **Planned shape:** `/api/research/compare` ships URL-batch only.
- **Hook (arrives with URL import, route track 3):** `fetch_bytes(url, ...)` —
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
| Edit recipes | Partially shipped; edit form exists but has no discoverable entry point | `/recipes/:id/edit`, the pre-filled `RecipeForm`, and PUT full-replace behavior already work | Add an "Edit recipe" action to Recipe Detail and cover navigation, responsive layout, and accessibility |
| Create grocery list from a recipe | Requested | Existing grocery-list generation and inventory availability | Add a "Create grocery list" button to Recipe Detail that creates a new list containing only what is still needed for that recipe |
| Explain grocery-list contents on creation | Requested | Existing grocery-list generation and inventory availability | Show which ingredients will be added or left out, with quantities and reasons, so a partial recipe list is understandable |
| Preparation-descriptor ingredient matching | Limited; leading descriptors match, trailing descriptors do not | `normalize_name`, editable inventory `match_name`, and shared inventory-math consumers | Define safe preparation-word equivalence so `onion, diced` can match inventory `onion`, then apply it consistently to availability, grocery generation, and cook deductions |
| "What can we make now" | Excluded | `check_availability` exists; runs on one recipe | `GET /api/recipes/makeable` — run it across all, filter `all_available` |
| Staples / low-stock alerts | Excluded | `inventory_items` row structure | `is_staple: bool` + `min_quantity: float` columns; `GET /api/inventory/low` |
| Undo for forward-only actions | Excluded | `CookLog.deductions` (requested/deducted/before/after) and `GroceryListItem.applied_quantity/unit` snapshot what was applied; `ReceiptItem.applied_quantity/unit` joins them once receipt OCR lands | One uniform reverse-apply op across cook + grocery (+ receipt, if receipt OCR lands); no per-action `/undo` route until designed |
| Frontend support for deferred features | Core v1 frontend shipped | Working React SPA, authenticated API adapters, routing, and hand-maintained API types | Add UI for photo and URL import, reviews, receipt OCR, and recipe research as their backend features land; see below |
| Multi-line ingredient paste | Excluded; caller pre-splits | §5.2 per-line ingredient build; `parse_ingredient` per line | Server-side split of a pasted block on `\n` (blank/header/bullet handling) before the existing per-line build; `issues.md` §Deferred item D2 |
| Availability / grocery uncertainty naming | v1 ships `AvailabilityStatus="have_uncertain"` and a negated `nettable` bool | `check_availability` / `generate_lines` set both; locked oracle tables in §7 | Investigate renaming to a positively-phrased `units_comparable` / `incomparable_units`, and a status enum on grocery lines for parity; raised by the frontend track (`frontend/decisions.md` §Q19 follow-up) — no user-facing effect, frontend copy already covers it |
| Display-unit conversion on output | Excluded; every response is canonical-unit | `inventory_items.display_unit` already stores a per-row preference; `units.from_base` already converts | Apply a display preference when serializing availability / grocery / cook-log quantities, or accept a `?units=` request parameter; see below |

### Edit recipes

- **Current behavior:** the frontend already has a pre-filled edit form at
  `/recipes/:id/edit`. Saving uses the backend's `PUT /api/recipes/{id}`
  full-replace contract, including removal and reordering of ingredients and
  steps.
- **User-facing gap:** Recipe Detail exposes "Delete recipe" but no visible
  "Edit recipe" action. Editing is therefore implemented but not discoverable
  through the normal interface.
- **Work to add:** put a clearly labelled, keyboard-accessible edit action in the
  Recipe Detail header that navigates with client-side routing. Keep it usable
  beside the destructive action at mobile and desktop widths. Add a focused
  Recipe Detail test; no backend, API-adapter, or RecipeForm behavior change is
  needed.
- **When to revisit:** the next frontend usability pass.

### Create grocery list from a recipe

- **Feature request:** add a "Create grocery list" button to the recipe page.
  Clicking it creates a new grocery list scoped to that recipe and opens the
  resulting list.
- **Contents:** use the recipe's selected multiplier (default `1`) and existing
  grocery-generation rules to subtract available inventory. Include only missing
  ingredients or shortfall quantities; preserve existing uncertainty handling
  when quantities or units cannot be compared.
- **Empty result:** if everything is already available, show that no groceries
  are needed instead of creating an empty list.
- **Interaction:** disable the button while creation is in progress to prevent
  duplicate lists, and show a recoverable error if creation fails.

### Explain grocery-list contents on creation

- **Problem:** adding a recipe can produce a grocery list with only some of its
  ingredients, making it look as though ingredients were silently lost.
- **Feature request:** show a clear notice or summary during grocery-list
  creation explaining which ingredients will be added and why. Include the
  ingredients left out and their reasons as well. Apply this to the general
  creation flow and the recipe-page shortcut.
- **Details:** show the amount to buy and whether an ingredient is missing or
  only partly stocked; explain omissions when inventory already covers the
  requirement. For example: "Flour: add 100 g — recipe needs 300 g, you have
  200 g" and "Eggs: not added — you have enough."
- **Uncertainty and empty results:** explain how ingredients with unknown
  quantities or incomparable units are handled, using the actual generation
  result without claiming they are covered by inventory. If nothing needs to
  be added, explicitly say why. Keep the details available long enough to read
  rather than relying only on a disappearing toast.
- **Constraint:** derive the explanation from the same server-side calculation
  that determines list contents so the summary and resulting list agree.

### Preparation-descriptor ingredient matching

- **Current behavior:** recipe `normalized_name` must exactly equal inventory
  `match_name` within a compatible unit bucket. `normalize_name` strips known
  descriptors only when they lead the name, so `diced onion` matches `onion`,
  while `onion, diced` becomes `onion diced` and does not.
- **Desired behavior:** preparation wording should not prevent safe matches to
  the underlying food. The motivating case is a recipe ingredient such as
  `onion, diced` matching an inventory item whose `match_name` is `onion`.
- **Before implementation:** decide which comma suffixes, parentheticals, and
  plain trailing words are equivalent; distinguish preparation descriptors from
  identity-bearing words such as `ground`, `dried`, `smoked`, and `canned`; and
  choose whether to extend normalization, produce candidate keys, or introduce
  aliases through the deferred `FoodItem` model.
- **Work to add:** lock both match and deliberate non-match examples in the
  normalization and inventory-math tests first. Apply the chosen semantics
  consistently to availability checks, grocery generation, and cook deductions,
  while preserving the ingredient's original display text.
- **When to revisit:** when real recipes need repeated manual `match_name`
  corrections, or as part of the `FoodItem` canonical-identity upgrade below.

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
  uncheck-reversal, no unsubmit, no uncook). Receipt `apply` joins them if
  receipt OCR lands.
- **Hook in v1:** Each already snapshots the actual applied state:
  - `CookLog.deductions[]` → each item records `{requested, deducted, before,
    after, reason}`.
  - `GroceryListItem.applied_quantity`, `applied_unit`, `submitted_at`.
  - (with receipt OCR) `ReceiptItem.applied_quantity`, `applied_unit`.
- **Work to add:** One uniform reverse operation across all of them. Data is
  present to undo: add back the `deducted`/`applied_quantity` to the respective
  inventory row. Design as a single feature, not separate routes. Consider a
  mutation-event audit trail (who reversed it, when) before implementing.

### Frontend support for deferred features

- **v1 status:** shipped. The React SPA works against the v1 API and includes
  authentication, guarded routing, recipes, inventory and availability,
  cook/history workflows, grocery lists, typed API adapters, tests, and a
  production build.
- **Contract constraint:** backend Pydantic schema changes must be hand-mirrored
  in `frontend/src/types.ts`; do not introduce generated client types.
- **Work to add as the corresponding backend features land:**
  - an import screen for URL import (**track 3**) — a preview the person
    corrects, then saves through the existing recipe-create adapter; see
    § URL import above and ticket 09 for the screen itself;
  - a review form and nested past reviews in RecipeDetail;
  - ReceiptUpload (photo → OCR preview → edit → apply);
  - Research (URL batch → ingredient-frequency table); and
  - `/receipts` and `/research` routes.

  Photo-upload controls and a Vite `/uploads` proxy were previously listed here
  and are removed: photo upload is off the route.
- **Tests:** cover each new API adapter and user workflow with the existing
  Vitest/MSW patterns, plus focused browser integration coverage where needed.

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

- **Feature request — match availability to the recipe unit:** when showing an
  ingredient's availability, attempt to express the available quantity in the
  unit used by that recipe ingredient, so the required and available amounts
  are easy to compare. For example, a recipe requiring `2 cups` of stock should
  show compatible inventory availability in `cups` rather than `ml`. Convert
  only when supported; otherwise retain the existing unit and uncertainty
  behavior without guessing a conversion between incompatible units. Keep
  stored quantities and availability calculations canonical.
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
- **When to revisit:** during a frontend output-formatting pass, where the
  display preference and copy can be evaluated together. No timeline.

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

### Deployment direction (2026-09-05)

- The initial deployment is for private household use from away from home.
- A future public service would serve entirely separate households, with no
  cross-household relationships or sharing. See
  [ADR 0001](adr/0001-independent-households.md).
- Initial remote access will use private Tailscale access, with Tailscale
  installed on household devices. The host is an existing Windows machine
  running WSL.
- Ordinary browser access without a private-network client remains the later
  preference.
- Hosting around $5/month later is acceptable; no provider is selected.
- Current work focuses only on the owner's household deployment. Implementing
  multiple-household support and deciding overlapping membership are deferred
  until multiple households are introduced.
- Household members will have individual logins with equal editing access;
  registration closes after setup and the operator handles password recovery.
- Up to 24 hours of lost changes and one day to restore service are acceptable.
  Backups stay on the local disk for now; a better backup destination is
  deferred until public deployment. These backups do not cover disk loss.
- See the [private deployment outline](deployment.md) and the
  [ready-for-agent deployment spec](../.scratch/private-household-deployment/spec.md).
  The spec owns implementation scope and acceptance checks, including the
  confirmed browser/real-backend test approach and actual-host verification.

### Remote deployment exploration (informational, 2026-09-04)

These are high-level findings and options, **not decisions, committed scope,
or an implementation schedule**. No hosting provider, session redesign, or
ordering relative to v2 has been selected. Provider prices and free-tier limits
below were checked on 2026-09-04 and should be rechecked before choosing a host.
This is a dated snapshot, so its "v2" references are preserved as written even
though the label is no longer used elsewhere in this file.

#### Scope and likely effort

- **Private household access from anywhere:** keep the shared-household model
  and closed registration. The existing React/FastAPI architecture can stay;
  most work would be targeted application changes and deployment setup.
- **Open signup for unrelated households:** substantially more work. All
  authenticated users currently share read/write access to all data;
  `created_by_id` is attribution, not authorization. Separate households would
  need memberships, household ownership and uniqueness rules, scoped reads and
  writes across all workflows, and cross-household isolation tests. Roles
  within one household alone would not provide this isolation. Public signup
  would also need account onboarding, recovery, and deletion flows.
- **Existing extension points:** centralized backend authentication, one
  frontend API client, centralized database setup, and the app factory/test
  seam make private deployment feasible without a broad business-logic refactor.
- **SQLite remains an option:** internet access alone does not require Postgres.
  Keep the database on persistent local storage. The current `BEGIN IMMEDIATE`
  transaction strategy serializes database transactions and would need review
  as concurrency grows; switching databases is more than a URL change.
  See [SQLite's deployment guidance](https://www.sqlite.org/whentouse.html).

#### Potential work for a private web deployment

| Area | High-level change | Likely impact |
| --- | --- | --- |
| Data durability | Establish migrations that preserve the existing database; persistent storage; automated backups and a tested restore procedure | Moderate migration setup, mostly operational work for storage/backups |
| Session storage | Store token digests instead of raw tokens; choose an existing-session rollout policy | Localized backend change; see hashed-token discussion below |
| Browser authentication | Consider `Secure`, `HttpOnly`, `SameSite` session cookies with appropriate CSRF protection instead of tokens in `localStorage` | Coordinated backend auth, frontend client/session handling, and auth-test changes |
| Abuse controls | Login/registration rate limits and request-size limits | Targeted proxy or application changes |
| Account usability | Keep registration closed; add a password-change screen using the existing API | Small frontend addition; decide how household account recovery would be operated |
| Production serving | Build the frontend; serve frontend routes and `/api` under one HTTPS origin; configure trusted proxy handling | Mostly deployment configuration, with static serving and SPA route fallback to add |
| Operations | Automatic restarts, production settings/secrets, health monitoring, error reporting, repeatable deployment and rollback | Mostly configuration; existing CI already tests and builds |

Cookie sessions and adopting migrations with existing data deserve the most
care; neither inherently requires refactoring recipe, inventory, or grocery
business logic. Cookie handling would need to preserve expiry, logout, and
password-change revocation behavior. See
[OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
and [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/).

One possible package is the built React frontend and FastAPI backend in a
single service, with SQLite on a persistent volume. This gives one URL and one
deployment. The current Vite `/api` proxy only supplies development routing.

#### Timing relative to v2 — suggested sequence, not adopted

An option discussed was **migrations/backups → authentication hardening →
private web deployment → larger v2 features**. The rationale is to preserve
real data before schema changes and establish operations before uploads,
outbound URL imports, or OCR add storage, access-control, external-request,
and processing concerns. Small UI improvements could proceed alongside this.
Migrations and backups would still be useful before data-changing v2 work even
if remote deployment is postponed.

A possible readiness milestone: use the app away from home, deploy an update
without losing data, and recover from a failed deployment. Private access via
Tailscale is a separate option with a different exposure model from a public
HTTPS endpoint.

#### Hosting options and free-tier tradeoffs

| Option | Cost/limits checked on 2026-09-04 | Fit and tradeoffs |
| --- | --- | --- |
| Railway | Hobby has a $5/month minimum including $5 of resource usage; excess usage costs extra. Free includes $1/month of resources after the initial trial and a 0.5 GB persistent volume | Candidate for straightforward cloud hosting while retaining SQLite. Free usage may not cover continuous operation; measure actual consumption. [Pricing](https://railway.com/pricing), [volumes](https://docs.railway.com/volumes/reference) |
| Render paid service + persistent disk | Paid compute plus disk charges; persistent disks require a paid service | Another managed-hosting candidate that can retain SQLite. [Persistent disks](https://render.com/docs/disks) |
| Existing home computer + Tailscale | Personal plan is free for up to six users; hardware, electricity, and home internet are separate | Candidate for free household remote access if an always-on computer is available. Household devices connect through Tailscale; availability depends on the home machine and connection. This provides private access rather than an ordinary publicly reachable website. [Free plan](https://tailscale.com/docs/reference/free-plans-discounts) |
| Oracle Cloud Always Free VM | Free within eligible compute/storage limits; idle instances may be reclaimed | Can host the whole app with persistent SQLite, but requires Linux administration, updates, HTTPS setup, and backups. Reclamation is relevant to a lightly used household app. [Limits and conditions](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) |

**Free-hosting storage caveat:** Render's free web service has no persistent
disk and loses local files, including SQLite, on restart, redeploy, or idle
shutdown. Its free Postgres database expires after 30 days. It is a demo option,
not a durable home for the current SQLite app.
See [Render's free-tier limitations](https://render.com/docs/free).

The preliminary shortlist was Railway for convenient cloud hosting, Tailscale
for free household access on existing hardware, and Oracle for free cloud
compute if server administration and free-tier limitations are acceptable.
This is comparison information only; no provider is selected.

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
  docs at `/docs` (no auth). v1 serves no files at all. Photo upload is off
  the route, so nothing is served at `/uploads`; were it ever built, recipe
  photos would be public there (LAN-safe, not sensitive) while receipt images
  stay private behind an auth'd route.
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
  lands).
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

3. **No LLM / AI services.** When research and receipt parsing land, they
   stay pure heuristics. If a future feature wants an LLM (e.g., "suggest recipes
   based on inventory"), it is out of scope for this app's ethos; discuss with
   the household before considering it.

4. **No live network in tests.** v1 has no outbound calls. When `fetch_bytes`
   (URL import + research) and `_ocr_image` (receipt OCR) arrive, they are
   the only network/subprocess seams, and both must be mocked offline. New
   network calls follow the same pattern.

5. **`frontend/src/types.ts` stays hand-maintained.** It mirrors the backend
   Pydantic schemas. Do not auto-generate it. When the API changes, update
   `types.ts` manually — it keeps the frontend author aware of contract changes.

6. **Forward-only writes stay forward-only.** Cook and grocery `submit` (v1),
   and receipt `apply` (if built), do not unwind. Until undo is designed as one
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
| Any web-search SDK bundled into the app | Research ships URL-batch only; `query` mode is deferred and unscheduled. If a web-search service is added later (e.g., Brave Search SDK), add it as a *new* feature, not a bundled dependency. |
