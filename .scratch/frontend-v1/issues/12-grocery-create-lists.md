# 12: Grocery — create + lists (vs MSW)

**What to build:** Turning selected recipes into a grocery list, and managing the set of lists. After this ticket a user can generate a named list from recipes ticked on the recipe list (with a per-recipe multiplier set at creation), see all their lists filtered by status with counts, open one, and delete one.

**Blocked by:** 05, 03.

**Status:** ready-for-agent

- [ ] A grocery-create `Dialog` launches from the recipe-list multi-select action bar (wiring the stub from ticket 5).
- [ ] The dialog collects a multiplier `Stepper` per selected recipe (default 1×) — the only place multipliers are set, since `POST /api/grocery` accepts them only at create — and an optional list name with a sensible default.
- [ ] If a selected recipe was deleted meanwhile, the dialog gives a recovery path: drop it from the selection and continue (re-validate against the `422`).
- [ ] `/groceries` lists the user's grocery lists, filterable to active or archived, with item and checked counts per list.
- [ ] A list can be opened (→ `/groceries/:id`) and deleted in any status with a confirmation.
- [ ] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18).

**Refs:** `docs/frontend/spec.md` §10.5, §10.6; plan Phase 6.
