# 11b: Made-history — global `/history` screen (vs MSW)

**What to build:** The household-wide activity log at `/history`, reusing the shared cook-log row. After this ticket a user can browse every cook across all recipes, newest first, page older entries in on demand with a count of how many exist, jump to a row's recipe, and still read the title of a since-deleted recipe.

**Blocked by:** 11a.

**Status:** done

**Files:** edit `frontend/src/pages/History.tsx` (+ `.module.css`), `frontend/src/components/CookLogRow.tsx` (+ `.module.css`, `.test.tsx` — add the recipe-title `<Link>`); create `frontend/src/pages/History.test.tsx`. Reuse `CookLogRow`/`DeductionDetail` from 11a. (`frontend/src/api/cookLogs.ts` was listed but needed no change — `cookLogsApi.list` from 11a already suffices.)

**Spec:** `docs/frontend/spec.md` §10.8 (global `/history` — pagination, load-more, deleted-recipe title), §5 "Cook + history" (`/api/cook-logs` list shape). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/History.test.tsx`.

- [x] `/history` lists every cook across all recipes, newest first, paginated with a "load more" and a count of how many exist. Query key `["cook-logs", { limit, offset }]`.
- [x] Each row uses the shared `CookLogRow` + `DeductionDetail` accordion from 11a.
- [x] Each row names its recipe and links to it; if that recipe was deleted, its title still shows as plain text with no link.
- [x] Flow test (vs MSW): first page renders with the total count; "load more" advances `offset` and appends; a row whose recipe is gone shows the title as plain text.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5. Split from ticket 11.

## Comments

- Branch `feat/frontend-v1-11b`; worktree `.claude/worktrees/frontend-v1-11b`.
- `History.tsx` pages by keeping each fetched page keyed by its own `offset`
  and concatenating in `offset` order; "Load more" advances `offset` by 50
  (`keepPreviousData` keeps rows on screen while the next page loads).
- Edited `CookLogRow.tsx` (not in **Files:**): 11a shipped the `showRecipeTitle`
  prop + deleted marker but no link. Added the `<Link to="/recipes/:id">` wrap
  for the linked-title AC; deleted recipes still render plain text.
- `cookLogsApi.list` already existed from 11a and needed no change; the
  queryFn does **not** forward TanStack's `signal` (matches RecipeList /
  RecipeDetail — the abort signal breaks `fetch` under the jsdom test env).

### `/code-review` findings

Actioned:
- **Spec c1** — a failed "load more" now renders its own `errorPanel` with a
  working **Retry** (`query.refetch()` on the same offset), replacing the weak
  text-only "try again"; added a flow test covering fail → Retry → recover.
- **Spec a1** — empty-state action is now a styled CTA (`.cta`, matching
  RecipeList's `CtaLink`), not a bare link.
- **Spec c2** — "Load more" spinner is gated on `fetchingNext`
  (`isFetching && query.data?.offset !== offset`), so a background refetch of an
  already-loaded page no longer spins it.
- **Standards / Files fence** — updated the **Files:** line above.
- **Standards CSS dup** — dropped the one-off `.link`; empty-state CTA reuses
  the shared token set.
- **Standards test naming** — `feed(n, over)` → `feed(n, overrides)`.

Deliberately skipped:
- **Standards #1 / Spec c1 root — `useInfiniteQuery`.** Spec §10.8 and this
  ticket both pin the query key as `["cook-logs", { limit, offset }]`;
  `useInfiniteQuery`'s key omits `offset`. Kept one `useQuery` per offset with a
  retained-pages map; the c1/c2 fixes above address the practical fallout.
- **Divergent-change split of `History.tsx`** — a `usePagedCookLogs` hook is not
  worth it for a single ~110-line screen.
