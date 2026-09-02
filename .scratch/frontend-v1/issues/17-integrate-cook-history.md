# 17: Integrate cook + history (real backend)

**What to build:** Wire the cook action and both history views to the real backend, run the cook adapter diff-review, and confirm the deduction accordion against real deduction data.

**Blocked by:** 10, 11a, 11b. External gate: backend Phase 5 (cooking + history) merged.

**Status:** ready-for-agent

- [ ] The cook action, the per-recipe history panel, and `/history` run against the real backend.
- [ ] Cook adapter diff-reviewed against the merged Phase 5 deduction DTO.
- [ ] Posting a cook invalidates and refetches availability, inventory, and cook-logs against the real backend; a real `409` stock-collision shows the retry copy and refetches.
- [ ] The `DeductionDetail` accordion renders all five reason branches from real cook logs, with nulls only where `docs/spec.md` §5.4 permits.
- [ ] A deleted recipe still shows its title as plain text in `/history` rows.
- [ ] types module + `docs/frontend/spec.md` §5 re-diffed for §5.4.
- [ ] Phase 5 gate (plan) closed.

**Refs:** plan Phase 5 gate; `docs/frontend/spec.md` §10.4, §10.8.
