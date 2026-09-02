# Informal Frontend Spec — v1

> **Superseded (2026-09-01).** The normative frontend contract is now
> [`spec.md`](spec.md), with delivery sequence in [`plan.md`](plan.md) and
> rationale in [`decisions.md`](decisions.md). This file is kept as background
> — the opportunity map (§2), risk register (§4), and API mirror (§6) that the
> formal spec was built from. When it disagrees with `spec.md`, `spec.md` wins.

> **Partition notice — read before editing anything here.**
>
> - This file and everything under `docs/frontend/` is **frontend-only**,
>   **informal**, and **non-normative**.
> - **Backend-implementation agents and phases must not read this as authority,
>   satisfy a requirement from it, or edit it.** The backend scope fence
>   (`../plan.md` §"Phase scope fence and handoff contract") names
>   `docs/frontend/` as off-limits.
> - The backend contract lives in [`../spec.md`](../spec.md). When this file and
>   `spec.md` disagree, **`spec.md` wins** — fix this file.
> - Nothing here schedules or gates backend work. It does not add a backend
>   model, field, route, dependency, or config option.

---

## 1. Purpose and boundaries

Backend v1 (`../plan.md`) is deliberately backend-only; there is no frontend
phase and the existing React skeleton does not work against the v1 API. This
document is the staging ground for frontend work that can proceed **in
parallel** with backend Phases 2–7, without touching backend docs or code.

It answers two questions:

1. **What frontend work can start now**, against a spec that is already frozen?
2. **What is the risk** of building ahead of the backend, and how is it contained?

### Ownership

| Area | Owner | Notes |
|---|---|---|
| `frontend/**` | frontend track | Full rewrite expected; current skeleton is throwaway (§5, R-3). |
| `docs/frontend/**` | frontend track | This doc + any future frontend planning. |
| `backend/**`, `docs/spec.md`, `docs/plan.md`, `docs/phases/**`, `docs/issues.md`, `docs/decisions.md` | backend track | Frontend track reads these as the contract; does not edit them. |
| `docs/features.md` | backend track owns the file | Frontend track may read §"Frontend (React SPA)" for intent; edits go through the backend doc process. |
| `.github/workflows/ci.yml`, `Makefile` | shared | The `frontend` CI job and `make test-frontend` already exist and must stay green. |

### How to keep this in sync

- The API section (§6) is a **hand mirror** of `spec.md` §5 (+ §1, §0). It is
  transcription, not a second source of truth.
- `frontend/src/types.ts` is contractually hand-maintained, not generated
  (`features.md` decision #5). Same discipline: when `spec.md` changes, update
  §6 here and `types.ts` together, and diff them against the spec.
- Watch `git log -- docs/spec.md` during Phases 2–6. Any spec change in a
  contract-test gate (§7, R-1..R-10 risks) can move a shape this doc mirrors.

---

## 2. Opportunity map — what is buildable now

Backend status: Phases 0–1 complete; 2–6 (auth, recipes, inventory/availability,
cook, grocery) not started; 7 is docs. `spec.md` is complete and authoritative,
so schemas are frozen *subject to* the churn risks in §4.

| Frontend track | Depends on | Start | Churn risk |
|---|---|---|---|
| **Tooling** — router, `RequireAuth`, `api.ts` rewrite (bearer inject + error normalize), test harness (MSW or stubs), `types.ts` rewrite | nothing | now | none — pure infra |
| **Design / IA** — screen inventory, component set, loading/empty/error states, nav | nothing | now | none |
| **Login** (+ dev-only Register) | spec §5.1 | now | low — auth schemas simple, resolved |
| **RecipeList** — `GET /api/recipes`, client search/filter/sort, multi-select → grocery create | spec §5.2 read shape | now | low |
| **RecipeForm** — create/update, dynamic ingredient rows, **paste box with client-side line split (D2)** | spec §5.2, §2.3 | now | low |
| **Inventory** — CRUD, `match_name` editor, PATCH bucket/atomic-pair rules | spec §5.5 (N5 resolved) | now | low |
| **RecipeDetail — recipe body + steps + cook-history shell** | spec §5.2, §5.4 read shapes | now | low |
| **RecipeDetail — availability table** (`have`/`short`/`have_uncertain`/`missing`/`to_taste`, multiplier control) | **Phase 4 gate** | after Phase 4 contract-test + diff review clears | **medium** — see R-2 |
| **Cook action + deduction detail** (`CookDeductionRead` 11-key entries) | **Phase 5 gate** | after Phase 5 clears | **medium** — see R-2 |
| **GroceryLists** — generate, check/uncheck, manual lines, submit, archive, applied state | **Phase 6 gate** | after Phase 6 clears | **medium** — N6/N3 semantics |

**Recommended order:** Tooling + Design → Login → RecipeList/RecipeForm/Inventory
→ RecipeDetail shell → integrate availability/cook/grocery as each backend phase
lands. Build the gated screens behind a thin adapter so a late DTO change is a
one-file edit.

### Integration timing against backend phases

| After backend phase completes | Frontend can integrate (not just mock) |
|---|---|
| Phase 2 — auth + app factory | Login, bearer flow, 401 handling, `GET /api/auth/me`, gated requests |
| Phase 3 — structured recipes | RecipeList, RecipeForm, RecipeDetail body, `GET/POST/PUT/DELETE /api/recipes` |
| Phase 4 — inventory + availability | Inventory CRUD, `GET /api/recipes/{id}/availability` |
| Phase 5 — cooking + history | Cook action, per-recipe + global cook-log views |
| Phase 6 — grocery lists | Full grocery flow |
| Phase 7 — docs | LAN/CORS deployment notes, registration-window procedure |

---

## 3. Proposed frontend architecture

Extends `features.md` §"Frontend (React SPA)". Nothing here is binding; it is the
current best plan.

### Stack deltas from the skeleton

- **Add `react-router-dom`.** Routes: `/login`, `/` → RecipeList (guarded),
  `/recipes/:id`, `/recipes/new`, `/recipes/:id/edit`, `/inventory`, `/groceries`,
  `/groceries/:id`, `/history`.
- **Add a fetch-mock layer for tests.** MSW is the likely pick (handlers mirror
  `spec.md` §5); plain `vi.stubGlobal("fetch")` is the low-dep fallback the
  current `api.test.ts` already uses. Decision open (§8).
- **State:** the skeleton's "`refresh()` after every mutation" pattern does not
  scale to six resources. Evaluate React Query / SWR vs. a hand-rolled
  per-resource hook. Decision open (§8).
- Keep TypeScript strict, `npm run build` = `tsc -b && vite build`, Vitest +
  Testing Library (all already configured).

### Modules

| Module | Responsibility |
|---|---|
| `src/types.ts` | Hand mirror of `spec.md` §5 response/request models. Rewrite from scratch. |
| `src/api/client.ts` | One `fetch` wrapper: prefix `/api`, inject `Authorization: Bearer <token>`, parse `{detail}` errors into a typed shape, handle 204, throw typed `ApiError` with `status`. |
| `src/api/<resource>.ts` | `auth`, `recipes`, `inventory`, `cookLogs`, `grocery` — thin typed wrappers over `client.ts`. |
| `src/auth/` | `AuthProvider` (token in `sessionStorage`), `useAuth`, `RequireAuth` route wrapper, login/logout. |
| `src/pages/` | Login, RecipeList, RecipeDetail, RecipeForm, Inventory, GroceryLists, GroceryListDetail, History. |
| `src/lib/parseIngredients.ts` | Client-side paste-block splitter (D2, §7). |
| `src/lib/format.ts` | Quantity/number formatting + rounding (backend sends raw floats, §4 R-8). |

### Auth model (from spec §0, §5.1, §3.4)

- Opaque bearer token. `POST /api/auth/login {username, password}` (JSON, **not**
  OAuth2 form) → `{token, user}`. Store token; send `Authorization: Bearer`.
- **Registration is disabled by default** (`allow_registration=False`), and may
  require a `code`. A normal deployment has no self-serve signup. Ship **Login as
  the primary screen**; a Register form is **dev/bootstrap-only** and should be
  behind a build flag or simply omitted from the shipped bundle.
- Any data route with missing/malformed/wrong-scheme/unknown/expired token →
  `401 {"detail": "not authenticated"}`. On 401: drop the stored token, redirect
  to `/login`.
- `POST /api/auth/logout` → 204; then clear local token.
- Session is a **fixed 30-day window**, not sliding. Expired token cannot even
  call `logout`/`me`. Frontend should treat any 401 as "log in again", no refresh
  flow exists.

---

## 4. Risks

| # | Risk | Severity | Containment |
|---|---|---|---|
| R-1 | `types.ts` is hand-maintained by contract; silent drift from `spec.md`. | med | §6 mirror + review types against spec on every spec change; CI type-check catches shape use, not wrong shape. |
| R-2 | Math DTOs may still change in Phase 4–6 contract-test gates (`plan.md` allows spec+test co-edits). | med | Don't integrate availability/cook/grocery rendering until the owning phase's diff review clears. Keep those screens behind `src/api/<resource>.ts` adapters. |
| R-3 | Existing `frontend/src/{types,api,App,api.test}.ts` describe a pre-v1 recipe (`ingredients: string`, `instructions`) that no longer exists. | low | Treat as delete-and-rewrite, not migration. Keep the files compiling until replaced so the `frontend` CI job stays green, or rewrite in one PR. |
| R-4 | No running backend until Phase 2 merges; end-to-end is phase-gated. | low | Build against MSW/stub handlers keyed to `spec.md` §5; swap to real calls per §2 timing table. |
| R-5 | Registration disabled by default — a signup UI is misleading in a real deployment. | low | Login-only shipped UI; Register is dev-bootstrap, flagged/omitted (§3). |
| R-6 | CORS: backend `cors_origins` defaults to `["http://localhost:5173"]`, `allow_credentials=False`. | low | Dev uses the Vite proxy (`/api` → `:8000`), no CORS. LAN deploy must add the serving origin to `RECIPE_CORS_ORIGINS` (Phase 7 documents this). Token is a header, not a cookie, so `allow_credentials=False` is fine. |
| R-7 | Phase 2 refactors `schemas.py` → `schemas/` package. | none-for-JSON | JSON shapes unchanged; just don't mirror backend module names. |
| R-8 | Converted display quantities are **raw floats, never rounded** (`spec.md` §0). `display_quantity` can be e.g. `0.026455...`. | low | All formatting/rounding is frontend-owned (`src/lib/format.ts`). Never show a raw float. |
| R-9 | Multi-line ingredient paste is **not** split server-side (D2). A `str` with `\n` becomes one garbled row. | med | Frontend paste box must split on `\n`, `strip()`, drop blanks, and decide on section headers (`"For the sauce:"`) / bullets (`- `, `* `) / soft-wrapped lines **before** POSTing an array. No backend counterpart exists. |
| R-10 | Availability `group_*` fields repeat identically across every member line of a group. | low | Render per-line, or dedupe by `group_key = "{normalized_name}|{bucket}"` for a group header. Summing per-line `need` recovers `group_need`. |
| R-11 | `409 {"detail": "conflict"}` covers both integrity errors and SQLite lock timeouts, generically. | low | On `cook`/`submit` 409, show "someone else was updating stock, retry" and re-fetch. |
| R-12 | Cook deduction and grocery `submit` are **forward-only**; no API undo. | low | UI must not imply reversibility. No "undo cook" / "un-submit" affordance. `submit` is re-runnable and only picks up newly-checked lines. |
| R-13 | `POST /api/grocery` 422s if **any** `recipe_id` doesn't exist. | low | Multi-select create: re-validate selection against a fresh list, surface which ids failed. |
| R-14 | `photo_path` always `null`; `source_url` is a free unvalidated string. | low | No photo UI, no URL-import UI in v1 (both v2). `source_url` is a plain text field + "open link" if it parses. |
| R-15 | Skeleton has no `react-router-dom`, no MSW; `App.tsx` is a single-file single-resource UI. | low | Expected; part of the Tooling track. |
| R-16 | `updated_at` / `id` on `recipe_ingredients` churn on every PUT (full replace). | none | Don't use ingredient-row `id` as a stable React key across an edit; use `position` or a local uid. |

---

## 5. Existing skeleton — disposition

| File | v1 fate |
|---|---|
| `src/types.ts` | Delete. `Recipe` has `ingredients: string`, `instructions`, no such v1 shape. |
| `src/api.ts` | Delete. Single-resource, no auth header, no `/api` namespacing. |
| `src/App.tsx` | Delete. Becomes the router shell + providers. |
| `src/api.test.ts` | Rewrite as `src/api/*.test.ts` against MSW/stub handlers. |
| `src/main.tsx`, `src/setupTests.ts`, `vite.config.ts`, `tsconfig*` | Keep. Add `/uploads` proxy only if v2 photo work lands. |
| `package.json` | Add `react-router-dom` (+ `msw`, + a data-fetching lib if chosen). |

---

## 6. Informal API reference (mirror of `spec.md` §5)

**Non-normative.** TypeScript-ish shapes for the frontend's `types.ts`. If this
disagrees with `spec.md`, `spec.md` is right — fix this section.

### Conventions (`spec.md` §0)

- Base path `/api`. Header `Authorization: Bearer <token>` on every route except
  `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/health`.
- JSON in/out only. No form-data, no file upload in v1.
- Datetimes: tz-aware UTC ISO 8601 (`...+00:00`). Strings.
- Errors: `{"detail": string}` for `HTTPException`;
  `{"detail": [{loc, msg, type}]}` for request-validation 422s.
- `404 {"detail": "<resource> not found"}`. `409 {"detail": "conflict"}` for
  integrity / lock. Domain 422s have string `detail`.
- Numbers are raw floats; **client formats and rounds**.

### Shared

```ts
type ISODateTime = string;              // "2026-09-01T12:34:56+00:00"
interface UserMini { id: number; username: string; }
interface UserRead { id: number; username: string; created_at: ISODateTime; }
interface TokenResponse { token: string; user: UserRead; }
interface ApiError { status: number; detail: string | ValidationIssue[]; }
```

### Auth — `/api/auth`

| Call | Request | Response |
|---|---|---|
| `POST /register` | `{username: string /* ^[A-Za-z0-9_.-]{3,50}$ */, password: string /* 8..128 */, code?: string }` | `201 TokenResponse` — `403` disabled / bad code, `409` taken, `422` |
| `POST /login` | `{username: string, password: string}` (JSON) | `200 TokenResponse` — `401 {"detail":"invalid username or password"}` |
| `POST /logout` | — (auth) | `204` |
| `GET /me` | — (auth) | `200 UserRead` |

### Recipes — `/api/recipes`

```ts
interface RecipeIngredientIn {
  quantity?: number | null;   // > 0 when set, finite
  unit?: string | null;       // <= 30
  item?: string | null;       // 1..200; REQUIRED for an object element
  note?: string | null;       // <= 200
}
// An ingredients element may instead be a bare string (a pasted line).
type RecipeIngredientElement = RecipeIngredientIn | string;

interface RecipeIngredientRead {
  id: number; position: number;
  quantity: number | null; unit: string | null; item: string; note: string | null;
  normalized_name: string; raw_text: string | null;   // raw_text set only for pasted-string rows
}

interface RecipeBase {
  title: string;              // 1..200
  notes: string;              // default ""
  prep_time: number | null;   // >= 0 minutes
  cook_time: number | null;   // >= 0
  servings: number | null;    // > 0 finite
  cuisine: string | null;     // <= 100
  source_url: string | null;  // <= 500, NOT validated
  tags: string[];             // <= 100 items, each <= 50; stored as-sent
  steps: string[];            // <= 100 items, each <= 2000; ordered
}

type RecipeCreate = RecipeBase & { ingredients: RecipeIngredientElement[] };
type RecipeUpdate = RecipeCreate;   // PUT fully replaces, including ingredients

type RecipeRead = RecipeBase & {
  id: number; created_at: ISODateTime; updated_at: ISODateTime;
  photo_path: string | null;        // always null in v1
  created_by: UserMini | null;
  ingredients: RecipeIngredientRead[];   // ordered by position
};
```

| Call | Success | Errors |
|---|---|---|
| `POST /api/recipes` (`RecipeCreate`) | `201 RecipeRead` | `422` |
| `GET /api/recipes` | `200 RecipeRead[]` — order `created_at DESC, id DESC` | — |
| `GET /api/recipes/{id}` | `200 RecipeRead` | `404` |
| `PUT /api/recipes/{id}` (`RecipeUpdate`) | `200 RecipeRead` (full replace) | `404`, `422` |
| `DELETE /api/recipes/{id}` | `204` | `404` |

Ingredient build rules the frontend must respect:
- A pasted `string` element is truncated to **200 chars** server-side, then
  parsed. Blank/whitespace-only string elements are **skipped**.
- An object element **must** have a non-empty `item` or the whole request is
  `422 "ingredient object requires a non-empty item"`.
- `quantity: null` ⇒ **to-taste**, even if `unit` is set (`unit` ignored).

### Availability — `GET /api/recipes/{id}/availability`

Query: `?multiplier=<number>` — `> 0`, finite, default `1.0`; `inf`/`nan` → `422`.

```ts
type AvailabilityStatus =
  | "ok" | "have_uncertain" | "short" | "missing" | "to_taste";

interface AvailabilityLine {
  item: string;
  need: number | null;          // this row's own quantity * multiplier, canonical unit; null for to_taste
  need_unit: string | null;
  group_key: string;            // `${normalized_name}|${bucket}` — identical across group members
  group_unit: string;
  group_need: number | null;
  group_have: number | null;    // null only for to_taste
  group_short: number | null;   // null only for to_taste
  status: AvailabilityStatus;
  nettable: boolean;
}

interface AvailabilityReport {
  recipe_id: number;
  multiplier: number;
  lines: AvailabilityLine[];
  all_available: boolean;       // true only if every quantified line is "ok" (empty/all-to-taste also true)
}
```

Status meaning (for UI copy):

| status | meaning | nettable |
|---|---|---|
| `ok` | compatible stock ≥ need | true |
| `short` | compatible stock < need, no stock in an incompatible unit | true |
| `have_uncertain` | compatible stock < need **and** some stock sits in an incompatible unit — true shortfall unknown | false |
| `missing` | no positive stock at all for the match name | false |
| `to_taste` | ingredient has no quantity | false |

`404` if the recipe doesn't exist. `group_*` repeat per member line (R-10).

### Cook + history — `/api/recipes/{id}/cook`, `/api/cook-logs`

```ts
interface CookRequest { multiplier?: number; deduct?: boolean; }  // > 0 finite, default 1; deduct default true

type CookDeductionReason =
  | "ok" | "clamped to 0" | "to taste"
  | "not in inventory" | "have uncertain (incompatible unit)";

interface CookDeductionRead {         // every key present; null where the branch doesn't apply
  item: string;                       // never null
  normalized_name: string | null;
  requested: number | null;
  requested_unit: string | null;
  deducted: number | null;
  deducted_unit: string | null;
  inventory_unit: string | null;
  before: number | null;
  after: number | null;
  applied: boolean;                   // never null
  reason: CookDeductionReason;        // never null
}

interface CookLogRead {
  id: number;
  recipe_id: number | null;           // null once the recipe is deleted
  recipe_title: string;               // snapshot, survives deletion
  multiplier: number;
  deducted: boolean;
  cooked_at: ISODateTime;
  cooked_by: UserMini | null;
  deductions: CookDeductionRead[];     // [] when deduct=false
}

interface CookLogList {
  items: CookLogRead[]; total: number; limit: number; offset: number;
}
```

| Call | Success | Errors |
|---|---|---|
| `POST /api/recipes/{id}/cook` (`CookRequest`) | `201 CookLogRead` | `404`, `409` (lock/integrity) |
| `GET /api/recipes/{id}/cook-logs` | `200 CookLogRead[]` — `cooked_at DESC, id DESC`, unpaginated | `404` |
| `GET /api/cook-logs?limit=&offset=` | `200 CookLogList` — `limit` 1..200 default 50, `offset` ≥ 0 | `422` |
| `GET /api/cook-logs/{log_id}` | `200 CookLogRead` (resolves after recipe deletion) | `404` |

Invariant for `applied` entries: `before - deducted === after`, all in
`inventory_unit`.

### Inventory — `/api/inventory`

```ts
interface InventoryItemCreate {       // POST — additive upsert on (match_name, unit_bucket)
  item: string;                       // 1..200
  quantity: number;                   // >= 0 finite
  unit?: string | null;               // <= 30; null => COUNT bucket
  match_name?: string | null;         // <= 200; server runs normalize_name(); "" after normalize => 422
}

interface InventoryItemUpdate {       // PATCH — absolute set, driven by which keys are present
  item?: string | null;               // null => 422
  match_name?: string | null;         // null => 422; stored normalized; collision => 409
  quantity?: number | null;           // null => 422; requires `unit` also present => else 422
  unit?: string | null;               // must keep the same bucket => else 422
}

interface InventoryItemRead {
  id: number; item: string; normalized_name: string; match_name: string;
  unit_bucket: string;                // "mass" | "volume" | "count" | "opaque:<token>"
  quantity_base: number;              // source of truth, canonical unit
  display_unit: string | null;
  display_quantity: number;           // raw float; == quantity_base when display_unit null/opaque
  updated_at: ISODateTime;
}
```

| Call | Success | Errors |
|---|---|---|
| `GET /api/inventory` | `200 InventoryItemRead[]` — `match_name ASC, unit_bucket ASC` | — |
| `POST /api/inventory` (`InventoryItemCreate`) | `201 InventoryItemRead` (adds into existing row if key matches) | `422` |
| `PATCH /api/inventory/{id}` (`InventoryItemUpdate`) | `200 InventoryItemRead` | `404`, `422`, `409` |
| `DELETE /api/inventory/{id}` | `204` | `404` |

PATCH rules the UI enforces client-side to avoid guaranteed 422s:
- Setting `quantity` **requires** sending `unit` in the same request.
- `unit` may not change the bucket (`g`→`kg` ok; `g`→`can` → 422; `null` on a
  non-COUNT row → 422; `null` on a COUNT row → ok).
- `{}` → `200` no-op. `match_name` is normalized server-side (`" Flour "` → `flour`).

### Grocery — `/api/grocery`

```ts
interface GroceryListCreate {
  name?: string | null;               // default "Groceries <UTC date>"
  recipe_ids: number[];               // non-empty, unique, all must exist => else 422
  multipliers?: Record<number, number>;  // each > 0 finite; keys subset of recipe_ids => else 422
}

interface GroceryListItemIn {          // POST .../items (manual)
  item: string;                       // 1..200
  quantity?: number | null;           // > 0 when set, finite
  unit?: string | null;               // <= 30
}

interface GroceryListItemUpdate {      // PATCH .../items/{id}
  checked?: boolean | null;
  item?: string | null;
  quantity?: number | null;           // quantity & unit are an ATOMIC PAIR:
  unit?: string | null;               //   if either key is in the body, BOTH must be => else 422 (N6)
}

interface GroceryListItemRead {
  id: number; item: string; normalized_name: string;
  quantity: number | null; unit: string | null;
  checked: boolean; checked_at: ISODateTime | null; submitted_at: ISODateTime | null;
  source: "generated" | "manual";
  nettable: boolean;                  // false => true shortfall uncertain (inform the shopper)
  added_to_inventory: boolean;        // freeze flag — a frozen line rejects PATCH/DELETE with 409
  applied_quantity: number | null; applied_unit: string | null;
}

interface GroceryListRead {
  id: number; name: string; status: "active" | "archived";
  source_recipe_ids: number[]; created_at: ISODateTime;
  created_by: UserMini | null;
  items: GroceryListItemRead[];        // ordered by id
}
```

| Call | Success | Errors |
|---|---|---|
| `POST /api/grocery` (`GroceryListCreate`) | `201 GroceryListRead` | `422` |
| `GET /api/grocery?status=active|archived` | `200 GroceryListRead[]` — `created_at DESC, id DESC` | — |
| `GET /api/grocery/{id}` | `200 GroceryListRead` | `404` |
| `DELETE /api/grocery/{id}` | `204` (any status) | `404` |
| `POST /api/grocery/{id}/items` (`GroceryListItemIn`) | `201 GroceryListItemRead` | `404`, `409` if archived |
| `PATCH /api/grocery/{id}/items/{item_id}` (`GroceryListItemUpdate`) | `200 GroceryListItemRead` | `404`, `409` frozen/archived, `422` non-atomic pair |
| `DELETE /api/grocery/{id}/items/{item_id}` | `204` | `404`, `409` frozen/archived |
| `POST /api/grocery/{id}/submit` | `200 GroceryListRead` — forward-only, re-runnable | `404`, `409` not active |
| `POST /api/grocery/{id}/archive` | `200 GroceryListRead` | `404`, `409 {"detail":"list is not active"}` |

Behaviour the UI must reflect:
- Editing `item` / `quantity` / `unit` on a generated line **reclassifies** it to
  `source:"manual"`, `nettable:true` (N6). A `checked`-only PATCH does not.
- `submit` applies only lines that are `checked`, not yet `added_to_inventory`,
  and have a non-null `quantity`. It does **not** archive. Re-submitting picks up
  newly-checked lines. Nothing checked → `200` no-op.
- A `nettable:false` checked line **with** a real quantity **is** submitted; the
  flag informs the shopper, it doesn't block.

---

## 7. Client-side ingredient paste splitter (D2)

Backend does **no** newline splitting (`issues.md` D2). This is frontend-owned.

Minimum behaviour for the RecipeForm paste box:
1. Split the pasted block on `\n`.
2. `trim()` each line; drop empty lines.
3. Strip a leading bullet (`- `, `* `, `• `, `\d+\.`) if present.
4. Decide on section headers (`"For the sauce:"`, trailing `:` with no
   quantity) — either drop them or fold into the next line's `note`. **Open.**
5. Optionally rejoin soft-wrapped continuation lines (line not starting with a
   quantity and short). **Open — start without this.**
6. POST the result as a `string[]` in `ingredients`; the server parses each and
   stores `raw_text`.

Structured rows (object elements) bypass the splitter entirely.

---

## 8. Open frontend decisions

| # | Decision | Options | Lean |
|---|---|---|---|
| F-1 | Test fetch mocking | MSW handlers vs. `vi.stubGlobal("fetch")` stubs | MSW — closer to real, reusable across pages |
| F-2 | Data fetching / cache | keep `refresh()`-after-mutation vs. React Query / SWR | React Query — six resources, availability re-fetch after cook, grocery re-fetch after submit |
| F-3 | Register UI | ship behind dev flag / omit from bundle / include with a warning | dev flag or omit |
| F-4 | Error surface | toast vs. inline-per-form vs. both; how to render validation `detail[]` | both; map `detail[].loc` to fields |
| F-5 | Optimistic updates | grocery check/uncheck, inventory quantity | optimistic for check/uncheck only |
| F-6 | Paste splitter scope | headers + soft-wrap now vs. later | ship 1–3 of §7 first, iterate |
| F-7 | Quantity display | decimal places, fraction rendering, unit-aware precision | `src/lib/format.ts`, unit-aware |
| F-8 | "Uncertain" UI language | how to phrase `have_uncertain` / `nettable:false` to a home cook | short: "check what you have" |

---

## 9. Change log

| Date | Change |
|---|---|
| 2026-09-01 | Initial draft. Research pass against `spec.md` (complete) and backend Phases 0–1 done, 2–7 pending. |
