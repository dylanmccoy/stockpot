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
- v1 excludes: meal planning; web recipe search; "what can we make now"; staples
  / low-stock alerts. The data model must not preclude them (see Deferred).

## Done criteria

**Plan is approved** when this file specifies the data model, module layout,
unit-conversion rules, the netting/deduction algorithms, the auth mechanism, the
import mechanism, dependencies, and the phased build sequence — all below.

**Backend v1 is done** when, verified through `/docs` and `uv run pytest`:

1. **Auth.** A user can register (while registration is enabled) and log in,
   receiving a bearer token. Every data endpoint except `/api/health` and the
   public auth routes returns 401 without a valid token.
2. **Structured recipes.** `POST/PUT /api/recipes` accept nested ingredient rows
   (`quantity` nullable, `unit` nullable, `item`, `note`), ordered `steps`,
   `tags`, `cuisine`, `prep_time`, `cook_time`, `servings`, `source_url`,
   `notes`. `GET` returns them nested and ordered. PUT fully replaces nested rows.
   `normalized_name` is computed server-side on every ingredient.
3. **Photo.** `POST /api/recipes/{id}/photo` stores one image under the uploads
   dir and records its relative path; it is served at `/uploads/...`. Wrong
   content-type and oversize are rejected.
4. **Inventory.** `/api/inventory` supports list / add / edit / remove of
   `{item, quantity ≥ 0, unit}` items, one row per normalized food name.
5. **Missing-ingredient check.** `GET /api/recipes/{id}/availability?multiplier=M`
   returns per-ingredient `status` in
   `{ok, short, missing, to_taste, have_uncertain}` with unit conversion applied
   when units are compatible and an explicit uncertain state otherwise, plus an
   `all_available` flag.
6. **Cook deducts stock.** `POST /api/recipes/{id}/cook {multiplier}` subtracts
   ingredients from inventory (converting units, clamping at 0, skipping
   unmatched), and writes an auditable `CookLog` row.
7. **Grocery list.** `POST /api/grocery {recipe_ids, multipliers?}` creates a
   persisted list whose lines are consolidated requirements across the selected
   recipes minus current stock; only shortfalls appear; unit-incompatible lines
   are flagged `nettable=false`, not dropped. Manual one-off items can be added.
   `PATCH` on a line toggles `checked`; checking a line with a quantity adds it
   to inventory (idempotent; unchecking reverses).
8. **Unit conversion** is a standalone pure module with a documented supported-
   unit set and defined behavior for unknown / incompatible pairs.
9. **URL import.** `POST /api/recipes/import {url, save?}` fetches via our own
   `httpx` call, parses with `recipe-scrapers`, and returns a structured recipe
   preview (ingredient strings parsed into rows where possible); unsupported
   sites return 422 with `unsupported: true`; fetch failures return 502. No test
   hits the network.
10. **Tests green.** `uv run pytest` passes: units, ingredient parser, inventory
    math, auth gating, recipe CRUD with nested rows, availability, cook,
    inventory CRUD, grocery generation + check-off, import (fetch monkeypatched).
11. **Docs.** `README.md`, `CLAUDE.md`, `backend/.env.example` updated for the
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
| **inventory_items** | `id` PK · `item` str(200) display · `normalized_name` str(200) **unique** indexed (add = upsert) · `quantity` float ≥0 default 0 · `unit` str(30)? · `updated_at` · `created_by_id` FK users? |
| **grocery_lists** | `id` PK · `name` str(200) default `"Groceries <date>"` · `status` str(20) `active`/`archived` · `source_recipe_ids` JSON `list[int]`=[] (informational, no FK) · `created_at` · `created_by_id` FK users? |
| **grocery_list_items** | `id` PK · `grocery_list_id` FK CASCADE · `item` str(200) · `normalized_name` str(200) indexed · `quantity` float? (null = to taste/manual) · `unit` str(30)? · `checked` bool=false · `checked_at` dt? · `source` str(20) `generated`/`manual` · `nettable` bool=true · `added_to_inventory` bool=false (idempotency guard) |
| **cook_logs** | `id` PK · `recipe_id` FK recipes SET NULL · `recipe_title` str(200) snapshot · `multiplier` float=1 · `cooked_at` · `cooked_by_id` FK users? · `deductions` JSON=[] (`[{item, normalized_name, quantity, unit, applied, reason}]`) |

Relationships: `Recipe.ingredients` → ordered by `position`,
`cascade="all, delete-orphan"`; read paths use `selectinload(Recipe.ingredients)`.
`GroceryList.items` cascade. Users are never deleted in v1 (nullable
`created_by_id`, no cascade).

**Design choices (recommended, decisive):**
- Steps/tags/`source_recipe_ids`/`deductions` are **JSON columns** — never queried
  individually. Ingredients get a **child table** — queried and matched.
- **No `FoodItem` table in v1.** Matching is `normalized_name` string equality on
  both sides. Upgrade path: add `FoodItem` + nullable FKs + backfill by
  `normalized_name`.
- `inventory_items.normalized_name` is **unique** → "add to stock" is a clean
  upsert. Upgrade path if "flour in bags" vs "flour in grams" ever matters: drop
  unique, add per-row merge.

**`backend/app/normalize.py`** (pure, no dep): `normalize_name(raw)` = strip →
lower → drop punctuation (keep spaces/hyphens) → collapse whitespace → naive
singularize (irregular map `{tomatoes→tomato, potatoes→potato, leaves→leaf, …}`,
then `-ies→-y`, `-ses/-xes/-oes→ -e`, trailing `-s` → drop). False matches are
acceptable at 2-user scale; no `inflect` dependency.

## Module / router layout (`backend/app/`)

```
config.py     + upload_dir, max_upload_bytes, allow_registration, session_ttl_days, registration_code?
database.py   unchanged
normalize.py  normalize_name()                                   [pure]
units.py      unit table + conversions                           [pure, no deps]
security.py   hash/verify_password (pwdlib), issue_token, get_current_user dep, CurrentUser alias
models.py     all tables
schemas/      package: common.py, auth.py, recipe.py, inventory.py, grocery.py  (__init__ re-exports)
services/
  ingredient_parse.py   parse_ingredient(text) -> row dict       [pure]
  import_recipe.py      _fetch_and_scrape(url)  [only network fn], map_to_preview(scraper, url)
  inventory_math.py     check_availability, generate_lines, add_to_inventory_calc, deduct_calc  [pure, dataclasses in/out]
routers/
  auth.py       /api/auth      register, login, logout, me
  recipes.py    /api/recipes   CRUD + /import + /{id}/photo + /{id}/availability + /{id}/cook
  inventory.py  /api/inventory  CRUD
  grocery.py    /api/grocery    lists + items + check-off
main.py       include 4 routers; mount /uploads StaticFiles; keep /api/health; os.makedirs(upload_dir) in lifespan
```

**Rule (documented in CLAUDE.md):** `services/` functions take/return plain
dataclasses or dicts, **never ORM objects**; routers marshal ORM ↔ dataclass.
That is the unit-test seam. `services/inventory_math.py` imports only `units`,
`normalize`, stdlib.

**Auth gating:** every router is
`APIRouter(..., dependencies=[Depends(get_current_user)])` except `auth`
(register/login public; logout/me protected) and inline `/api/health`. The
`/uploads` StaticFiles mount is unauthenticated — acceptable on LAN, noted in
docs; swap to an auth'd `FileResponse` route if it ever matters.

## Unit conversion — `backend/app/units.py` (pure Python, no `pint`)

Dimensions: `MASS` (base **g**), `VOLUME` (base **ml**), `COUNT` (base **unit**).

Static synonym table `str → (Dimension, factor_to_base)`:
- **mass:** g/gram(s) 1 · kg 1000 · mg 0.001 · oz/ounce 28.3495 · lb/lbs/pound(s) 453.592
- **volume:** ml 1 · l/litre/liter 1000 · tsp/teaspoon 4.92892 · tbsp/tablespoon 14.7868 · cup(s) 236.588 · fl-oz 29.5735 · pint 473.176 · quart 946.353 · gallon 3785.41
- **count:** unit/each/"" 1 · dozen 12 · pair 2 · clove/slice/piece/stick/can/package/pkg/jar 1 (informal 1:1 with "each")
- **left UNKNOWN on purpose** (→ non-nettable): head, bulb, bunch, sprig, pinch, handful, dash, splash, "to taste". Documented tuning knob.

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
```
for ing in recipe.ingredients (ordered):
    if ing.quantity is None:                 -> line(status="to_taste"); continue
    need  = ing.quantity * M
    stock = inventory_by_norm.get(ing.normalized_name)
    if stock is None:                         -> line(need, have=0, short=need, status="missing"); continue
    nb, sb = to_base(need, ing.unit), to_base(stock.quantity, stock.unit)
    if nb is None or sb is None or nb.dim != sb.dim:
        -> line(need, have=stock.quantity, status="have_uncertain", nettable=false); continue
    short_base = nb.amt - sb.amt
    -> line(status="ok", have=stock.quantity) if short_base <= 0
       else line(need, have=stock.quantity, short=from_base(short_base, nb.dim, ing.unit), status="short")
report.all_available = no line in {missing, short}
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
        stock = inventory_by_norm.get(norm)
        if stock is None:
            need, nettable = q, (q.amount is not None and (q.unit is None or parse_unit(q.unit) is not None))
        else:
            nb, sb = to_base(q.amount, q.unit), to_base(stock.quantity, stock.unit)
            if q.amount is None or nb is None or sb is None or nb.dim != sb.dim:
                need, nettable = q, false
            else:
                short = nb.amt - sb.amt
                if short <= 0: continue                          # fully in stock -> no line
                need, nettable = Quantity(from_base(short, nb.dim, q.unit), q.unit), true
        items.append(GLItem(item=r.display_item, normalized_name=norm,
                            quantity=need.amount, unit=need.unit, nettable=nettable, source="generated"))
    if r.to_taste and norm not already emitted:
        items.append(GLItem(item=r.display_item, quantity=None, unit=None, nettable=false, source="generated"))
persist GroceryList(name or default, source_recipe_ids=recipe_ids, items=items)
```
Consolidation across recipes = keying `reqs` by `normalized_name`.

### check off a grocery line — `PATCH /api/grocery/{list}/items/{id} {checked}`
```
item.checked = checked
if checked and not item.added_to_inventory:
    if item.quantity is not None: add_to_inventory(item.normalized_name, item.item, item.quantity, item.unit)
    item.added_to_inventory = true;  item.checked_at = now
elif not checked and item.added_to_inventory:                    # reverse -> idempotent both ways
    if item.quantity is not None: add_to_inventory(item.normalized_name, item.item, -item.quantity, item.unit)
    item.added_to_inventory = false; item.checked_at = null
```

### add_to_inventory(norm, display, amount, unit)
```
row = inventory.get_by_norm(norm)
if row is None:
    insert InventoryItem(item=display, normalized_name=norm, quantity=max(amount,0), unit=unit); return
nb, cb = to_base(amount, unit), to_base(row.quantity, row.unit)
if nb and cb and nb.dim == cb.dim: row.quantity = from_base(cb.amt + nb.amt, cb.dim, row.unit)  # keep display unit
elif row.unit == unit or (row.unit is None and unit is None):    row.quantity += amount
else:                                                            row.quantity += amount          # best-effort
row.quantity = max(row.quantity, 0); row.updated_at = now
```

### mark as cooked — `POST /api/recipes/{id}/cook {multiplier}`
```
log = CookLog(recipe_id, recipe_title=recipe.title, multiplier=M, cooked_by=user)
for ing in recipe.ingredients:
    if ing.quantity is None: log.deductions += {item, applied:false, reason:"to taste"}; continue
    need = ing.quantity * M;  row = inventory.get_by_norm(ing.normalized_name)
    if row is None: log.deductions += {..., applied:false, reason:"not in inventory"}; continue
    nb, hb = to_base(need, ing.unit), to_base(row.quantity, row.unit)
    if nb and hb and nb.dim == hb.dim:
        row.quantity = max(from_base(hb.amt - nb.amt, nb.dim, row.unit), 0)
        applied, reason = true, ("ok" if hb.amt >= nb.amt else "clamped to 0")
    elif row.unit == ing.unit or (row.unit is None and ing.unit is None):
        row.quantity = max(row.quantity - need, 0); applied, reason = true, "ok"
    else:
        applied, reason = false, "unit mismatch"
    row.updated_at = now
    log.deductions += {item, normalized_name, quantity:need, unit:ing.unit, applied, reason}
save(log)
```
Cook is intentionally lossy (clamp at 0, skip mismatches); `deductions` JSON makes
a future "undo" = `add_to_inventory` for each `applied` entry.

## Auth approach

- **Hashing:** `pwdlib[argon2]` (`hash_password`/`verify_password` in
  `security.py`). Dummy-verify on unknown username to blunt timing enumeration.
- **Sessions:** opaque `secrets.token_urlsafe(32)` in the `sessions` table, TTL
  `RECIPE_SESSION_TTL_DAYS` (default 30). No JWT, no signing secret to manage.
  `get_current_user(authorization: str = Header(...))` parses `Bearer <token>`,
  looks up a non-expired row, bumps `last_used_at`, else 401.
  `CurrentUser = Annotated[User, Depends(get_current_user)]`.
- **Registration:** open endpoint, permitted only while
  `RECIPE_ALLOW_REGISTRATION=true` (default). Household registers both accounts,
  then sets it `false` in `.env`. Optional `RECIPE_REGISTRATION_CODE` documented
  as an alternative.
- **Endpoints (`/api/auth`):** `POST /register {username,password}` → 201
  `{token,user}` (409 dup / 403 disabled / 422 short pw); `POST /login` (JSON,
  not OAuth2 form, to keep the fetch wrapper uniform) → `{token,user}` (401);
  `POST /logout` → 204 (deletes the row); `GET /me` → `UserRead`.
- **CORS:** no code change (token is a header, not a cookie; `allow_headers=["*"]`
  already passes it). For LAN hosting, add the server origin to
  `RECIPE_CORS_ORIGINS` or set `["*"]` (safe — not credentialed). Doc note only.

## URL import approach

`services/import_recipe.py`:
```
def _fetch_and_scrape(url):                         # the ONLY network call; monkeypatched in tests
    html = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": ...}).text
    return scrape_html(html, org_url=url)           # recipe_scrapers

def map_to_preview(scraper, url) -> RecipeImportPreview:
    title = safe(scraper.title)
    cook  = safe(scraper.total_time)                # -> cook_time; prep_time stays None
    serv  = parse_yields(safe(scraper.yields))      # "4 servings" -> 4.0
    steps = safe(scraper.instructions_list) or (safe(scraper.instructions) or "").split("\n")   # drop blanks
    raws  = flatten(safe(scraper.ingredient_groups)) or safe(scraper.ingredients) or []
    ings  = [parse_ingredient(s) for s in raws]
    return preview(title, cook_time=cook, servings=serv, steps=[...], ingredients=ings,
                   source_url=url, remote_image_url=safe(scraper.image),
                   cuisine=safe(scraper.cuisine), tags=[], unsupported=False, warnings=[...])
```
Route `POST /api/recipes/import {url, save: bool = false}`:
- `try _fetch_and_scrape`; on any `recipe_scrapers` failure retry
  `scrape_html(html, org_url, wild_mode=True)`; still failing → **422**
  `{detail:"Could not parse this site", unsupported:true}`.
- `httpx` transport error → **502** `{detail:"Could not fetch URL"}`.
- `save=false` (default) → **200** `RecipeImportPreview` (frontend loads it into
  the form later). `save=true` → create the Recipe, download `remote_image_url`
  into `uploads/` via the photo code (failure leaves `photo_path` null) → **201**
  `RecipeRead`.

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
  image download (timeout/size control, offline-testable).

**Not added:** `pint` (units are a bounded pure-Python set) · `python-jose`/`pyjwt`
(opaque tokens) · `passlib` (using `pwdlib`) · `alembic` (staying on
`create_all`) · `inflect` (naive singularize).

**Backend dev:** none — `test_import.py` monkeypatches `_fetch_and_scrape`.

**Frontend:** `react-router-dom` (confirmed) — added during the later frontend
effort, not v1.

## Schema management

Stay on `create_all`:
- lifespan keeps `Base.metadata.create_all(bind=engine)` and adds
  `os.makedirs(settings.upload_dir, exist_ok=True)`.
- `create_all` won't ALTER the stale `recipes` table → **delete
  `backend/recipe.db`** in Phase 0 and again after the schema-expanding phases.
- `.gitignore` += `uploads/` (already ignores `*.db`).
- Document in README + CLAUDE.md: "No migrations. After a model change:
  `rm backend/recipe.db` and restart; local data is lost."

**Cost of Alembic now (rejected):** +dep, `alembic/` + `env.py` wired to
`Base.metadata` / `settings.database_url` + `alembic.ini`, `--autogenerate` +
review per change (SQLite needs batch mode; autogen misses some), a new CI step.
Buys zero data loss + a real upgrade path. Revisit at the first schema change
*after* the household has recipes worth keeping.

## Schemas (`backend/app/schemas/` package)

- `common.py` — `UserMini {id, username}`.
- `auth.py` — `RegisterRequest {username 3..50 regex, password 8..128}`,
  `LoginRequest`, `TokenResponse {token, user: UserRead}`,
  `UserRead {id, username, created_at}`.
- `recipe.py`:
  - `RecipeIngredientIn {quantity: float|None, unit: str|None ≤30, item: str 1..200, note: str|None}`
    — no `position` (array index), no `normalized_name` (server-computed).
  - `RecipeIngredientRead` adds `{id, position, normalized_name}`.
  - `RecipeBase {title 1..200, notes="", prep_time ≥0|None, cook_time ≥0|None,
    servings >0|None, cuisine|None, source_url|None, tags: list[str]=[],
    steps: list[str]=[]}`.
  - `RecipeCreate` / `RecipeUpdate` = `RecipeBase` + `ingredients:
    list[RecipeIngredientIn] = []` — **PUT fully replaces** nested rows.
  - `RecipeRead` = `RecipeBase` + `{id, created_at, updated_at, photo_path,
    created_by: UserMini|None, ingredients: list[RecipeIngredientRead]}`.
  - `RecipeImportPreview` = `RecipeCreate` shape + `{source_url, remote_image_url:
    str|None, unsupported: bool, warnings: list[str]}`.
  - `AvailabilityLine {ingredient_id, item, need: float|None, need_unit,
    have: float|None, have_unit, short: float|None,
    status: Literal["ok","short","missing","to_taste","have_uncertain"],
    nettable: bool}`; `AvailabilityReport {recipe_id, multiplier, lines,
    all_available}`.
  - `CookRequest {multiplier: float = 1 (>0)}`;
    `CookLogRead {id, recipe_id, recipe_title, multiplier, cooked_at,
    cooked_by: UserMini|None, deductions: list[dict]}`.
- `inventory.py` — `InventoryItemIn {item, quantity: float ≥0, unit: str|None}`;
  `InventoryItemRead` adds `{id, normalized_name, updated_at}`.
- `grocery.py` — `GroceryListCreate {name: str|None, recipe_ids: list[int],
  multipliers: dict[int, float] = {}}`;
  `GroceryListItemIn {item, quantity: float|None, unit: str|None}`;
  `GroceryListItemUpdate {checked: bool|None, quantity, unit, item}`;
  `GroceryListItemRead {id, item, normalized_name, quantity, unit, checked,
  checked_at, source, nettable, added_to_inventory}`;
  `GroceryListRead {id, name, status, source_recipe_ids, created_at, created_by,
  items}`.

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

**`conftest.py` is the load-bearing change.** Keep the in-memory `StaticPool`
engine + `create_all`/`drop_all` + `dependency_overrides[get_db]`. Add:
- an autouse fixture pointing `RECIPE_UPLOAD_DIR` at a `tmp_path_factory` dir
  **before app import** (StaticFiles reads `directory` at mount time) — or
  monkeypatch `settings.upload_dir` + the import service. Note this wrinkle.
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
- `test_inventory_math.py` — pure. availability (all 5 statuses); `generate_lines`
  (consolidation across 2 recipes, netting, skip in-stock, non-nettable
  surfaced); `deduct` (clamp at 0, mismatch skipped, cross-unit convert);
  `add_to_inventory` (new row, merge same dim, merge same unit, incompatible
  best-effort).
- `test_auth.py` — anonymous `client`. register 201/409/403/422; login
  200+token / 401 bad pw / 401 unknown user; `/me` 200 with token & 401 without;
  logout invalidates; a gated endpoint 401 without token.
- `test_recipes.py` — expanded, `auth_client`. nested create/read (positions,
  computed `normalized_name`); PUT clears old ingredients; steps/tags round-trip;
  `/availability?multiplier=2`; `/cook` writes `CookLog` + mutates inventory
  (clamp, mismatch); photo upload (in-memory PNG bytes; wrong content-type
  415/422; oversize 413).
- `test_inventory.py` — CRUD, `normalized_name` upsert/uniqueness, negative qty
  rejected.
- `test_grocery.py` — generate from 2 selected recipes (consolidation + netting),
  manual item add, check off → inventory up + `added_to_inventory` set, uncheck →
  reversed, delete list cascades items, non-nettable line present.
- `test_import.py` — **no live HTTP.** Monkeypatch
  `app.services.import_recipe._fetch_and_scrape` to return a stub scraper; assert
  preview mapping + parser wiring; stub raises → 422 `unsupported:true`; fetch
  error → 502.

`pyproject.toml` `testpaths`/`addopts` unchanged. No mypy/lint added (ethos).

## Build sequence (each phase ends with `uv run pytest` green)

- **Phase 0 — reset & deps.** `uv add recipe-scrapers pwdlib[argon2]
  python-multipart httpx`. Delete `backend/recipe.db`. `.gitignore` += `uploads/`.
  Old tests still green.
- **Phase 1 — pure core.** `normalize.py`, `units.py`,
  `services/ingredient_parse.py` + `test_units.py`, `test_ingredient_parse.py`.
  Nothing else touched.
- **Phase 2 — auth.** `User`/`Session` models, `security.py`, `schemas/auth.py`,
  `routers/auth.py`, wire into `main.py`, `config` additions. conftest: `user` +
  `auth_client`; migrate `test_recipes.py` to `auth_client`; add
  `dependencies=[Depends(get_current_user)]` to the recipes router. `test_auth.py`.
  End: existing recipe CRUD works, now gated; login works.
- **Phase 3 — structured recipes + photo.** Expand `Recipe`, add
  `RecipeIngredient`, drop the old text cols; `schemas/recipe.py` nested; rewrite
  `routers/recipes.py` for nested create/replace; `config` upload dir; `main.py`
  StaticFiles mount; `POST /{id}/photo`. Expand `test_recipes.py`. Delete
  `recipe.db`. End: full structured recipe CRUD + photos.
- **Phase 4 — inventory + math services.** `InventoryItem` model;
  `services/inventory_math.py` (`check_availability`, `add_to_inventory_calc`,
  `deduct_calc`); `routers/inventory.py` CRUD; `GET
  /api/recipes/{id}/availability`. `test_inventory.py`, `test_inventory_math.py`,
  availability tests. End: inventory CRUD + missing-ingredient check.
- **Phase 5 — cook = deduct.** `CookLog` model; `POST /api/recipes/{id}/cook`
  using `deduct_calc` + writes `CookLog`. Cook tests in `test_recipes.py`.
- **Phase 6 — grocery lists.** `GroceryList`/`GroceryListItem` models;
  `generate_lines` in `inventory_math.py`; `routers/grocery.py` (create-from-
  recipes, get, list, add manual item, PATCH check-off → `add_to_inventory`,
  delete). `test_grocery.py`. End: backend feature-complete.
- **Phase 7 — URL import.** `services/import_recipe.py`; `POST
  /api/recipes/import` in `recipes.py`; remote image download reuse.
  `test_import.py` (monkeypatched fetch).
- **Phase 8 — docs.** Update `README.md`, `CLAUDE.md`, `backend/.env.example`
  (new `RECIPE_*` vars, `rm backend/recipe.db` note, new architecture &
  API surface, LAN deploy: `uvicorn app.main:app --host 0.0.0.0 --port 8000`,
  "register both accounts then set `RECIPE_ALLOW_REGISTRATION=false`").

## Deferred (post-v1) — data model already accommodates

- **"What can we make now"** — run `check_availability` across all recipes, filter
  `all_available`; add `GET /api/recipes/makeable`.
- **Staples / low-stock alerts** — add `is_staple bool` + `min_quantity float` to
  `inventory_items`; add `GET /api/inventory/low`.
- **Web recipe search** — new `services/search.py` + route feeding the same
  `RecipeImportPreview` shape.
- **Frontend** — `react-router-dom`; `auth.tsx` + `RequireAuth`; namespaced
  `api.ts` injecting the bearer token; `types.ts` mirroring the new schemas;
  pages: Login, RecipeList (search/filter + multi-select → grocery list),
  RecipeDetail (scale control, availability panel, "mark as cooked"), RecipeForm
  (dynamic ingredient rows, import-from-URL, photo), Inventory, GroceryLists.
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
     `CookLog` recorded.
  6. `POST /api/grocery {recipe_ids:[id]}` → list has only shortfalls,
     consolidated; `PATCH` a line `checked:true` → inventory rises,
     `added_to_inventory:true`; `checked:false` → reverses.
  7. `POST /api/recipes/import {url:"<a supported recipe site>"}` → structured
     preview; a junk URL → 422 `unsupported:true`.
- Confirm `GET` on any data route without `Authorization` → 401.

## Critical files

- `backend/app/models.py` — all new tables.
- `backend/app/main.py` — 4 new routers, `/uploads` mount, `makedirs` in lifespan.
- `backend/app/routers/recipes.py` — nested CRUD + `/import` + `/photo` +
  `/availability` + `/cook`.
- `backend/app/config.py` — new `RECIPE_*` settings.
- `backend/tests/conftest.py` — `auth_client` (new default) + `user` + uploads-dir
  fixtures.
- `backend/app/schemas.py` → becomes `backend/app/schemas/` package.
- New: `backend/app/normalize.py`, `units.py`, `security.py`,
  `services/{ingredient_parse,import_recipe,inventory_math}.py`,
  `routers/{auth,inventory,grocery}.py`.

## Status

- [x] Requirements gathered
- [x] Codebase exploration
- [x] Design pass
- [x] Final plan written and approved
- [x] Git repo initialised, skeleton pushed, this plan committed to `docs/plan.md`
- [ ] Phase 0 — reset & deps (not started; awaiting go-ahead)
