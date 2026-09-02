# Recipe & Food Inventory

A single-household app for storing recipes with structured ingredients, tracking
food on hand, checking a recipe against stock, recording cooking, and building
grocery lists from what is missing. The unit of work is "make this recipe now."

## Language

### Units and quantities

Three distinct concepts in this codebase are all casually called "unit". They
are never interchangeable.

**Author's unit**:
The word an ingredient was written with, kept verbatim apart from casing and a
trailing period (`cups`, `tbsp`, `can`). Display only — it never drives math.
_Avoid_: unit (unqualified), raw unit

**Canonical unit**:
The one unit every quantity in a bucket is measured and reported in — `g`,
`ml`, `unit`, or the opaque token itself. All stored amounts and all API-visible
quantities outside a recipe body are in canonical units.
_Avoid_: base unit, normalized unit

**Display unit**:
A per-inventory-row *preference* for how to render that row's amount back to a
human. Never a source of truth; the canonical amount is.
_Avoid_: preferred unit, user unit

**Unit bucket**:
The compatibility class two amounts must share before they can be added or
netted against each other: `mass`, `volume`, `count`, or `opaque:<token>`.
Amounts in different buckets are never combined.
_Avoid_: dimension (that is the narrower mass/volume/count enum), unit type

**Opaque unit**:
A real-world unit deliberately left unconvertible — `can`, `clove`, `bunch`.
It sums against itself and against nothing else.
_Avoid_: unknown unit, custom unit
