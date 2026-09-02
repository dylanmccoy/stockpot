# Frontend v1 — Implementation Specification

This is the normative implementation contract for the **frontend v1** SPA. It
defines the stack, the app shell, per-screen behavior, the client-owned pure
logic (with locked oracle tables), the error model, and the accessibility bar.

**Supersedes** [`informal-frontend-spec.md`](informal-frontend-spec.md). That
file is retained only as background; where the two disagree, **this file wins**.

## Document map

| Document | Authority |
|---|---|
| [`spec.md`](spec.md) (this file) | Normative frontend v1 behavior: stack, shell, screens, pure logic, errors, a11y |
| [`plan.md`](plan.md) | Delivery sequence: frontend-native phases 0–8 and their mapping to backend phases |
| [`decisions.md`](decisions.md) | Historical rationale for the decisions in this spec (grill outcomes Q1–Q25); non-normative |
| [`../spec.md`](../spec.md) | **The backend contract.** The API sections here are a hand mirror of it; when they disagree, the backend spec wins — fix this file |

### Partition (unchanged)

- `frontend/**` and `docs/frontend/**` are the frontend track's to own.
- The frontend track **reads** `../spec.md` as the API contract and does **not**
  edit `../spec.md`, `../plan.md`, `../phases/**`, `../issues.md`,
  `../decisions.md`, or `backend/**`.
- One row in `../features.md` is owned by the backend track; a v2 note is
  proposed there (see §11, Q19) but any change goes through the backend process.

### Sync discipline (R-1)

`§5` (API mirror) and `frontend/src/types.ts` are **hand-maintained mirrors** of
`../spec.md` §5 (+ §0). They are transcription, not a second source of truth.
When `../spec.md` changes:

1. Update `§5` here and `frontend/src/types.ts` together.
2. Diff both against the backend spec section that moved.
3. If a math DTO moved (availability / cook / grocery), the owning screen stays
   behind its `src/api/<resource>.ts` adapter until the change is absorbed (R-2).

Watch `git log -- docs/spec.md` during backend Phases 2–6.

---

## 0. Conventions

| Aspect | Value |
|---|---|
| Base path | all API calls are same-origin `/api/...`; the Vite dev proxy forwards to `:8000` |
| Auth header | `Authorization: Bearer <token>` injected by `api/client.ts` on every call except `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/health` |
| Content type | `application/json` request and response throughout; no form-data, no upload |
| Datetimes | tz-aware UTC ISO 8601 strings (`…+00:00`); formatted for display client-side |
| Numbers | responses carry **raw floats, never rounded**; `src/lib/format.ts` owns all rounding and fraction rendering (§7.2) |
| Errors | `{ detail: string }` or `{ detail: ValidationIssue[] }`; normalized to a typed `ApiError` by `api/client.ts` (§7.3) and surfaced per the catalog in §6 |
| Token storage | `localStorage`, key `recipe.token` (§4) |

---

## 1. Stack

| Concern | Choice | Notes |
|---|---|---|
| Build / dev | Vite 5 + React 18 + TypeScript strict | keep the skeleton's `vite.config.ts`, `tsconfig*`, `npm run build` = `tsc -b && vite build` |
| Routing | `react-router-dom` v6+, **classic component routing** | no data-router loaders/actions — TanStack Query owns data |
| Data / cache | **TanStack Query** (`@tanstack/react-query`) | query keys per resource; `invalidateQueries` after mutations; built-in loading/error/stale |
| Styling | **CSS Modules** + a `src/styles/tokens.css` custom-property layer | scoped by default; light/dark = a `:root` / `[data-theme]` token swap; no CSS framework |
| Tests | Vitest + Testing Library (already configured) + **MSW** | MSW handlers mirror `../spec.md` §5 and are the "backend" until integration |
| Lint / format | ESLint (`@typescript-eslint`, `eslint-plugin-react-hooks`) + Prettier | added in Phase 0; `npm run lint` must be green in CI |

New runtime deps: `react-router-dom`, `@tanstack/react-query`.
New dev deps: `msw`, `eslint` + plugins, `prettier`.
Every added dep is listed here; adding one not listed needs a spec update.

### Module layout

```
src/
  main.tsx                 # providers: QueryClientProvider, AuthProvider, RouterProvider
  app/
    router.tsx             # route table (§3)
    AppShell.tsx           # nav chrome: top bar >=640px, bottom tab bar <640px
    RequireAuth.tsx        # redirects to /login?next=<path> when unauthenticated
  styles/
    tokens.css             # color / space / type / radius custom properties, both themes
    global.css             # reset, base element styles
  api/
    client.ts              # the one fetch wrapper: /api prefix, bearer inject, ApiError normalize, 204
    auth.ts recipes.ts inventory.ts cookLogs.ts grocery.ts   # thin typed wrappers (adapters, R-2)
  types.ts                 # hand mirror of ../spec.md §5 (R-1)
  auth/
    AuthProvider.tsx useAuth.ts     # token in localStorage, login/logout, 401 handling
  lib/
    parseIngredients.ts    # paste-block splitter (§7.1)
    format.ts              # quantity / number / fraction / datetime formatting (§7.2)
    apiError.ts            # parseApiError + useFormErrors (§7.3)
  components/              # the ~8 primitives (§8)
  pages/
    Login.tsx
    RecipeList.tsx RecipeDetail.tsx RecipeForm.tsx
    Inventory.tsx
    GroceryLists.tsx GroceryListDetail.tsx
    History.tsx
  test/
    server.ts handlers.ts  # MSW: shared handler set + error-case handlers
```

Import direction is one-way:
`types → api/client → api/<resource> → lib → components → pages → app`.
`auth/` sits beside `api/` (client injects the token that `auth/` owns).

---

## 2. Existing skeleton — disposition

Delete-and-rewrite in **Phase 0**, in one PR, keeping the `frontend` CI job green
(`npm run lint && npm run test:run && npm run build`).

| File | Fate |
|---|---|
| `src/App.tsx` | **delete** → becomes `app/AppShell.tsx` + `app/router.tsx` |
| `src/types.ts` | **delete** → rewrite from `../spec.md` §5 (§5 below) |
| `src/api.ts` | **delete** → `api/client.ts` + `api/<resource>.ts` |
| `src/api.test.ts` | **delete** → `api/client.test.ts` + per-resource tests against MSW |
| `src/main.tsx` | rewrite: mount the provider stack |
| `src/setupTests.ts` | keep + extend: start/stop the MSW server, `jest-dom` |
| `src/vite-env.d.ts` | keep; add `VITE_ENABLE_REGISTER` to an `ImportMetaEnv` interface |
| `vite.config.ts`, `tsconfig*`, `index.html` | keep (retitle `index.html` to "Recipes") |
| `package.json` | add the deps in §1; add `lint` script |

---

## 3. App shell & routing

### Navigation model

- **≥ 640px:** persistent **top bar** — brand + four links: **Recipes ·
  Inventory · Groceries · History** + a user menu (username, "Log out").
- **< 640px:** a fixed **bottom tab bar** with the same four destinations,
  thumb-reachable; the top bar collapses to brand + user menu.
- Detail and form screens are **pushed routes** with a back affordance, not tabs.
- The active destination is marked (`aria-current="page"`).

### Route table

| Path | Screen | Guard | Notes |
|---|---|---|---|
| `/login` | Login | public | redirects to `next` (or `/`) on success |
| `/` | RecipeList | auth | the home surface (no dashboard in v1) |
| `/recipes/new` | RecipeForm (create) | auth | |
| `/recipes/:id` | RecipeDetail | auth | includes availability, cook action, per-recipe history panel |
| `/recipes/:id/edit` | RecipeForm (edit) | auth | PUT = full replace |
| `/inventory` | Inventory | auth | |
| `/groceries` | GroceryLists | auth | `?status=active` default; archived toggle |
| `/groceries/:id` | GroceryListDetail | auth | |
| `/history` | History | auth | global cook log, paginated |
| `*` | NotFound | — | in-app 404 page |

`RequireAuth` wraps every `auth` route: no token → `Navigate` to
`/login?next=<attempted path>`, replace.

### Loading / empty / error conventions (all screens)

| State | Treatment |
|---|---|
| loading | skeleton rows / spinner in the content region; nav chrome stays interactive |
| empty | a centered empty state with a one-line prompt and the primary action (e.g. "No recipes yet — Add your first") |
| query error | inline panel with the `ApiError` message + a "Retry" button (re-runs the query) |
| mutation error | per §6 — toast, inline-field, or inline-form by error class |
| 404 on a `/:id` route | the in-content "not found" panel + a link back to the list |

---

## 4. Auth & session

From `../spec.md` §0, §5.1, §3.4:

- **Token:** opaque bearer. `POST /api/auth/login { username, password }` (JSON,
  **not** OAuth2 form) → `{ token, user }`. Store `token` in `localStorage`
  under `recipe.token`; `api/client.ts` reads it and sets
  `Authorization: Bearer <token>`.
- **Why `localStorage`, not `sessionStorage`:** the session is a fixed 30-day
  window with **no refresh flow**; clearing it on every tab close is hostile for
  a daily household tool. XSS exposure is within the project's accepted posture
  (LAN, no HTTPS).
- **On any `401`** from a data route: clear `recipe.token`, drop the React Query
  cache, `Navigate` to `/login?next=<current path>`. No refresh attempt — every
  `401` means "log in again".
- **Logout:** `POST /api/auth/logout` → `204`; then clear the token and cache.
  An expired token can't even call `logout` (it `401`s first) — treat a `401`
  from logout as success.
- **`GET /api/auth/me`** on app load with a stored token: valid → hydrate the
  user; `401` → clear and treat as logged out.

### Registration

- **Disabled server-side by default** (`allow_registration=False`), and may
  require a `code`.
- The Register form is built **behind `import.meta.env.VITE_ENABLE_REGISTER`**
  (default off). The shipped production bundle has **no** signup UI.
- When enabled: `username` (`^[A-Za-z0-9_.-]{3,50}$`), `password` (8–128),
  optional `code`. Errors per §6 (`403` disabled / bad code, `409` taken).

---

## 5. API mirror (non-normative — mirrors `../spec.md` §5)

TypeScript shapes for `src/types.ts`. **If this disagrees with `../spec.md`, the
backend spec is right — fix this section and `types.ts` together (R-1).**

### Shared

```ts
type ISODateTime = string;                       // "2026-09-01T12:34:56+00:00"
interface UserMini { id: number; username: string; }
interface UserRead { id: number; username: string; created_at: ISODateTime; }
interface TokenResponse { token: string; user: UserRead; }

interface ValidationIssue { loc: (string | number)[]; msg: string; type: string; }
interface ApiError { status: number; detail: string | ValidationIssue[]; }
```

### Auth — `/api/auth`

| Call | Request | Response |
|---|---|---|
| `POST /register` | `{ username, password, code? }` | `201 TokenResponse` · `403` disabled/bad-code · `409` taken · `422` |
| `POST /login` | `{ username, password }` (JSON) | `200 TokenResponse` · `401 {"detail":"invalid username or password"}` |
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
type RecipeIngredientElement = RecipeIngredientIn | string;   // a bare string = a pasted line

interface RecipeIngredientRead {
  id: number; position: number;
  quantity: number | null; unit: string | null; item: string; note: string | null;
  normalized_name: string;
  raw_text: string | null;    // set only for pasted-string rows
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
| `GET /api/recipes` | `200 RecipeRead[]` — `created_at DESC, id DESC` | — |
| `GET /api/recipes/{id}` | `200 RecipeRead` | `404` |
| `PUT /api/recipes/{id}` (`RecipeUpdate`) | `200 RecipeRead` (full replace) | `404`, `422` |
| `DELETE /api/recipes/{id}` | `204` | `404` |

Ingredient build rules the client must respect:
- A pasted `string` is truncated to **200 chars** server-side, then parsed;
  blank/whitespace-only string elements are **skipped**.
- An object element **must** carry a non-empty `item` → else the whole request
  is `422 "ingredient object requires a non-empty item"`.
- `quantity: null` ⇒ **to-taste** even if `unit` is set (`unit` ignored).
- Don't use `RecipeIngredientRead.id` as a stable React key across an edit
  (churns on every PUT, R-16); use `position` or a local uid.

### Availability — `GET /api/recipes/{id}/availability?multiplier=<number>`

`multiplier > 0`, finite, default `1.0`; `inf`/`nan` → `422`.

```ts
type AvailabilityStatus = "ok" | "have_uncertain" | "short" | "missing" | "to_taste";

interface AvailabilityLine {
  item: string;
  need: number | null;          // this row's own quantity * multiplier, canonical unit; null for to_taste
  need_unit: string | null;
  group_key: string;            // `${normalized_name}|${bucket}` — identical across group members (R-10)
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
  all_available: boolean;       // true iff every non-to_taste line is "ok" (empty / all-to-taste also true)
}
```

| status | meaning | UI copy (§7.4) |
|---|---|---|
| `ok` | compatible stock ≥ need | "Have it" (quiet) |
| `short` | compatible stock < need, no incompatible-unit stock | "Short {group_short} {group_unit}" |
| `have_uncertain` | compatible short **and** some stock in an incompatible unit | "Check what you have" (amber); **never show a number** |
| `missing` | no positive stock for the match name | "Missing" |
| `to_taste` | ingredient has no quantity | "To taste" (quiet) |

`group_*` repeat per member line — render per line, or dedupe by `group_key` for
a group header. Summing per-line `need` recovers `group_need`.

### Cook + history — `/api/recipes/{id}/cook`, `/api/recipes/{id}/cook-logs`, `/api/cook-logs`

```ts
interface CookRequest { multiplier?: number; deduct?: boolean; }  // > 0 finite, default 1; deduct default true

type CookDeductionReason =
  | "ok" | "clamped to 0" | "to taste"
  | "not in inventory" | "have uncertain (incompatible unit)";

interface CookDeductionRead {          // every key present; null where the branch doesn't apply
  item: string;                        // never null
  normalized_name: string | null;
  requested: number | null;            // canonical; first row of a group only, else null
  requested_unit: string | null;
  deducted: number | null;
  deducted_unit: string | null;
  inventory_unit: string | null;
  before: number | null;
  after: number | null;
  applied: boolean;                    // never null
  reason: CookDeductionReason;         // never null
}

interface CookLogRead {
  id: number;
  recipe_id: number | null;            // null once the recipe is deleted
  recipe_title: string;                // snapshot, survives deletion
  multiplier: number;
  deducted: boolean;
  cooked_at: ISODateTime;
  cooked_by: UserMini | null;
  deductions: CookDeductionRead[];      // [] when deduct=false
}

interface CookLogList { items: CookLogRead[]; total: number; limit: number; offset: number; }
```

| Call | Success | Errors |
|---|---|---|
| `POST /api/recipes/{id}/cook` (`CookRequest`) | `201 CookLogRead` | `404`, `409` |
| `GET /api/recipes/{id}/cook-logs` | `200 CookLogRead[]` — `cooked_at DESC, id DESC`, unpaginated | `404` |
| `GET /api/cook-logs?limit=&offset=` | `200 CookLogList` — `limit` 1..200 default 50, `offset` ≥ 0 | `422` |
| `GET /api/cook-logs/{log_id}` | `200 CookLogRead` (resolves after recipe deletion) | `404` |

Applied-entry invariant: `before - deducted === after`, all in `inventory_unit`.
Cook is **forward-only** — no undo affordance anywhere (R-12).

### Inventory — `/api/inventory`

```ts
interface InventoryItemCreate {        // POST — additive upsert on (match_name, unit_bucket)
  item: string;                        // 1..200
  quantity: number;                    // >= 0 finite
  unit?: string | null;                // <= 30; null => COUNT bucket
  match_name?: string | null;          // <= 200; server runs normalize_name(); "" after normalize => 422
}

interface InventoryItemUpdate {        // PATCH — absolute set, driven by which keys are present
  item?: string | null;                // null => 422
  match_name?: string | null;          // null => 422; stored normalized; collision => 409
  quantity?: number | null;            // null => 422; requires `unit` also present => else 422
  unit?: string | null;                // must keep the same bucket => else 422
}

interface InventoryItemRead {
  id: number; item: string; normalized_name: string; match_name: string;
  unit_bucket: string;                 // "mass" | "volume" | "count" | "opaque:<token>"
  quantity_base: number;               // source of truth, canonical unit
  display_unit: string | null;
  display_quantity: number;            // raw float; == quantity_base when display_unit null/opaque
  updated_at: ISODateTime;
}
```

| Call | Success | Errors |
|---|---|---|
| `GET /api/inventory` | `200 InventoryItemRead[]` — `match_name ASC, unit_bucket ASC` | — |
| `POST /api/inventory` (`InventoryItemCreate`) | `201 InventoryItemRead` (adds into an existing row if the key matches) | `422` |
| `PATCH /api/inventory/{id}` (`InventoryItemUpdate`) | `200 InventoryItemRead` | `404`, `422`, `409` |
| `DELETE /api/inventory/{id}` | `204` | `404` |

PATCH rules enforced client-side before sending (to avoid guaranteed 422s):
- Setting `quantity` **requires** `unit` in the same request.
- `unit` may not change the bucket (`g`→`kg` ok; `g`→`can` → 422; `null` on a
  non-COUNT row → 422; `null` on a COUNT row → ok).
- `{}` → `200` no-op. `match_name` is normalized server-side (`" Flour "` → `flour`).
- A `match_name` PATCH whose normalized value collides with another
  `(match_name, unit_bucket)` row → `409`.

### Grocery — `/api/grocery`

```ts
interface GroceryListCreate {
  name?: string | null;                // default "Groceries <UTC date>"
  recipe_ids: number[];                // non-empty, unique, all must exist => else 422
  multipliers?: Record<number, number>;  // each > 0 finite; keys subset of recipe_ids => else 422
}

interface GroceryListItemIn {           // POST .../items (manual)
  item: string;                        // 1..200
  quantity?: number | null;            // > 0 when set, finite
  unit?: string | null;                // <= 30
}

interface GroceryListItemUpdate {       // PATCH .../items/{id}
  checked?: boolean | null;
  item?: string | null;
  quantity?: number | null;            // quantity & unit are an ATOMIC PAIR — if either key is
  unit?: string | null;                //   in the body, BOTH must be => else 422 (N6)
}

interface GroceryListItemRead {
  id: number; item: string; normalized_name: string;
  quantity: number | null; unit: string | null;
  checked: boolean; checked_at: ISODateTime | null; submitted_at: ISODateTime | null;
  source: "generated" | "manual";
  nettable: boolean;                   // false => true shortfall uncertain — inform the shopper (§7.4)
  added_to_inventory: boolean;         // freeze flag — a frozen line rejects PATCH/DELETE with 409
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
| `GET /api/grocery?status=active\|archived` | `200 GroceryListRead[]` — `created_at DESC, id DESC` | — |
| `GET /api/grocery/{id}` | `200 GroceryListRead` | `404` |
| `DELETE /api/grocery/{id}` | `204` (any status) | `404` |
| `POST /api/grocery/{id}/items` (`GroceryListItemIn`) | `201 GroceryListItemRead` | `404`, `409` if archived |
| `PATCH /api/grocery/{id}/items/{item_id}` (`GroceryListItemUpdate`) | `200 GroceryListItemRead` | `404`, `409` frozen/archived, `422` non-atomic pair |
| `DELETE /api/grocery/{id}/items/{item_id}` | `204` | `404`, `409` frozen/archived |
| `POST /api/grocery/{id}/submit` | `200 GroceryListRead` — forward-only, re-runnable | `404`, `409` not active |
| `POST /api/grocery/{id}/archive` | `200 GroceryListRead` | `404`, `409 {"detail":"list is not active"}` |

Behavior the UI must reflect:
- Editing `item` / `quantity` / `unit` on a **generated** line **reclassifies**
  it to `source:"manual"`, `nettable:true` (N6). A `checked`-only PATCH does not.
- `submit` applies only lines that are `checked`, not yet `added_to_inventory`,
  and have a non-null `quantity`. It does **not** archive. Re-submitting picks up
  newly-checked lines. Nothing eligible → `200` no-op.
- A `nettable:false` checked line **with** a real quantity **is** submitted; the
  flag informs the shopper, it doesn't block.
- `submit` / `archive` are **forward-only** — no "un-submit" / "un-archive" (R-12).
- `POST /api/grocery` `422`s if **any** `recipe_id` doesn't exist — re-validate
  the selection against a fresh list and surface which ids failed (R-13).

---

## 6. Error model & catalog

`api/client.ts` normalizes every non-2xx response into
`ApiError { status, detail }` (§7.3) and throws it. Screens route it by class:

- **transport / `500` / unexpected** → **toast** (generic copy).
- **`422` with `detail: ValidationIssue[]`** → **inline per-field**, mapped by
  the last string in each `loc` to a form field.
- **`422` / `403` / `409` with `detail: string`** → **inline form-level banner**,
  message shown verbatim (the backend strings are already human).
- **`401`** → **silent**: clear token + cache, redirect to `/login?next=`.

A shared `useFormErrors` hook splits field-level from form-level for forms.
Toasts are `aria-live="polite"` regions (§9).

### Consolidated catalog

Derived from `../spec.md` §0, §5, and R-11/R-13 — **non-authoritative mirror**.

| status | `detail` shape | trigger(s) | endpoints | FE surface | copy |
|---|---|---|---|---|---|
| `422` | `ValidationIssue[]` | Pydantic validation: wrong type, out-of-range (`quantity <= 0`, `multiplier <= 0`), `inf`/`nan`, missing required, `recipe_ids` empty or duplicate | all `POST` / `PUT` / `PATCH` | inline per-field via `loc` | humanized `msg` under the field |
| `422` | `string` | domain rules: `"ingredient object requires a non-empty item"`, `"unit is required when setting quantity"`, `"unit changes the bucket; remove and re-add"`, `"match_name normalizes to empty"`, `"quantity and unit must be set together"`, `multipliers` key not in `recipe_ids`, a `recipe_id` that doesn't exist | recipes, inventory, grocery | inline form-level banner | verbatim |
| `401` | `"not authenticated"` | missing / malformed / wrong-scheme / unknown / expired token | every gated route | silent: clear token + cache, `→ /login?next=` | — |
| `401` | `"invalid username or password"` | login failure (both modes) | `POST /api/auth/login` | inline form-level | verbatim |
| `403` | `"registration disabled"` / `"invalid registration code"` | register when disabled / bad or missing code | `POST /api/auth/register` | inline form-level | verbatim |
| `404` | `"<resource> not found"` | addressed id doesn't exist | every `/{id}` route | in-content not-found panel + back link | "This {resource} no longer exists." |
| `409` | `"conflict"` | `IntegrityError` **or** SQLite lock timeout — generic (R-11) | `cook`, grocery `submit`, inventory `POST`/`PATCH` | toast + auto-refetch the affected query | "Someone else was updating stock. We've refreshed — try again." |
| `409` | `"username taken"` | duplicate username (case-insensitive) | `POST /api/auth/register` | inline field (username) | verbatim |
| `409` | `"match_name already in use for this bucket"` | PATCH `match_name` collision | `PATCH /api/inventory/{id}` | inline field (match_name) | verbatim |
| `409` | `"list is not active"` | mutate / submit / archive an archived (or non-active) list | grocery list + item routes, `submit`, `archive` | toast + refetch the list | "This list is archived." |
| `409` | `"conflict"` on a frozen grocery line | `PATCH` / `DELETE` a line with `added_to_inventory: true` | grocery item routes | toast + refetch | "This item was already added to inventory." |
| `500` | `"Internal Server Error"` | non-lock `OperationalError`; a drifted `CookDeductionRead` entry on read | any | generic toast | "Something went wrong. Try again." |

MSW ships a happy-path handler set **and** targeted error handlers for every row
above, so each surface is exercised in tests without a real backend.

---

## 7. Client-owned pure logic (locked oracle gate — R-7 analogue)

`§7.1`–`§7.3` are the frontend's load-bearing pure logic. Their oracle tables
below are **locked**: authored and accepted as black-box tests **before** the
implementation pass (see [`plan.md`](plan.md) §Contract-test gate). An
implementation may add cases but must not alter an accepted expected value; a
wrong oracle is fixed by editing this spec and the test together, with a reason.

### 7.1 `lib/parseIngredients.ts` — paste-block splitter (D2 / R-9)

The backend does **no** newline splitting. `parseIngredients(block: string):
string[]` runs entirely client-side, and its output array is POSTed as
`ingredients` string elements.

Algorithm (v1 scope — Q17):

1. Split `block` on `\n`.
2. `trim()` each line; drop empty lines.
3. Strip one leading bullet/marker if present: `- `, `* `, `• `, or `\d+[.)]\s`.
4. **Drop section headers**: a line that ends with `:` **and** has no parseable
   leading quantity (integer, decimal, `a/b`, `a b/c`, or a unicode vulgar
   fraction). Not folded into a note — folding guesses wrong too often.
5. **No** soft-wrap rejoin in v1.
6. Return the surviving lines in order.

The RecipeForm paste action shows a **preview of parsed rows** (run through the
same parse the server will do — see §10.3) before anything is POSTed, so the
user hand-fixes mistakes.

**Locked oracle table** — `parseIngredients(input) === output`:

| # | Input (`\n`-joined) | Output |
|---|---|---|
| P1 | `"2 tbsp olive oil\n1 onion, diced\n\nsalt to taste"` | `["2 tbsp olive oil", "1 onion, diced", "salt to taste"]` |
| P2 | `"- 2 eggs\n* 1 cup flour\n• 1 tsp salt"` | `["2 eggs", "1 cup flour", "1 tsp salt"]` |
| P3 | `"1. Preheat\n2) Mix"` | `["Preheat", "Mix"]` |
| P4 | `"For the sauce:\n2 tbsp soy sauce\nFor the garnish:\n1 scallion"` | `["2 tbsp soy sauce", "1 scallion"]` |
| P5 | `"   \n\t\n  2 cups rice  \n"` | `["2 cups rice"]` |
| P6 | `"1/2 tsp cumin\n½ tsp salt\n1 1/2 cups stock"` | `["1/2 tsp cumin", "½ tsp salt", "1 1/2 cups stock"]` |
| P7 | `"2 cups whole milk: room temp"` | `["2 cups whole milk: room temp"]` (has a leading quantity → not a header even though it contains `:`) |
| P8 | `""` | `[]` |
| P9 | `"Chicken:\n  \n- Chicken thighs\n1kg potatoes"` | `["Chicken thighs", "1kg potatoes"]` |
| P10 | `"3 large eggs\nzest of 1 lemon"` | `["3 large eggs", "zest of 1 lemon"]` |

Header detection keys on **trailing `:` after trim** + **no leading quantity**.
`"…: room temp"` (P7) does not end with `:` so it is never a header; the leading
`2` also disqualifies it.

### 7.2 `lib/format.ts` — quantity / number / datetime formatting (R-8)

Responses carry raw floats (`0.026455…`, `266.1616`). **Never render a raw
float.** `formatQuantity(value: number, unit: string | null): string`:

- **Fraction-prefer** when `value < 10` **and** `value` is within `0.02` (2%,
  relative) of a common cooking fraction: snap to
  `⅛ ¼ ⅓ ½ ⅔ ¾` (and integer + fraction, e.g. `1½`).
- **Counts** (`unit` is `null` / `"unit"` / `"each"`): if within `0.01` of a
  whole number, render the integer.
- **Canonical bulk units** (`unit` ∈ `{"g", "ml"}`): always decimal, never a
  fraction; 3 significant figures, trailing zeros trimmed.
- **Otherwise:** round to **3 significant figures**, trim trailing zeros. No
  thousands separators in v1.
- `value` is `null` → `""` (caller renders "to taste" / "—" itself).

**Locked oracle table** — `formatQuantity(value, unit) === output`:

| # | value | unit | output |
|---|---|---|---|
| F1 | `0.5` | `"cup"` | `"½"` |
| F2 | `1.5` | `"cups"` | `"1½"` |
| F3 | `0.3333333` | `"cup"` | `"⅓"` |
| F4 | `0.26` | `"tsp"` | `"0.26"` (0.26 is 4% off ¼ = 0.25, outside the 2% snap band → decimal) |
| F5 | `2` | `null` | `"2"` |
| F6 | `2.997` | `null` | `"3"` |
| F7 | `473.176` | `"ml"` | `"473"` |
| F8 | `266.1616` | `"ml"` | `"266"` |
| F9 | `0.0264554` | `"g"` | `"0.0265"` |
| F10 | `12000` | `"g"` | `"12000"` |
| F11 | `1.25` | `"lb"` | `"1¼"` |
| F12 | `0.125` | `"tsp"` | `"⅛"` |
| F13 | `7.5` | `"cup"` | `"7½"` |
| F14 | `10.5` | `"cup"` | `"10.5"` (`value >= 10` → no fraction) |
| F15 | `null` | `"g"` | `""` |

`formatDateTime(iso: string): string` → locale short form
(`"Aug 28, 2026, 6:12 PM"`); `formatRelative` optional for history rows.

### 7.3 `lib/apiError.ts` — `parseApiError`

`parseApiError(status: number, body: unknown): ApiError` normalizes FastAPI's two
error shapes plus the degenerate cases.

Rules:
- `body.detail` is a string → `{ status, detail: body.detail }`.
- `body.detail` is an array → `{ status, detail: body.detail as ValidationIssue[] }`
  (each entry kept as `{ loc, msg, type }`).
- `body` has no `detail`, or `body` is not an object, or parsing the body threw
  → `{ status, detail: <standard reason phrase for status, else "Request failed"> }`.
- `204` never reaches this function.

**Locked oracle table** — `parseApiError(status, body)` → `detail`:

| # | status | body | result `detail` |
|---|---|---|---|
| E1 | 422 | `{ detail: [{ loc: ["body","username"], msg: "field required", type: "value_error.missing" }] }` | the array, length 1, `loc` last element `"username"` |
| E2 | 401 | `{ detail: "not authenticated" }` | `"not authenticated"` |
| E3 | 409 | `{ detail: "conflict" }` | `"conflict"` |
| E4 | 500 | `"<html>502 Bad Gateway</html>"` | `"Internal Server Error"` |
| E5 | 404 | `{}` | `"Not Found"` |
| E6 | 400 | `null` | `"Request failed"` |
| E7 | 422 | `{ detail: "quantity and unit must be set together" }` | `"quantity and unit must be set together"` (string, not array) |
| E8 | 403 | `{ detail: [{ loc: ["body","code"], msg: "x", type: "y" }, { loc: ["body","username"], msg: "z", type: "w" }] }` | the array, length 2 |

`isFieldError(e): e is ApiError & { detail: ValidationIssue[] }` and
`fieldName(issue): string` (= `String(issue.loc.at(-1))`) are exported helpers.

### 7.4 "Uncertain" language (Q19 — copy, not logic)

`have_uncertain` (availability) and `nettable:false` (grocery) both mean "true
shortfall unknown — stock sits in an incomparable unit." Never show a computed
shortfall number for these.

| Surface | Rendering |
|---|---|
| Availability row | amber badge **"Check what you have"**; subtext "You have some, but in a unit we can't compare (e.g. cans vs grams)." |
| Grocery line | amber tag **"amount uncertain"** beside the quantity; subtext "buy based on what you find you're short." |

A backend rename of these two names is **out of scope for v1**; a v2
investigation note is recorded (§11, Q19).

---

## 8. Component system

~8 hand-rolled primitives in `src/components/`, on the `tokens.css` custom
properties. No component library. Each is keyboard- and screen-reader-correct so
screens inherit the a11y bar (§9) for free.

| Primitive | Responsibility / notes |
|---|---|
| `Button` | variants `primary` / `secondary` / `ghost` / `danger`; `loading` disables + shows a spinner; real `<button type>` |
| `Input` / `Textarea` / `Select` | controlled; `id` wired to a `<label>`; `aria-invalid` + `aria-describedby` for the error slot |
| `Field` | label + control + hint + error text; the single place field errors render (fed by `useFormErrors`) |
| `Card` | padded surface for list items and panels |
| `DataTable` | responsive: real `<table>` ≥ 640px, stacked key/value rows below; `scope` on headers; horizontal scroll container when it must stay tabular |
| `Dialog` | focus trap, `Esc` to close, restores focus to the opener, `role="dialog"` + `aria-labelledby`; used by the grocery-create flow and confirmations |
| `Toast` (+ `ToastProvider`) | `aria-live="polite"`; auto-dismiss with a pause-on-hover; error toasts persist until dismissed |
| `Badge` | status pills — availability status, `source`, `nettable`, frozen/checked |
| `Stepper` | numeric control for the multiplier (§10.2) and grocery-create per-recipe multipliers (§10.5); presets + free input, enforces `> 0` |

`tokens.css` defines: color roles (bg, surface, text, muted, border, accent,
`ok`/`warn`/`danger`), a 4px-based space scale, a type scale, radii. Both a
`:root` (light) and `[data-theme="dark"]` block; theme follows
`prefers-color-scheme` with a manual override persisted in `localStorage`.

---

## 9. Accessibility bar (v1 requirement — Phase 1)

Enforced by the primitives; every screen must clear it:

- Semantic landmarks: one `<header>`/`<nav>`, one `<main>`, labelled regions.
- Every input has an associated `<label>`; errors linked via `aria-describedby`;
  invalid controls carry `aria-invalid`.
- Visible focus ring on every interactive element (never `outline: none` without
  a replacement).
- Full keyboard operation: the tab bar / top nav, dialogs (focus trap + `Esc` +
  focus restore), the ingredient-row editor, and grocery check/uncheck.
- Toasts and async status via `aria-live`; route changes move focus to `<main>`
  or the page `<h1>`.
- Text contrast ≥ 4.5:1 in **both** themes; status is never color-only (icon or
  text label alongside).
- Respect `prefers-reduced-motion` for spinners/transitions.

---

## 10. Screen specs

Each screen: its data (query keys), the mutations it fires and what they
invalidate, and behavior rules. Screens gated on a backend phase are marked; they
sit behind their `src/api/<resource>.ts` adapter until that phase's DTOs land
(R-2).

### 10.1 Login  (`/login`) — backend Phase 2

- Form: `username`, `password`; submit → `POST /api/auth/login`.
- Success → store token, `GET /api/auth/me`, redirect to `next` or `/`.
- `401` → inline form-level "invalid username or password".
- Register form rendered **only** when `VITE_ENABLE_REGISTER` is set: adds an
  optional `code` field; `403` / `409` inline.
- No "remember me" — the session is always the fixed 30-day window.

### 10.2 RecipeList  (`/`) — backend Phase 3

- Query `["recipes"]` → `GET /api/recipes` (server order preserved:
  `created_at DESC, id DESC`).
- **Client-side** controls (no backend support): free-text search over
  `title` + `cuisine` + `tags`; filter chips for `cuisine` and `tags` (union
  within a facet, intersection across facets); sort toggle
  (newest / title A–Z / recently updated).
- Card grid; each card: title, cuisine, tag chips, prep+cook time, ingredient
  count. Click → `/recipes/:id`.
- **Multi-select mode** → a checkbox per card; a sticky action bar shows the
  count and **"Create grocery list"** → opens the create `Dialog` (§10.5).
- Empty state: "No recipes yet — Add your first recipe" → `/recipes/new`.

### 10.3 RecipeForm  (`/recipes/new`, `/recipes/:id/edit`) — backend Phase 3

- Edit mode seeds from `["recipe", id]`; `PUT` is a **full replace** including
  ingredients.
- Fields: `title`, `cuisine`, `servings`, `prep_time`, `cook_time`,
  `source_url` (plain text + an "open link" affordance if it parses — no
  validation, no import: R-14), `tags` (chip input), `notes`, `steps` (ordered
  add/remove/reorder list).
- **Ingredients — one unified editable table (Q22):**
  - Each row = editable fields `quantity` / `unit` / `item` / `note`; add,
    remove, reorder. React key = a local uid, **not** the server row `id`
    (R-16).
  - A **"Paste ingredients"** action opens a `Textarea` → on confirm runs
    `parseIngredients` (§7.1), shows a **preview** of the resulting rows parsed
    the way the server will parse them (a local, display-only mirror of
    `parse_ingredient` — the server remains the source of truth), and
    **appends** them to the table.
  - On submit, each row serializes as:
    - a **string** element if it came from paste and was left untouched (server
      stores `raw_text`), or
    - an **object** `RecipeIngredientIn` if hand-entered or edited (must have a
      non-empty `item`; the form blocks submit otherwise, matching the server
      `422`).
  - `quantity` blank ⇒ omit / `null` ⇒ to-taste.
- Errors: `422 ValidationIssue[]` → map `loc` (`["body","ingredients",3,"item"]`)
  to the offending row/field; domain `422` strings → form-level banner.

### 10.4 RecipeDetail  (`/recipes/:id`) — body Phase 3; availability Phase 4; cook Phase 5

- Query `["recipe", id]` → `GET /api/recipes/{id}`.
- **Multiplier `Stepper`** (presets `½ 1 2 3` + free input, `> 0`) — one control,
  **resets to `1.0` on every visit** (a stale remembered multiplier is a
  footgun). It:
  - rescales the **displayed** ingredient quantities (via `formatQuantity` on
    `quantity * multiplier`), and
  - drives `["availability", id, multiplier]` →
    `GET /api/recipes/{id}/availability?multiplier=`, and
  - is the value sent by the cook action.
- **Availability table** (Phase 4): per line `item`, scaled `need`, and a status
  `Badge` per §5 / §7.4. Dedupe `group_*` into a group header by `group_key`, or
  render per line. `all_available` drives a header banner ("You have everything"
  / "Missing N items").
- **Cook action** (Phase 5): a **"Mark as cooked"** button + a
  **"deduct from inventory"** toggle (default on) → `POST /api/recipes/{id}/cook
  { multiplier, deduct }`. On `201`: invalidate `["availability", id]`,
  `["inventory"]`, `["cook-logs"]`, `["recipe-cook-logs", id]`. On `409`: the
  R-11 toast + refetch. **No confirm-heavy modal, no undo** (R-12) — but the
  button copy makes the deduction explicit.
- **Per-recipe history panel** (§10.8).
- Delete recipe → `Dialog` confirm → `DELETE` → invalidate `["recipes"]`,
  navigate to `/`.

### 10.5 Grocery create dialog (from RecipeList multi-select) — backend Phase 6

- Opens with the selected recipes listed, each with a compact **`Stepper`**
  (per-recipe multiplier, default `1×`) — this is the **only** point multipliers
  can be set (`POST /api/grocery` takes them at create only; a later line edit
  trips N6 reclassification).
- Optional list `name` (placeholder shows the server default).
- Submit → `POST /api/grocery { recipe_ids, multipliers }`.
  - `201` → invalidate `["grocery"]`, navigate to `/groceries/:id`.
  - `422` because a `recipe_id` vanished (R-13) → refetch `["recipes"]`, show
    which selected ids are gone, let the user drop them and retry.

### 10.6 GroceryLists  (`/groceries`) — backend Phase 6

- Query `["grocery", { status }]` → `GET /api/grocery?status=`; `active` default,
  a toggle for `archived`.
- Each list card: `name`, item count, checked count, `created_at`, status.
- Delete a list → `Dialog` confirm → `DELETE` (works in any status) → invalidate.

### 10.7 GroceryListDetail  (`/groceries/:id`) — backend Phase 6

- Query `["grocery", id]` → `GET /api/grocery/{id}`.
- Lines grouped **generated** vs **manual**; each: `item`, `formatQuantity`,
  a `checked` checkbox, `source`/`nettable`/frozen `Badge`s.
- **Check / uncheck** → `PATCH .../items/{id} { checked }` — the **only
  optimistic** mutation (Q16): flip immediately, roll back on error via React
  Query `onError`. Does **not** reclassify.
- **Edit `item` / `quantity` / `unit`** → inline; `quantity` + `unit` sent as an
  **atomic pair** (the form disables sending one without the other; matches the
  `422` N6 rule). On success of an edit to a **generated** line, show a quiet
  note that it's now a manual line ("we'll stop netting this against your
  stock").
- **Add manual line** → `POST .../items { item, quantity?, unit? }`.
- **Frozen lines** (`added_to_inventory: true`): render read-only with an
  "added to inventory" `Badge` and `applied_quantity`/`applied_unit`; `PATCH` /
  `DELETE` affordances hidden (they'd `409`).
- **Submit** → `Dialog` explaining "adds every checked, unfrozen, quantified line
  to your inventory; this can't be undone" → `POST .../submit`. On `200`:
  invalidate `["grocery", id]`, `["inventory"]`. Re-submitting is allowed and
  only picks up newly-checked lines — the button stays available.
- **Archive** → `Dialog` confirm → `POST .../archive`. `409 "list is not
  active"` → toast + refetch.
- Archived list → all mutation affordances hidden; `409` from a stale one → toast.

### 10.8 History

**Two surfaces, one shared `CookLogRow` + `DeductionDetail` accordion.**

**Per-recipe panel** — inside RecipeDetail (§10.4), **not** its own route.
- Query `["recipe-cook-logs", id]` → `GET /api/recipes/{id}/cook-logs`
  (unpaginated, `cooked_at DESC, id DESC`).
- Header: "Cooked N times · last {formatRelative}".
- No recipe-title column (you know the recipe).

**Global `/history`** — backend Phase 5, a primary nav destination.
- Query `["cook-logs", { limit, offset }]` → `GET /api/cook-logs?limit=50&offset=`.
- Newest-first across all recipes; "Showing X of `total`" + **Load more**
  (`offset += limit`).
- Each row shows the **recipe title**, linked to `/recipes/:recipe_id` when
  `recipe_id` is non-null; when `null` (recipe deleted) render `recipe_title`
  (snapshot) as plain text + a "recipe deleted" marker.

**Shared row:**
- Line: `formatDateTime(cooked_at)` · `cooked_by.username` ·
  `×{formatQuantity(multiplier, null)}` · deduct on/off.
- `deduct: false` → no accordion, a grey "logged — stock not changed" `Badge`
  (`deductions` is `[]`).
- **Collapsed accordion**: a summary from `deductions[].reason`, e.g.
  "12 ingredients · 2 ran out · 1 not tracked".
- **Expanded**: a compact table, one row per `CookDeductionRead`:
  `item` · `requested → deducted {inventory_unit}` · `before → after` · a chip:

  | `reason` | chip |
  |---|---|
  | `ok` | quiet / none |
  | `clamped to 0` | amber "ran out" |
  | `not in inventory` | grey "not tracked" |
  | `have uncertain (incompatible unit)` | amber "check what you have" |
  | `to taste` | grey "to taste" |

- No undo affordance on either surface (R-12).

### 10.9 Inventory  (`/inventory`) — backend Phase 4

- Query `["inventory"]` → `GET /api/inventory` (server order
  `match_name ASC, unit_bucket ASC`).
- `DataTable`: `item`, `match_name`, `unit_bucket`,
  `formatQuantity(display_quantity, display_unit)`, `updated_at`.
- **Add** → `POST /api/inventory { item, quantity, unit?, match_name? }` — note
  it's an **additive upsert**: a matching `(match_name, unit_bucket)` row gains
  quantity rather than a new row appearing. Copy in the form says so.
- **Edit** → inline `PATCH`, with the §5 rules enforced **before** sending:
  - setting `quantity` forces the `unit` field into the request;
  - `unit` can't change the bucket — the field offers only same-bucket units;
    for a non-COUNT row, clearing `unit` is blocked; for a COUNT row it's
    allowed;
  - `match_name` is shown normalized after save; a normalized collision →
    `409` inline on the field.
- **`match_name` editor** is prominent — it's the recipe↔inventory join key; a
  small hint explains "this links the item to recipe ingredients".
- **Delete** → `Dialog` confirm → `DELETE`.
- After a cook or a grocery submit elsewhere, `["inventory"]` is invalidated so
  quantities here stay live.

---

## 11. Open decisions

Tracked here (few enough to not need a separate `issues.md`). Each is resolved
before its owning phase.

| # | Decision | Owning phase | Lean |
|---|---|---|---|
| O-1 | Tag/cuisine facet source — derive from the loaded recipe list, or a fixed vocab | 3 | derive from loaded list |
| O-2 | Reorder UX for ingredient rows / steps — drag vs up/down buttons | 3 | up/down buttons (keyboard-safe, cheap); drag is a later polish |
| O-3 | History "Load more" vs numbered pages | 5 | Load more |
| O-4 | Theme toggle placement (user menu vs a settings screen) | 1 | user menu; no settings screen in v1 |
| O-5 | Offline/refetch behavior for the store-walk (grocery detail on a phone with flaky wifi) | 6 | React Query defaults + a visible "reconnecting" hint; no service worker in v1 |

**Q19 — backend vocabulary (v2, backend-owned):** investigate renaming
`AvailabilityStatus` `"have_uncertain"` and the `nettable` boolean (a negated
name) to something a reader parses without the spec — e.g. `units_comparable` /
`incomparable_units`, and consider giving grocery lines a status enum for
parity. **Not a v1 frontend change**; a one-line note is proposed in
`../features.md` for the backend track to carry through its own process. v1
frontend copy (§7.4) fully covers the cook-facing language regardless.

---

## 12. Definition of done (frontend v1)

- Every screen in §10 is implemented against real endpoints (backend Phases 2–6
  merged) with the loading/empty/error conventions of §3.
- The three oracle suites (§7.1–§7.3) are green and were authored under the
  contract-test gate ([`plan.md`](plan.md)).
- Testing Library flow tests cover Login, RecipeForm (create + edit), Inventory
  PATCH rules, and Grocery check→submit (Q21).
- `npm run lint && npm run test:run && npm run build` are green; the `frontend`
  CI job passes.
- `src/types.ts` matches `../spec.md` §5 (R-1 diff done).
- No signup UI in the default bundle (`VITE_ENABLE_REGISTER` unset).
- The a11y bar (§9) is met on every screen.
- LAN deployment notes exist (Phase 8): serving origin added to
  `RECIPE_CORS_ORIGINS`, the `VITE_ENABLE_REGISTER` bootstrap procedure, and the
  `npm run build` output location.
