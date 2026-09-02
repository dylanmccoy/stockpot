# Frontend v1 — Decisions

Rationale for the decisions baked into [`spec.md`](spec.md) and
[`plan.md`](plan.md). **Non-normative:** when this file conflicts with `spec.md`,
`spec.md` wins.

Source: a `/grill-with-docs` session on 2026-09-01 that worked the design tree in
four rounds (Q1–Q25). Backend state at the time: Phases 0–1 complete, 2–7
pending, `../spec.md` complete and frozen.

## Round 1 — framing

| # | Decision | Outcome | Why |
|---|---|---|---|
| Q1 | Session deliverable | Formal doc set (`spec.md` + `plan.md` + `decisions.md`) that supersedes the informal spec | The backend earned its stability from a normative spec + phased plan + locked oracles; the frontend gets the same rigor before code |
| Q2 | Backend integration strategy | **Mock-first parallel** — build against MSW keyed to `../spec.md` §5; integrate per phase gate; gated math screens behind `src/api/<resource>.ts` adapters | `../spec.md` is complete and frozen; churn risk is confined to three math DTOs (R-2) and already contained by the adapter pattern; keeps the frontend track unblocked |
| Q3 | v1 screen scope | All nine screens (Login, RecipeList, RecipeDetail, RecipeForm, Inventory, GroceryLists, GroceryListDetail, History) | The product *is* the recipe→availability→cook→grocery loop; a cut that drops grocery/cook is just a recipe box |
| Q4 | Skeleton disposition | Delete-and-rewrite `src/{App,types,api,api.test}` in Phase 0; keep `main.tsx`, `setupTests.ts`, `vite.config.ts`, `tsconfig*`; CI stays green in the same PR | The skeleton describes a pre-v1 `ingredients: string` recipe that no longer exists — no migration value |
| Q5 | Target devices | Responsive, both equal, **mobile-priority for the cook + shop flows** | RecipeForm / bulk Inventory are laptop tasks; RecipeDetail-while-cooking and GroceryList-while-shopping are phone tasks. Layout mobile-first, widen up |
| Q6 | Design ambition | **Clean utilitarian** — ~8 hand-rolled primitives on a small token set, light/dark; no component library | A daily household tool should feel calm and consistent; a component library is overkill for nine screens and one user base |

## Round 2 — tooling, testing discipline, app shell

| # | Decision | Outcome | Why |
|---|---|---|---|
| Q7 | Data-fetching / cache | **TanStack Query**; consequence: **classic** react-router component routing, not data-router loaders/actions | Purpose-built for per-resource keys + cross-resource `invalidateQueries` (cook → availability, submit → inventory); pairs cleanly with MSW; React Query owns the data lifecycle so RR loaders would duplicate it |
| Q8 | Styling mechanism | **CSS Modules** + a `tokens.css` custom-property layer | Scoped-by-default removes the naming-collision tax, keeps styles colocated, zero runtime; light/dark is a `:root` / `[data-theme]` var swap. Tailwind was offered as the velocity alternative; not chosen |
| Q9 | Test fetch mocking | **MSW** | With mock-first development the mock layer *is* the backend for weeks — it must be realistic (status codes, `{detail}` shapes, `422[]`); handlers double as living API docs and later as the integration seam |
| Q10 | Auth token storage + Register UI | **`localStorage`** (`recipe.token`); Register form **behind `VITE_ENABLE_REGISTER`**, default off | The session is a fixed 30-day window with no refresh flow — clearing on tab close is hostile for a daily tool; XSS is within the accepted LAN/no-HTTPS posture. Registration is disabled server-side by default, so a signup UI in the shipped bundle is misleading |
| Q11 | Client-logic contract tests | **Locked oracle tables** in `spec.md` for the paste splitter, `format.ts`, and `parseApiError`; authored TDD under a gate mirroring the backend's | These three are the frontend's load-bearing pure logic; the splitter has *no server counterpart*, so a bug there silently garbles every pasted recipe |
| Q12 | Navigation & app shell | **Top bar ≥ 640px → bottom tab bar < 640px**; four primary destinations (Recipes, Inventory, Groceries, History); detail/form screens are pushed routes | Four destinations map perfectly to a thumb-reachable mobile tab bar and the same four sit in a desktop top bar |
| Q13 | Home surface | **RecipeList is `/`** (guarded; `→ /login` when unauthenticated) | `GET /api/recipes/makeable` is explicitly v2/excluded — no endpoint exists for a dashboard, and a client-side aggregate is scope creep. A dashboard is a clean v2 addition once `makeable` lands |

## Round 3 — plan structure & screen behavior

| # | Decision | Outcome | Why |
|---|---|---|---|
| Q14 | Frontend phase breakdown & gate | **Frontend-native phases 0–8** + a backend-phase mapping table for integration timing; the three oracle tables are the only *locked* gates, every phase also has a plain acceptance checklist; `decisions.md` yes, issues folded into `spec.md` §11 | Frontend phases don't line up 1:1 with backend phases (tooling + design system have no backend analogue); page-level snapshot gates are brittle and low-value |
| Q15 | Error surface | **Both toast and inline, by error class** (transport/500 → toast; `422[]` → inline per-field by `loc`; domain `422`/`403`/`409` string → inline form banner; `401` → silent redirect). One `parseApiError` → `ApiError` feeds a `useFormErrors` hook. **Plus a consolidated error catalog** in `spec.md` §6 (the backend documents errors only per-endpoint + in §0 — scattered) | Different error classes need different placement; the catalog is the single reference for `parseApiError`, `useFormErrors`, MSW error handlers, and the copy deck |
| Q16 | Optimistic updates | **Only grocery line check/uncheck** | High-frequency (walking a store), low-stakes, trivially rolled back on error. Everything else (inventory quantity, recipe saves, cook, submit) is infrequent and the stakes reward true server state |
| Q17 | Paste splitter scope | v1: split on `\n`, trim, drop blanks, strip leading bullets/markers, **drop section headers** (trailing `:` + no leading quantity), **no soft-wrap rejoin**; a **parsed-row preview before POST** | Folding headers into a note guesses wrong too often; soft-wrap rejoin mis-fires on legitimate no-quantity ingredients ("salt", "olive oil"). The preview lets the user hand-fix |
| Q18 | Quantity display | Unit-aware, **fraction-preferring for `value < 10`** within 2% of a common cooking fraction; counts → integer within 1%; canonical bulk units (`g`, `ml`) always decimal; otherwise 3 sig figs, trailing zeros trimmed. Locked oracle table | Recipe-scale amounts read as `1½ cups`, not `1.5`; but `473 ml` must not become a fraction. Backend sends raw floats (R-8), so all of this is frontend-owned |
| Q19 | "Uncertain" language | **Copy only, no backend rename.** Availability: amber "Check what you have"; grocery: amber "amount uncertain". Never show a computed shortfall for these. A **v2 investigation note** is proposed in `../features.md` for the backend track | `have_uncertain` / `nettable` are API vocabulary read by a developer; the cook sees only rendered copy. Renaming the wire fields churns `../spec.md`, the schemas, ~4 locked oracle tables, and every backend test for zero user-facing gain — and violates the frozen-contract / scope-fence posture. See the follow-up note below |
| Q20 | Multiplier control | **One `Stepper` on RecipeDetail** (`½ 1 2 3` + free input, `> 0`); rescales **both** the displayed ingredient quantities and the availability query, and is the value the cook action sends; **resets to 1.0 on every visit** | A cook scaling a recipe wants to see "3 cups", not "1 cup ×3". A stale remembered 3× is a footgun — make it a deliberate per-session choice |

## Round 4 — remaining forks

| # | Decision | Outcome | Why |
|---|---|---|---|
| Q21 | Page-level test depth | **Testing Library flow tests for Login, RecipeForm (create + edit), Inventory PATCH rules, Grocery check→submit**; thin coverage elsewhere | With no real backend for weeks, the four listed carry the wiring risk (especially the gated math adapters); not every screen needs a flow test |
| Q22 | RecipeForm ingredient entry | **One unified editable table** where rows are editable fields; a "Paste ingredients" action runs the splitter, shows a preview, and **appends** parsed rows. Pasted-untouched rows POST as strings; hand-entered/edited rows POST as objects | Matches the backend, which accepts a mixed `ingredients[]` array of strings and objects in one request. One mental model, no mode switch |
| Q23 | Per-recipe multipliers at grocery creation | **Collect a per-recipe multiplier `Stepper` in the create dialog** (default 1×) | `POST /api/grocery` accepts `multipliers` **only at create** — there is no later API to change them. Editing quantities line-by-line afterward also trips the N6 reclassification (edited generated line → `manual`, loses the shortfall claim) |
| Q24 | Made-history surfaces | **Two entry points, one shared `CookLogRow` + `DeductionDetail` accordion.** Per-recipe = a panel *inside* RecipeDetail (`GET /api/recipes/{id}/cook-logs`, unpaginated, no recipe-title column). Global = its own `/history` route (`GET /api/cook-logs?limit=&offset=`, paginated, recipe-title column with a deleted-recipe fallback). Deduction detail is a collapsed accordion. No undo affordance | Same data model, different framing — per-recipe is contextual ("have I made this before"), global is a standalone activity log. Like GitHub showing a file's commits vs the repo history |
| Q25 | Accessibility bar | **WCAG AA basics as a Phase-1 requirement**, baked into the 8 primitives (landmarks, labelled inputs, visible focus, keyboard-operable tab bar + dialogs, `aria-live` toasts, ≥ 4.5:1 contrast both themes, no color-only status) | Cheap when the component set enforces it, expensive to retrofit onto nine screens; a one-handed kitchen tool needs keyboard/focus/contrast hygiene |

## Q19 follow-up — backend vocabulary (for the backend track)

Recorded here because the frontend track cannot edit `../spec.md`. A one-line
pointer is proposed in `../features.md`.

**Observation.** `AvailabilityStatus` value `"have_uncertain"` and the `nettable`
boolean (present on both `AvailabilityLine` and `GroceryListItemRead`) are
precise but terse, and `nettable` is a **negated** name — `nettable: false` is
the interesting case ("we cannot compute a reliable net shortfall because stock
sits in an incomparable unit").

**Recommendation for a future backend revision (v2, not v1):**
- Rename `nettable` to a positively-phrased name — `units_comparable` or
  `shortfall_certain`.
- Consider `incomparable_units` in place of `"have_uncertain"` (names the cause,
  not the conclusion) — though `"have_uncertain"` groups naturally with
  `ok`/`short`/`missing`/`to_taste` as outcome states, so this is weaker.
- Consider giving grocery lines their own status enum for parity with
  availability (grocery currently carries only `nettable` for the same concept).

**Why not in v1:** `../spec.md` is complete and frozen; `"have_uncertain"` is in
the locked availability oracle table (`../spec.md` §7) and `nettable` is in both
the availability and grocery oracle tables. A rename churns the spec, the
schemas, ~4 locked oracle tables, and every backend test — for no user-facing
gain, since `spec.md` §7.4 fully covers the cook-facing language.
