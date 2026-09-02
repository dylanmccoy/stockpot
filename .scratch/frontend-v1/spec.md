# Frontend v1 — SPA for the household recipe & inventory backend

Status: ready-for-agent

Related docs (authoritative; this ticket summarizes them):
- `docs/frontend/spec.md` — normative frontend contract
- `docs/frontend/plan.md` — phased delivery (frontend-native Phases 0–8)
- `docs/frontend/decisions.md` — grill outcomes Q1–Q25
- `docs/spec.md` — the frozen backend API contract (read-only for this work)

---

## Problem Statement

The backend v1 delivers the whole "make this recipe now" loop — structured
recipes, real-quantity inventory, availability checks, cook logging with stock
deduction, and grocery-list generation netted against stock — but the only way to
use it is the FastAPI `/docs` page and the test suite. There is no interface a
household member can actually use in a kitchen or at a store.

The existing React skeleton (`frontend/src/App.tsx` / `api.ts` / `types.ts`)
describes a pre-v1 recipe shape (`ingredients: string`, `instructions`) that no
longer exists, has no auth, no routing, and does not work against the v1 API.

## Solution

A single-page web app that runs on the household LAN and exposes the full backend
v1 loop through nine screens:

- **Log in** once (a fixed 30-day session).
- **Recipes**: browse a searchable/filterable list, view a recipe with its
  structured ingredients and steps, create and edit recipes (including pasting a
  block of ingredient lines), delete recipes.
- **Recipe detail** also shows, scaled by a **multiplier** control: an
  **availability** table (per ingredient: have it / short / check what you have /
  missing / to taste), a **"mark as cooked"** action with an optional
  **deduct-from-inventory** toggle, and a **made-history** panel for that recipe.
- **Inventory**: a table of inventory items with add (additive upsert),
  inline edit under the backend's PATCH rules, a prominent `match_name` editor,
  and delete.
- **Groceries**: select recipes from the list to generate a grocery list (with a
  per-recipe multiplier), check items off while shopping, add manual lines, edit
  lines, submit checked lines back into inventory, and archive the list.
- **History**: a global, paginated cook log across all recipes, each entry
  expandable to its per-ingredient deduction detail.

The UI is responsive (mobile-first for the cook and shop flows), uses a small
hand-rolled component system with light/dark theming, and meets a WCAG AA basics
bar. It is built **mock-first** against MSW handlers that mirror the backend
contract, and wired to the real API screen-by-screen as each backend phase
merges.

## User Stories

### Authentication & session

1. As a household member, I want to log in with a username and password, so that I can use the app.
2. As a logged-in user, I want my session to last 30 days without re-login, so that I don't have to authenticate every time I open the app in the kitchen.
3. As a logged-in user, I want to stay logged in after closing and reopening the browser tab, so that the app is there when I come back to it.
4. As a user whose session has expired or become invalid, I want to be sent back to the login screen automatically on my next action, so that I am never stuck looking at a broken screen.
5. As a user who gets bounced to login mid-task, I want to return to the screen I was on after logging back in, so that I don't lose my place.
6. As a user, I want a clear "invalid username or password" message on a failed login, so that I know to try again rather than assuming the app is down.
7. As a logged-in user, I want a "log out" action in a user menu, so that I can end my session on a shared device.
8. As a developer bootstrapping a fresh deployment, I want a registration form available behind a build flag, so that I can create the first user without hand-crafting an API call.
9. As a household running a normal deployment, I want no sign-up UI visible, so that the disabled-registration backend behavior is not contradicted by the interface.
10. As a developer using the flagged registration form, I want to see the specific backend rejection (registration disabled / invalid code / username taken), so that I can correct the input.

### Navigation & shell

11. As a user on a phone, I want a bottom tab bar with Recipes, Inventory, Groceries, and History, so that I can switch sections one-handed.
12. As a user on a laptop, I want the same four destinations in a top navigation bar, so that the app feels native to the larger screen.
13. As a user, I want the current section visually marked, so that I always know where I am.
14. As a user on a detail or form screen, I want a back affordance, so that I can return to the list I came from.
15. As a user, I want the app to open on the recipe list when I am logged in, so that I land somewhere useful.
16. As a user, I want to choose a light or dark theme (and have it remembered), so that the app is comfortable in different lighting.
17. As a user, I want the app to follow my system light/dark setting by default, so that it looks right without configuration.

### Recipe list (home)

18. As a user, I want to see all recipes as cards with title, cuisine, tags, and prep/cook time, so that I can scan my collection.
19. As a user, I want recipes ordered newest-first by default, so that recently added recipes are easy to find.
20. As a user, I want to type in a search box and filter recipes by title, cuisine, or tag text, so that I can find a recipe quickly.
21. As a user, I want to filter recipes by one or more cuisines and tags, so that I can narrow to a category.
22. As a user, I want to re-sort the list by title or by most recently updated, so that I can browse in the order that suits my task.
23. As a user, I want to click a recipe card to open its detail screen, so that I can see the full recipe.
24. As a user, I want an obvious "add recipe" action, so that I can start a new recipe.
25. As a user with no recipes yet, I want an empty state that invites me to add my first recipe, so that I know what to do next.
26. As a user, I want to enter a multi-select mode and tick several recipes, so that I can turn them into a grocery list in one step.
27. As a user in multi-select mode, I want a running count and a "create grocery list" action in a sticky bar, so that I can act on my selection without scrolling.

### Recipe create / edit

28. As a user, I want a form to create a recipe with title, cuisine, servings, prep time, cook time, source URL, tags, notes, and ordered steps, so that I can capture a full recipe.
29. As a user, I want to add, remove, and reorder ordered steps, so that the method reads correctly.
30. As a user, I want to add, remove, and reorder ingredient rows, each with quantity, unit, item, and an optional note, so that I can enter a structured ingredient list.
31. As a user, I want to leave an ingredient's quantity blank to mean "to taste", so that seasonings are represented honestly.
32. As a user, I want to paste a block of ingredient lines from a recipe website, have blank lines and bullet markers stripped and section headers like "For the sauce:" dropped, and have the resulting lines appended as rows, so that I don't have to type each line.
33. As a user, I want to see a preview of how my pasted lines will be interpreted (quantity / unit / item / note) before I save, so that I can fix a misparse by hand.
34. As a user editing an existing recipe, I want the form pre-filled with the current recipe, so that I only change what I need to.
35. As a user saving an edited recipe, I want the save to fully replace the recipe including its ingredients, so that removed rows actually go away.
36. As a user, I want field-level validation errors shown under the offending input (including which ingredient row is wrong), so that I can correct a rejected save.
37. As a user, I want a form-level message for a whole-request rejection (e.g. an ingredient row with no item text), so that I understand why the save failed.
38. As a user, I want the source URL rendered as an "open link" when it is a valid URL, so that I can jump to the original, while still being able to store any free text there.

### Recipe detail — body

39. As a user, I want to see a recipe's ingredients in order with quantities formatted for humans (e.g. "1½ cups", not "1.5"), so that the recipe is readable.
40. As a user, I want a raw converted quantity like 0.0264554 never shown as-is, so that numbers always look deliberate.
41. As a user, I want to see the recipe's steps, notes, cuisine, servings, and times, so that I have everything I need to cook.
42. As a user, I want to delete a recipe from its detail screen with a confirmation, so that I don't remove it by accident.

### Recipe detail — multiplier

43. As a user, I want a single multiplier control on the recipe detail screen with presets (½, 1, 2, 3) and a free numeric input, so that I can scale a recipe.
44. As a user, I want changing the multiplier to rescale the displayed ingredient quantities, so that I see "3 cups" rather than doing "1 cup × 3" in my head.
45. As a user, I want the multiplier to reset to 1 each time I open the screen, so that a scale I used once doesn't silently apply to a later cook.

### Recipe detail — availability

46. As a user, I want an availability table for the recipe against my current inventory, scaled by the multiplier, so that I know whether I can cook it now.
47. As a user, I want each ingredient marked as "have it", "short by X", "check what you have", "missing", or "to taste", so that I know exactly what is lacking.
48. As a user, I want a "check what you have" ingredient shown in amber with an explanation that I hold stock in an incomparable unit, and with no misleading shortfall number, so that I go verify rather than trust a bad figure.
49. As a user, I want a header banner telling me whether I have everything or how many items are missing, so that I get the answer at a glance.
50. As a user, I want ingredients that share a match name and unit grouped, so that the table isn't cluttered with duplicate rows.

### Recipe detail — cook

51. As a user, I want a "mark as cooked" button, so that I can record that I made the recipe.
52. As a user, I want a "deduct from inventory" toggle (on by default) next to it, so that I can log a cook without touching stock when I want to.
53. As a user, I want cooking at the current multiplier to deduct scaled amounts, so that a double batch draws down twice the stock.
54. As a user, I want the availability table and inventory to refresh right after I cook, so that the screen reflects the new stock.
55. As a user, I want no "undo cook" affordance, so that the interface doesn't imply a reversal the backend can't do.
56. As a user, I want a clear retry message if my cook collides with someone else's stock update, so that I just try again.

### Made-history

57. As a user, I want a "cooked N times" panel on the recipe detail screen listing every time this recipe was made, newest first, so that I can see its history in context.
58. As a user, I want a global History screen listing every cook across all recipes, newest first, so that I have a household activity log.
59. As a user, I want the global History to page in older entries on demand with a count of how many exist, so that a long history stays manageable.
60. As a user, I want each global History row to name its recipe and link to it, and to still show the recipe's title as plain text if that recipe was later deleted, so that old entries stay meaningful.
61. As a user, I want each history row to show the date, who cooked it, the multiplier, and whether stock was deducted, so that I can read the event at a glance.
62. As a user, I want to expand a history row to a per-ingredient deduction detail (requested, deducted, before, after) with a plain-language reason chip per ingredient, so that I can audit what a cook did to my stock.
63. As a user, I want a cook logged without deduction shown as "logged — stock not changed" with no detail table, so that I'm not looking for numbers that don't exist.

### Inventory

64. As a user, I want a table of my inventory items showing item, match name, unit bucket, quantity in a sensible unit, and last-updated, so that I can see what the household has.
65. As a user, I want inventory ordered by match name so related items sit together, so that the table is easy to scan.
66. As a user, I want to add an inventory item with an item name, quantity, unit, and optional match name, so that I can record new stock.
67. As a user, I want adding stock that matches an existing item+unit to increase that row's quantity rather than create a duplicate, and I want the form to tell me it works that way, so that the behavior isn't surprising.
68. As a user, I want to edit an item's quantity inline, and be required to confirm the unit when I do, so that the stored amount is unambiguous.
69. As a user, I want to be prevented from changing an item's unit to one in a different bucket, so that I don't get a guaranteed rejection.
70. As a user, I want to edit an item's match name and see it saved in its normalized form, so that it links to recipe ingredients correctly.
71. As a user, I want an inline error if my new match name collides with another item in the same bucket, so that I can pick a different one.
72. As a user, I want a short hint explaining that match name is what links an inventory item to recipe ingredients, so that I edit it deliberately.
73. As a user, I want to delete an inventory item with a confirmation, so that I don't remove stock by accident.
74. As a user, I want the inventory quantities to update after I cook a recipe or submit a grocery list, so that the table stays live.

### Groceries — list management

75. As a user, I want to create a grocery list from recipes I selected on the recipe list, so that I can shop for a set of meals.
76. As a user, I want to set a multiplier per selected recipe when creating the list, so that a list for a party scales the right recipes.
77. As a user, I want to optionally name the grocery list, and otherwise get a sensible default name, so that I can tell lists apart.
78. As a user creating a list, I want a clear recovery path if one of my selected recipes was deleted meanwhile, so that I can drop it and continue.
79. As a user, I want to see my grocery lists, filter to active or archived, and see item and checked counts per list, so that I can pick up where I left off.
80. As a user, I want to delete a grocery list regardless of its status with a confirmation, so that I can clean up.

### Groceries — shopping a list

81. As a user, I want each grocery line shown with its item and a human-formatted quantity, grouped into generated and manually-added lines, so that the list is organized.
82. As a user in a store, I want to tap a line to check it off and have it respond instantly, so that checking items is fast even on flaky wifi.
83. As a user, I want a checked line to revert if the server rejects the change, so that my list stays truthful.
84. As a user, I want a line whose true shortfall is uncertain marked "amount uncertain" with a note to buy based on what I find, so that I'm not misled by a number.
85. As a user, I want to add a manual line to a grocery list with an item and optional quantity/unit, so that I can shop for things not derived from a recipe.
86. As a user, I want to edit a generated line's item, quantity, or unit, sending quantity and unit together, so that I can correct the solver.
87. As a user, I want a quiet note when editing a generated line turns it into a manual line that will no longer be netted against stock, so that I understand the consequence.
88. As a user, I want to submit the checked lines of a list into my inventory, with a dialog that explains this adds stock and cannot be undone, so that I do it deliberately.
89. As a user, I want to keep shopping after a submit and submit again later to pick up newly-checked lines, so that a multi-day shop works.
90. As a user, I want lines that were already submitted shown as read-only with the amount that was added, so that I can see what's done.
91. As a user, I want submitted lines to be un-editable and un-deletable without a confusing error, so that the frozen state is obvious.
92. As a user, I want to archive a finished grocery list, so that it leaves my active view.
93. As a user, I want a clear message if I act on a list that was archived by someone else, so that I refetch and move on.

### Cross-cutting

94. As a user, I want a loading skeleton or spinner while a screen fetches, with the navigation still usable, so that the app feels responsive.
95. As a user, I want a query failure shown inline with a retry button, so that a transient error doesn't require a full reload.
96. As a user, I want unexpected errors surfaced as a dismissible toast, so that I'm informed without losing the screen.
97. As a user hitting a detail URL for something that doesn't exist, I want an in-content "not found" panel with a link back to the list, so that I can recover.
98. As a keyboard-only user, I want every control reachable and operable by keyboard with a visible focus ring, so that I can use the whole app without a mouse.
99. As a screen-reader user, I want labelled inputs, announced errors, and announced async status, so that the app is usable non-visually.
100. As a user with reduced-motion settings, I want spinners and transitions toned down, so that the app respects my preference.
101. As a user, I want text to meet contrast requirements in both light and dark themes, and status never conveyed by color alone, so that the app is legible.

## Implementation Decisions

### Stack

- **Vite + React 18 + TypeScript strict** (keep the skeleton's build config,
  `tsconfig` solution layout, and `npm run build` = `tsc -b && vite build`).
- **`react-router-dom` v6+ in classic component-routing mode** — no data-router
  loaders/actions.
- **TanStack Query** owns all server state: one query key per resource, mutations
  call `invalidateQueries` for affected keys (cook → availability + inventory +
  cook-logs; grocery submit → grocery list + inventory).
- **CSS Modules** for component styles over a `tokens.css` custom-property layer;
  light/dark is a `:root` / `[data-theme]` token swap following
  `prefers-color-scheme` with a `localStorage` override. No CSS framework.
- **MSW** for tests and for mock-first development; handlers mirror `docs/spec.md`
  §5.
- **ESLint + Prettier** added; `npm run lint` joins the frontend CI job
  (`npm ci && npm run lint && npm run test:run && npm run build`).
- New runtime deps: `react-router-dom`, `@tanstack/react-query`. New dev deps:
  `msw`, `eslint` (+ `@typescript-eslint`, `eslint-plugin-react-hooks`),
  `prettier`. Any dep beyond this list requires a `docs/frontend/spec.md` update.

### Modules (by responsibility, not path)

- **HTTP client** — one `fetch` wrapper: prefixes `/api`, injects
  `Authorization: Bearer <token>` from `localStorage`, normalizes both FastAPI
  error shapes into a typed `ApiError { status, detail }`, handles 204, throws
  `ApiError` on non-2xx. A `401` triggers: clear token, drop the query cache,
  redirect to login preserving the attempted route.
- **Resource adapters** — thin typed wrappers per resource (`auth`, `recipes`,
  `inventory`, `cookLogs`, `grocery`) over the client. These are the containment
  boundary (R-2) for the three math DTOs (availability, cook deduction, grocery
  line) that a backend Phase 4–6 contract gate could still move: a late DTO
  change is a one-adapter edit.
- **Types module** — a hand-maintained mirror of `docs/spec.md` §5 request/response
  shapes. Not generated (R-1). When `docs/spec.md` changes, this and
  `docs/frontend/spec.md` §5 are updated together and diffed against the backend
  section that moved.
- **Auth provider** — token in `localStorage` (key `recipe.token`), `login` /
  `logout`, hydrate the current user via `GET /api/auth/me` on load, drop cache
  on `401`. A `RequireAuth` wrapper guards routes and redirects to
  `login?next=<path>`.
- **`parseIngredients`** — pure client-side paste-block splitter (the backend does
  no newline splitting). Splits on `\n`, trims, drops blank lines, strips one
  leading bullet/number marker, drops section-header lines (trailing `:` with no
  parseable leading quantity). No soft-wrap rejoin in v1. Output is POSTed as
  string elements in `ingredients`.
- **`format`** — pure quantity/number/datetime formatting. `formatQuantity(value,
  unit)`: fraction-prefer (`⅛ ¼ ⅓ ½ ⅔ ¾` incl. integer+fraction) when
  `value < 10` and within 2% of a common fraction; counts snap to integer within
  1%; canonical bulk units (`g`, `ml`) always decimal; otherwise 3 significant
  figures, trailing zeros trimmed, no thousands separators. `null` → `""`.
- **`apiError`** — `parseApiError(status, body)` producing `ApiError`; helpers
  `isFieldError`, `fieldName` (last `loc` segment). A `useFormErrors` hook splits
  field-level (`detail` is `ValidationIssue[]`) from form-level (`detail` is a
  string).
- **Component primitives** (~8): `Button`, `Input`/`Textarea`/`Select`, `Field`
  (label + control + hint + error), `Card`, `DataTable` (real `<table>` ≥ 640px,
  stacked rows below), `Dialog` (focus trap, `Esc`, focus restore), `Toast` +
  provider (`aria-live="polite"`), `Badge`, `Stepper` (numeric, presets + free
  input, enforces `> 0`). Accessibility is built into the primitives so screens
  inherit the AA bar.
- **Pages**: Login, RecipeList, RecipeDetail, RecipeForm, Inventory,
  GroceryLists, GroceryListDetail, History.
- **App shell**: responsive nav (top bar ≥ 640px, bottom tab bar < 640px; four
  primary destinations), route table, `RequireAuth`.

### Import direction (one-way)

`types → http client → resource adapters → lib (parseIngredients / format /
apiError) → components → pages → app shell`. The auth provider sits beside the
adapters (the client reads the token the provider owns).

### Routes

`/login` (public) · `/` RecipeList · `/recipes/new` · `/recipes/:id` ·
`/recipes/:id/edit` · `/inventory` · `/groceries` (`?status=active` default) ·
`/groceries/:id` · `/history` · `*` in-app NotFound. Every non-login route is
guarded.

### API contract

The frontend consumes `docs/spec.md` §5 unchanged. It does **not** modify any
backend model, field, route, dependency, or config. `POST /api/grocery` accepts
per-recipe `multipliers` **only at create**, which is why the grocery-create
dialog collects them (there is no later API to set them, and editing a generated
line's quantity reclassifies it to a manual line).

### Error model

Normalized `ApiError` routed by class:
- transport / `500` / unexpected → toast (generic copy);
- `422` with `ValidationIssue[]` → inline per field, mapped by the last `loc`
  segment (including array indices for ingredient rows);
- `422` / `403` / `409` with string `detail` → inline form-level banner,
  verbatim;
- `401` → silent: clear token + cache, redirect to `login?next=`.

`docs/frontend/spec.md` §6 carries a consolidated catalog (status × detail shape
× trigger × surface × copy) derived from the backend spec; MSW ships an error
handler per catalog row.

### "Uncertain" language

`have_uncertain` availability status and `nettable: false` grocery lines render
as amber "Check what you have" / "amount uncertain" with an explanation and
**never** a computed shortfall number. The backend field names are not changed in
v1; a v2 investigation note is recorded in `docs/features.md` and
`docs/frontend/decisions.md`.

### Optimistic updates

Only grocery line check/uncheck is optimistic (flip immediately, roll back on
error). All other mutations wait for the server response.

### Auth / registration

Token in `localStorage`; the session is the backend's fixed 30-day window with no
refresh flow, so any `401` means "log in again". The registration form is built
only when `VITE_ENABLE_REGISTER` is set; the default production bundle has no
sign-up UI.

### Delivery

Nine frontend-native phases (0 tooling & skeleton rewrite → 1 design system &
shell → 2 auth → 3 recipes → 4 inventory & availability → 5 cook & history → 6
grocery → 7 hardening → 8 deployment docs), each mapped to the backend phase it
integrates against. Phases 0–1 have no backend dependency. Phases 2–6 are built
against MSW ahead of their backend phase and wired to real calls (and their gate
closed) only once that backend phase merges; Phases 4–6 also require an adapter
diff review against the merged DTOs. The skeleton rewrite happens in Phase 0 in
one PR, keeping CI green.

### Skeleton disposition

Delete `App.tsx`, `types.ts`, `api.ts`, `api.test.ts` (pre-v1 shapes). Keep
`main.tsx` (rewritten to mount providers), `setupTests.ts` (extended for MSW),
`vite.config.ts`, `tsconfig*`, `index.html` (retitled).

## Testing Decisions

### What makes a good test here

- Assert **user-visible behavior** through the rendered UI and the network
  boundary — what the user sees and what requests go out — never component
  internals, hook call counts, or query-cache shape.
- Prefer the **highest seam**: render the real component tree and let real
  `fetch` calls hit MSW. Do not mock the HTTP client, the resource adapters, or
  TanStack Query in page tests — those are exactly the wiring that must be
  covered (query keys, cross-resource invalidation, `loc`→field error mapping,
  the 401 redirect).
- Pure functions are tested by **direct call against the locked oracle tables**;
  no mocking machinery.

### Seams

1. **MSW network boundary (primary, single architectural seam).** A `renderApp`
   test helper wraps the provider stack (a fresh `QueryClient`, the auth
   provider, `MemoryRouter` at a given route, an optional seeded token) and
   renders a real page. A shared happy-path handler set mirrors `docs/spec.md`
   §5; per-test `server.use(...)` layers error and edge cases. This is the direct
   analogue of the backend's `conftest.py` `client` fixture (build the real app,
   drive it through real HTTP).
2. **Direct calls to pure/leaf units.** `parseIngredients`, `formatQuantity` /
   `formatDateTime`, `parseApiError` against their locked oracle tables in
   `docs/frontend/spec.md` §7. The 8 UI primitives are leaf components with no
   I/O — rendered and asserted directly (keyboard, focus, ARIA wiring).

### Locked oracle gate (R-7 analogue)

For `parseIngredients`, `format`, and `parseApiError`, a fresh-context author
translates the oracle table in `docs/frontend/spec.md` §7 into black-box tests
that are accepted **before** implementation code is written. The implementation
pass may add cases but may not change an accepted expected value; a wrong oracle
is fixed by editing the spec and the test together with the reason recorded in
`docs/frontend/decisions.md`.

### Modules under test

- **Pure**: `parseIngredients` (10 oracle rows), `format` (15 rows),
  `parseApiError` (8 rows).
- **Primitives**: each of the 8, in isolation, for behavior + accessibility
  wiring.
- **Flow tests through Seam 1** (Q21): Login (success redirect to `next`; `401`
  inline; the five auth-failure shapes each land as a redirect; logout clears),
  RecipeForm create (mixed pasted-string and structured-object rows in one save)
  and edit (full replace clears removed rows; `loc`-mapped errors), Inventory
  PATCH rules (quantity-without-unit rejected; bucket-changing unit rejected;
  null-unit on non-COUNT rejected; valid `{quantity, unit}` updates the row;
  `match_name` collision shows inline), Grocery check→submit (optimistic
  check/uncheck with rollback; edit a generated line reclassifies it; submit
  freezes lines and invalidates inventory; PATCH/DELETE a frozen line surfaces
  the conflict copy).
- **Error catalog**: each `docs/frontend/spec.md` §6 row exercised via an MSW
  error handler with the asserted surface (toast vs inline-field vs inline-form
  vs redirect).

### Prior art

- Backend `backend/tests/conftest.py` — the `client` / `auth_client` fixtures
  build the app through its factory and tests go through real HTTP with no
  dependency overrides. `renderApp` + MSW is the same philosophy on the frontend.
- The existing `frontend/src/api.test.ts` (being deleted) already tests the API
  wrapper through a faked `fetch`; the replacement raises the seam from a
  hand-stubbed `fetch` to MSW handlers reused across every page test.
- Backend `docs/spec.md` §7 locked oracle tables and
  `docs/plan.md` §"Independent contract-test gate" — the model for the three
  frontend oracle suites and their gate.

## Out of Scope

- **Any backend change.** No model, field, route, dependency, or config edit; no
  rename of `have_uncertain` / `nettable` (v2 note only).
- **Dashboard / "what can we make now"** — `GET /api/recipes/makeable` is v2; `/`
  is the recipe list.
- **Photo upload, URL import, per-cook reviews, receipt OCR, recipe research** —
  all v2; no photo UI (`photo_path` is always null), `source_url` is a plain
  text field only.
- **Staples / low-stock alerts.**
- **Any undo** for cook or grocery submit — the backend is forward-only; the UI
  must not imply reversibility.
- **Offline-first / service worker / background sync.** The store-walk case is
  handled with TanStack Query defaults plus a visible "reconnecting" hint only.
- **Drag-and-drop reorder** for ingredient rows and steps — v1 uses up/down
  buttons (keyboard-safe); drag is a later polish.
- **Auto-generated API types** — the types module stays hand-maintained by
  contract (R-1).
- **Internationalization / localization** beyond the browser's locale date
  formatting.
- **Multi-household / per-user authorization** — v1 is a single shared household;
  `created_by` / `cooked_by` are attribution only.
- **Deployment automation** — Phase 8 is written notes (LAN serving, CORS origin,
  the flagged-registration bootstrap), not scripts.

## Further Notes

- **`docs/frontend/spec.md` is the normative contract**; this ticket is a
  synthesis. `docs/frontend/plan.md` has the phase checklists and exit criteria;
  `docs/frontend/decisions.md` records the rationale for every decision above
  (grill outcomes Q1–Q25). `docs/frontend/informal-frontend-spec.md` is
  superseded and retained only as background.
- **Sync discipline (R-1).** Watch `git log -- docs/spec.md` during backend
  Phases 2–6. Any change to a shape the frontend mirrors updates the types module
  and `docs/frontend/spec.md` §5 together, with a diff against the backend
  section that moved.
- **Adapter containment (R-2).** The availability, cook-deduction, and grocery
  DTOs may still shift in a backend Phase 4–6 contract-test gate. Keep those
  screens behind their resource adapter and do not wire them to real calls until
  the owning backend phase's diff review clears.
- **Partition.** The frontend track owns `frontend/**` and `docs/frontend/**` and
  reads `docs/spec.md` as the contract. It does not edit `docs/spec.md`,
  `docs/plan.md`, `docs/phases/**`, `docs/issues.md`, `docs/decisions.md`, or
  `backend/**`. One row was added to `docs/features.md` (backend-owned) for the
  v2 vocabulary note, pointing at `docs/frontend/decisions.md`.
- **Known backend quirks the UI must absorb**: `409 {"detail":"conflict"}` is
  generic for both integrity errors and SQLite lock timeouts (retry copy);
  `POST /api/grocery` 422s if any `recipe_id` is missing (re-validate the
  selection); converted display quantities are raw floats (never render one
  unformatted); availability `group_*` fields repeat per member line (dedupe by
  `group_key` or render per line); a recipe ingredient's row `id` churns on every
  PUT (don't use it as a React key across an edit).
