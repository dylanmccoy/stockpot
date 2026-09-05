# 05b: Recipe list — multi-select gather mode (vs MSW)

**What to build:** The entry point for turning several recipes into a grocery list. After this ticket a user on `/` can flip into a multi-select mode, tick recipes, see a running count in a sticky action bar, and press a "create grocery list" button whose handler is a stub. This ticket owns only the selection UI; the create dialog itself is ticket 12a.

**Blocked by:** 05a.

**Status:** done

- [ ] A toggle enters/leaves multi-select mode; leaving it clears the selection.
- [ ] In select mode, tapping a card ticks/unticks it (card click no longer navigates).
- [ ] A sticky action bar shows the running count and a "create grocery list" button; it is hidden when the selection is empty.
- [ ] The button handler is a stub (no dialog, no request) with a `// wired in ticket 12a` marker.
- [ ] Flow test (vs MSW): enter select mode, tick two recipes → "2 selected" and the bar is visible; untick both → bar hidden; leave select mode → selection cleared.

**Refs:** `docs/frontend/spec.md` §10.2; plan Phase 3. Split from ticket 05.
