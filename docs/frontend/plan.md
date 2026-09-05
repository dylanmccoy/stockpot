# Frontend v1 Delivery Plan

Execution roadmap for the frontend v1 SPA. It defines phase order, gates, and the
integration timing against the backend. It does not repeat the contract — that is
[`spec.md`](spec.md).

## Document map

| Document | Authority |
|---|---|
| [`spec.md`](spec.md) | Normative frontend v1 behavior: stack, shell, screens, pure logic, errors, a11y |
| [`plan.md`](plan.md) (this file) | Delivery sequence, phase gates, backend-phase mapping |
| [`decisions.md`](decisions.md) | Grill outcomes Q1–Q25 with rationale; non-normative |
| [`../spec.md`](../spec.md) | The backend API contract (frozen for v1); the frontend reads it, never edits it |

When documents disagree: `../spec.md` for API shape → `spec.md` for frontend
behavior → this file for sequence → `decisions.md` for rationale only.

## Outcome

Ship the household web UI for the backend v1 loop:

1. Log in (fixed 30-day session).
2. Create / edit / browse structured recipes.
3. Track inventory with real quantities.
4. See a recipe's availability against stock, scaled by a multiplier.
5. Mark a recipe cooked, optionally deducting stock; review made-history.
6. Build grocery lists from selected recipes, check them off, submit back to
   stock.

No dashboard, no "what can we make now", no photo/URL import, no reviews, no
receipt OCR — those are v2 (`../features.md`).

## Strategy

- **Mock-first, parallel with backend Phases 2–6.** `../spec.md` is complete and
  frozen. Build against MSW handlers keyed to `../spec.md` §5; swap to real calls
  per the mapping table below as each backend phase merges.
- **Adapters contain the churn (R-2).** The three math DTOs (availability, cook,
  grocery) may still move in a backend Phase 4–6 contract-test gate. Every screen
  that renders them sits behind `src/api/<resource>.ts`; a late DTO change is a
  one-file edit, and the screen is not wired to real calls until that phase's
  diff review clears.
- **Smallest thing that satisfies the spec.** Every new dependency is listed in
  `spec.md` §1 with a reason; adding one not listed needs a spec update.
- Every phase ends with `cd frontend && npm run lint && npm run test:run &&
  npm run build` green, and the `frontend` CI job green.

## Constraints

- Extend `frontend/`; keep Vite + React 18 + TS strict, the `tsconfig` solution
  layout, and `npm run build` = `tsc -b && vite build`.
- Dev uses the Vite proxy (`/api` → `:8000`); no base URL, no CORS in dev.
- No live network calls in the **Vitest suite** — MSW intercepts everything.
  (The separate `integration` Playwright project is the deliberate exception: it
  boots the real backend beside Vite and drives it through the dev proxy — see
  Phase 2.)
- The frontend track does not edit `../spec.md`, `../plan.md`, `../phases/**`,
  `../issues.md`, `../decisions.md`, or `backend/**`. One row in `../features.md`
  is proposed for the backend track (Q19) and changed only through their process.
- `src/types.ts` stays a hand-maintained mirror of `../spec.md` §5 (R-1).

## Contract-test gate (R-7 analogue)

`spec.md` §7.1–§7.3 — the paste splitter, `format.ts`, and `parseApiError` — use
a locked-oracle slice, mirroring the backend's independent gate:

- Before implementation code for one of these modules is written, a
  **fresh-context author** translates that module's oracle table in `spec.md`
  into black-box tests (`*.oracle.test.ts`) and they are accepted.
- The implementation pass may add cases but must not edit or delete an accepted
  oracle case.
- A wrong oracle is fixed by editing `spec.md` and the test together, with the
  reason recorded in `decisions.md`.
- Everything else (page flow tests, `api/` wrappers, component tests) is authored
  by the normal implementation pass.

## Phases

Nine phases, 0–8. Phase 8 is deployment docs. Each phase links the `spec.md`
sections it implements and ends with the full frontend check green.

| # | Phase | Depends on (frontend) | Integrates real backend after | Gate |
|---|---|---|---|---|
| 0 | Tooling & skeleton rewrite | — | — (MSW only) | CI green on the rewrite |
| 1 | Design system & app shell | 0 | — | a11y bar (spec §9) on a demo route |
| 2 | Auth | 1 | **BE Phase 2** | 5 × 401 paths; login/logout flow test |
| 3 | Recipes (list, detail body, form) | 2 | **BE Phase 3** | splitter oracle; RecipeForm create+edit flow tests |
| 4 | Inventory & availability | 3 | **BE Phase 4** | PATCH-rule flow test; availability adapter diff review |
| 5 | Cook & history | 4 | **BE Phase 5** | cook adapter diff review; deduction accordion renders all 5 reasons |
| 6 | Grocery | 5 | **BE Phase 6** | grocery adapter diff review; check→submit flow test |
| 7 | Hardening | 2–6 | — | error catalog (spec §6) each exercised in tests; a11y sweep |
| 8 | Deployment docs | 7 | — | LAN/CORS/bootstrap notes reviewed |

### Backend → frontend integration map

| Backend phase merged | Frontend can integrate (not just mock) |
|---|---|
| BE 2 — auth + app factory | Login, bearer flow, 401 handling, `GET /api/auth/me` |
| BE 3 — structured recipes | RecipeList, RecipeForm, RecipeDetail body, recipes CRUD |
| BE 4 — inventory + availability | Inventory CRUD, `GET /api/recipes/{id}/availability` |
| BE 5 — cooking + history | Cook action, per-recipe + global cook-log views |
| BE 6 — grocery lists | Full grocery flow (create, items, submit, archive) |
| BE 7 — docs | Frontend Phase 8 LAN/CORS deployment notes |

Frontend Phases 0–1 have no backend dependency and can start immediately.
Phases 2–6 can each be **built** against MSW ahead of the matching backend phase;
they are **wired to real calls and their gate closed** only once that backend
phase has merged and (for 4–6) its contract-test diff review has cleared.

---

## Phase 0 — Tooling & skeleton rewrite

**Goal:** replace the pre-v1 skeleton with the module layout in `spec.md` §1, add
the stack, keep CI green.

Spec: `spec.md` §1, §2.

- [ ] Add deps: `react-router-dom`, `@tanstack/react-query`; dev: `msw`,
      `eslint` + `@typescript-eslint` + `eslint-plugin-react-hooks`, `prettier`.
- [ ] Delete `src/{App,types,api,api.test}.tsx?`; scaffold `src/app/`, `src/api/`,
      `src/auth/`, `src/lib/`, `src/components/`, `src/pages/`, `src/styles/`,
      `src/test/`.
- [ ] `api/client.ts`: `/api` prefix, `Authorization: Bearer` injection from
      `localStorage`, `parseApiError` normalization, 204 handling, typed throw.
- [ ] `src/types.ts`: transcribe `../spec.md` §5 (= `spec.md` §5); diff.
- [ ] MSW: `src/test/server.ts` + `handlers.ts` (happy path for every `../spec.md`
      §5 route) + error handlers for every `spec.md` §6 row; wire into
      `setupTests.ts`.
- [ ] `main.tsx`: `QueryClientProvider` + `AuthProvider` + router.
- [ ] Add `npm run lint`; update the `frontend` CI job to
      `npm ci && npm run lint && npm run test:run && npm run build`.
- [ ] Retitle `index.html` to "Recipes".

**Exit:** CI green; `api/client.test.ts` green against MSW; no dead skeleton
files remain.

---

## Phase 1 — Design system & app shell

**Goal:** the token layer, the ~8 primitives, and the responsive nav shell.

Spec: `spec.md` §3 (shell), §8 (components), §9 (a11y).

- [ ] `styles/tokens.css` — color roles, 4px space scale, type scale, radii;
      `:root` light + `[data-theme="dark"]`; `prefers-color-scheme` default with
      a `localStorage` override; `global.css` reset.
- [ ] Primitives: `Button`, `Input`/`Textarea`/`Select`, `Field`, `Card`,
      `DataTable`, `Dialog`, `Toast` + `ToastProvider`, `Badge`, `Stepper` —
      each keyboard- and SR-correct per §9.
- [ ] `app/AppShell.tsx` — top bar ≥ 640px, bottom tab bar < 640px, four
      destinations, `aria-current`, user menu with theme toggle + logout.
- [ ] `app/router.tsx` — the full route table (`spec.md` §3) with placeholder
      pages; `app/RequireAuth.tsx` → `/login?next=`.
- [ ] `lib/apiError.ts` — `parseApiError` + `useFormErrors` + `isFieldError` /
      `fieldName` (oracle suite per the gate).
- [ ] A component demo route (dev-only) to eyeball every primitive in both
      themes.

**Exit:** a11y bar met on the demo route (keyboard, focus, contrast both themes,
live regions); `parseApiError` oracle suite green.

---

## Phase 2 — Auth  (integrates BE Phase 2)

Spec: `spec.md` §4, §10.1; error rows `401` / `403` in §6.

- [x] `auth/AuthProvider` + `useAuth`: token in `localStorage` (`recipe.token`),
      `login` / `logout`, `me` hydration on load, cache drop on `401`.
- [x] `api/client.ts` 401 interceptor → clear token + cache + `Navigate
      /login?next=`.
- [x] `api/auth.ts`; `pages/Login.tsx`; Register form behind
      `VITE_ENABLE_REGISTER` (+ `ImportMetaEnv` typing).
- [x] Tests: 5 × `get_current_user` 401 shapes surface as a redirect; login
      success → `next` redirect; login `401` → inline; logout clears; expired
      token on load → logged out. (`src/app/auth.flow.test.tsx` vs MSW.)
- [x] Integrated against real BE Phase 2 (ticket 14): MSW handlers diffed
      byte-for-byte against a running backend — bearer header, `token` field,
      and every `401` / `403` / `409` / `422` body shape match, so `handlers.ts`
      / `client.ts` need no change. End-to-end confirmed by
      `frontend/e2e/auth.integration.spec.ts` (the `integration` Playwright
      project boots `uv run uvicorn` beside Vite and drives the full login /
      reload-`me` / logout / rejected-token / registration lifecycle through the
      real dev proxy).

**Exit:** ✅ the flow test passes vs MSW **and** the same scenarios pass
end-to-end against real BE Phase 2; no signup UI when the flag is unset
(`src/pages/Login.test.tsx`).

Notes on E2E coverage vs the MSW flow test:

- The **five** `get_current_user` `401` shapes collapse to one real response
  (`401 {"detail":"not authenticated"}`), so the E2E exercises one real
  rejected-token redirect; the 5-way enumeration stays in `auth.flow.test.tsx`.
- Registration refusal is exercised E2E via the real `403 "invalid
  registration code"` (Playwright has no per-project `webServer`, so a
  registration-**disabled** backend can't run in the same pass). Same status +
  inline-banner surface per `spec.md` §6; the `"registration disabled"` string
  itself is locked in `src/pages/Login.test.tsx` vs MSW.

> **Cross-track note (backend conformance).** `docs/spec.md` §Mechanical
> defaults guarantees datetimes serialize as `…+00:00`, but the running backend
> (Pydantic 2.13) emits `…Z` with microseconds (e.g.
> `2026-09-02T20:23:30.628187Z`). The frontend absorbs both (`lib/format.ts`
> `formatDateTime` parses via `new Date`), and the MSW fixture keeps the
> spec form per R-1. Flagged for the backend track; no frontend change.

---

## Phase 3 — Recipes  (integrates BE Phase 3)

Spec: `spec.md` §7.1 (splitter), §10.2, §10.3, §10.4 (body only), §10.8
(per-recipe panel shell); `../spec.md` §5.2.

- [x] `lib/parseIngredients.ts` — oracle suite authored under the gate first.
- [x] `api/recipes.ts`; `api/cookLogs.ts` (read shape only for the panel shell).
- [x] `pages/RecipeList.tsx` — `["recipes"]` query; client search / cuisine+tag
      facets / sort; card grid; multi-select mode + sticky action bar (dialog
      wired in Phase 6).
- [x] `pages/RecipeForm.tsx` — unified editable ingredient table + paste-to-append
      with a parsed-row preview; steps list; tag chips; `source_url` plain field;
      create + edit (PUT full replace); `loc`-mapped `422` errors.
- [x] `pages/RecipeDetail.tsx` — body, ingredients, steps, notes; multiplier
      `Stepper` rescales displayed quantities (availability/cook wired later);
      per-recipe history panel shell; delete → confirm → `/`.
- [x] Flow tests: RecipeForm create (mixed pasted + structured rows), RecipeForm
      edit (full replace clears old rows).
- [x] Integrated against real BE Phase 3 (ticket 15): `types.ts` / `spec.md` §5.2
      re-diffed against the merged backend — request + response shapes match
      field-for-field, no drift. The one gap was error *shape*: Pydantic
      union-tags a bad object ingredient element's `loc`
      (`["body","ingredients",N,"RecipeIngredientIn","item"]`, plus a
      `["body","ingredients",N,"str"]` sibling), which the spec §10.3 map didn't
      expect — reconciled in `lib/apiError.ts` (`normalizeLoc` /
      `isUnionBranchNoise`), covered by `apiError.test.ts`, `errorHandlers.ts`
      (`ingredientMemberValidation`), and a RecipeForm screen test. End-to-end
      confirmed by `frontend/e2e/recipes.integration.spec.ts` (the `integration`
      Playwright project: list read, mixed create round-trip, PUT full-replace
      row drop + id churn, `loc`-mapped `422` on the row, multiplier rescale).

**Exit:** ✅ splitter oracle green; both RecipeForm flow tests green vs MSW **and**
the create / edit-full-replace / `422`-mapping scenarios pass end-to-end against
real BE Phase 3.

Notes on E2E coverage vs the MSW flow tests:

- Pydantic renders an untagged-union member error
  (`list[RecipeIngredientIn | str]`) with the winning branch name spliced into
  `loc` and a losing-branch sibling. `normalizeLoc` collapses the tag and
  `isUnionBranchNoise` drops the sibling, so both the spec's clean
  `["body","ingredients",N,"item"]` shape and the real tagged one map to the
  same row + field.
- Datetimes still serialize as `…Z` with microseconds, not the `…+00:00` the
  spec form promises (already flagged for the backend track under Phase 2). The
  frontend absorbs both via `lib/format.ts`; the MSW fixture keeps the spec
  form per R-1.

---

## Phase 4 — Inventory & availability  (integrates BE Phase 4)

Spec: `spec.md` §10.9, §10.4 (availability table), §7.4; `../spec.md` §5.3, §5.5.

- [x] `api/inventory.ts` (adapter — R-2). (ticket 08a)
- [x] `pages/Inventory.tsx` — `["inventory"]` table; additive-upsert add form
      with explanatory copy; inline `PATCH` with the §5 client-side rule
      enforcement (quantity forces unit; unit stays in bucket; COUNT vs non-COUNT
      null; normalized `match_name`; `409` collision inline); prominent
      `match_name` editor; delete confirm. (tickets 08a, 08b)
- [x] `api/recipes.ts` availability adapter; RecipeDetail availability table:
      per-line scaled `need`, status `Badge`s (§7.4 copy), `group_key` dedupe or
      per-line, `all_available` header banner. (ticket 09)
- [x] Flow test: the four PATCH-rejection rules return the expected inline errors;
      a valid `{quantity, unit}` PATCH updates the row. (ticket 08b)

**Exit:** availability adapter diff-reviewed against the merged BE Phase 4 DTOs;
PATCH-rule flow test green. — **cleared** (ticket 16): `AvailabilityLine` gained
`ingredient_id` and `need_unit` tightened to non-null in `types.ts` + §5;
inventory + availability shapes and all four PATCH rejections verified against
the merged BE Phase 4 backend.

---

## Phase 5 — Cook & history  (integrates BE Phase 5)

Spec: `spec.md` §10.4 (cook action), §10.8; `../spec.md` §5.4.

- [x] `api/cookLogs.ts` full; cook mutation on `api/recipes.ts`. (ticket 10; wired
      to the real backend, ticket 17)
- [x] RecipeDetail cook action: "Mark as cooked" + "deduct" toggle → `POST
      /cook`; on `201` invalidate availability/inventory/cook-logs; on `409` the
      R-11 toast + refetch. No undo affordance. (ticket 10)
- [x] Shared `CookLogRow` + `DeductionDetail` accordion (collapsed summary from
      `reason`s; expanded 11-key table; the 5 reason chips including the amber
      "check what you have"). (tickets 11a, 11b)
- [x] `pages/History.tsx` — `["cook-logs", {limit, offset}]`; newest-first;
      recipe-title link with the deleted-recipe fallback; Load more. (ticket 11b)
- [x] Wire the per-recipe panel (`["recipe-cook-logs", id]`). (ticket 11a)

**Exit:** cook adapter diff-reviewed against merged BE Phase 5; the accordion
renders all five `reason` branches with `null`s only where §5.4 permits. —
**cleared** (ticket 17): `CookRequest`/`CookDeductionRead`/`CookLogRead` verified
field-for-field against the merged BE Phase 5 backend, live — a single real
`POST /cook` produced all five `reason` branches (`ok`, `clamped to 0`,
`to taste`, `not in inventory`, `have uncertain (incompatible unit)`), each
matching `types.ts`'s null-per-branch shape exactly; deleting the cooked recipe
then confirmed `recipe_id: null` / `recipe_title` snapshot on both the global
and per-recipe feeds. No DTO drift — `api/cookLogs.ts`, `api/recipes.ts` cook
adapter, and `types.ts` needed no code changes, only the dated re-diff note.

---

## Phase 6 — Grocery  (integrates BE Phase 6)

Spec: `spec.md` §10.5, §10.6, §10.7; `../spec.md` §5.6.

- [x] `api/grocery.ts` (adapter — R-2). (ticket 12a; wired to the real backend,
      ticket 18)
- [x] Grocery create `Dialog` from RecipeList multi-select: per-recipe multiplier
      `Stepper`s (the only place multipliers are set), optional name; `422`
      missing-`recipe_id` recovery (R-13). (ticket 12a)
- [x] `pages/GroceryLists.tsx` — active/archived; delete-in-any-status. (ticket 12b)
- [x] `pages/GroceryListDetail.tsx` — generated vs manual grouping; **optimistic**
      check/uncheck with rollback; atomic `{quantity, unit}` inline edit +
      "now manual" note on a generated line; add manual line; frozen lines
      read-only with `applied_*`; submit `Dialog` (forward-only copy) + re-submit
      allowed; archive confirm + `409` handling. (tickets 13a, 13b, 13c)
- [x] Flow test: check two lines → submit → inventory invalidated, lines frozen;
      PATCH a frozen line → `409` toast; edit a generated line → reclassified.
      (tickets 13c, 18 — live-verified against the real backend)

**Exit:** grocery adapter diff-reviewed against merged BE Phase 6; check→submit
flow test green. — **cleared** (ticket 18): `GroceryListCreate`,
`GroceryListItemUpdate`, `GroceryListItemRead`, `GroceryListRead` verified
field-for-field against the merged BE Phase 6 backend, live. Found and fixed one
real drift: `GroceryListItemIn.quantity`/`.unit` were typed `?:` (omittable) in
`types.ts`, but the backend schema declares them required-nullable (no default)
— an amount-less manual-line POST that omitted the keys 422'd ("field
required"). Fixed `types.ts`, the `docs/frontend/spec.md` §5 mirror, and
`buildAddLine` (now always sends `quantity`/`unit`, `null` when blank).
Live-drove the full flow against a booted BE Phase 6: create, `422` missing
`recipe_id`, check two lines → submit → both frozen with `applied_*` set and
`GET /inventory` reflecting both, `PATCH`/`DELETE` on a frozen line → `409`,
editing an unfrozen generated line → reclassified to `manual`/`nettable:true`,
a non-atomic `{quantity}`-only PATCH → `422` (N6), archive → `409` on
re-archive/PATCH/submit/item-POST of an archived list, `DELETE` on any status.

---

## Phase 7 — Hardening

Spec: `spec.md` §6, §9, §12.

- [x] Every `spec.md` §6 catalog row exercised by a test (MSW error handler →
      asserted surface). — ticket 19a.
- [x] A11y sweep across all nine screens: keyboard traversal, focus on route
      change, `aria-live` on toasts, contrast in both themes, no color-only
      status. — ticket 19b.
- [x] Loading / empty / error states present and consistent on every screen
      (`spec.md` §3). — ticket 19b.
- [x] `src/types.ts` re-diffed against `../spec.md` §5 after any Phase 2–6 spec
      churn. — ticket 19b.
- [x] React Query defaults reviewed (stale times, retry, refetch-on-focus) for
      the store-walk case (O-5). — ticket 19a.

**Exit:** `spec.md` §12 checklist complete except deployment docs. Met —
see §12 in `spec.md` (Phase 8 remains, blocked on backend Phase 7).

---

## Phase 8 — Deployment docs

Depends on backend Phase 7.

- [ ] LAN serving: build output, how to serve `dist/`, adding the serving origin
      to `RECIPE_CORS_ORIGINS` (token is a header not a cookie, so
      `allow_credentials=False` is fine).
- [ ] First-user bootstrap: run the backend with
      `RECIPE_ALLOW_REGISTRATION=true` + `RECIPE_REGISTRATION_CODE`, build the
      frontend with `VITE_ENABLE_REGISTER=1`, register, then rebuild/redeploy
      without the flag.
- [ ] Note the fixed 30-day session and no-refresh behavior for operators.

**Exit:** notes reviewed; a fresh reader can deploy the SPA on the LAN from them.

---

## Status

| Phase | Status |
|---|---|
| 0 — Tooling & skeleton rewrite | Complete |
| 1 — Design system & app shell | Complete |
| 2 — Auth | Complete — built vs MSW (ticket 04) and integrated against real BE Phase 2 (ticket 14) |
| 3 — Recipes | Complete — built vs MSW (03 oracles, 05a/05b list, 06a–c form, 07 detail) and integrated against real BE Phase 3 (ticket 15) |
| 4 — Inventory & availability | Complete — built vs MSW (08a, 08b, 09) and integrated against real BE Phase 4 (ticket 16) |
| 5 — Cook & history | Complete — built vs MSW (10, 11a, 11b) and integrated against real BE Phase 5 (ticket 17) |
| 6 — Grocery | Complete — built vs MSW (12a, 12b, 13a, 13b, 13c) and integrated against real BE Phase 6 (ticket 18) |
| 7 — Hardening | Complete — error-catalog coverage + React Query defaults (ticket 19a) and a11y sweep + state conventions + types re-diff (ticket 19b) |
| 8 — Deployment docs | Not started — blocked on BE Phase 7 |
