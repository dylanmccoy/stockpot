# 11b: Made-history — global `/history` screen (vs MSW)

**What to build:** The household-wide activity log at `/history`, reusing the shared cook-log row. After this ticket a user can browse every cook across all recipes, newest first, page older entries in on demand with a count of how many exist, jump to a row's recipe, and still read the title of a since-deleted recipe.

**Blocked by:** 11a.

**Status:** ready-for-agent

**Files:** edit `frontend/src/pages/History.tsx`, `frontend/src/api/cookLogs.ts`; create `frontend/src/pages/History.test.tsx`. Reuse `CookLogRow`/`DeductionDetail` from 11a.

**Spec:** `docs/frontend/spec.md` §10.8 (global `/history` — pagination, load-more, deleted-recipe title), §5 "Cook + history" (`/api/cook-logs` list shape). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/History.test.tsx`.

- [ ] `/history` lists every cook across all recipes, newest first, paginated with a "load more" and a count of how many exist. Query key `["cook-logs", { limit, offset }]`.
- [ ] Each row uses the shared `CookLogRow` + `DeductionDetail` accordion from 11a.
- [ ] Each row names its recipe and links to it; if that recipe was deleted, its title still shows as plain text with no link.
- [ ] Flow test (vs MSW): first page renders with the total count; "load more" advances `offset` and appends; a row whose recipe is gone shows the title as plain text.

**Refs:** `docs/frontend/spec.md` §10.8; plan Phase 5. Split from ticket 11.
