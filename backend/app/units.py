"""Pure unit conversion and quantity management module.

Implements deterministic unit parsing and conversion per spec.md §2.2.
No third-party dependencies. Dimensions: MASS (base g), VOLUME (base ml), COUNT (base unit).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.normalize import _singularize_token


class Dimension(Enum):
    """Base units: g for mass, ml for volume, unit for count."""

    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"


@dataclass(frozen=True)
class Quantity:
    """A quantity with an amount and unit."""

    amount: Optional[float]
    unit: Optional[str]


@dataclass(frozen=True)
class UnitDef:
    """Definition of a known unit."""

    dimension: Dimension
    factor_to_base: float
    canonical: str  # "g", "ml", or "unit"


# Build unit definitions with shared instances for synonyms
# Created instances
_GRAM_DEF = UnitDef(Dimension.MASS, 1.0, "g")
_KG_DEF = UnitDef(Dimension.MASS, 1000.0, "g")
_MG_DEF = UnitDef(Dimension.MASS, 0.001, "g")
_OUNCE_DEF = UnitDef(Dimension.MASS, 28.3495, "g")
_LB_DEF = UnitDef(Dimension.MASS, 453.592, "g")

_ML_DEF = UnitDef(Dimension.VOLUME, 1.0, "ml")
_L_DEF = UnitDef(Dimension.VOLUME, 1000.0, "ml")
_TSP_DEF = UnitDef(Dimension.VOLUME, 4.92892, "ml")
_TBSP_DEF = UnitDef(Dimension.VOLUME, 14.7868, "ml")
_CUP_DEF = UnitDef(Dimension.VOLUME, 236.588, "ml")
_FLOZ_DEF = UnitDef(Dimension.VOLUME, 29.5735, "ml")
_PINT_DEF = UnitDef(Dimension.VOLUME, 473.176, "ml")
_QUART_DEF = UnitDef(Dimension.VOLUME, 946.353, "ml")
_GALLON_DEF = UnitDef(Dimension.VOLUME, 3785.41, "ml")

_UNIT_DEF = UnitDef(Dimension.COUNT, 1.0, "unit")
_DOZEN_DEF = UnitDef(Dimension.COUNT, 12.0, "unit")
_PAIR_DEF = UnitDef(Dimension.COUNT, 2.0, "unit")

# Synonym table: normalized token -> UnitDef
# All synonyms for the same unit share the same UnitDef instance
_UNIT_TABLE: dict[str, UnitDef] = {
    # MASS (base g)
    "g": _GRAM_DEF,
    "gram": _GRAM_DEF,
    "kg": _KG_DEF,
    "mg": _MG_DEF,
    "oz": _OUNCE_DEF,
    "ounce": _OUNCE_DEF,
    "lb": _LB_DEF,
    "lbs": _LB_DEF,
    "pound": _LB_DEF,
    # VOLUME (base ml)
    "ml": _ML_DEF,
    "l": _L_DEF,
    "litre": _L_DEF,
    "liter": _L_DEF,
    "tsp": _TSP_DEF,
    "teaspoon": _TSP_DEF,
    "tbsp": _TBSP_DEF,
    "tablespoon": _TBSP_DEF,
    "cup": _CUP_DEF,
    "fl-oz": _FLOZ_DEF,
    "fl oz": _FLOZ_DEF,
    "floz": _FLOZ_DEF,
    "pint": _PINT_DEF,
    "quart": _QUART_DEF,
    "gallon": _GALLON_DEF,
    # COUNT (base unit)
    "unit": _UNIT_DEF,
    "each": _UNIT_DEF,
    "dozen": _DOZEN_DEF,
    "pair": _PAIR_DEF,
}

# Deliberately unknown tokens: exact-string match only
OPAQUE_TOKENS = frozenset({
    "clove",
    "slice",
    "piece",
    "stick",
    "can",
    "package",
    "pkg",
    "jar",
    "bottle",
    "box",
    "bag",
    "head",
    "bulb",
    "bunch",
    "sprig",
    "pinch",
    "handful",
    "dash",
    "splash",
    "to taste",
})


def normalize_unit_token(s: Optional[str]) -> Optional[str]:
    """Normalize a unit token to a canonical form.

    None or "" -> None
    else: lower -> strip -> strip one trailing "." ->
          singularize whole string (call _singularize_token) -> return

    Examples: "Cups." -> "cup"; "boxes" -> "box"; "bunches" -> "bunch";
              "fl oz" -> "fl oz" (unchanged); "lbs" -> "lb"
    """
    if s is None or s == "":
        return None

    # Lower and strip
    s = s.strip().lower()

    # Strip one trailing "."
    if s.endswith("."):
        s = s[:-1]

    # Singularize the whole string
    s = _singularize_token(s)

    return s


def parse_unit(s: Optional[str]) -> Optional[UnitDef]:
    """Parse a unit token to a UnitDef, or None if opaque/unknown.

    normalize_unit_token then dict lookup; normalized None is the COUNT token;
    a non-None token absent from the table => unknown/opaque (return None)

    Always returns the same instance from _UNIT_TABLE (same object identity for is checks).
    """
    normalized = normalize_unit_token(s)

    if normalized is None:
        # None or empty maps to the COUNT token
        return _UNIT_TABLE["unit"]

    # Check if it's in the known table (returns the same cached instance)
    if normalized in _UNIT_TABLE:
        return _UNIT_TABLE[normalized]

    # Unknown or opaque -> None
    return None


def to_base(amount: float, unit: Optional[str]) -> Optional[tuple[float, Dimension]]:
    """Convert a quantity to base units.

    unit resolves to None-token  -> (amount, COUNT)
    unit is known                -> (amount * factor_to_base, dimension)
    unit is opaque/unknown       -> None
    """
    parsed = parse_unit(unit)

    if parsed is None:
        # Opaque or unknown
        return None

    base_amount = amount * parsed.factor_to_base
    return (base_amount, parsed.dimension)


def from_base(amount: float, dim: Dimension, unit: Optional[str]) -> Optional[float]:
    """Convert from base units back to the specified unit.

    unit None / canonical-for-dim -> amount        (already base)
    unit known & same dimension   -> amount / factor_to_base
    otherwise                     -> None
    """
    parsed = parse_unit(unit)

    if parsed is None:
        # Opaque or unknown
        return None

    if parsed.dimension != dim:
        # Cross-dimension
        return None

    # Convert from base to target unit
    return amount / parsed.factor_to_base


def compatible(a: Optional[str], b: Optional[str]) -> bool:
    """Check if two units are compatible (same dimension).

    both resolve to a known UnitDef of the same Dimension; a None token counts as COUNT
    """
    parsed_a = parse_unit(a)
    parsed_b = parse_unit(b)

    if parsed_a is None or parsed_b is None:
        return False

    return parsed_a.dimension == parsed_b.dimension


def bucket_of(unit: Optional[str]) -> str:
    """Get the partition bucket for a unit.

    None                -> "count"
    known               -> dimension.value  ("mass" | "volume" | "count")
    opaque/unknown      -> "opaque:" + normalize_unit_token(unit)
    """
    parsed = parse_unit(unit)

    if parsed is not None:
        # Known unit -> return the dimension name
        return parsed.dimension.value

    # Opaque or unknown
    normalized = normalize_unit_token(unit)
    return f"opaque:{normalized}"


def canon_unit(bucket: str) -> str:
    """Get the canonical unit for a bucket.

    "mass" -> "g"
    "volume" -> "ml"
    "count" -> "unit"
    "opaque:X" -> "X"
    """
    if bucket == "mass":
        return "g"
    elif bucket == "volume":
        return "ml"
    elif bucket == "count":
        return "unit"
    elif bucket.startswith("opaque:"):
        return bucket[7:]  # Remove "opaque:" prefix
    else:
        # Shouldn't happen, but fallback
        return bucket


def add_quantities(qs: list[Quantity]) -> list[Quantity]:
    """Partition quantities by bucket and sum within each partition.

    Partitions are emitted in first-seen input order, each expressed in its
    canonical unit.

    - known units: partition by Dimension, sum in base units, emit canonical
    - opaque units: partition by normalized token, sum raw amounts, emit as-is
    - None units: merged into COUNT partition
    - all-None partition: emit Quantity(None, <unit>)
    - None mixed with numbers: None counts as 0
    """
    if not qs:
        return []

    # Track first-seen order, base amounts, and whether all amounts are None
    buckets: dict[str, tuple[list[float], list[bool], Optional[str]]] = {}
    bucket_order: list[str] = []

    for q in qs:
        bucket = bucket_of(q.unit)

        if bucket not in buckets:
            bucket_order.append(bucket)
            buckets[bucket] = ([], [], q.unit)

        base_amounts, all_none_flags, first_unit = buckets[bucket]

        # Check if this specific quantity has a None amount
        all_none_flags.append(q.amount is None)

        # If the amount is None, treat it as 0 for summation
        if q.amount is None:
            # For known units, we need to convert to base; for opaque, just use 0
            if bucket in ("mass", "volume", "count"):
                base_amounts.append(0.0)
            else:
                base_amounts.append(0.0)
        else:
            # For known units, convert to base units
            if bucket in ("mass", "volume", "count"):
                # Get the UnitDef for this unit
                parsed = parse_unit(q.unit)
                if parsed is not None:
                    # Convert to base
                    base = q.amount * parsed.factor_to_base
                    base_amounts.append(base)
                else:
                    # Shouldn't happen for known buckets, but fallback
                    base_amounts.append(q.amount)
            else:
                # Opaque bucket - use raw amount
                base_amounts.append(q.amount)

    # Process each bucket and emit results
    result: list[Quantity] = []

    for bucket in bucket_order:
        base_amounts, all_none_flags, first_unit = buckets[bucket]

        # Check if ALL amounts in this partition are None
        if all(flag for flag in all_none_flags):
            # All None - emit Quantity(None, canonical)
            canonical = canon_unit(bucket)
            result.append(Quantity(None, canonical))
        else:
            # Sum the base amounts
            total_base = sum(base_amounts)

            # Convert from base to canonical unit if needed
            if bucket in ("mass", "volume", "count"):
                # Determine dimension
                if bucket == "mass":
                    dim = Dimension.MASS
                elif bucket == "volume":
                    dim = Dimension.VOLUME
                else:
                    dim = Dimension.COUNT

                # Get canonical unit
                canonical = canon_unit(bucket)

                # For known units, the total is already in base units
                # The result should be in canonical units (which is the base for each dimension)
                result.append(Quantity(total_base, canonical))
            else:
                # Opaque bucket - total_base is the raw sum
                canonical = canon_unit(bucket)
                result.append(Quantity(total_base, canonical))

    return result
