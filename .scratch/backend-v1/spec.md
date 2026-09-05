# Backend v1 — Implementation Specification

This is the normative implementation contract for backend v1. It defines data
models, pure services, infrastructure, HTTP behavior, transaction semantics, and
acceptance tests. When another planning document disagrees with this file,
**this file wins for v1 behavior**.

Related documents:

- [`plan.md`](plan.md) — delivery order and status.
- [`phases/`](phases/) — execution checklists that link back here.
- [`issues.md`](issues.md) — unresolved decisions that must update this file
  before their owning phase is implemented.
- [`decisions.md`](decisions.md) — historical rationale.
- [`features.md`](features.md) — deferred work and upgrade paths.

## Mechanical defaults

- **Error bodies:** FastAPI defaults — `{"detail": "<msg>"}` for `HTTPException`,
  `{"detail": [{"loc", "msg", "type"}, …]}` for request-validation 422s.
- **Datetimes:** timezone-aware UTC, serialized ISO 8601 (`…+00:00`).
- **`GET /api/health`** → `200 {"status": "ok"}`, unauthenticated. (No tesseract line — that is v2.)
- **Converted display quantities are not rounded** — raw `float`; clients format.
- **Pagination:** only `GET /api/cook-logs` is paginated (`limit` default 50,
  `1..200`; `offset` default 0, `≥0`). `GET /api/recipes`, `/api/inventory`,
  `/api/grocery`, and `GET /api/recipes/{id}/cook-logs` return everything, with a
  fixed ordering given per endpoint. `GET /api/grocery` accepts an optional
  `?status=active|archived` filter.
- **`source_url`** — plain string `≤ 500`, not URL-validated.
- **`tags` / `steps`** — stored as sent (no dedupe, no case-fold). Sanity caps:
  each list `≤ 100` items; each tag `≤ 50` chars; each step `≤ 2000` chars.
- **`note`** on a recipe ingredient — `≤ 200` chars (matches the column).
- **`quantity = null`** on a recipe ingredient ⇒ **to-taste**, even if `unit` is set (the `unit` is ignored).
- **Additive `POST /api/inventory` into an existing `(match_name, unit_bucket)` row**
  keeps that row's existing `item` / `normalized_name`. Rename via `PATCH`.
- **`match_name` is a canonical server-owned key.** A `match_name` supplied to
  inventory `POST` / `PATCH` is run through `normalize_name` (not merely
  `.strip()`ed); a value that normalizes to `""` → `422`. Collision detection and
  the additive-upsert `ON CONFLICT` both key off the normalized value. Display
  `item` is stored exactly as typed.
- **`created_by_id` / `cooked_by_id`** are never reassigned on update.
- **Session lifetime is a fixed window** from creation: `expires_at = created_at +
  SESSION_TTL_DAYS`. `last_used_at` is bumped on every authenticated request;
  `expires_at` is **not** slid. Consequence: an expired token cannot call
  `logout` / `me` (401 first) — acceptable, it is already dead.
- **All `DELETE` endpoints** → `204` with an empty body.
- **`POST /api/recipes/{id}/cook`** → `201` (it creates a `CookLog`).
- **Register check order:** body validation `422` → registration disabled `403`
  → bad/missing `code` `403` → duplicate username `409` → create.
- **Registration `code` comparison** uses `secrets.compare_digest`.

## Accepted security posture

Listed so it is a conscious choice, not an oversight. None of these are fixed in v1.

- Session tokens are stored **in plaintext** in `sessions`. DB theft ⇒ usable tokens until `expires_at`.
- **No HTTPS** in-app. Tokens travel in clear on the LAN.
- **No login rate-limiting or lockout.** A dummy argon2 verify on unknown usernames blunts timing enumeration only.
- **`/docs` (full OpenAPI) is unauthenticated.**
- v1 is a **single shared household**: every authenticated user has full read/write on all data. `created_by_id` is attribution only.

---

## 0. Conventions

| Aspect | Value |
|---|---|
| Base path | all endpoints under `/api` |
| Auth header | `Authorization: Bearer <token>` |
| Auth scope | every route requires a valid token **except** `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/health` |
| Content type | `application/json` request and response bodies throughout (no form-data, no file uploads in v1) |
| IDs | integer surrogate PKs, assigned by SQLite |
| Timestamps | tz-aware UTC, ISO 8601 |
| 404 | any addressed resource that does not exist → `404 {"detail": "<resource> not found"}` |
| 409 | `IntegrityError` (unique/FK/check) and `OperationalError: database is locked` are translated to `409` by a global handler; any other `OperationalError` → `500` |
| 422 | Pydantic request-validation failures (FastAPI default shape) **and** the explicit domain 422s named in this spec |

---

## 1. Data model — `backend/app/models.py`

SQLAlchemy 2.0 `Mapped[...]` style, one file. All `float` columns are finite
(`CHECK` where noted). Schema is created by `Base.metadata.create_all(bind=engine)`
in the app-factory lifespan. **No migrations** — a model change requires
`rm backend/recipe.db`.

Import layering (one-way):
`config → database → normalize / units → models → security / services → schemas / routers → main`.

**Datetime columns.** Every `datetime` column is typed `UtcDateTime` (§3.2), not
a bare `DateTime(timezone=True)`: SQLite has no timezone type and hands back a
naive value, which would break the `…+00:00` guarantee in §Mechanical defaults on
every read path — including raw-SQL paths that bypass the ORM. The decorator
re-attaches UTC on read, in one place.

**Timestamps are Python-side.** Creation defaults and update bumps are
`default=_utcnow` / `onupdate=_utcnow`, where `_utcnow()` is
`datetime.now(timezone.utc)`, defined in `models.py` beside the columns and
imported by the routers that need it. SQLite's `CURRENT_TIMESTAMP` is never used: it
produces a naive, second-precision string that would defeat `UtcDateTime` and
lose sub-second ordering. Statements that bypass ORM defaults by construction
(the §5.5 upsert) bind `_utcnow()` explicitly.

### users

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `username` | `str(50)` | regex `^[A-Za-z0-9_.-]{3,50}$`, enforced in the schema |
| `password_hash` | `str(255)` | argon2 (`pwdlib`) |
| `created_at` | datetime(tz) | `UtcDateTime`, `default=_utcnow` |

Indexes: `UNIQUE` on `lower(username)` — `Index("uq_users_username_lower", func.lower(username), unique=True)`.
Users are never deleted in v1.

### sessions

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `token` | `str(64)` | `secrets.token_urlsafe(32)` (43 chars); `UNIQUE`, indexed |
| `user_id` | int FK → `users.id` | `ON DELETE CASCADE`, `passive_deletes=True` |
| `created_at` | datetime(tz) | |
| `last_used_at` | datetime(tz) | bumped by `get_current_user` on every authenticated request |
| `expires_at` | datetime(tz) | `= created_at + timedelta(days=settings.session_ttl_days)`; never extended |

### recipes

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `title` | `str(200)` | `min_length 1` (schema) |
| `notes` | `Text` | default `""` |
| `prep_time` | `int?` | `≥ 0` (schema) — minutes |
| `cook_time` | `int?` | `≥ 0` |
| `servings` | `float?` | `> 0` |
| `cuisine` | `str(100)?` | free string |
| `source_url` | `str(500)?` | free string, not URL-validated |
| `photo_path` | `str(500)?` | **reserved for v2**; always `NULL` in v1; exposed in `RecipeRead` |
| `tags` | JSON `list[str]` | default `[]` |
| `steps` | JSON `list[str]` | default `[]` — ordered |
| `created_at` | datetime(tz) | |
| `updated_at` | datetime(tz) | `default=_utcnow`, `onupdate=_utcnow` |
| `created_by_id` | int FK → `users.id`? | nullable, **no** cascade; set on create, never reassigned |

Relationship: `ingredients` → `RecipeIngredient`, `order_by="RecipeIngredient.position"`,
`cascade="all, delete-orphan"`. Read paths use `selectinload(Recipe.ingredients)`.

### recipe_ingredients

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | churns on every PUT — harmless |
| `recipe_id` | int FK → `recipes.id` | `ON DELETE CASCADE`, `passive_deletes=True` |
| `position` | int | 0-based, contiguous, server-assigned from array order |
| `quantity` | `float?` | `> 0` when set, finite; `NULL` = to taste |
| `unit` | `str(30)?` | the **author's unit** — the word as written, lower-cased with one trailing `.` stripped, on **both** input paths (parsed string and structured object; §5.2). Never singularized. |
| `item` | `str(200)` | display text |
| `note` | `str(200)?` | |
| `normalized_name` | `str(200)` | **server-computed** `normalize_name(item)`; indexed |
| `raw_text` | `str(300)?` | **active in v1**: the verbatim source line when the row came from a pasted string; `NULL` for structured rows. Stored value is `<= 200` — pasted lines are truncated to 200 before parse (§5.2, R-4); the extra column headroom is left intentionally. |

Index: `(recipe_id, position)`.

### inventory_items

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `item` | `str(200)` | display text; set on first insert into a `(match_name, unit_bucket)` row, only changed by `PATCH` |
| `normalized_name` | `str(200)` | `normalize_name(item)`; indexed; tracks `item` |
| `match_name` | `str(200)` | the recipe↔inventory match key; indexed. **User-editable but canonical:** every value (default or supplied) is `normalize_name(...)`ed before store; normalizes-to-`""` → `422` |
| `unit_bucket` | `str(30)` | `"mass"` \| `"volume"` \| `"count"` \| `"opaque:<canonical-token>"` |
| `quantity_base` | `float` | **source of truth**, in the bucket's canonical unit (g / ml / count / raw opaque amount). `CHECK(quantity_base >= 0)`, finite. Default `0` |
| `display_unit` | `str(30)?` | **preferred display unit only** — never drives math. `NULL` / opaque ⇒ display in the canonical unit |
| `updated_at` | datetime(tz) | `default=_utcnow`, `onupdate=_utcnow` |
| `created_by_id` | int FK → `users.id`? | nullable, no cascade |

Constraint: `UNIQUE (match_name, unit_bucket)`.
`unit_bucket` widened to `str(30)` (vs the plan's `str(20)`) to fit `opaque:` + a long unknown token.

### grocery_lists

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | `str(200)` | default `"Groceries YYYY-MM-DD"` (UTC date) |
| `status` | `str(20)` | `"active"` \| `"archived"`; default `"active"` |
| `source_recipe_ids` | JSON `list[int]` | informational, **no FK**; default `[]` |
| `created_at` | datetime(tz) | |
| `created_by_id` | int FK → `users.id`? | nullable, no cascade |

Relationship: `items` → `GroceryListItem`, `cascade="all, delete-orphan"`, `order_by` by `id`.

### grocery_list_items

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `grocery_list_id` | int FK → `grocery_lists.id` | `ON DELETE CASCADE`, `passive_deletes=True` |
| `item` | `str(200)` | |
| `normalized_name` | `str(200)` | `normalize_name(item)`; indexed; recomputed on `item` edit |
| `quantity` | `float?` | `> 0` when set, finite. For `source="generated"`: the shortfall **in the bucket's canonical unit**. For `source="manual"`: as the user typed |
| `unit` | `str(30)?` | canonical unit for generated lines; as typed for manual |
| `checked` | bool | default `false` |
| `checked_at` | datetime(tz)? | set when `checked` flips to `true`, cleared to `NULL` when it flips to `false` |
| `submitted_at` | datetime(tz)? | set by `submit` when the line is applied |
| `source` | `str(20)` | `"generated"` \| `"manual"` |
| `nettable` | bool | default `true`. `false` = the true shortfall is uncertain (see §5) |
| `added_to_inventory` | bool | default `false`. Idempotency guard **and** freeze flag |
| `applied_quantity` | `float?` | canonical amount `submit` actually added |
| `applied_unit` | `str(30)?` | canonical unit `submit` actually added |

### cook_logs

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `recipe_id` | int FK → `recipes.id`? | `ON DELETE SET NULL`, `passive_deletes=True` |
| `recipe_title` | `str(200)` | snapshot, survives recipe deletion |
| `multiplier` | `float` | `> 0`, finite; default `1` |
| `deducted` | bool | default `true`; `false` = logged without touching stock |
| `cooked_at` | datetime(tz) | |
| `cooked_by_id` | int FK → `users.id`? | nullable, no cascade |
| `deductions` | JSON `list[dict]` | one entry per member ingredient; `[]` when `deducted=false`. Stored raw; **serialized through `list[CookDeductionRead]` on read** (§5.4), so every entry is validated. |

---

## 2. Pure modules

### 2.1 `backend/app/normalize.py`

```python
def normalize_name(raw: str) -> str
```

Pipeline, in order:

1. `raw.strip().lower()`
2. drop punctuation, keep spaces and hyphens: `re.sub(r"[^\w\s-]", "", s)`
3. collapse whitespace: `re.sub(r"\s+", " ", s).strip()`
4. **strip leading descriptor tokens**: while the first space-delimited token is in
   `LEADING_DESCRIPTORS`, drop it.
5. **singularize the final token** only, via `_singularize_token` (below).
6. return; an empty string is a valid (degenerate) result.

`_singularize_token(tok: str) -> str` — the shared singularization rule. Also
called by `units.normalize_unit_token` (§2.2), so the two never drift. Rule, in
order:
   - irregular map first: `{tomatoes: tomato, potatoes: potato, leaves: leaf,
     loaves: loaf, halves: half, knives: knife, wolves: wolf}` (extend freely — tuning knob)
   - `-ies` → `-y`
   - `-ses` / `-xes` / `-zes` / `-ches` / `-shes` → drop `-es`
   - `-oes` → `-o`
   - trailing `-s`, and not `-ss` → drop the `-s`
   - otherwise (no trailing `-s`, or ends `-ss`) → unchanged

`LEADING_DESCRIPTORS` — initial set, **documented tuning knob**:
`diced, chopped, minced, sliced, shredded, grated, crushed, cubed, julienned,
large, small, medium, jumbo, boneless, skinless, ripe, peeled`.

**Not stripped** (identity-bearing, #R4): `fresh, dried, ground, cooked, raw,
smoked, frozen, canned, roasted, toasted`.

**Locked normalization oracles (R-7):**

| Input | Exact output | Contract exercised |
|---|---|---|
| `"  Diced Tomatoes! "` | `"tomato"` | trim, case, punctuation, descriptor, irregular |
| `"large eggs"` | `"egg"` | descriptor + trailing `-s` |
| `"chopped   red onions"` | `"red onion"` | whitespace + final-token-only singularization |
| `"fresh tomatoes"` | `"fresh tomato"` | identity-bearing word retained |
| `"ground beef"` | `"ground beef"` | identity-bearing word retained |
| `"berries"` | `"berry"` | `-ies` rule |
| `"boxes"` | `"box"` | `-xes` rule |
| `"potatoes"` | `"potato"` | irregular map before suffix rules |
| `"glass"` | `"glass"` | terminal `-ss` retained |
| `"Chef's   choice"` | `"chefs choice"` | punctuation removal + whitespace |
| `"!!!"` | `""` | valid degenerate result |

These exact cases are the v1 oracle. **Global idempotence is not a v1
invariant:** the deliberately small open-vocabulary heuristic can map
`"buses" → "bus" → "bu"` on repeated calls. Callers normalize source text
once; robust name inflection remains deferred (D1).

### 2.2 `backend/app/units.py`

No third-party dependency. Dimensions: `MASS` (base **g**), `VOLUME` (base **ml**),
`COUNT` (base **unit**).

```python
class Dimension(enum.Enum): MASS = "mass"; VOLUME = "volume"; COUNT = "count"

@dataclass(frozen=True)
class Quantity:
    amount: float | None
    unit:   str | None

@dataclass(frozen=True)
class UnitDef:
    dimension:      Dimension
    factor_to_base: float
    canonical:      str      # "g" | "ml" | "unit"
```

Synonym table `str → UnitDef` (key = normalized token):

| Dimension | Tokens → factor to base |
|---|---|
| MASS (g) | `g`/`gram` 1 · `kg` 1000 · `mg` 0.001 · `oz`/`ounce` 28.3495 · `lb`/`lbs`/`pound` 453.592 |
| VOLUME (ml) | `ml` 1 · `l`/`litre`/`liter` 1000 · `tsp`/`teaspoon` 4.92892 · `tbsp`/`tablespoon` 14.7868 · `cup` 236.588 · `fl-oz`/`fl oz`/`floz` 29.5735 · `pint` 473.176 · `quart` 946.353 · `gallon` 3785.41 |
| COUNT (unit) | `unit`/`each`/`""`/`None` 1 · `dozen` 12 · `pair` 2 |

**Deliberately unknown → opaque** (exact-string match only; same token still nets):
`clove, slice, piece, stick, can, package, pkg, jar, bottle, box, bag, head,
bulb, bunch, sprig, pinch, handful, dash, splash, "to taste"`.

```python
def normalize_unit_token(s: str | None) -> str | None
    # None or "" -> None
    # else: lower -> strip -> strip one trailing "." ->
    #       normalize._singularize_token (§2.1 step 5) applied to the WHOLE string
    #       (not final-token-only; unit tokens are <=2 words) -> return
    # e.g. "Cups." -> "cup"; "boxes" -> "box"; "bunches" -> "bunch";
    #      "fl oz" -> "fl oz" (unchanged); "lbs" -> "lb"

def parse_unit(s: str | None) -> UnitDef | None
    # normalize_unit_token then dict lookup; normalized None is the COUNT token;
    # a non-None token absent from the table => unknown/opaque (return None)

def to_base(amount: float, unit: str | None) -> tuple[float, Dimension] | None
    # unit resolves to None-token  -> (amount, COUNT)
    # unit is known                -> (amount * factor_to_base, dimension)
    # unit is opaque/unknown       -> None

def from_base(amount: float, dim: Dimension, unit: str | None) -> float | None
    # unit None / canonical-for-dim -> amount        (already base)
    # unit known & same dimension   -> amount / factor_to_base
    # otherwise                     -> None

def compatible(a: str | None, b: str | None) -> bool
    # both resolve to a known UnitDef of the same Dimension; a None token counts as COUNT

def bucket_of(unit: str | None) -> str
    # None                -> "count"
    # known               -> dimension.value  ("mass" | "volume" | "count")
    # opaque/unknown      -> "opaque:" + normalize_unit_token(unit)

def canon_unit(bucket: str) -> str
    # "mass" -> "g" ; "volume" -> "ml" ; "count" -> "unit" ; "opaque:X" -> "X"

def add_quantities(qs: list[Quantity]) -> list[Quantity]
```

`add_quantities` partitions the input and returns one `Quantity` per partition,
each already expressed in its **canonical unit**:

- **known units** — partition by `Dimension`. Sum in base units. Emit
  `Quantity(total_base, canon_unit(dimension))`.
- **opaque units** — partition by the exact normalized token. Sum the raw amounts.
  Emit `Quantity(total, token)`.
- **`None` units** — merged into the COUNT partition.
- If **every** amount in a partition is `None`, emit `Quantity(None, <unit>)` for it.
  A `None` amount mixed with numbers is treated as `0` for the sum.
- Partitions are emitted in **first-seen input order**. This makes grocery-line
  insertion order deterministic (decision SD4) and is consistent with the
  recipe/ingredient traversal order used by first-writer-wins decision S4.

For all numeric assertions in §2 and §7, use
`pytest.approx(expected, rel=1e-9, abs=1e-9)`; do not compare conversion results
by exact binary-float equality.

**Locked conversion oracles (R-7):** each successful row also asserts that
`from_base(base, dimension, input_unit)` returns the original amount within the
tolerance above.

| Amount | Unit | Exact `to_base` result | Round-trip result |
|---:|---|---|---:|
| `1` | `kg` | `(1000, MASS)` | `1` |
| `16` | `oz` | `(453.592, MASS)` | `16` |
| `2` | `cup` | `(473.176, VOLUME)` | `2` |
| `3` | `dozen` | `(36, COUNT)` | `3` |
| `5` | `null` | `(5, COUNT)` | `5` |
| `1` | `can` | `null` | n/a |

Additionally, parameterize the round-trip over **every known synonym-table
token** and amounts `0.125`, `1`, and `17.5`; cross-dimension `from_base` and an
opaque target unit return `None`.

**Locked `add_quantities` oracles (R-7):** tuples below are shorthand for
`Quantity(amount, unit)`. Output list order is exact.

| Input | Exact output |
|---|---|
| `[]` | `[]` |
| `[(1, "kg"), (500, "g")]` | `[(1500, "g")]` |
| `[(1, "cup"), (2, "tbsp")]` | `[(266.1616, "ml")]` |
| `[(2, "can"), (1, "cans")]` | `[(3, "can")]` |
| `[(2, "can"), (1, "jar")]` | `[(2, "can"), (1, "jar")]` |
| `[(2, null), (1, "dozen")]` | `[(14, "unit")]` |
| `[(null, "can"), (2, "can")]` | `[(2, "can")]` |
| `[(null, "kg"), (null, "g")]` | `[(null, "g")]` |
| `[(1, "can"), (1, "kg"), (1, null), (1, "jar")]` | `[(1, "can"), (1000, "g"), (1, "unit"), (1, "jar")]` |

Interpretation-independent checks over finite numeric inputs:

- `parse_ingredient(text)` never raises for the deterministic adversarial corpus
  and returns `quantity is None` or a positive finite float.
- Unit conversion round-trips as specified above for every known token.
- `add_quantities` conserves the approximate sum of base-unit numeric amounts
  per known dimension, and the raw numeric sum per normalized opaque token;
  `None` contributes zero unless every member of its partition is `None`.

### 2.3 `backend/app/services/ingredient_parse.py`

```python
def parse_ingredient(text: str) -> dict
    # -> {"quantity": float | None, "unit": str | None, "item": str, "note": str | None}
```

**Contract:** callers skip blank/whitespace-only strings before calling (§5.2).
For every non-blank input, the parser never raises. `item` is always non-empty
(falls back to the whole cleaned line). `quantity` is either a **positive finite
float** or `None` — the parser never emits `0`, negative, or non-finite.

Heuristic (implementer's exact regex is free, but it must satisfy the table):

- Leading number = quantity. Accept integer, decimal, `a/b`, `a b/c` (mixed),
  and single unicode vulgar fractions (`½ ¼ ¾ ⅓ ⅔ ⅛`). Mixed `1 1/2` → `1.5`.
- The token immediately after the number, if it is a known or opaque unit word
  (after `normalize_unit_token`), is `unit`. Store it **as it appeared**
  (lower-cased, trailing `.` stripped) — do **not** singularize (`"cups"` stays `"cups"`).
- A trailing `(...)` parenthetical → `note`; a trailing / embedded `"to taste"`
  → `note = "to taste"` and `quantity = None`.
- Everything left after removing quantity, unit, and note → `item`
  (descriptors are **kept** in `item`; `normalize_name` strips them for `normalized_name`).
- No parseable leading number → `quantity = None`, `unit = None`, `item` = cleaned line.

**Acceptance table (locked):**

| Input | quantity | unit | item | note |
|---|---|---|---|---|
| `2 tbsp olive oil` | `2.0` | `tbsp` | `olive oil` | `null` |
| `1 1/2 cups flour` | `1.5` | `cups` | `flour` | `null` |
| `½ tsp salt` | `0.5` | `tsp` | `salt` | `null` |
| `salt to taste` | `null` | `null` | `salt` | `to taste` |
| `3 large eggs` | `3.0` | `null` | `large eggs` | `null` |
| `1 (14 oz) can tomatoes` | `1.0` | `can` | `tomatoes` | `14 oz` |
| `asdfghjkl` | `null` | `null` | `asdfghjkl` | `null` |

The deterministic adversarial corpus for the no-raise/positive-finite invariant
is: `"0 eggs"`, `"-1 cup flour"`, `"1/0 cup flour"`, `"NaN cups flour"`,
`"1e309 cups flour"`, and `"not a quantity"`. Exact fallback parsing is free;
each result must satisfy the contract above.

---

## 3. App infrastructure

### 3.1 `backend/app/config.py`

`Settings(pydantic_settings.BaseSettings)`, env prefix `RECIPE_`, also reads `backend/.env`.

| Field | Type | Default |
|---|---|---|
| `database_url` | `str` | `sqlite:///./recipe.db` (existing) |
| `cors_origins` | `list[str]` | `["http://localhost:5173"]` (existing) |
| `session_ttl_days` | `int` | `Field(30, ge=0)` — `0` is legal and meaningful (an instantly-expired token, which is how §7 exercises the expiry branch); a negative value raises `ValidationError` when `Settings` is constructed |
| `allow_registration` | `bool` | `False` |
| `registration_code` | `str \| None` | `None` |

### 3.2 `backend/app/database.py`

```python
def make_engine(url: str) -> Engine
def make_session_factory(engine: Engine) -> sessionmaker[Session]

engine = make_engine(settings.database_url)          # the ONE module-level default; uvicorn only
# NO module-level SessionLocal.

class UtcDateTime(TypeDecorator):                    # impl = DateTime(timezone=True)
    """Stores UTC; re-attaches tzinfo=utc on every read."""
    def process_bind_param(self, value, dialect)     # naive -> assume UTC; aware -> convert to UTC
    def process_result_value(self, value, dialect)   # naive -> replace(tzinfo=utc)

def get_db(request: Request) -> Iterator[Session]:   # importable; routers bind Depends(get_db) statically
    factory = request.app.state.session_factory
    db = factory()
    request.state.db = db                            # TransactionRoute reads it from here
    try:
        yield db                                     # NO commit here - see TransactionRoute
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

SessionDep = Annotated[Session, Depends(get_db)]

class TransactionRoute(APIRoute):                    # owns the commit; see §6
    def get_route_handler(self):
        original = super().get_route_handler()
        async def custom(request: Request) -> Response:
            response = await original(request)       # endpoint ran and serialized
            db = getattr(request.state, "db", None)
            if db is not None:
                db.commit()
            return response
        return custom
```

`TransactionRoute` lives here, beside `get_db`, and **not** in `main.py`: a
router must name it when it constructs its `APIRouter`, and a router cannot
import `main` without an import cycle.

Why the commit moved out of `get_db`: a dependency's post-`yield` code runs
**after** the response has been generated. Starlette then finds a registered
handler for a commit-time `IntegrityError` or `OperationalError` and refuses to
use it because the response has already started — so the caller receives `200`
with the write silently discarded, which §6 and §0 both promise cannot happen.
`TransactionRoute` commits inside `wrap_app_handling_exceptions` and before the
response is sent, so the failure converts to `409` exactly like an in-handler
one. Response serialization completes before the commit, so no ORM attribute is
touched post-commit and `expire_on_commit` needs no change.

A route with no database dependency leaves `request.state.db` unset; the wrapper
no-ops, so `/api/health` needs no special case.

`make_engine`, for a SQLite URL:

- `connect_args={"check_same_thread": False}`.
- in-memory URL (`sqlite://` / `:memory:`) → `poolclass=StaticPool` (test fixture).
- `event.listens_for(engine, "connect")`: on the raw DBAPI connection set
  `dbapi_conn.isolation_level = None` (disable pysqlite autobegin) **and**
  `cursor.execute("PRAGMA foreign_keys=ON"); cursor.execute("PRAGMA busy_timeout=5000")`.
- `event.listens_for(engine, "begin")`: `conn.exec_driver_sql("BEGIN IMMEDIATE")`.
  Every request-scoped transaction — reads, the `last_used_at` bump, and mutations
  alike — therefore takes the write lock before its first `SELECT`. Accepted
  trade-off: all requests serialize on the single SQLite writer; immaterial at
  ≤ 2 concurrent household users, and lost updates are impossible everywhere.

### 3.3 `backend/app/main.py`

```python
def get_settings(request: Request) -> Settings:
    return request.app.state.settings

def create_app(settings: Settings, engine: Engine) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)     # the ONLY DB wiring

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

    app.add_exception_handler(RequestValidationError, _validation_error_to_422)
    app.add_exception_handler(IntegrityError, _to_409)
    app.add_exception_handler(OperationalError, _to_409_if_locked_else_500)

    for r in (auth.router, recipes.router, cook_logs.router, inventory.router, grocery.router):
        app.include_router(r)          # each router was built with route_class=TransactionRoute

    @app.get("/api/health")
    def health(): return {"status": "ok"}

    return app

app = create_app(settings, engine)          # module-level, for `uvicorn app.main:app`
```

`_to_409(request, exc)` → `JSONResponse(status_code=409, content={"detail": "conflict"})`.
`_to_409_if_locked_else_500` → 409 when `"database is locked"` / `"database is busy"`
in `str(exc.orig)`, otherwise re-raise (→ 500).

`_validation_error_to_422(request, exc)` → `JSONResponse(status_code=422,
content={"detail": <errors>})`, where `<errors>` is
`jsonable_encoder(exc.errors())` with every non-finite `float` (anywhere in the
structure) replaced by its `repr` (`"inf"` / `"-inf"` / `"nan"`). This exists
because `json.loads` accepts the JSON literals `Infinity` / `NaN`, so a raw
client can put a non-finite `float` into a request that §7 requires to `422`
(negative / `0` / `inf` / `nan` quantities, multipliers, servings). Validation
does reject it — but FastAPI's default handler echoes the offending value into
the error body's `input`, and `JSONResponse` encodes with `allow_nan=False`, so
the mandated 422 would raise an unhandled `ValueError` at encode time. The
scrub is the only change from FastAPI's default 422 body; the
`{"detail": [{"loc", "msg", "type"}, …]}` shape in §Mechanical defaults is
unchanged for all finite inputs.

These handlers cover **commit-time** failures as well as in-handler ones, because
`TransactionRoute` (§3.2) commits inside the exception-handling window. An
`IntegrityError` raised by `COMMIT`, and a `SQLITE_BUSY` at `COMMIT`, both reach
`_to_409` / `_to_409_if_locked_else_500` and return `409 {"detail": "conflict"}`.

`route_class=TransactionRoute` is a property of the `APIRouter` a route is
**declared** on; `include_router` cannot apply it retroactively. Every router
that depends on `get_db` must therefore pass it at construction. §7's
`test_transactions.py` guard test is what makes a forgotten `route_class=` fail
instead of silently reverting that router to a commit-after-response.

**No `StaticFiles` mount. No `/uploads`. No `dependency_overrides` anywhere.**

### 3.4 `backend/app/security.py`

```python
def hash_password(pw: str) -> str                    # pwdlib argon2
def verify_password(pw: str, hashed: str) -> bool
_DUMMY_HASH = hash_password(secrets.token_hex(16))   # module load; for timing-equalised login

def issue_token(db: Session, user: User, settings: Settings) -> Session   # inserts a sessions row, returns it

def get_current_user(
    request: Request,
    db: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(default=None),
) -> User

CurrentUser = Annotated[User, Depends(get_current_user)]
```

`get_current_user` returns **401 `{"detail": "not authenticated"}`** for every one of:

| Case | Trigger |
|---|---|
| missing | `authorization is None` |
| malformed | `authorization.split(" ")` is not exactly two non-empty parts |
| wrong scheme | `parts[0].lower() != "bearer"` |
| unknown token | no `sessions` row with `token == parts[1]` |
| expired | `row.expires_at <= _utcnow()` — a plain aware comparison; `UtcDateTime` (§3.2) guarantees `expires_at` is tz-aware, so no ad-hoc naive normalization is needed or permitted here |

On success: `row.last_used_at = _utcnow()` (no `expires_at` change — the write rides
the request's single `BEGIN IMMEDIATE` transaction, committed by
`TransactionRoute`), return `row.user`.

`issue_token` takes `settings` as an argument and reads `session_ttl_days` from
it — never from the module-level `Settings`. Both call sites are in
`routers/auth.py`, which already has settings injected. This is what makes
`create_app(test_settings, test_engine)` able to influence token lifetime, and
leaves no module-global configuration read on a request path.

Router wiring: every router is
`APIRouter(prefix="/api/<x>", route_class=TransactionRoute, dependencies=[Depends(get_current_user)])`
**except** `auth` (see §5.1 — same `route_class`, no blanket dependency) and the
inline `/api/health` (no database, no `route_class`).

---

## 4. Service layer — `backend/app/services/inventory_math.py`

Pure. Imports only `units`, `normalize`, stdlib. **No ORM, no `Session`.** Every
function takes/returns the frozen dataclasses below. A function **proposes**; the
router **applies** inside the request transaction.

```python
@dataclass(frozen=True)
class ReqLine:                     # one recipe ingredient, multiplier already applied
    ingredient_id:   int
    item:            str           # display text of this row
    normalized_name: str
    quantity:        float | None  # * M already; None = to taste
    unit:            str | None

@dataclass(frozen=True)
class StockRow:                    # one inventory_items row, ORM-free
    id:            int
    match_name:    str
    unit_bucket:   str
    quantity_base: float

@dataclass(frozen=True)
class AvailabilityLineDTO:
    ingredient_id: int
    item:          str
    need:          float | None
    need_unit:     str
    group_key:     str
    group_unit:    str
    group_need:    float | None
    group_have:    float | None
    group_short:   float | None
    status:        str            # ok | short | missing | to_taste | have_uncertain
    nettable:      bool

@dataclass(frozen=True)
class GroceryLineDTO:
    item:            str
    normalized_name: str
    quantity:        float | None  # canonical
    unit:            str | None    # canonical unit label
    nettable:        bool

@dataclass(frozen=True)
class InventoryDelta:              # proposal for the additive upsert
    match_name:      str
    unit_bucket:     str
    item:            str
    normalized_name: str
    add_base:        float         # >= 0, canonical
    display_unit:    str | None
    canonical_added: Quantity      # (add_base, canon_unit(bucket)) — for grocery applied_* snapshot

@dataclass(frozen=True)
class RowDeduction:
    row_id:            int
    new_quantity_base: float

@dataclass(frozen=True)
class DeductProposal:
    row_updates: list[RowDeduction]   # inventory rows to write
    log_entries: list[dict]           # the full CookLog.deductions list (all branches)
```

### 4.1 `aggregate(reqs, M) -> dict[(normalized_name, bucket), GroupAgg]`

Shared helper (also used inline by `check_availability` / cook).
`bucket = bucket_of(ing.unit)` (a `None` unit → `"count"`).
For each group:

- `need_base` = Σ over quantified members of `to_base(qty*M, unit).amount`
  (known dims) or `qty*M` (opaque / count).
- `members` = `[(ingredient_id, own_need_base)]` in **`position` order**.
- `display_item` = the **first** member's `item` (decision S4).
- `to_taste_members` = ingredient ids with `quantity is None`.

### 4.2 `check_availability(reqs: list[ReqLine], stock: list[StockRow]) -> list[AvailabilityLineDTO]`

```
groups = aggregate(reqs, M)                       # M already folded into ReqLine.quantity
for g in groups:
    canon = canon_unit(g.bucket)

    # to-taste members: one vacuous line each (decision SD1)
    for ing_id in g.to_taste_members:
        emit AvailabilityLineDTO(
            ingredient_id=ing_id, item=<that row's item>,
            need=None, need_unit=canon,
            group_key=f"{g.norm}|{g.bucket}", group_unit=canon,
            group_need=None, group_have=None, group_short=None,
            status="to_taste", nettable=False)

    if not g.members:                             # group had only to-taste rows
        continue

    pos    = [r for r in stock if r.match_name == g.norm and r.quantity_base > 0]   # POSITIVE only
    compat = [r for r in pos if r.unit_bucket == g.bucket]
    incomp = [r for r in pos if r.unit_bucket != g.bucket]

    if compat:
        have  = sum(r.quantity_base for r in compat)          # already canonical — no to_base
        short = g.need_base - have
        if short <= 0:
            gstatus, nettable, ghave, gshort = "ok",             True,  have, 0.0
        elif incomp:
            gstatus, nettable, ghave, gshort = "have_uncertain", False, have, short
        else:
            gstatus, nettable, ghave, gshort = "short",          True,  have, short
    elif incomp:
        gstatus, nettable, ghave, gshort = "have_uncertain", False, 0.0, g.need_base
    else:
        gstatus, nettable, ghave, gshort = "missing",        False, 0.0, g.need_base

    for (ing_id, own_need_base) in g.members:
        emit AvailabilityLineDTO(
            ingredient_id=ing_id, item=<that row's item>,
            need=own_need_base, need_unit=canon,
            group_key=f"{g.norm}|{g.bucket}", group_unit=canon,
            group_need=g.need_base, group_have=ghave, group_short=gshort,
            status=gstatus, nettable=nettable)
```

`AvailabilityReport.all_available` (built by the router) =
`every line with status != "to_taste" has status == "ok"`
(empty recipe, or all-to-taste recipe → `true`).

### 4.3 `generate_lines(reqs_by_recipe: list[list[ReqLine]], stock: list[StockRow]) -> list[GroceryLineDTO]`

```
reqs = {}   # normalized_name -> {quantities: list[Quantity], display_item, to_taste: bool}
for recipe_reqs in reqs_by_recipe:                        # recipe_ids order
    for ing in recipe_reqs:                               # position order
        slot = reqs.setdefault(ing.normalized_name, {...})
        slot.display_item = slot.display_item or ing.item     # first writer wins (decision S4)
        if ing.quantity is None: slot.to_taste = True; continue
        slot.quantities.append(Quantity(ing.quantity, ing.unit))   # * M already folded in

out = []
for norm, slot in reqs.items():
    for q in add_quantities(slot.quantities):             # consolidated per dimension/token
        bucket = bucket_of(q.unit); canon = canon_unit(bucket)
        pos    = [iv for iv in stock if iv.match_name == norm and iv.quantity_base > 0]
        compat = [iv for iv in pos if iv.unit_bucket == bucket]
        incomp = [iv for iv in pos if iv.unit_bucket != bucket]
        need_base = q.amount if (bucket.startswith("opaque:") or q.unit is None) \
                    else to_base(q.amount, q.unit)[0]
        if q.amount is None:
            out.append(GroceryLineDTO(slot.display_item, norm, None, canon, False))
        elif not compat:
            out.append(GroceryLineDTO(slot.display_item, norm, need_base, canon, nettable=(not pos)))
        else:
            have = sum(iv.quantity_base for iv in compat)
            short = need_base - have
            if short <= 0: continue                       # covered -> no line
            out.append(GroceryLineDTO(slot.display_item, norm, short, canon, nettable=(not incomp)))
    if slot.to_taste and norm produced no line above:
        out.append(GroceryLineDTO(slot.display_item, norm, None, None, False))
return out
```

### 4.4 `add_to_inventory_calc(match_name, display_item, amount, unit) -> InventoryDelta`

```
bucket = bucket_of(normalize_unit_token(unit))
canon  = canon_unit(bucket)
a      = max(amount, 0.0)
add_base = a if (bucket.startswith("opaque:") or normalize_unit_token(unit) is None) \
           else to_base(a, unit)[0]
return InventoryDelta(
    # canonical key: normalize the supplied value, or derive from the display item.
    # The router rejects a "" result (422) before it reaches the upsert.
    match_name = normalize_name(match_name) if match_name else normalize_name(display_item),
    unit_bucket = bucket,
    item = display_item,
    normalized_name = normalize_name(display_item),
    add_base = add_base,
    display_unit = unit,                          # opaque token or known unit or None
    canonical_added = Quantity(add_base, canon))
```

The **router** performs the atomic upsert (§5.5).

### 4.5 `deduct_calc(reqs: list[ReqLine], stock: list[StockRow]) -> DeductProposal`

```
groups = aggregate(reqs, M)
row_updates, log = [], []
live = {r.id: r.quantity_base for r in stock}          # working copy

for g in groups:
    canon = canon_unit(g.bucket)

    for ing_id in g.to_taste_members:
        log.append(_entry(item=<row item>, normalized_name=None,
                          requested=None, requested_unit=None,
                          deducted=None, deducted_unit=None, inventory_unit=None,
                          before=None, after=None, applied=False, reason="to taste"))

    if not g.members: continue

    pos    = [r for r in stock if r.match_name == g.norm and live[r.id] > 0]
    compat = sorted([r for r in pos if r.unit_bucket == g.bucket], key=lambda r: r.id)   # deterministic ascending row-ID order (decision SD2)

    if not pos:
        log.append(_entry(item=g.display_item, normalized_name=g.norm,
                          requested=g.need_base, requested_unit=canon,
                          deducted=0.0, deducted_unit=canon, inventory_unit=canon,
                          before=None, after=None, applied=False, reason="not in inventory"))
        continue
    if not compat:
        log.append(_entry(item=g.display_item, normalized_name=g.norm,
                          requested=g.need_base, requested_unit=canon,
                          deducted=0.0, deducted_unit=canon, inventory_unit=canon,
                          before=None, after=None, applied=False,
                          reason="have uncertain (incompatible unit)"))
        continue

    remaining = g.need_base
    for i, r in enumerate(compat):
        before = live[r.id]
        take   = min(remaining, before)
        live[r.id] = before - take
        remaining -= take
        row_updates.append(RowDeduction(r.id, live[r.id]))
        log.append(_entry(item=g.display_item, normalized_name=g.norm,
                          requested=(g.need_base if i == 0 else None), requested_unit=canon,
                          deducted=take, deducted_unit=canon, inventory_unit=canon,
                          before=before, after=live[r.id], applied=True,
                          reason=("ok" if remaining <= 0 else "clamped to 0")))
        if remaining <= 0: break
    # if remaining > 0 after the loop, the last entry already carries reason "clamped to 0"

return DeductProposal(row_updates, log)
```

`_entry(...)` returns a plain `dict` carrying **all eleven keys** every time
(`item, normalized_name, requested, requested_unit, deducted, deducted_unit,
inventory_unit, before, after, applied, reason`), with `null` where the branch
does not populate one. Its signature names all eleven parameters as **required**
(no defaults) — omitting one is a `TypeError` at cook time, not a silently
missing key. The stored column stays `list[dict]`; the read path validates each
entry through `CookDeductionRead` (§5.4).

Cook deliberately does **not** adopt the #N3 uncertainty split — it draws down the
compatible bucket and clamps, logging `"clamped to 0"` for any remainder even when
incompatible-bucket stock exists. It must never silently deduct a `jar` for a
`can`.

---

## 5. HTTP API

### 5.1 Auth — `routers/auth.py`, prefix `/api/auth`

`register` and `login` are **public**; `logout`, `me`, and `change-password`
require a token. The router is built with `route_class=TransactionRoute` (§3.2)
like every other database-touching router.

#### `POST /api/auth/register`

Body `RegisterRequest`:

| Field | Type | Rule |
|---|---|---|
| `username` | `str` | regex `^[A-Za-z0-9_.-]{3,50}$` |
| `password` | `str` | `8 ≤ len ≤ 128` |
| `code` | `str \| None` | required iff `settings.registration_code` is set |

Flow (order matters):

1. Pydantic validation → `422`.
2. `settings.allow_registration is False` → `403 {"detail": "registration disabled"}`.
3. `settings.registration_code` set and `not secrets.compare_digest(code or "", registration_code)`
   → `403 {"detail": "invalid registration code"}`.
4. A user with `lower(username)` already present → `409 {"detail": "username taken"}`.
5. Create `users` row (`password_hash = hash_password(password)`),
   `issue_token`, return **`201 TokenResponse`**.

#### `POST /api/auth/login`

Body `LoginRequest {username: str, password: str}` (JSON, not OAuth2 form).

- Look up by `lower(username) == lower(input)`.
- No user → call `verify_password(password, _DUMMY_HASH)` (discard result), then `401`.
- User found, `verify_password` false → `401`.
- Else `issue_token`, return **`200 TokenResponse`**.
- `401` body: `{"detail": "invalid username or password"}` (same for both failure modes).

#### `POST /api/auth/logout`  — auth required

Delete the `sessions` row for the presented token. **`204`**. (Idempotent enough:
the token is valid or the request would have 401'd in the dependency.)

#### `GET /api/auth/me`  — auth required

**`200 UserRead`** for the current user.

#### `POST /api/auth/change-password`  — auth required

Body `ChangePasswordRequest`:

| Field | Type | Rule |
|---|---|---|
| `current_password` | `str` | must match the stored hash |
| `new_password` | `str` | `8 ≤ len ≤ 128` — the same rule `register` applies |

Flow (order matters):

1. Pydantic validation → `422` (this is where a too-short `new_password` fails).
2. `verify_password(current_password, user.password_hash)` false
   → **`403 {"detail": "incorrect password"}`**. Not `401`: the presented token
   is valid and the *action* is refused, so telling the client to re-authenticate
   would be wrong.
3. `user.password_hash = hash_password(new_password)`.
4. Delete **every** `sessions` row for that user — `DELETE WHERE user_id = :me`,
   including the caller's own. Unconditional, no `AND id != current` special
   case.
5. `issue_token(db, user, settings)` and return **`200 TokenResponse`** — the
   same shape `login` returns.

Consequence, and the point of the endpoint: the device that changed the password
stays signed in on a fresh token; every other device is signed out immediately.
There is no self-service reset — a forgotten password is still an operator task
(§Accepted security posture); this covers the "I know it and want to rotate it"
case, which was previously a `sqlite3` shell job.

#### Schemas

```
UserMini              { id: int, username: str }
UserRead              { id: int, username: str, created_at: datetime }
TokenResponse         { token: str, user: UserRead }
ChangePasswordRequest { current_password: str, new_password: str }   # new_password 8..128
```

---

### 5.2 Recipes CRUD — `routers/recipes.py`, prefix `/api/recipes`

#### Schemas

```
RecipeIngredientIn {
    model_config = ConfigDict(extra="forbid")   # unknown key -> 422 naming the key
    quantity: float | None    # > 0 when set, allow_inf_nan=False
    unit:     str | None      # <= 30
    item:     str | None      # 1..200; REQUIRED for an object element
    note:     str | None      # <= 200
}
# An `ingredients` element may instead be a bare `str` (a pasted line).

RecipeIngredientRead {
    id: int, position: int,
    quantity: float | None, unit: str | None, item: str, note: str | None,
    normalized_name: str, raw_text: str | None
}

RecipeBase {
    title:      str            # 1..200
    notes:      str    = ""
    prep_time:  int | None     # >= 0
    cook_time:  int | None     # >= 0
    servings:   float | None   # > 0, allow_inf_nan=False
    cuisine:    str | None     # <= 100
    source_url: str | None     # <= 500, not URL-validated
    tags:       list[str] = [] # <= 100 items, each <= 50
    steps:      list[str] = [] # <= 100 items, each <= 2000
}

RecipeCreate = RecipeBase + { ingredients: list[RecipeIngredientIn | str] = [] }
RecipeUpdate = RecipeCreate     # PUT fully replaces, including ingredients

RecipeRead   = RecipeBase + {
    id: int, created_at: datetime, updated_at: datetime,
    photo_path: str | None,        # always null in v1
    created_by: UserMini | None,
    ingredients: list[RecipeIngredientRead]   # ordered by position
}
```

#### Ingredient list build (used by `POST` and `PUT`)

```
rows = []
for element in payload.ingredients:
    if isinstance(element, str):
        element = element[:200]                             # bound the pasted line (R-4)
        if element.strip() == "": continue                 # blank pasted line -> skip
        parsed = parse_ingredient(element)
        rows.append({**parsed, "raw_text": element})
    else:
        if not (element.item and element.item.strip()):
            422  "ingredient object requires a non-empty item"
        unit = element.unit
        if unit is not None:
            unit = unit.strip().lower()
            if unit.endswith("."): unit = unit[:-1]     # one trailing period
            unit = unit or None                          # "" / "." -> None
        rows.append({"quantity": element.quantity, "unit": unit,
                     "item": element.item, "note": element.note, "raw_text": None})
for i, r in enumerate(rows):
    RecipeIngredient(position=i, normalized_name=normalize_name(r["item"]), **r)
```

`quantity` from a parsed string is trusted (parser guarantees `> 0` or `None`).
`quantity` from an object element is Pydantic-validated (`> 0` or `None`, finite).

**`unit` normalization is symmetric across both input paths.** The parser
already lower-cases and strips one trailing `.` for string elements; the object
branch above does the same, so `{"unit": "Tbsp."}` and the pasted line
`2 Tbsp. butter` persist the identical author's unit `tbsp`. Neither path
**singularizes**: `cups` stays `cups`. Singularization would contradict the
locked §2.3 oracle, and every consumer that does arithmetic
(`bucket_of`, `add_quantities`, `to_base`) calls `normalize_unit_token` — which
singularizes internally — so the stored value is display text only. `RecipeRead`
is its sole raw consumer, and `2 cup flour` reads wrong.

**`extra="forbid"` on `RecipeIngredientIn` only** (not on every request schema).
It is the one schema where a mistyped key produces a *successful wrong write*
rather than an error: `{"item": "flour", "qty": 500}` would otherwise return
`201` and silently store a to-taste ingredient, because `quantity=None` is a
legitimate value. Elsewhere a dropped key fails on a required field.

**Zero-content recipes are legal, permanently.** Only `title` is required;
`ingredients` and `steps` both default to `[]`, and a title-only `POST` returns
`201`. This is a deliberate capture-now-fill-later flow, and every downstream
path is already total on it: availability returns `lines: []` with
`all_available: true`, grocery generation emits nothing, and `cook` writes
`deductions: []`. There is no minimum-content rule to add.

**Length bound (R-4).** A pasted `str` element is truncated to **200 chars**
before parsing. This is the single guard that keeps every string sink fed by a
pasted line within its column: `raw_text` (`str(300)`), and the parser's
`item` / `note` (`str(200)` each — `item` falls back to the whole cleaned line
when nothing parses). SQLite does not enforce `String(n)`, so without this an
over-length line stores verbatim in v1 and only breaks on a non-SQLite backend.
Object-element `item` / `note` are already Pydantic-bounded and are not
truncated. A pasted element is one ingredient line by contract; 200 is well
above any real line, so this effectively never fires for a well-formed client.

#### Endpoints

| Method / path | Body | Success | Errors |
|---|---|---|---|
| `POST /api/recipes` | `RecipeCreate` | `201 RecipeRead` | `422` |
| `GET /api/recipes` | — | `200 list[RecipeRead]`, order `created_at DESC, id DESC` | — |
| `GET /api/recipes/{id}` | — | `200 RecipeRead` | `404` |
| `PUT /api/recipes/{id}` | `RecipeUpdate` | `200 RecipeRead` (full replace; old ingredient rows deleted via delete-orphan) | `404`, `422` |
| `DELETE /api/recipes/{id}` | — | `204` (cascade ingredients; `cook_logs.recipe_id → NULL`) | `404` |

`created_by_id` is set from `CurrentUser` on `POST` only. `updated_at` auto-bumps on `PUT`.

---

### 5.3 Availability — `GET /api/recipes/{id}/availability`

Query: `multiplier: float = 1.0` — `Query(1.0, gt=0)`, `allow_inf_nan=False` (reject `inf` / `nan` → `422`).

- `404` if the recipe does not exist.
- Router: load recipe + `selectinload(ingredients)`; load **all** `inventory_items`;
  build `list[ReqLine]` with
  `quantity = None if ing.quantity is None else ing.quantity * multiplier`
  (to-taste rows stay `None` — never `None * multiplier`); map inventory
  → `list[StockRow]`; call `check_availability`; assemble:

```
AvailabilityLine  = AvailabilityLineDTO            (same fields, as JSON)
AvailabilityReport {
    recipe_id: int,
    multiplier: float,
    lines: list[AvailabilityLine],
    all_available: bool
}
```

Worked semantics (from §4.2):

| Situation | status | nettable | group_have | group_short |
|---|---|---|---|---|
| compatible stock ≥ need | `ok` | `true` | have | `0` |
| compatible stock < need, **some** positive incompatible-bucket stock | `have_uncertain` | `false` | have | need − have |
| compatible stock < need, **no** incompatible-bucket stock | `short` | `true` | have | need − have |
| no compatible stock, some positive incompatible-bucket stock | `have_uncertain` | `false` | `0` | need |
| no positive stock at all for the match name (incl. only `quantity_base = 0` rows) | `missing` | `false` | `0` | need |
| `quantity is None` member | `to_taste` | `false` | `null` | `null` |

`need` / `need_unit` on each line are **that ingredient row's own** `quantity × M`
in the group's canonical unit. `group_*` are identical across every member line of
a `group_key`. A client summing per-line `need` recovers `group_need`.

---

### 5.4 Cook + made-history

#### `POST /api/recipes/{id}/cook`  → `201 CookLogRead`

Body `CookRequest`:

| Field | Type | Rule |
|---|---|---|
| `multiplier` | `float` | `> 0`, `allow_inf_nan=False`; default `1` |
| `deduct` | `bool` | default `true` |

- `404` if the recipe does not exist.
- Build `CookLog(recipe_id, recipe_title=recipe.title, multiplier, deducted=deduct, cooked_by=user)`.
- `deduct=false` → save log with `deductions=[]`, return.
- `deduct=true` → map recipe ingredients + all inventory rows to DTOs
  (each `ReqLine` built with
  `quantity = None if ing.quantity is None else ing.quantity * multiplier`
  — to-taste rows stay `None`, never `None * multiplier`), call
  `deduct_calc`, then **within the request's single `BEGIN IMMEDIATE` transaction**
  apply every `RowDeduction` (`UPDATE inventory_items SET quantity_base=?, updated_at=? WHERE id=?`,
  binding `_utcnow()` — a Core `UPDATE` does not fire the ORM's `onupdate`),
  set `log.deductions = proposal.log_entries`, save.
- `IntegrityError` / lock timeout → `409` (global handler), whole transaction rolled back.

#### `CookDeductionRead` — Pydantic model; JSON shape of each `deductions[]` entry

A real `BaseModel` (in `schemas/cook_logs.py`), used as
`CookLogRead.deductions: list[CookDeductionRead]`. The DB column stays raw
`JSON list[dict]` (written from `_entry()`); FastAPI validates every stored dict
against this model on read, so a malformed or drifted entry is a loud `500`, not
a silent shape change.

```python
class CookDeductionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")   # stray / renamed key -> 500 on read
    item:            str
    normalized_name: str | None
    requested:       float | None
    requested_unit:  str | None
    deducted:        float | None
    deducted_unit:   str | None
    inventory_unit:  str | None
    before:          float | None
    after:           float | None
    applied:         bool
    reason: Literal["ok", "clamped to 0", "to taste",
                    "not in inventory", "have uncertain (incompatible unit)"]
```

Every entry carries **all** keys; `null` where the branch does not apply.
`item`, `applied`, `reason` are never `null` — set in every branch.

| Key | Type | `ok` / `clamped to 0` | `to taste` | `not in inventory` | `have uncertain (incompatible unit)` |
|---|---|---|---|---|---|
| `item` | str | display | display | display | display |
| `normalized_name` | str \| null | set | `null` | set | set |
| `requested` | float \| null | canonical, **first row of the group only** else `null` | `null` | canonical `group_need` | canonical `group_need` |
| `requested_unit` | str \| null | canonical | `null` | canonical | canonical |
| `deducted` | float \| null | canonical amount taken from this row | `null` | `0` | `0` |
| `deducted_unit` | str \| null | canonical | `null` | canonical | canonical |
| `inventory_unit` | str \| null | canonical | `null` | canonical | canonical |
| `before` | float \| null | canonical | `null` | `null` | `null` |
| `after` | float \| null | canonical | `null` | `null` | `null` |
| `applied` | bool | `true` | `false` | `false` | `false` |
| `reason` | str | `"ok"` \| `"clamped to 0"` | `"to taste"` | `"not in inventory"` | `"have uncertain (incompatible unit)"` |

Invariant on applied entries: `before − deducted == after`.
`requested`/`deducted`/`before`/`after` are all in `inventory_unit`
(`requested_unit == deducted_unit == inventory_unit`).

#### `CookLogRead`

```
CookLogRead {
    id: int,
    recipe_id: int | null,        # null once the recipe is deleted
    recipe_title: str,            # snapshot
    multiplier: float,
    deducted: bool,
    cooked_at: datetime,
    cooked_by: UserMini | null,
    deductions: list[CookDeductionRead]     # [] when deducted=false
}
```

#### `GET /api/recipes/{id}/cook-logs`  → `200 list[CookLogRead]`

Every made-event for the recipe, `order_by(cooked_at DESC, id DESC)`, unpaginated.
`404` if the recipe does not exist.

#### Global reads — `routers/cook_logs.py`, prefix `/api/cook-logs`

| Method / path | Query | Success | Errors |
|---|---|---|---|
| `GET /api/cook-logs` | `limit: int = 50` (`1..200`), `offset: int = 0` (`≥ 0`) | `200 CookLogList` | `422` |
| `GET /api/cook-logs/{log_id}` | — | `200 CookLogRead` (resolves even after the recipe is deleted) | `404` |

```
CookLogList { items: list[CookLogRead], total: int, limit: int, offset: int }
```

`total` = total count of all cook logs, ignoring pagination.
Ordering: `cooked_at DESC, id DESC`.

---

### 5.5 Inventory — `routers/inventory.py`, prefix `/api/inventory`

#### Schemas

```
InventoryItemCreate {              # POST body — additive upsert
    item:       str            # 1..200, required
    quantity:   float          # >= 0, allow_inf_nan=False, required
    unit:       str | None     # <= 30 ; None => COUNT bucket
    match_name: str | None     # <= 200 ; normalize_name(match_name or item); "" after normalize => 422
}

InventoryItemUpdate {             # PATCH body — absolute replacement, model_fields_set-driven
    item:       str | None     # <= 200
    match_name: str | None     # <= 200 ; stored as normalize_name(value); "" after normalize => 422
    quantity:   float | None   # >= 0, allow_inf_nan=False
    unit:       str | None     # <= 30
}

InventoryItemRead {
    id: int, item: str, normalized_name: str, match_name: str,
    unit_bucket: str, quantity_base: float,
    display_unit: str | null,
    display_quantity: float,        # from_base(quantity_base, dim, display_unit); == quantity_base when display_unit is null/opaque
    updated_at: datetime
}
```

For an opaque bucket, `display_unit` is always the opaque token and
`display_quantity == quantity_base`. For a COUNT row with no preference,
`display_unit` is `null` and `display_quantity == quantity_base`.

#### `GET /api/inventory`  → `200 list[InventoryItemRead]`

All rows, `order_by(match_name ASC, unit_bucket ASC)`.

#### `POST /api/inventory`  → `201 InventoryItemRead`

Additive upsert via `add_to_inventory_calc` + the SQL below (SQLAlchemy
`sqlite_insert(...).on_conflict_do_update(...)`), inside the request transaction:

```
delta = add_to_inventory_calc(body.match_name, body.item, body.quantity, body.unit)
if not delta.match_name:                              422  "match_name normalizes to empty"

now = _utcnow()                                   # bound explicitly - see below

INSERT INTO inventory_items
      (item, normalized_name, match_name, unit_bucket, quantity_base, display_unit, created_by_id, updated_at)
VALUES (:item, :normalized_name, :match_name, :unit_bucket, :add_base, :display_unit, :user_id, :now)
ON CONFLICT (match_name, unit_bucket) DO UPDATE SET
      quantity_base = inventory_items.quantity_base + excluded.quantity_base,
      display_unit  = COALESCE(excluded.display_unit, inventory_items.display_unit),
      updated_at    = :now
RETURNING *;
```

`updated_at` binds a Python `_utcnow()` value on **both** branches. This
statement is an `INSERT … ON CONFLICT`, so it bypasses the ORM's
`onupdate=_utcnow` by construction; SQLite's `CURRENT_TIMESTAMP` is not an
option because it is naive and second-precision (§1). One clock produces every
timestamp in the system, whichever path wrote the row.

`item` / `normalized_name` / `created_by_id` are **not** touched on conflict.
`POST` can never 409 on the composite key (it upserts that key by definition).
`quantity_base` stays `≥ 0` and finite (`CHECK`).

#### `PATCH /api/inventory/{id}`  → `200 InventoryItemRead`

`404` if the row does not exist. `S = body.model_fields_set`.

```
if not S:                                             return read(row)          # 200 no-op

for f in ("item", "match_name", "quantity"):
    if f in S and getattr(body, f) is None:           422  f"{f} cannot be null"

if "quantity" in S and "unit" not in S:               422  "unit is required when setting quantity"   # decision S2

if "unit" in S:
    if bucket_of(normalize_unit_token(body.unit)) != row.unit_bucket:
                                                      422  "unit changes the bucket; remove and re-add"
    # (covers unit:null on a non-COUNT row -> 422 ; unit:null on a COUNT row -> ok)

if "match_name" in S:
    nm = normalize_name(body.match_name)               # canonical key, not strip
    if nm == "":                                       422  "match_name normalizes to empty"
    if a *different* row exists with (nm, row.unit_bucket):
                                                      409  "match_name already in use for this bucket"

# ---- apply (all within the single BEGIN IMMEDIATE transaction) ----
if "quantity" in S:
    a = max(body.quantity, 0.0)
    row.quantity_base = a if (row.unit_bucket.startswith("opaque:") or normalize_unit_token(body.unit) is None) \
                        else to_base(a, body.unit)[0]     # ABSOLUTE set, canonical
if "unit" in S:        row.display_unit = body.unit        # preference only
if "match_name" in S:  row.match_name  = nm
if "item" in S:        row.item = body.item; row.normalized_name = normalize_name(body.item)
row.updated_at = _utcnow()
return read(row)                                           # display_quantity recomputed
```

Examples:

| Request | Effect |
|---|---|
| `{"quantity": 200, "unit": "g"}` on a `mass` row | `quantity_base = 200` |
| `{"quantity": 0.2, "unit": "kg"}` on a `mass` row | `quantity_base = 200` |
| `{"unit": "kg"}` on a `mass` row | `display_unit = "kg"`, `quantity_base` unchanged, `display_quantity` recomputed |
| `{"quantity": 200}` (no unit) | `422` |
| `{"unit": "can"}` on a `mass` row | `422` (bucket change) |
| `{"unit": null}` on a `mass` row | `422`; on a `count` row → sets `display_unit = null` |
| `{"match_name": " Flour "}` on a `mass` row | stored as `flour` (normalized) |
| `{"match_name": "flour"}` colliding with another `(flour, mass)` row | `409` |
| `{"match_name": "!!!"}` (normalizes to `""`) | `422` |
| `{}` | `200`, unchanged |

#### `DELETE /api/inventory/{id}`  → `204`

`404` if the row does not exist. Hard delete.

---

### 5.6 Grocery lists — `routers/grocery.py`, prefix `/api/grocery`

#### Schemas

```
GroceryListCreate {
    name:        str | None                       # default "Groceries <UTC date>"
    recipe_ids:  list[int]                         # non-empty, unique, every id must exist  -> else 422
    multipliers: dict[int, float] = {}             # each > 0 finite ; keys ⊆ recipe_ids     -> else 422
}

GroceryListItemIn {                               # POST .../items  (manual)
    item:     str            # 1..200
    quantity: float | None   # > 0 when set, finite
    unit:     str | None     # <= 30
}

GroceryListItemUpdate {                           # PATCH .../items/{id}
    checked:  bool | None
    quantity: float | None   # > 0 when set, finite
    unit:     str | None
    item:     str | None
    # quantity + unit are an atomic pair: if either key is present in the
    # request body, both must be (values may be null) -> else 422 (N6).
}

GroceryListItemRead {
    id: int, item: str, normalized_name: str,
    quantity: float | null, unit: str | null,
    checked: bool, checked_at: datetime | null, submitted_at: datetime | null,
    source: "generated" | "manual", nettable: bool,
    added_to_inventory: bool,
    applied_quantity: float | null, applied_unit: str | null
}

GroceryListRead {
    id: int, name: str, status: "active" | "archived",
    source_recipe_ids: list[int], created_at: datetime,
    created_by: UserMini | null,
    items: list[GroceryListItemRead]        # ordered by id
}
```

#### `POST /api/grocery`  → `201 GroceryListRead`

1. Validate `recipe_ids` non-empty + unique + all exist → else `422`.
2. Validate `multipliers` keys ⊆ `recipe_ids`, values `> 0` finite → else `422`.
3. For each recipe (in `recipe_ids` order) build `list[ReqLine]` with
   `quantity = None if ing.quantity is None else ing.quantity * multipliers.get(rid, 1)`
   (to-taste rows stay `None` — never `None * multiplier`).
4. Load all inventory → `list[StockRow]`. Call `generate_lines`.
5. Persist `GroceryList(name or default, status="active", source_recipe_ids=recipe_ids)`
   with one `GroceryListItem(source="generated", checked=false, added_to_inventory=false)`
   per `GroceryLineDTO` (`quantity` / `unit` canonical, `nettable` from the DTO,
   `normalized_name` from the DTO).

Netting summary (from §4.3):

| Requirement vs positive stock | line emitted | `nettable` |
|---|---|---|
| compatible stock covers it | none | — |
| compatible short, no incompatible stock | shortfall, canonical | `true` |
| compatible short, incompatible stock present | **compatible-bucket remainder**, canonical | `false` |
| no compatible stock, incompatible stock present | full need, canonical | `false` |
| no positive stock at all | full need, canonical | `true` |
| requirement has no amount (opaque/None, unquantified) | line with `quantity = null` | `false` |
| ingredient is entirely to-taste | line with `quantity = null, unit = null` | `false` |

#### `GET /api/grocery`  → `200 list[GroceryListRead]`

Optional `?status=active|archived`. Order `created_at DESC, id DESC`.

#### `GET /api/grocery/{id}`  → `200 GroceryListRead`  (`404`)

#### `DELETE /api/grocery/{id}`  → `204`

Any status. Cascades items.

#### `POST /api/grocery/{id}/items`  → `201 GroceryListItemRead`

`404` if the list does not exist. `409` if the list is `archived`.
Creates `GroceryListItem(source="manual", nettable=true, checked=false,
added_to_inventory=false, normalized_name=normalize_name(item))`.
Manual amounts are stored exactly as typed.

#### `PATCH /api/grocery/{id}/items/{item_id}`  → `200 GroceryListItemRead`

- `404` if the list or the line does not exist.
- `409` if `line.added_to_inventory` (frozen) **or** `list.status == "archived"`.
- `422` if exactly one of `quantity` / `unit` is present in the request body
  (`model_fields_set`) — they are an atomic pair: `"quantity and unit must be
  set together"` (N6). Values may be `null`; both keys must appear together.
- Apply supplied fields:
  - `quantity` + `unit` given → set as-is, no conversion. A unit-only edit
    (`500 g` line + `{"unit": "kg"}`) is rejected by the rule above, so the
    stored number always matches the unit the caller sent.
  - `item` given → set + recompute `normalized_name`.
  - `checked` given → set; `checked_at = _utcnow()` when `true`, `null` when `false`.
- **Any `item` / `quantity` / `unit` edit reclassifies the line** (N6):
  `source → "manual"`, `nettable → true`. The solver's shortfall claim is void
  once a human overrides the substance of a generated line, so it is treated as
  hand-entered. A `checked`-only PATCH does **not** reclassify.
- No inventory side effect. Nothing reaches stock until `submit`.

#### `DELETE /api/grocery/{id}/items/{item_id}`  → `204`  (decision S5)

`404` if the list or line does not exist. `409` if `line.added_to_inventory` or
`list.status == "archived"`.

#### `POST /api/grocery/{id}/submit`  → `200 GroceryListRead`

`404` if the list does not exist. `409` if `list.status != "active"`.
Inside the request's single `BEGIN IMMEDIATE` transaction:

```
for line in list.items:
    if (not line.checked) or line.added_to_inventory or (line.quantity is None):
        continue
    delta = add_to_inventory_calc(normalize_name(line.item), line.item, line.quantity, line.unit)
    <perform the ON CONFLICT upsert from §5.5 with delta>
    line.applied_quantity, line.applied_unit = delta.canonical_added.amount, delta.canonical_added.unit
    line.added_to_inventory = True
    line.submitted_at = _utcnow()
# status is NOT changed
```

- Forward-only. Already-applied lines are skipped ⇒ re-submitting picks up only
  newly-checked lines (shop today, finish tomorrow).
- `submit` with nothing eligible → `200`, list unchanged (explicit no-op).
- A checked `nettable=false` line **with** a real `quantity` **is** added (the flag
  informs the shopper, it does not block submit). A checked line with
  `quantity = null` is silently skipped.
- `IntegrityError` / lock timeout → `409`, whole transaction rolled back.

#### `POST /api/grocery/{id}/archive`  → `200 GroceryListRead`

`404` if the list does not exist. Guarded, idempotent-ish:

```
UPDATE grocery_lists SET status='archived' WHERE id=:id AND status='active';
```

If `rowcount == 0` (already archived) → `409 {"detail": "list is not active"}`.
This is the **only** path to `archived`. A `PATCH` / `submit` / item-`DELETE` /
item-`POST` on an archived list → `409`.

---

## 6. Concurrency & transactions

- **Every** request-scoped SQLite transaction opens with `BEGIN IMMEDIATE`
  (§3.2). Reads, the auth `last_used_at` bump, and mutations all take the write
  lock before their first `SELECT`.
- **`TransactionRoute` (§3.2) owns the commit.** It runs the endpoint, then
  commits, then returns the response — so the commit happens *inside* the
  exception-handling window and *before* the response is sent.
- `get_db` owns session lifetime, not the commit: it stashes the session on
  `request.state.db`, `rollback()`s on any exception, and always `close()`s. It
  no longer commits after `yield`, because post-`yield` code runs after the
  response is generated, where a raised exception can no longer be converted.
- **Routers never call `commit()`.** They `flush()` for exactly one reason: to
  obtain a generated id. `flush()` is no longer load-bearing for error handling
  — it used to be the only reason a constraint violation happened to surface
  correctly, and it never covered `SQLITE_BUSY` at `COMMIT` at all.
- **A commit-time failure converts like any other.** An `IntegrityError` or an
  `OperationalError: database is locked` raised by `COMMIT` reaches the global
  handlers and returns `409`. It is never a `500`, and — the defect this
  replaces — never a `200` with the write discarded.
- Unchanged: a route raising `HTTPException(404)` still rolls back, so
  `get_current_user`'s `last_used_at` bump is lost on an error response.
- The auth bump and a route's mutation are therefore **one** transaction, so
  `last_used_at` persists even on plain authenticated `GET`s.
- `services/` functions are pure and propose DTOs; the router applies the proposal
  and holds the transaction. A mid-operation failure rolls back the whole thing —
  no half-applied cook, no partly-submitted grocery list.
- `IntegrityError` and `OperationalError: database is locked` → **409** via the
  global handlers (`main.py`), never surfaced as 500.
- `PRAGMA busy_timeout=5000` — a brief writer overlap waits rather than erroring.

---

## 7. Acceptance criteria / test matrix

Every phase ends with `cd backend && uv run pytest` green. `conftest.py` builds
the app through the factory — `create_app(test_settings, test_engine)` — with
`test_settings.allow_registration = true` and a fixed `test_settings.registration_code`
(so the "requires the configured code when enabled" path is exercised; the
anonymous `client` fixture supplies that code), over an in-memory `StaticPool`
engine carrying the same `connect` / `begin` listeners. **No `dependency_overrides`.**
Fixtures: `user` (registers a default user), `auth_client` (**new default**,
`Authorization` preset), `client` (anonymous, for auth/401 tests).

### Locked contract oracles (R-7)

These cases are authored and accepted independently before their owning
production pass under `plan.md` §Independent contract-test gate. They are
black-box contracts, not implementation sketches. The implementation pass may
add cases but may not alter these expected values.

#### Availability

Shorthand used only in this table:

- `R(id, item, norm, amount, unit)` = `ReqLine`.
- `S(id, norm, bucket, base)` = `StockRow`.
- `A(id, need, unit, group_need, group_have, group_short, status, nettable)` =
  one `AvailabilityLineDTO`. Its `item` comes from that requirement;
  `group_key = f"{norm}|{bucket_of(unit)}"` and `group_unit = unit`.

Unless shown otherwise, requirements use `item="Tomatoes"`, `norm="tomato"`.
Groups are emitted in first-seen order. Within a group, to-taste lines are
emitted first in their stored order, followed by quantified members in stored
order, matching §4.2.

| Case | Requirements | Stock | Exact availability outputs |
|---|---|---|---|
| missing | `[R(1,"Tomatoes","tomato",3,"can")]` | `[]` | `[A(1,3,"can",3,0,3,"missing",false)]` |
| compatible short | same as missing | `[S(10,"tomato","opaque:can",1)]` | `[A(1,3,"can",3,1,2,"short",true)]` |
| mixed-bucket uncertain short | same as missing | `[S(10,"tomato","opaque:can",1), S(11,"tomato","opaque:jar",1)]` | `[A(1,3,"can",3,1,2,"have_uncertain",false)]` |
| compatible fully covers despite other bucket | same as missing | `[S(10,"tomato","opaque:can",3), S(11,"tomato","opaque:jar",1)]` | `[A(1,3,"can",3,3,0,"ok",true)]` |
| only incompatible | same as missing | `[S(11,"tomato","opaque:jar",1)]` | `[A(1,3,"can",3,0,3,"have_uncertain",false)]` |
| zero stock is absent | same as missing | `[S(10,"tomato","opaque:can",0)]` | `[A(1,3,"can",3,0,3,"missing",false)]` |
| duplicate members aggregate once | `[R(1,"Tomatoes","tomato",2,"can"), R(2,"Canned tomato","tomato",1,"can")]` | `[S(10,"tomato","opaque:can",2)]` | `[A(1,2,"can",3,2,1,"short",true), A(2,1,"can",3,2,1,"short",true)]` |
| canonical mass | `[R(1,"Flour","flour",1,"kg")]` | `[S(10,"flour","mass",500)]` | `[A(1,1000,"g",1000,500,500,"short",true)]` |
| to taste | `[R(1,"Salt","salt",null,"can")]` | `[]` | `[A(1,null,"can",null,null,null,"to_taste",false)]` |

The router's `all_available` is true only for the fully-covered row above and
for an empty/all-to-taste report; it is false for every other quantified case.

#### Grocery generation

`G(item, norm, quantity, unit, nettable)` means one `GroceryLineDTO`.
Requirements use the `R(...)` shorthand above; the outer list preserves
`recipe_ids` order. Output order is exact first-seen normalized-name then
first-seen `add_quantities` partition order.

| Case | Requirements by recipe | Stock | Exact output |
|---|---|---|---|
| missing opaque | `[[R(1,"Tomatoes","tomato",2,"can")]]` | `[]` | `[G("Tomatoes","tomato",2,"can",true)]` |
| compatible partial | same as missing opaque | `[S(10,"tomato","opaque:can",1)]` | `[G("Tomatoes","tomato",1,"can",true)]` |
| mixed-bucket partial | `[[R(1,"Tomatoes","tomato",3,"can")]]` | `[S(10,"tomato","opaque:can",1), S(11,"tomato","opaque:jar",1)]` | `[G("Tomatoes","tomato",2,"can",false)]` |
| only incompatible | same as missing opaque | `[S(11,"tomato","opaque:jar",1)]` | `[G("Tomatoes","tomato",2,"can",false)]` |
| fully covered | same as missing opaque | `[S(10,"tomato","opaque:can",3), S(11,"tomato","opaque:jar",1)]` | `[]` |
| cross-recipe known consolidation | `[[R(1,"Flour","flour",1,"kg")], [R(2,"Plain flour","flour",500,"g")]]` | `[S(10,"flour","mass",200)]` | `[G("Flour","flour",1300,"g",true)]` |
| first-seen partition order | `[[R(1,"Tomatoes","tomato",2,"can"), R(2,"Tomatoes","tomato",500,"g")]]` | `[]` | `[G("Tomatoes","tomato",2,"can",true), G("Tomatoes","tomato",500,"g",true)]` |
| only to taste | `[[R(1,"Salt","salt",null,null)]]` | `[]` | `[G("Salt","salt",null,null,false)]` |

#### Deduction

`D(row_id, new_base)` means one `RowDeduction`. `L(requested, deducted,
before, after, applied, reason)` abbreviates a log entry for `item="Tomatoes"`,
`normalized_name="tomato"`, and canonical `requested_unit`, `deducted_unit`,
and `inventory_unit` `="can"`. Every actual entry has all eleven keys. Output
and log order are exact.

| Case | Requirements | Stock | Exact row updates | Exact log values |
|---|---|---|---|---|
| not in inventory | `[R(1,"Tomatoes","tomato",3,"can")]` | `[]` | `[]` | `[L(3,0,null,null,false,"not in inventory")]` |
| only incompatible | same as above | `[S(11,"tomato","opaque:jar",2)]` | `[]` | `[L(3,0,null,null,false,"have uncertain (incompatible unit)")]` |
| enough compatible | same as above | `[S(10,"tomato","opaque:can",5)]` | `[D(10,2)]` | `[L(3,3,5,2,true,"ok")]` |
| clamp compatible | same as above | `[S(10,"tomato","opaque:can",2)]` | `[D(10,0)]` | `[L(3,2,2,0,true,"clamped to 0")]` |
| compatible wins over incompatible | same as above | `[S(10,"tomato","opaque:can",1), S(11,"tomato","opaque:jar",9)]` | `[D(10,0)]` | `[L(3,1,1,0,true,"clamped to 0")]` |
| ascending row-ID draw | same as above | `[S(20,"tomato","opaque:can",2), S(10,"tomato","opaque:can",2)]` | `[D(10,0), D(20,1)]` | `[L(3,2,2,0,true,"clamped to 0"), L(null,1,2,1,true,"ok")]` |

For a to-taste requirement, deduction produces no row update and one log entry
whose `item="Salt"`, `normalized_name`, all quantity/unit and before/after
fields are `null`, `applied=false`, and `reason="to taste"`.

#### Add-to-inventory proposal

| Inputs `(match_name, display_item, amount, unit)` | Exact proposal fields |
|---|---|
| `(null, "Flour", 1, "kg")` | `match_name="flour"`, `unit_bucket="mass"`, `item="Flour"`, `normalized_name="flour"`, `add_base=1000`, `display_unit="kg"`, `canonical_added=(1000,"g")` |
| `(" Tomatoes ", "Canned Tomatoes", 2, "cans")` | `match_name="tomato"`, `unit_bucket="opaque:can"`, `item="Canned Tomatoes"`, `normalized_name="canned tomato"`, `add_base=2`, `display_unit="cans"`, `canonical_added=(2,"can")` |
| `("flour", "Flour", -2, "g")` | `add_base=0`, `canonical_added=(0,"g")` (pure-service clamp; HTTP validation rejects the negative input) |

#### Interpretation-independent checks

- For each availability group, every quantified member repeats the same exact
  `group_*`, status, and `nettable` values; stock is never spent once per member.
- `deduct_calc` never emits a negative `new_quantity_base`; for every applied
  entry, `before - deducted == after` within the §2 tolerance.
- Grocery output never has a negative quantity; compatible positive stock that
  fully covers a requirement emits no line.
- Reordering inventory input does not change availability or grocery values;
  deduction order is determined by ascending row ID, not input order.

| File | Must assert |
|---|---|
| `test_normalize.py` | every locked §2.1 input/output row exactly; descriptor and identity-bearing lists; final-token-only singularization; punctuation/whitespace; degenerate empty result. Global idempotence is deliberately **not** asserted (D1). |
| `test_units.py` | every locked §2.2 conversion and `add_quantities` row, including exact output order, plus every listed invariant using the specified tolerance; plurals/abbrevs; unknown → `None`; cross-dimension incompatible; `dozen`/`pair`; `bucket_of` / `canon_unit`. **R-3 — plural round-trip:** for every synonym-table token, `parse_unit(plural) is parse_unit(singular_key)`; for every deliberately-opaque token, `normalize_unit_token(plural) == normalize_unit_token(singular)`. `boxes → box`, `bunches → bunch`, `dashes → dash`, `splashes → splash`, `pinches → pinch` asserted explicitly (a bare trailing-`s` strip would leave `boxe` / `dashe` and split the opaque bucket). |
| `test_ingredient_parse.py` | the 7-row acceptance table in §2.3 exactly; the deterministic adversarial corpus never raises and always returns a non-empty `item` plus `quantity=None` or a positive finite float; unicode `½`; mixed `1 1/2` → `1.5`; garbage → raw fallback. |
| `test_inventory_math.py` | every locked §7 availability, grocery-generation, deduction, add-to-inventory, and invariant case. Also: `clove` need vs `bulb` stock → `have_uncertain`; canonical `requested`/`deducted`/`deducted_unit`; kg-from-g (stock `2000 g`, recipe `1 kg` → `deducted 1000`, `after 1000`, all `g`); every log entry has all 11 keys and each round-trips through `CookDeductionRead` (`_entry` requires every kwarg — a missing one is a `TypeError`) (N7). |
| `test_auth.py` | anonymous `client`. register `201` / `409` dup / `409` **case-insensitive** dup (`Alice` vs `alice`) / `403` when `allow_registration=false` / `403` wrong `code` when configured / `422` short pw / `422` bad username. login `200` + token / `401` bad pw / `401` unknown user. logout invalidates. **Five `get_current_user` 401s:** missing header, malformed (`"garbage"`), wrong scheme (`"Basic xyz"`), unknown token, expired — each on a gated route and on `/me`; `/me` `200` with a good token. **The expired case is produced by building the app with `Settings(session_ttl_days=0)` and issuing a token through the real login route**, not by reaching into the database and rewriting `expires_at`; that reach-around is deleted (it only existed because `issue_token` read the module-level settings). **`change-password`:** wrong `current_password` → `403 {"detail": "incorrect password"}`; `new_password` shorter than 8 → `422`; success → `200 TokenResponse` whose token authenticates, the caller's old token → `401`, and a second device's token issued before the change → `401`. **Datetimes:** `created_at` in every `UserRead` ends with an explicit UTC offset. |
| `test_validation.py` | negative / `0` / `inf` / `nan` rejected `422` on: recipe ingredient `quantity`, inventory `POST`/`PATCH` `quantity`, `cook` `multiplier`, grocery `multipliers`, `availability?multiplier=`. `recipe_ids` empty or with a duplicate → `422`. A `multipliers` key not in `recipe_ids` → `422`. |
| `test_recipes.py` | `auth_client`. nested create/read (positions 0..n-1, computed `normalized_name`); **string elements in `ingredients` are parsed and `raw_text` stored; object elements store `raw_text=null`; blank string elements skipped**; a pasted line > 200 chars is truncated to 200 before parsing — `raw_text`, `item`, and `note` all fit their columns and the recipe still creates (no 422) (R-4); PUT clears old ingredient rows; steps/tags round-trip; `DELETE` cascades ingredients and nulls `cook_logs.recipe_id`. the happy-path recipe includes a to-taste line (`"salt to taste"` → `quantity=None`); `/availability?multiplier=2` — per-line `need` + `group_*` canonical, `group_unit` present, no `have`/`short` on the line; the to-taste line survives `multiplier` scaling (no `TypeError`) and reports `status="to_taste"`; cook-to-zero food → `missing`. `/cook` writes a `CookLog` and mutates inventory (clamp; incompatible bucket); the to-taste line yields a `"to taste"` deduction entry and is never applied; every deduction entry validates against `CookDeductionRead` — all 11 keys present, `reason` in the allowed `Literal` set, `null` only where the §5.4 table permits; a stored entry with an extra/unknown key or an unlisted `reason` → `500` on read (N7); `"ok"`, `"clamped to 0"`, `"not in inventory"`, `"have uncertain (incompatible unit)"`, `"to taste"` each exercised at least once across the cook tests; `cook {deduct:false}` leaves inventory untouched but still writes a `CookLog`; `GET .../cook-logs` newest-first across both modes. **Unit normalization (both paths):** an object element `{"unit": "Tbsp."}` and the pasted line `2 Tbsp. butter` both store `unit == "tbsp"`; `{"unit": "cups"}` stores `cups` (no singularization). **Unknown key:** `{"item": "flour", "qty": 500}` → `422` naming `qty` (never a `201` storing a to-taste row). **Zero content:** a title-only `POST` → `201` with `ingredients: []` and `steps: []`, and its `/availability` returns `lines: []` with `all_available: true`. **Datetimes:** a freshly created recipe has `created_at == updated_at`, both ending in an explicit UTC offset; a `PUT` advances `updated_at` past `created_at`. |
| `test_transactions.py` | **Commit-time failure → `409`.** Prior art: `test_exception_handlers.py`, which builds a local app and attaches a throwaway route. Do the same with a route that leaves the session in a state that fails at `COMMIT` (not at `flush()`), and assert `409 {"detail": "conflict"}` — today's tests raise from inside a route *body*, the path where handlers already worked, so this is the uncovered half. Also assert the written row is absent afterwards. **Route-class guard:** iterate `built_app.routes` and assert every `APIRoute` under `/api` that depends on `get_db` is a `TransactionRoute`. This is the only mechanism that fails when a later phase adds a router and forgets `route_class=`; a behavioral test passes, because the bug is silent by construction. `/api/health` is exempt (no database dependency). |
| `test_config.py` | Direct construction, no HTTP — prior art: `test_engine_listeners.py`. `Settings(session_ttl_days=-1)` raises `ValidationError`; `session_ttl_days=0` is accepted; the default is `30`. |
| `test_cook_logs.py` | `auth_client`. `GET /api/cook-logs` paginates newest-first across recipes (`limit`/`offset`, `total`); `GET /api/cook-logs/{id}` returns one; both still resolve after the recipe is deleted (`recipe_id` null, `recipe_title` stands). |
| `test_inventory.py` | `auth_client`. `POST` additive upsert (two `POST`s to the same `(match_name, unit_bucket)` sum in `quantity_base`; `POST` missing `item` or `quantity` → `422`). `PATCH {quantity:200, unit:"g"}` absolute set; `PATCH {unit:"kg"}` display-only change (`quantity_base` untouched, `display_quantity` changes); **`PATCH {quantity:200}` with no unit → `422`**; `PATCH {unit:"can"}` on a mass row → `422`; `PATCH {unit:null}` on a non-COUNT row → `422`, on a COUNT row → `200`; `PATCH {item:null}` / `{quantity:null}` / `{match_name:null}` → `422`; `PATCH {}` → `200` no-op; `PATCH {match_name:...}` onto an occupied `(match_name, unit_bucket)` → `409`; add → cook → `GET` shows `display_quantity` recomputed from the reduced `quantity_base`; composite uniqueness; cross-unit add merges via `quantity_base`; same food in two incompatible units → two rows; editing `match_name` re-points matching; negative / non-finite qty → `422`. **N5 — `match_name` is canonical:** `POST` / `PATCH` `match_name` `" Flour "` or `"FLOUR"` is stored as `flour` (matches a recipe ingredient whose canonical name is `flour`); `match_name` that normalizes to `""` (`"  "`, `"!!!"`) → `422`; `PATCH {match_name}` whose *normalized* value collides with a different `(match_name, unit_bucket)` row → `409`; two `POST`s with `match_name` `"Flour"` then `"flour"` (same unit) hit the same row (additive), not two rows. |
| `test_grocery.py` | generate from 2 selected recipes (consolidation + netting; generated `quantity`/`unit` canonical; a to-taste ingredient (`quantity=None`) in a selected recipe survives `multipliers` scaling (no `TypeError`) and emits a `quantity=null, unit=null` line; food cooked to `quantity_base=0` still produces a full-need line); manual item add (amounts as typed); check off → inventory unchanged; edit a checked line then `submit` → inventory reflects the edited value; `POST /submit` → inventory up + line frozen (`added_to_inventory`, canonical `applied_quantity`); `PATCH` a frozen line → `409`; `DELETE` a frozen line → `409`; `DELETE` an unfrozen line → `204`; uncheck before submit → no-op; `submit` does **not** archive — check a further line and re-submit picks it up; `submit` with nothing checked → `200` no-op; `POST /archive` → `status=archived`, later `PATCH`/`submit`/item-`POST`/item-`DELETE` → `409`; sequential double-submit idempotency; delete list cascades items; non-nettable line present; #N3: `need 3 can / 1 can + 1 jar` → a `2 can` line `nettable=false`; `1 can` only → `nettable=true`. **N6 — atomic quantity/unit + reclassify:** on a generated `500 g` line, `PATCH {unit:"kg"}` alone → `422`, `PATCH {quantity:200}` alone → `422`; `PATCH {quantity:0.5, unit:"kg"}` → `200`, line now `source="manual"`, `nettable=true`, and `submit` adds the `0.5 kg` the caller sent (not `500 kg`); `PATCH {item:"almond flour"}` on a generated `nettable=false` line → `source="manual"`, `nettable=true`, `normalized_name` recomputed; `PATCH {checked:true}` alone leaves `source`/`nettable` unchanged. |
| `test_concurrency.py` | **file-backed SQLite (`tmp_path`), two independent engines/connections.** Assert the properties that make the lost update *impossible*, not the lost update itself: with `BEGIN IMMEDIATE` on every transaction (§3.2) the interleave is unconstructable, so a test that tries to build it can only pass vacuously. Required: (1) **serialization** — A begins and writes uncommitted; B's `BEGIN` blocks and, with `busy_timeout` lowered for the test, raises `OperationalError: database is locked`; (2) **the `409` mapping** — that error, raised through an HTTP request, returns `409` and not `500` (this exercises `_to_409_if_locked_else_500`, which nothing else covers); (3) **freshness** — after A commits, B's retry reads A's committed value. Keep one threaded two-`cook` HTTP smoke test through `TestClient` (final `quantity_base` correct, both `CookLog`s honest) as a coarse check, but it is not the guard. |

### End-to-end verification (via `/docs`)

```
cd backend && rm -f recipe.db
RECIPE_ALLOW_REGISTRATION=true RECIPE_REGISTRATION_CODE=devcode uv run uvicorn app.main:app --reload
```

1. `POST /api/auth/register {username, password, code:"devcode"}` → copy token → Authorize.
   **Stop the server, restart without those two env vars.** A second `POST /api/auth/register` → `403`.
2. `POST /api/recipes` with a mix of pasted-string and structured ingredient rows (include one to-taste line, e.g. `"salt to taste"`) + `steps`; `GET` it back nested and ordered. Later `availability` / `cook` / `grocery` on this recipe must not `TypeError` on the to-taste line.
3. `POST /api/inventory` `{item:"flour", quantity:500, unit:"g"}` and `{item:"tomatoes", quantity:1, unit:"can"}`.
   A second `POST` `{item:"flour", quantity:250, unit:"g"}` → the flour row `quantity_base = 750`.
   `PATCH /api/inventory/{flour_id} {quantity:200, unit:"g"}` → `quantity_base = 200`.
   `PATCH {unit:"kg"}` → `display_quantity` becomes `0.2`, `quantity_base` still `200`.
   `PATCH {quantity:200}` (no unit) → `422`. `PATCH {unit:"can"}` → `422`.
   `GET /api/recipes/{id}/availability?multiplier=1` → per-line `need` + `group_*` canonical with `group_unit`; `have_uncertain` only when positive stock sits in an incompatible unit.
4. `POST /api/recipes/{id}/cook {multiplier:1}` → inventory `quantity_base` drops; `CookLog` has canonical `requested`/`deducted`/`deducted_unit`/`before`/`after` and `before − deducted == after`.
   Cook a food to `0` → follow-up `availability` reports it `missing`; `POST /api/grocery` emits a full-need line for it.
5. `POST /api/grocery {recipe_ids:[id]}` → only shortfalls, consolidated, canonical `quantity`.
   `PATCH` a line `{checked:true}` → inventory unchanged, `source`/`nettable` unchanged.
   `PATCH` a generated line `{unit:"kg"}` alone → `422`; `{quantity, unit}` together → `200`,
   line flips to `source:"manual"`, `nettable:true`.
   `POST /api/grocery/{id}/submit` → inventory rises, line `added_to_inventory` + canonical `applied_quantity` set, **`status` still `active`**.
   Check another line, `submit` again → only that line added. `PATCH` / `DELETE` a frozen line → `409`.
6. `POST /api/grocery/{id}/archive` → `status:archived`; further `PATCH` / `submit` → `409`.
7. `POST /api/recipes/{id}/cook {multiplier:1, deduct:false}` → inventory unchanged, entry in `GET /api/recipes/{id}/cook-logs`.
8. `GET /api/cook-logs` newest-first across recipes; `GET /api/cook-logs/{id}` returns one; delete that recipe → the log still resolves.
9. Any data route with no / malformed (`garbage`) / wrong-scheme (`Basic x`) / unknown / expired token → `401`.
   `POST /api/auth/change-password` with a wrong `current_password` → `403`; with a correct one → `200` and a new token; re-Authorize with it, and the previous token → `401`.
   Every `created_at` / `updated_at` in the responses above ends with `+00:00`.
10. Recipe ingredient `quantity: -1` or `0`, grocery `multiplier: 0` / `inf` → `422`.
