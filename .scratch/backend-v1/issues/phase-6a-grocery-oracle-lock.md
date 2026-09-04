# phase-6a: Grocery contract-test lock (R-7)

**What to build:** A locked, independently-reviewed black-box test slice for
`generate_lines`, grocery line mutation (N6), submit, and the submit race —
authored from `docs/spec.md` §4.3 / §5.6 / §6 / §7 only, in a fresh context,
before Phase 6 production code.

**Blocked by:** `phase-5c` (Phase 5 complete).

**Status:** done

**Files:** edit `backend/tests/test_inventory_math.py` and/or create a grocery contract test; `docs/phases/phase-6.md`. Authored black-box from the spec in a fresh context — no production code.

**Spec:** `docs/spec.md` §4.3 (`generate_lines` + netting table), §5.6 (grocery API — line mutation N6, submit, archive), §6 (submit race), §7 Grocery generation / mutation / submit contract rows. Read only these sections.

**Tests:** n/a — locked; the `generate_lines` rows are not expected to pass until `phase-6b`.

- [x] Every §7 **Grocery generation** oracle row asserted exactly in
      `test_inventory_math.py`: missing opaque, compatible partial, mixed-bucket
      partial, only incompatible, fully covered (no line), cross-recipe known
      consolidation, first-seen partition order, only to taste. Output order is
      first-seen normalized-name then first-seen `add_quantities` partition.
      *(new "§7 — Grocery generation" section; `GROCERY_GENERATION_CASES` — the
      8 named rows + a 9th multi-food row locking first-seen-normalized-name
      order across recipes, which no §7 table row does; + invariant tests: no
      negative quantity, fully-covered-emits-no-line, inventory-reorder-stable,
      empty input. Values cross-checked against a faithful port of the §4.3
      pseudocode over the real `units` module.)*
- [x] The N6 grocery-mutation contract specified: `quantity` + `unit` are an
      atomic pair (exactly one present in `model_fields_set` -> `422
      "quantity and unit must be set together"`); any `item` / `quantity` /
      `unit` edit reclassifies the line `source -> "manual"`,
      `nettable -> true`; a `checked`-only PATCH does not.
      *(`test_grocery_contract.py` §A: unit-only / quantity-only / quantity+item
      no-unit -> 422; `{quantity,unit}` edit sets as-sent + reclassifies, with a
      real `nettable` false->true flip locked on the generated non-nettable
      line; `item` edit reclassifies + recomputes `normalized_name`;
      `checked`-only leaves `source`/`nettable`; null/null passes the atomic-pair
      gate (reclassification of a pure no-value edit left to `phase-6c`).)*
- [x] The submit contract specified: forward-only; already-applied lines skipped;
      canonical `applied_*`; status not changed; a checked `quantity=null` line
      skipped; a checked `nettable=false` line with a real quantity is added;
      `IntegrityError` / lock timeout -> `409`, whole transaction rolled back.
      *(`test_grocery_contract.py` §B + §C: forward-only two-pass submit,
      canonical `applied_quantity`/`applied_unit` (`0.5 kg` -> `500 g`), list
      stays `active`, null-quantity line skipped, non-nettable line applied,
      nothing-eligible no-op, `404`/non-active `409`, frozen-line `409` on
      PATCH/DELETE. Lock-timeout -> `409 {"detail":"conflict"}` with a
      single-line and a two-line list (the latter locks §6 "no partly-submitted
      grocery list"). A raw `IntegrityError`-triggered `409` is not
      reconstructable black-box before the schema exists — deferred to
      `phase-6d` `test_grocery.py` (generic commit-time -> `409` is already
      locked in `test_transactions.py` / `test_cook_contract.py`).)*
- [x] The submit-race contract specified: concurrent submits apply each checked
      line at most once.
      *(`test_two_concurrent_submits_apply_the_checked_line_at_most_once` —
      file-backed DB, two threaded HTTP submits; each responds `200`|`409`, the
      line freezes once, `applied_quantity` canonical, inventory reflects one
      application not two.)*
- [x] Reviewed and accepted as **locked** per
      [`docs/plan.md` §Independent contract-test gate](../../../docs/plan.md);
      the acceptance is recorded.
      *(fresh-context two-axis `/code-review` on the diff. Spec axis: all 8 §7
      generation rows match the table verbatim and re-derive correctly against
      §4.3; no wrong locked values. Standards axis: no hard violations, tracks
      the sibling `test_cook_contract.py` / `test_inventory_math.py` house
      style. Findings actioned — dropped unused helper params; added the
      `nettable` false->true flip, the third-key-present 422, and the two-line
      rollback test; commented the 9th generation row's provenance. Acceptance
      recorded here + in the commit + the `phase-6.md` gate note.)*
- [x] `docs/phases/phase-6.md` R-7 gate checkbox ticked.
- [x] The `generate_lines` oracle rows are not expected to pass until `phase-6b`.
      *(Both files fail on collection — `test_inventory_math.py` on the
      `generate_lines` / `GroceryLineDTO` import, `test_grocery_contract.py` on
      `app.schemas.grocery`. `cd backend && uv run pytest` is red on this branch
      by design; the rest of the suite is 585 passed. Matches the `phase-4a` /
      `phase-5a` locked-oracle pattern per `.scratch/backend-v1/issues/README.md`.)*

## Comments

- Branch: `test/backend-v1-phase-6a` (off `main`).
- Worktree: `.claude/worktrees/backend-v1-phase-6a`.
- Two test files: new section in `backend/tests/test_inventory_math.py`
  (generate_lines oracle) + new `backend/tests/test_grocery_contract.py`
  (24 tests, N6 / submit / submit-race). No production code touched.
- Not expected to pass until `phase-6b` lands `generate_lines` /
  `GroceryLineDTO` and `app.schemas.grocery`; `phase-6d` (submit) / `phase-6e`
  (archive) close the rest. `phase-6b`+ may add cases but must not edit an
  accepted expected value here.
