# Display-unit conversion: which preference wins?

Type: grilling
Status: open
Blocked by: 03
Parent: ../map.md

## Question

Every quantity outside a recipe body is emitted in its bucket's **canonical
unit** (decision #P5). So `2 lb` of chicken becomes a grocery line asking for
`453.592 g`, and `1 cup` of stock reports availability in `ml`. `features.md`
deferred this because the *conversion* is trivial (`units.from_base` already
exists and already returns `None` for an incomparable target) while the
*preference source* is a real design question.

Decide:

1. **Where the preference comes from.** Per-inventory-row `display_unit` (the
   column exists, and `InventoryItemRead.display_quantity` already demonstrates
   the pattern)? A per-user setting? A `?units=` request parameter? Or match
   the unit the recipe ingredient was authored in — which is what the original
   feature request actually asked for?
2. **Which responses convert.** Availability `need_unit` / `group_unit`,
   generated grocery-line `unit`, cook-log quantities — all, or some?
3. **Whether the canonical value stays in the payload** alongside the converted
   one, so tests and clients keep an unambiguous number.
4. **What happens when conversion is impossible** — cross-bucket, or an opaque
   unit like `can`. Existing uncertainty behaviour must not be papered over
   with a guessed conversion.

### Constraints

- **Nothing about storage changes.** `quantity_base` stays canonical, and the
  R-7 locked oracles stay expressed in canonical units. This is a
  serialization-layer decision only.
- Read `CONTEXT.md` first: *author's unit*, *canonical unit*, *display unit*,
  and *unit bucket* are four different things and this ticket touches all four.
  If the decision needs a fifth term, add it there.
