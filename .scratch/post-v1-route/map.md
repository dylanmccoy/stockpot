# Post-v1 route

Label: `wayfinder:map`
Charted: 2026-09-05

## Destination

A **committed post-v1 route**: the ordered tracks that follow shipped v1, with
each track's gating decisions resolved, recorded in
[`docs/features.md`](../../docs/features.md). The map is done when nothing is
left to decide before someone can write a spec and build. It ships no code.

## Notes

**Domain.** Household recipe + food inventory app. Read
[`CONTEXT.md`](../../CONTEXT.md) for vocabulary (three distinct things are
called "unit"), [`docs/features.md`](../../docs/features.md) for the full
catalogue of deferred work, and
[`docs/adr/0001-independent-households.md`](../../docs/adr/0001-independent-households.md).

**Skills.** Call `grilling` + `domain-modeling` on every ticket unless the
ticket's Type says otherwise.

**Plan only.** No building. A chosen track hands off to the repo's existing
flow: `.scratch/<slug>/spec.md` + `issues/NN-*.md`, which is how both v1s
shipped. Do not blur the two — an open ticket here is always a question.

**`features.md` is the catalogue and never loses an entry.** This effort
reorders and annotates it; it deletes nothing. Anything ruled out below keeps
its existing `features.md` section, and unscheduled catalogue items (recipe
research, multi-line paste, undo, and the rest) stay there awaiting a later
route.

**`created_by_id` is attribution, not authorization.** Every authenticated user
today reads and writes all data. Do not let a roles system be mistaken for
household isolation.

### Settled at charting (2026-09-05)

| # | Decision |
|---|---|
| 1 | Destination is a committed route, not a spec for one feature and not an ops decision. |
| 2 | Selection criteria: **daily-use friction** and **durability/risk**. Time cost is not weighted heavily. |
| 3 | **No real household data exists yet.** Deployment and Alembic are at their cheapest right now; this stops being true the moment the app is in real use. |
| 4 | `docs/deployment.md` + `.scratch/private-household-deployment/spec.md` are a **settled prior**. The map reopens only the parts the spec itself marks unverified. |
| 5 | Multi-household support is **out of scope** (below). |
| 6 | Route order: **Deploy → Friction pass → Recipe entry → Inventory upkeep.** Flipped from the owner's first instinct (entry first) because that ordering was an admitted guess and deploying is the cheapest way to replace it with evidence. |
| 7 | Alembic arrives **lazily**, as an explicit gate on the first schema-changing track — not as a track of its own. The deploy, friction, and entry tracks are all data-model-neutral, so the gate falls in front of inventory upkeep. |
| 8 | Recipes come from **websites** → the entry track is URL import. |
| 9 | The friction pass is the three already-specced S items; the two M items each hide a real design decision and became tickets 04 and 05. |
| 10 | The finished route lands in `docs/features.md`. |

### The route

| # | Track | Contents | Gate |
|---|---|---|---|
| 1 | **Deploy** | `.scratch/private-household-deployment/spec.md` — ready-for-agent | Ticket 01 |
| 2 | **Friction pass** | Edit-recipe button · create grocery list from a recipe · "what can we make now" | — |
| 3 | **Recipe entry** | URL import (`recipe-scrapers`, SSRF-guarded fetch) | ~~02~~ · ~~10~~ · ~~06~~ · ticket 09 |
| 4 | **Inventory upkeep** | One of receipts / staples / undo — which one is ticket 07 | Alembic (ticket 08) |

## Decisions so far

<!-- one line per closed ticket -->

- [Does `recipe-scrapers` cover the sites the household cooks from?](issues/02-recipe-scrapers-coverage.md):
  Yes — adopt it as specced. Measured against the library's 1109 real-page
  fixtures, the generic path finds usable ingredients on 87.7% of pages, so
  "supported site" barely matters (half the 625 scrapers override nothing).
  JSON-LD-only is a false economy. Three spec amendments needed; the failure
  population is newsletters and bot-protected sites, not ordinary blogs.
  [Full findings](research/recipe-scrapers.md).
- [What shape should the recipe-import endpoint have?](issues/10-import-endpoint-shape.md):
  Import is read-only and returns a create body; the person saves through the
  existing `POST /api/recipes`. One endpoint takes a website address or a
  pasted page. A scrape succeeds when it has ingredients and steps — title
  optional, `yields`/`total_time` never required. `ingredient_groups()` is used
  for clean lines; the group purpose text is a deliberate loss.
  Supersedes the API in `features.md` § URL import.

## Not yet specified

- **Fallback host topology** — if ticket 01 shows the Windows Tailscale Serve →
  Windows localhost → WSL composition doesn't hold, something has to replace it
  (WSL mirrored networking, the app running natively on Windows, Tailscale
  inside WSL, different hardware). Can't phrase the choice until we know which
  hop fails.
- **Whether multi-line ingredient paste rides with URL import** — it's the
  natural fallback for an unsupported site, so ticket 06 may pull it in.
- **What the friction pass actually contains** — ticket 03 may add items nobody
  has written down, or retire ones that turn out not to bite.
- **Whether a fifth track exists.** Real use may surface a problem that is in
  no document today.

- [What happens when URL import can't scrape a site?](issues/06-url-import-unsupported-fallback.md):
  Closed as absorbed, not decided. Tickets 02 and 10 answered the fallback, the
  wild-mode question, and the partial-scrape question. Multi-line ingredient
  paste turned out to belong to the manual form, not import, and stays
  catalogued in `features.md` as deferred item D2.

## Out of scope

Ruled beyond this map's destination. Each keeps its existing `features.md`
section; nothing here is deleted, and nothing here graduates — it returns only
as a fresh effort.

- **Multi-household / public signup** — memberships, scoped authorization,
  isolation tests, onboarding and recovery flows. ADR 0001 records the boundary
  without committing to build it; zero users and zero data make it speculative.
- **Photo upload** — the owner's call: photos for recipes aren't necessary. The
  full spec stays in `features.md`.
- **Public-internet hosting** — cookie-session redesign, abuse controls,
  off-machine backups, provider selection. The deployment spec already defers
  all of it to a later effort.
- **Meal planning** — already excluded by design in `features.md`; a
  product-direction change, not an extension.
- **Building anything.** This map decides; `.scratch/<slug>/` builds.
