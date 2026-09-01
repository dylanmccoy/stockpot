# Open Backend v1 Issues

Only unresolved findings belong here. Resolved review findings N1–N4 and their
rationale are preserved in [`decisions.md`](decisions.md).

These issues do not block Phases 0–3. Each becomes a gate for its owning phase
and must be resolved in the normative [`spec.md`](spec.md) before that phase is
implemented.

| ID | Severity | Owner | Summary | Confidence | Status |
|---|---|---|---|---:|---|
| N5 | High | Phase 4 | Canonicalize and validate editable inventory `match_name` | 0.97 | Open |
| N7 | Medium | Phase 5 | Type and stabilize every cook-deduction response entry | 0.99 | Open |
| N6 | Medium | Phase 6 | Make grocery quantity/unit edits physically safe | 0.96 | Open |

## N5 — Inventory `match_name` is not canonicalized

**Current specification:** An explicitly supplied `match_name` is trimmed but
not passed through `normalize_name`; collision checks use the trimmed value.

**Failure scenario:** Editing a row to `" Flour "` or `"Flour"` fails to match a
recipe ingredient whose canonical name is `"flour"`. An empty string creates an
effectively unreachable stock row, and differently cased values can represent
the same logical identity without colliding.

**Impact:** The repair mechanism can disconnect stock or create duplicate
logical identities, producing false missing/short results.

**Required decision:** Confirm that `match_name` is a canonical server-owned key
even when its source text comes from a user.

**Recommended resolution:**

- Run every supplied `match_name` through `normalize_name`.
- Reject an empty normalized result with 422.
- Detect `(match_name, unit_bucket)` collisions after normalization.
- Test casing, surrounding punctuation/whitespace, empty input, and collision
  after normalization.

**Resolution must update:** `spec.md` inventory model, inventory POST/PATCH
algorithms, tests, and [`phases/phase-4.md`](phases/phase-4.md).

## N7 — Cook deductions are untyped

**Current specification:** `CookLog.deductions` is stored and returned as
`list[dict]`. The prose requires a consistent full key set, using nulls when a
field is inapplicable, but response validation cannot enforce it.

**Failure scenario:** A client reads `deducted_unit`, `before`, or `after`
successfully for applied entries but encounters a missing or misspelled key for
`to_taste`, missing-stock, or incompatible-stock entries.

**Impact:** The promised audit format varies by branch and becomes fragile
before deferred undo and review features consume it.

**Required decision:** Decide whether v1 guarantees the deduction audit shape at
the Pydantic boundary rather than by convention alone.

**Recommended resolution:**

- Add a typed `CookDeductionRead` schema.
- Make inapplicable fields explicitly nullable while keeping every key present.
- Use `list[CookDeductionRead]` in `CookLogRead`; the database JSON column can
  remain unchanged.
- Test every deduction reason against the same response key set.

**Resolution must update:** `spec.md` cook-log model/API/test matrix and
[`phases/phase-5.md`](phases/phase-5.md).

## N6 — Grocery quantity and unit edits are not atomic

**Current specification:** Grocery-line PATCH independently applies optional
`item`, `quantity`, and `unit` fields, leaving `source` and `nettable` untouched.

**Failure scenario:** A generated line contains `500 g flour`. A PATCH that only
sets `unit: "kg"` leaves the number at 500, so submit adds 500 kg. Editing the
item or units can also leave a stale generated/nettable classification attached
to different data.

**Impact:** A normal edit can add orders of magnitude too much inventory and
violate the generated-line canonical-unit contract.

**Required decision:** Choose whether unit-only edits preserve physical quantity
or whether changing a unit requires an explicit quantity/unit pair.

**Recommended resolution:**

- Treat quantity and unit as an atomic pair, or convert the existing quantity
  when only the unit changes.
- After a semantic item/quantity/unit edit, either canonicalize the line or
  reclassify it as manual.
- Recompute or explicitly clear `nettable` after semantic edits.
- Test `500 g` followed by a unit-only `kg` edit.

**Resolution must update:** `spec.md` grocery update schema/algorithm/test matrix
and [`phases/phase-6.md`](phases/phase-6.md).

## Closing an issue

1. Record the chosen behavior in `spec.md`.
2. Update its phase checklist and acceptance tests.
3. Move the resolution summary to `decisions.md`.
4. Remove the issue from this file rather than leaving a resolved-history table.
