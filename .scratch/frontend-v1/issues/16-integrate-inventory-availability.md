# 16: Integrate inventory + availability (real backend)

**What to build:** Wire the inventory screen and the availability table to the real backend, and run the availability adapter diff-review against the merged DTO.

**Blocked by:** 08, 09. External gate: backend Phase 4 (inventory + availability) merged.

**Status:** ready-for-agent

- [ ] Inventory CRUD and `GET /api/recipes/{id}/availability` run against the real backend.
- [ ] Availability adapter diff-reviewed against the merged Phase 4 DTO shape (`group_*` fields, status enum values, `nettable`); any change absorbed in the one adapter.
- [ ] The four PATCH-rule rejections and the valid `{ quantity, unit }` update behave the same against the real backend as against MSW; the `match_name` `409` collision surfaces inline.
- [ ] The availability header banner and per-line statuses render correctly from real data, including a real `have_uncertain` line as amber with no number.
- [ ] types module + `docs/frontend/spec.md` §5 re-diffed for §5.3 and §5.5.
- [ ] Phase 4 gate (plan) closed.

**Refs:** plan Phase 4 gate; `docs/frontend/spec.md` §10.9, §10.4, §7.4.
