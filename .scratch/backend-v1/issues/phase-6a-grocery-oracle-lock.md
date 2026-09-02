# phase-6a: Grocery contract-test lock (R-7)

**What to build:** A locked, independently-reviewed black-box test slice for
`generate_lines`, grocery line mutation (N6), submit, and the submit race —
authored from `docs/spec.md` §4.3 / §5.6 / §6 / §7 only, in a fresh context,
before Phase 6 production code.

**Blocked by:** `phase-5c` (Phase 5 complete).

**Status:** ready-for-agent

- [ ] Every §7 **Grocery generation** oracle row asserted exactly in
      `test_inventory_math.py`: missing opaque, compatible partial, mixed-bucket
      partial, only incompatible, fully covered (no line), cross-recipe known
      consolidation, first-seen partition order, only to taste. Output order is
      first-seen normalized-name then first-seen `add_quantities` partition.
- [ ] The N6 grocery-mutation contract specified: `quantity` + `unit` are an
      atomic pair (exactly one present in `model_fields_set` -> `422
      "quantity and unit must be set together"`); any `item` / `quantity` /
      `unit` edit reclassifies the line `source -> "manual"`,
      `nettable -> true`; a `checked`-only PATCH does not.
- [ ] The submit contract specified: forward-only; already-applied lines skipped;
      canonical `applied_*`; status not changed; a checked `quantity=null` line
      skipped; a checked `nettable=false` line with a real quantity is added;
      `IntegrityError` / lock timeout -> `409`, whole transaction rolled back.
- [ ] The submit-race contract specified: concurrent submits apply each checked
      line at most once.
- [ ] Reviewed and accepted as **locked** per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      the acceptance is recorded.
- [ ] `docs/phases/phase-6.md` R-7 gate checkbox ticked.
- [ ] The `generate_lines` oracle rows are not expected to pass until `phase-6b`.
