# What happens when URL import can't scrape a site?

Type: grilling
Status: closed — absorbed by 02 and 10
Blocked by: —
Parent: ../map.md

## Question

`features.md` specs the success path and the error codes (unsupported → 422
with `unsupported: true`; any fetch failure → 502) but not what the *person*
does next. If the entry track is the household's main way of getting recipes
in, the failure path is load-bearing — a dead end there sends them back to
typing the recipe by hand, which is the problem the track exists to solve.

Decide:

1. **The fallback.** Dead end with an error? Drop the fetched page's text into
   a paste box so the existing form can be filled semi-manually? Prefill just
   the title and URL and let them type the rest?
2. **Whether multi-line ingredient paste comes along.** It is the natural
   partner to a paste-box fallback, it is catalogued in `features.md` as
   deferred item D2, and it is small. Pulling it in here or leaving it out is
   this ticket's call.
3. **Whether wild mode is even shown to the user** as a distinct "try harder"
   step, or always attempted silently behind one action.
4. **What a partial scrape does** — title and steps but no ingredients, say.
   Save it as a stub (title-only recipes are permanently legal per decision
   Q5), or refuse?

### What ticket 02 settled

Wild mode is good — 87.7% of real pages yield usable ingredients — so the
fallback is **not** a routine path. But the failures it does have are sharply
shaped, and no parser can fix either kind:

- **No recipe markup at all** — newsletter and prose sources. Measured: 6/6
  Substack posts and one bespoke CMS returned `NoSchemaFoundInWildMode`.
- **Bot protection** — 2 of 20 live fetches hit a Cloudflare 403, and both were
  on *supported* sites. At least as common as missing markup, and it defeats
  `fetch_bytes` before parsing is even reached.

Two consequences for this ticket:

- A free implementation exists. Tandoor accepts pasted raw HTML *or* pasted
  JSON-LD, wraps it in a synthetic `<script type="application/ld+json">`, and
  re-scrapes with the same parser — no second parsing path to maintain.
- Item 4 (partial scrapes) is no longer hypothetical. Every field accessor in
  the library can raise, so partial results are the **normal** shape, not an
  edge case. Decide what a partial save looks like, not whether one can happen.

## Closed — absorbed, not decided here

Tickets 02 and 10 answered three of the four items, so nothing decision-shaped
remains:

| Item | Where it went |
|---|---|
| 1. The fallback | [Ticket 10](10-import-endpoint-shape.md) item 2 — one endpoint takes a website address *or* a pasted page, one parser for both |
| 3. Is wild mode a separate "try harder" step? | [Ticket 02](02-recipe-scrapers-coverage.md) — no. One `scrape_html(..., supported_only=False)` call does both, so there is no second step to show |
| 4. What a partial scrape does | [Ticket 10](10-import-endpoint-shape.md) item 3 — a scrape succeeds with ingredients and steps; a missing `yields`/`total_time`/title is not a failure |

**Item 2 (multi-line ingredient paste) survives, but not here.** It turned out
to belong to the manual recipe form, not to import: `RecipeCreate.ingredients`
already accepts `list[str]`, and the import paste path carries HTML rather than
ingredient text. Server-side splitting of a pasted block on `\n` stays
catalogued in `docs/features.md` as deferred item D2, unscheduled.
