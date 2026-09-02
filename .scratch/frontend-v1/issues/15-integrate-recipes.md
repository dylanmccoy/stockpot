# 15: Integrate recipes (real backend)

**What to build:** Wire the three recipe screens to the real backend and confirm recipe CRUD, the paste-and-save flow, and error mapping against it.

**Blocked by:** 05, 06, 07. External gate: backend Phase 3 (structured recipes) merged.

**Status:** ready-for-agent

- [ ] RecipeList, RecipeForm, and RecipeDetail body run against the real recipes endpoints.
- [ ] The recipes request/response shapes match `docs/spec.md` §5.2 as merged; types module and `docs/frontend/spec.md` §5 re-diffed against the backend section and any drift reconciled.
- [ ] Both RecipeForm flow tests pass against the real backend: create with mixed pasted-string + structured rows; edit full-replace clears removed rows; `loc`-mapped `422`s land on the right fields.
- [ ] PUT full-replace confirmed to drop removed ingredient rows server-side; the ingredient-row `id` churn on PUT does not break the form.
- [ ] Phase 3 gate (plan) closed.

**Refs:** plan Phase 3 gate; `docs/frontend/spec.md` §10.2–§10.4.
