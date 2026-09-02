# 05: Recipe list + browse (vs MSW)

**What to build:** The home screen — browsing, searching, filtering, and sorting the recipe collection, and entering a multi-select mode to gather recipes for a grocery list. After this ticket a user landing on `/` sees their recipes as cards, can find one by text or facet, re-sort, open one, and tick several with a running count (the "create grocery list" action is stubbed until ticket 12).

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] `/` renders recipes as cards (title, cuisine, tags, prep/cook time), newest-first by default, behind `RequireAuth`. Query key `["recipes"]`.
- [ ] Client-side search box filters by title, cuisine, or tag text.
- [ ] Multi-select facets for one or more cuisines and one or more tags.
- [ ] Re-sort control: by title, or by most recently updated.
- [ ] Card click opens `/recipes/:id`. An "add recipe" action opens `/recipes/new`.
- [ ] Empty state invites adding the first recipe.
- [ ] Multi-select mode: toggle in, tick recipes, running count + a sticky action bar with a "create grocery list" button whose handler is stubbed (wired in ticket 12).

**Refs:** `docs/frontend/spec.md` §10.2; plan Phase 3.
