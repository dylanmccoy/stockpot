# frontend/CLAUDE.md

Navigation map that keeps each frontend `/implement` inside the smart zone —
file map, spec-section table, invariants. Stack and command table: root
`CLAUDE.md`.

Import direction is one-way:
`types → lib → api/client → api/<resource> → components → pages → app`.

## Read only what the ticket cites

`docs/frontend/spec.md` is ~930 lines. Read the sections the ticket's **Spec:**
field names, nothing else. §5 there is a **non-normative mirror** of `docs/spec.md`
§5 — use it; only open the backend spec when a ticket says to (the integrate-*
tickets do, for a re-diff).

To read one section: `grep -nE '^#{1,6} ' docs/frontend/spec.md` for the
line-numbered heading list, then `Read` with `offset`/`limit` bounded to the
cited section.

| Area | `docs/frontend/spec.md` §§ | File(s) | Test |
| --- | --- | --- | --- |
| App shell / routing | 3 | `app/router.tsx`, `app/AppShell.tsx`, `app/RequireAuth.tsx` | `app/router.test.tsx`, `app/AppShell.test.tsx` |
| Auth & session | 4, 5 "Auth" | `auth/`, `pages/Login.tsx`, `pages/RegisterForm.tsx` | `auth/AuthProvider.test.tsx`, `pages/Login.test.tsx`, `app/auth.flow.test.tsx` |
| Error model & catalog | 6 | `lib/apiError.ts`, `test/errorHandlers.ts` | `test/errorHandlers.test.ts` |
| `lib/parseIngredients.ts` (paste splitter) | 7.1 | `lib/parseIngredients.ts` | `.oracle.test.ts` + `.test.ts` |
| `lib/format.ts` (quantity / number / datetime) | 7.2 | `lib/format.ts` | `.oracle.test.ts` + `.test.ts` |
| `lib/apiError.ts` (`parseApiError`) | 7.3 | `lib/apiError.ts` | `.oracle.test.ts` + `.test.ts` |
| "Uncertain" copy | 7.4 | (screen code) | (screen test) |
| Component system | 8 | `components/` | one `*.test.tsx` per component |
| Accessibility bar | 9 | (screen code) | assert in screen tests + `test:e2e` |
| Login | 10.1, 4 | `pages/Login.tsx` | `pages/Login.test.tsx` |
| RecipeList | 10.2 | `pages/RecipeList.tsx` | `pages/RecipeList.test.tsx` |
| RecipeForm | 10.3, 7.1, 7.3 | `pages/RecipeForm.tsx` | `pages/RecipeForm.test.tsx` |
| RecipeDetail (body / availability / cook) | 10.4, 7.2, 7.4 | `pages/RecipeDetail.tsx` | `pages/RecipeDetail.test.tsx` |
| Grocery create dialog | 10.5 | `pages/RecipeList.tsx` + create-dialog component | `pages/RecipeList.test.tsx` |
| GroceryLists index | 10.6 | `pages/GroceryLists.tsx` | `pages/GroceryLists.test.tsx` |
| GroceryListDetail | 10.7, 7.2, 7.4 | `pages/GroceryListDetail.tsx` | `pages/GroceryListDetail.test.tsx` |
| History (per-recipe panel + `/history`) | 10.8 | `pages/History.tsx`, shared `CookLogRow`/`DeductionDetail` | `pages/History.test.tsx` |
| Inventory | 10.9 | `pages/Inventory.tsx` | `pages/Inventory.test.tsx` |
| API mirror per resource | 5 "<resource>" | `api/<resource>.ts` | `api/client.test.ts` |
| Definition of done | 12 | — | — |

Delivery phases: `docs/frontend/plan.md` (0–8). Ticket order and split-parent
markers: `.scratch/frontend-v1/issues/`.

## File map (`frontend/src/`)

| Path | Responsibility |
| --- | --- |
| `types.ts` | Hand-maintained mirror of `docs/spec.md` §5 (R-1). Change it and `docs/frontend/spec.md` §5 together. |
| `api/client.ts` | The one `fetch` wrapper: `/api` prefix, `Authorization: Bearer` from `localStorage`, both FastAPI error shapes → thrown `ApiError`, 204 handling, 401 seam. |
| `api/{auth,recipes,inventory,cookLogs,grocery}.ts` | Thin typed adapters (R-2). All resource calls go through these. |
| `auth/` | `AuthProvider` + `useAuth` + `context.ts`. Token in `localStorage` under `recipe.token`; `me` hydration; cache drop on 401. |
| `app/` | `router.tsx` (`<Routes>` table), `AppShell.tsx` (responsive nav), `RequireAuth.tsx` (→ `/login?next=`), `theme.tsx`. |
| `lib/` | Pure leaf helpers under the locked-oracle gate (`*.oracle.test.ts`). |
| `components/` | Design-system primitives; barrel export in `components/index.ts`. |
| `pages/` | One module per screen (spec §10). |
| `test/` | MSW `server.ts` + `handlers.ts` (happy path per `docs/spec.md` §5) + `errorHandlers.ts` (one per `docs/frontend/spec.md` §6 row). |
| `styles/` | `tokens.css` + `global.css`. |

## Invariants agents keep re-deriving

- All server state goes through TanStack Query via an `api/<resource>.ts` adapter.
  No ad-hoc `fetch` in components or pages.
- `types.ts` is the mirror — never widen it to fit a component. Fix the mirror
  **and** `docs/frontend/spec.md` §5 together.
- `lib/*` changes are gated by the locked `*.oracle.test.ts` — never edit an
  oracle to make code pass.
- Styling: CSS Modules + `styles/tokens.css` only. No inline style objects, no
  new raw colors, no status conveyed by color alone (§9).
- Tests run with `onUnhandledRequest: "error"` — every request needs an MSW
  handler in `test/handlers.ts` or a per-test override.
- Mock-first: build against MSW; the `integrate-*` tickets (15–18) wire each
  resource to the real backend and re-diff `types.ts` against `docs/spec.md` §5.

## Commands

Full table in root `CLAUDE.md`. From `frontend/`: `npm run test:run` (all),
`npm run test:run -- src/pages/RecipeForm.test.tsx` (one file).
