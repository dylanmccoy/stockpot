# What happens when URL import can't scrape a site?

Type: grilling
Status: open
Blocked by: 02
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

### Depends on

Ticket 02's answer about wild-mode quality. If wild mode returns usable
structure on most unsupported sites, the fallback matters much less than if it
returns mush.
