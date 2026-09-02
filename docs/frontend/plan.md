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
- No live network calls in tests — MSW intercepts everything.
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

- [ ] `auth/AuthProvider` + `useAuth`: token in `localStorage` (`recipe.token`),
      `login` / `logout`, `me` hydration on load, cache drop on `401`.
- [ ] `api/client.ts` 401 interceptor → clear token + cache + `Navigate
      /login?next=`.
- [ ] `api/auth.ts`; `pages/Login.tsx`; Register form behind
      `VITE_ENABLE_REGISTER` (+ `ImportMetaEnv` typing).
- [ ] Tests: 5 × `get_current_user` 401 shapes surface as a redirect; login
      success → `next` redirect; login `401` → inline; logout clears; expired
      token on load → logged out.

**Exit:** the flow test passes against real BE Phase 2; no signup UI when the
flag is unset.

---

## Phase 3 — Recipes  (integrates BE Phase 3)

Spec: `spec.md` §7.1 (splitter), §10.2, §10.3, §10.4 (body only), §10.8
(per-recipe panel shell); `../spec.md` §5.2.

- [ ] `lib/parseIngredients.ts` — oracle suite authored under the gate first.
- [ ] `api/recipes.ts`; `api/cookLogs.ts` (read shape only for the panel shell).
- [ ] `pages/RecipeList.tsx` — `["recipes"]` query; client search / cuisine+tag
      facets / sort; card grid; multi-select mode + sticky action bar (dialog
      wired in Phase 6).
- [ ] `pages/RecipeForm.tsx` — unified editable ingredient table + paste-to-append
      with a parsed-row preview; steps list; tag chips; `source_url` plain field;
      create + edit (PUT full replace); `loc`-mapped `422` errors.
- [ ] `pages/RecipeDetail.tsx` — body, ingredients, steps, notes; multiplier
      `Stepper` rescales displayed quantities (availability/cook wired later);
      per-recipe history panel shell; delete → confirm → `/`.
- [ ] Flow tests: RecipeForm create (mixed pasted + structured rows), RecipeForm
      edit (full replace clears old rows).

**Exit:** splitter oracle green; both RecipeForm flow tests green against real
BE Phase 3.

---

## Phase 4 — Inventory & availability  (integrates BE Phase 4)

Spec: `spec.md` §10.9, §10.4 (availability table), §7.4; `../spec.md` §5.3, §5.5.

- [ ] `api/inventory.ts` (adapter — R-2).
- [ ] `pages/Inventory.tsx` — `["inventory"]` table; additive-upsert add form
      with explanatory copy; inline `PATCH` with the §5 client-side rule
      enforcement (quantity forces unit; unit stays in bucket; COUNT vs non-COUNT
      null; normalized `match_name`; `409` collision inline); prominent
      `match_name` editor; delete confirm.
- [ ] `api/recipes.ts` availability adapter; RecipeDetail availability table:
      per-line scaled `need`, status `Badge`s (§7.4 copy), `group_key` dedupe or
      per-line, `all_available` header banner.
- [ ] Flow test: the four PATCH-rejection rules return the expected inline errors;
      a valid `{quantity, unit}` PATCH updates the row.

**Exit:** availability adapter diff-reviewed against the merged BE Phase 4 DTOs;
PATCH-rule flow test green.

---

## Phase 5 — Cook & history  (integrates BE Phase 5)

Spec: `spec.md` §10.4 (cook action), §10.8; `../spec.md` §5.4.

- [ ] `api/cookLogs.ts` full; cook mutation on `api/recipes.ts`.
- [ ] RecipeDetail cook action: "Mark as cooked" + "deduct" toggle → `POST
      /cook`; on `201` invalidate availability/inventory/cook-logs; on `409` the
      R-11 toast + refetch. No undo affordance.
- [ ] Shared `CookLogRow` + `DeductionDetail` accordion (collapsed summary from
      `reason`s; expanded 11-key table; the 5 reason chips including the amber
      "check what you have").
- [ ] `pages/History.tsx` — `["cook-logs", {limit, offset}]`; newest-first;
      recipe-title link with the deleted-recipe fallback; Load more.
- [ ] Wire the per-recipe panel (`["recipe-cook-logs", id]`).

**Exit:** cook adapter diff-reviewed against merged BE Phase 5; the accordion
renders all five `reason` branches with `null`s only where §5.4 permits.

---

## Phase 6 — Grocery  (integrates BE Phase 6)

Spec: `spec.md` §10.5, §10.6, §10.7; `../spec.md` §5.6.

- [ ] `api/grocery.ts` (adapter — R-2).
- [ ] Grocery create `Dialog` from RecipeList multi-select: per-recipe multiplier
      `Stepper`s (the only place multipliers are set), optional name; `422`
      missing-`recipe_id` recovery (R-13).
- [ ] `pages/GroceryLists.tsx` — active/archived; delete-in-any-status.
- [ ] `pages/GroceryListDetail.tsx` — generated vs manual grouping; **optimistic**
      check/uncheck with rollback; atomic `{quantity, unit}` inline edit +
      "now manual" note on a generated line; add manual line; frozen lines
      read-only with `applied_*`; submit `Dialog` (forward-only copy) + re-submit
      allowed; archive confirm + `409` handling.
- [ ] Flow test: check two lines → submit → inventory invalidated, lines frozen;
      PATCH a frozen line → `409` toast; edit a generated line → reclassified.

**Exit:** grocery adapter diff-reviewed against merged BE Phase 6; check→submit
flow test green.

---

## Phase 7 — Hardening

Spec: `spec.md` §6, §9, §12.

- [ ] Every `spec.md` §6 catalog row exercised by a test (MSW error handler →
      asserted surface).
- [ ] A11y sweep across all nine screens: keyboard traversal, focus on route
      change, `aria-live` on toasts, contrast in both themes, no color-only
      status.
- [ ] Loading / empty / error states present and consistent on every screen
      (`spec.md` §3).
- [ ] `src/types.ts` re-diffed against `../spec.md` §5 after any Phase 2–6 spec
      churn.
- [ ] React Query defaults reviewed (stale times, retry, refetch-on-focus) for
      the store-walk case (O-5).

**Exit:** `spec.md` §12 checklist complete except deployment docs.

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
| 0 — Tooling & skeleton rewrite | Not started |
| 1 — Design system & app shell | Not started |
| 2 — Auth | Not started |
| 3 — Recipes | Not started |
| 4 — Inventory & availability | Not started |
| 5 — Cook & history | Not started |
| 6 — Grocery | Not started |
| 7 — Hardening | Not started |
| 8 — Deployment docs | Not started |
