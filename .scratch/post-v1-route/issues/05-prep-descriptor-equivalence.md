# Prep-descriptor matching: which trailing words are safe to ignore?

Type: grilling
Status: open
Blocked by: 03
Parent: ../map.md

## Question

A recipe ingredient matches inventory only when `normalized_name` exactly
equals the inventory row's `match_name` within a compatible unit bucket.
`normalize_name` strips known descriptors only when they **lead** the name — so
`diced onion` matches `onion`, but `onion, diced` normalizes to `onion diced`
and matches nothing.

Decide:

1. **Which trailing forms are equivalent** — comma suffixes (`onion, diced`),
   parentheticals (`onion (diced)`), plain trailing words (`onion diced`).
2. **Where the line is between preparation and identity.** `diced`, `chopped`,
   `sliced` describe a knife. `ground`, `dried`, `smoked`, `canned` describe a
   different food. Getting this wrong deducts the wrong stock silently.
3. **The mechanism** — extend `normalize_name`, generate candidate keys and try
   them in order, or introduce aliases via the deferred `FoodItem` model.

### Constraints

- **Lock the examples first**, both matches and deliberate non-matches, in the
  normalization and inventory-math tests. This is the class of change that is
  easy to over-fit.
- Whatever is chosen applies **consistently** to all three consumers:
  availability checks, grocery generation, and cook deductions. A rule that
  matches during availability but not during deduction is worse than no rule.
- The ingredient's original display text is preserved regardless.
