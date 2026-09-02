# 05a: Recipe list — browse, search, filter, sort (vs MSW)

**What to build:** The home screen as a place to see and find recipes. After this ticket a user landing on `/` sees their recipes as cards, newest-first, can find one by free text or by cuisine/tag facets, re-sort the list, open a recipe, start a new one, and gets a helpful empty state with no recipes yet.

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] `/` renders recipes as cards (title, cuisine, tags, prep/cook time), newest-first by default, behind `RequireAuth`. Query key `["recipes"]`.
- [ ] Client-side search box filters by title, cuisine, or tag text.
- [ ] Multi-select facets for one or more cuisines and one or more tags.
- [ ] Re-sort control: by title, or by most recently updated.
- [ ] Card click opens `/recipes/:id`. An "add recipe" action opens `/recipes/new`.
- [ ] Empty state invites adding the first recipe.
- [ ] Flow test (vs MSW): list renders from `["recipes"]`; search narrows; a cuisine + a tag facet narrow; re-sort reorders; empty list shows the empty state.

**Refs:** `docs/frontend/spec.md` §10.2; plan Phase 3. Split from ticket 05.
