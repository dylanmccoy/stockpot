"""Locked contract tests for ``app.units`` (spec.md §2.2).

R-7 independent contract-test gate: oracles are translated from the normative
spec, not an implementation. The implementation pass may add cases but must not
edit or delete the expected values here.

All numeric comparisons use ``pytest.approx(expected, rel=1e-9, abs=1e-9)`` per
the §2 floating-tolerance rule; conversion results are never compared by exact
binary-float equality.
"""

import pytest

from app.units import (
    Dimension,
    Quantity,
    UnitDef,
    add_quantities,
    bucket_of,
    canon_unit,
    compatible,
    from_base,
    normalize_unit_token,
    parse_unit,
    to_base,
)

REL = 1e-9
ABS = 1e-9


def _approx(x: float) -> object:
    return pytest.approx(x, rel=REL, abs=ABS)


# --- synonym table: (token, factor_to_base, dimension) ----------------------
# Values are the normative §2.2 table; this locks every factor.

KNOWN_TOKENS = [
    ("g", 1.0, Dimension.MASS),
    ("gram", 1.0, Dimension.MASS),
    ("kg", 1000.0, Dimension.MASS),
    ("mg", 0.001, Dimension.MASS),
    ("oz", 28.3495, Dimension.MASS),
    ("ounce", 28.3495, Dimension.MASS),
    ("lb", 453.592, Dimension.MASS),
    ("lbs", 453.592, Dimension.MASS),
    ("pound", 453.592, Dimension.MASS),
    ("ml", 1.0, Dimension.VOLUME),
    ("l", 1000.0, Dimension.VOLUME),
    ("litre", 1000.0, Dimension.VOLUME),
    ("liter", 1000.0, Dimension.VOLUME),
    ("tsp", 4.92892, Dimension.VOLUME),
    ("teaspoon", 4.92892, Dimension.VOLUME),
    ("tbsp", 14.7868, Dimension.VOLUME),
    ("tablespoon", 14.7868, Dimension.VOLUME),
    ("cup", 236.588, Dimension.VOLUME),
    ("fl-oz", 29.5735, Dimension.VOLUME),
    ("fl oz", 29.5735, Dimension.VOLUME),
    ("floz", 29.5735, Dimension.VOLUME),
    ("pint", 473.176, Dimension.VOLUME),
    ("quart", 946.353, Dimension.VOLUME),
    ("gallon", 3785.41, Dimension.VOLUME),
    ("unit", 1.0, Dimension.COUNT),
    ("each", 1.0, Dimension.COUNT),
    ("dozen", 12.0, Dimension.COUNT),
    ("pair", 2.0, Dimension.COUNT),
]

OPAQUE_TOKENS = [
    "clove", "slice", "piece", "stick", "can", "package", "pkg", "jar",
    "bottle", "box", "bag", "head", "bulb", "bunch", "sprig", "pinch",
    "handful", "dash", "splash", "to taste",
]


# --- normalize_unit_token (spec.md §2.2 inline examples) -------------------

def test_normalize_unit_token_none_and_empty() -> None:
    assert normalize_unit_token(None) is None
    assert normalize_unit_token("") is None


def test_normalize_unit_token_examples() -> None:
    assert normalize_unit_token("Cups.") == "cup"
    assert normalize_unit_token("boxes") == "box"
    assert normalize_unit_token("bunches") == "bunch"
    assert normalize_unit_token("fl oz") == "fl oz"      # unchanged (2 words, no -s)
    assert normalize_unit_token("lbs") == "lb"
    assert normalize_unit_token("  KG  ") == "kg"        # lower + strip
    assert normalize_unit_token("tsp.") == "tsp"         # one trailing "." stripped


# --- parse_unit -----------------------------------------------------------------

@pytest.mark.parametrize("val", [None, ""])
def test_parse_unit_none_or_empty_is_count_token(val) -> None:
    ud = parse_unit(val)
    assert isinstance(ud, UnitDef)
    assert ud.dimension is Dimension.COUNT
    assert ud.canonical == "unit"
    assert ud.factor_to_base == _approx(1.0)


@pytest.mark.parametrize("tok,factor,dim", KNOWN_TOKENS)
def test_parse_unit_known_tokens(tok: str, factor: float, dim: Dimension) -> None:
    ud = parse_unit(tok)
    assert isinstance(ud, UnitDef)
    assert ud.dimension is dim
    assert ud.factor_to_base == _approx(factor)
    assert ud.canonical == {"mass": "g", "volume": "ml", "count": "unit"}[dim.value]


@pytest.mark.parametrize("tok", OPAQUE_TOKENS + ["xyzzy", "wibble"])
def test_parse_unit_unknown_or_opaque_returns_none(tok: str) -> None:
    assert parse_unit(tok) is None


# --- to_base: locked oracles (spec.md §2.2 "Locked conversion oracles") ----

LOCKED_TO_BASE = [
    (1, "kg", 1000.0, Dimension.MASS),
    (16, "oz", 453.592, Dimension.MASS),
    (2, "cup", 473.176, Dimension.VOLUME),
    (3, "dozen", 36.0, Dimension.COUNT),
    (5, None, 5.0, Dimension.COUNT),
]


@pytest.mark.parametrize("amount,unit,expected_base,expected_dim", LOCKED_TO_BASE)
def test_locked_to_base_oracles(amount, unit, expected_base, expected_dim) -> None:
    res = to_base(amount, unit)
    assert res is not None
    base, dim = res
    assert dim is expected_dim
    assert base == _approx(expected_base)


@pytest.mark.parametrize("amount,unit,expected_base,expected_dim", LOCKED_TO_BASE)
def test_locked_to_base_round_trip(amount, unit, expected_base, expected_dim) -> None:
    base, dim = to_base(amount, unit)
    assert from_base(base, dim, unit) == _approx(float(amount))


def test_to_base_can_is_opaque_returns_none() -> None:
    assert to_base(1, "can") is None


@pytest.mark.parametrize("tok", ["can", "xyzzy", "to taste"])
def test_to_base_unknown_or_opaque_returns_none(tok: str) -> None:
    assert to_base(1.0, tok) is None


def test_to_base_none_unit_is_count() -> None:
    res = to_base(5.0, None)
    assert res is not None
    base, dim = res
    assert dim is Dimension.COUNT
    assert base == _approx(5.0)


# --- round-trip over every known synonym token (spec.md §2.2) --------------

@pytest.mark.parametrize("amt", [0.125, 1.0, 17.5])
@pytest.mark.parametrize("tok,factor,dim", KNOWN_TOKENS)
def test_conversion_round_trip_every_known_token(
    tok: str, factor: float, dim: Dimension, amt: float
) -> None:
    res = to_base(amt, tok)
    assert res is not None
    base, got_dim = res
    assert got_dim is dim
    assert base == _approx(amt * factor)
    assert from_base(base, dim, tok) == _approx(amt)


def test_from_base_none_and_canonical_units_pass_through() -> None:
    assert from_base(5.0, Dimension.COUNT, None) == _approx(5.0)
    assert from_base(5.0, Dimension.COUNT, "unit") == _approx(5.0)
    assert from_base(250.0, Dimension.MASS, "g") == _approx(250.0)
    assert from_base(250.0, Dimension.VOLUME, "ml") == _approx(250.0)


@pytest.mark.parametrize(
    "amount,dim,unit",
    [
        (100.0, Dimension.MASS, "cup"),    # mass base, volume unit
        (100.0, Dimension.VOLUME, "g"),    # volume base, mass unit
        (100.0, Dimension.COUNT, "g"),     # count base, mass unit
        (100.0, Dimension.MASS, "dozen"),  # mass base, count unit
    ],
)
def test_from_base_cross_dimension_returns_none(amount, dim, unit) -> None:
    assert from_base(amount, dim, unit) is None


@pytest.mark.parametrize("unit", ["can", "jar", "xyzzy"])
def test_from_base_opaque_target_returns_none(unit: str) -> None:
    assert from_base(100.0, Dimension.MASS, unit) is None


# --- R-3 plural round-trip: known units -----------------------------------------
# For every synonym-table token, parse_unit(plural) resolves to the same UnitDef.

KNOWN_PLURALS = [
    ("g", "grams"), ("gram", "grams"), ("kg", "kgs"), ("mg", "mgs"),
    ("oz", "ozs"), ("ounce", "ounces"), ("lb", "lbs"), ("pound", "pounds"),
    ("ml", "mls"), ("l", "ls"), ("litre", "litres"), ("liter", "liters"),
    ("tsp", "tsps"), ("teaspoon", "teaspoons"),
    ("tbsp", "tbsps"), ("tablespoon", "tablespoons"),
    ("cup", "cups"), ("floz", "flozs"), ("fl oz", "fl ozs"), ("fl-oz", "fl-ozs"),
    ("pint", "pints"), ("quart", "quarts"), ("gallon", "gallons"),
    ("unit", "units"), ("each", "eaches"), ("dozen", "dozens"), ("pair", "pairs"),
]


@pytest.mark.parametrize("singular,plural", KNOWN_PLURALS)
def test_plural_round_trip_known_units(singular: str, plural: str) -> None:
    assert parse_unit(singular) is not None
    assert parse_unit(plural) is parse_unit(singular)


# --- R-3 plural round-trip: opaque tokens -------------------------------------

OPAQUE_PLURALS = [
    ("clove", "cloves"), ("slice", "slices"), ("piece", "pieces"),
    ("stick", "sticks"), ("can", "cans"), ("package", "packages"),
    ("pkg", "pkgs"), ("jar", "jars"), ("bottle", "bottles"), ("box", "boxes"),
    ("bag", "bags"), ("head", "heads"), ("bulb", "bulbs"), ("bunch", "bunches"),
    ("sprig", "sprigs"), ("pinch", "pinches"), ("handful", "handfuls"),
    ("dash", "dashes"), ("splash", "splashes"),
]


@pytest.mark.parametrize("singular,plural", OPAQUE_PLURALS)
def test_plural_round_trip_opaque_tokens(singular: str, plural: str) -> None:
    assert normalize_unit_token(singular) == singular
    assert normalize_unit_token(plural) == singular
    # plural and singular net into one opaque bucket
    assert bucket_of(plural) == bucket_of(singular) == f"opaque:{singular}"


def test_to_taste_is_a_stable_opaque_token() -> None:
    # "to taste" is the one OPAQUE_TOKENS value with no plural form, so it is
    # not covered by the parametrized round-trip above. It must still normalize
    # to itself unchanged (not be rewritten to another opaque key) and land in
    # its own opaque bucket (spec.md §2.2 opaque list + §7 test_units row).
    assert normalize_unit_token("to taste") == "to taste"
    assert normalize_unit_token("  To Taste  ") == "to taste"
    assert bucket_of("to taste") == "opaque:to taste"
    assert canon_unit(bucket_of("to taste")) == "to taste"


def test_es_group_opaque_plurals_named() -> None:
    # A bare trailing-"s" strip would leave "boxe"/"dashe" and split the bucket.
    assert normalize_unit_token("boxes") == "box"
    assert normalize_unit_token("bunches") == "bunch"
    assert normalize_unit_token("dashes") == "dash"
    assert normalize_unit_token("splashes") == "splash"
    assert normalize_unit_token("pinches") == "pinch"


# --- bucket_of ----------------------------------------------------------------

def test_bucket_of() -> None:
    assert bucket_of(None) == "count"
    assert bucket_of("") == "count"
    assert bucket_of("g") == "mass"
    assert bucket_of("kg") == "mass"
    assert bucket_of("ounce") == "mass"
    assert bucket_of("ml") == "volume"
    assert bucket_of("cup") == "volume"
    assert bucket_of("gallon") == "volume"
    assert bucket_of("unit") == "count"
    assert bucket_of("each") == "count"
    assert bucket_of("dozen") == "count"
    assert bucket_of("pair") == "count"
    assert bucket_of("can") == "opaque:can"
    assert bucket_of("cans") == "opaque:can"     # plural nets to the same bucket
    assert bucket_of("Cans") == "opaque:can"     # case-normalized
    assert bucket_of("xyzzy") == "opaque:xyzzy"  # unknown -> opaque


# --- canon_unit -------------------------------------------------------------

def test_canon_unit() -> None:
    assert canon_unit("mass") == "g"
    assert canon_unit("volume") == "ml"
    assert canon_unit("count") == "unit"
    assert canon_unit("opaque:can") == "can"
    assert canon_unit("opaque:to taste") == "to taste"


# --- compatible -----------------------------------------------------------------

def test_compatible_true_cases() -> None:
    assert compatible("g", "kg")
    assert compatible("kg", "g")
    assert compatible("ml", "l")
    assert compatible("tsp", "cup")
    assert compatible("unit", None)      # None token counts as COUNT
    assert compatible(None, "dozen")
    assert compatible(None, None)


def test_compatible_false_cases() -> None:
    assert not compatible("g", "ml")     # different dimension
    assert not compatible("g", "unit")
    assert not compatible("cup", "dozen")
    assert not compatible("can", "can")  # opaque never resolves to a known UnitDef
    assert not compatible("can", "jar")
    assert not compatible("g", "xyzzy")


# --- add_quantities: locked oracles (spec.md §2.2) ------------------------

ADD_ORACLES = [
    ([], []),
    ([(1, "kg"), (500, "g")], [(1500.0, "g")]),
    ([(1, "cup"), (2, "tbsp")], [(266.1616, "ml")]),
    ([(2, "can"), (1, "cans")], [(3.0, "can")]),
    ([(2, "can"), (1, "jar")], [(2.0, "can"), (1.0, "jar")]),
    ([(2, None), (1, "dozen")], [(14.0, "unit")]),
    ([(None, "can"), (2, "can")], [(2.0, "can")]),
    ([(None, "kg"), (None, "g")], [(None, "g")]),
    (
        [(1, "can"), (1, "kg"), (1, None), (1, "jar")],
        [(1.0, "can"), (1000.0, "g"), (1.0, "unit"), (1.0, "jar")],
    ),
]


def _assert_quantities(got, expected) -> None:
    assert [type(q) for q in got] == [Quantity] * len(got)
    assert len(got) == len(expected)
    for q, (amt, unit) in zip(got, expected):
        assert q.unit == unit
        if amt is None:
            assert q.amount is None
        else:
            assert q.amount == _approx(amt)


@pytest.mark.parametrize("inp,expected", ADD_ORACLES)
def test_locked_add_quantities_oracles(inp, expected) -> None:
    got = add_quantities([Quantity(a, u) for a, u in inp])
    _assert_quantities(got, expected)


def test_add_quantities_partitions_emitted_in_first_seen_order() -> None:
    _assert_quantities(
        add_quantities([Quantity(1, "jar"), Quantity(1, "can"), Quantity(1, "kg")]),
        [(1.0, "jar"), (1.0, "can"), (1000.0, "g")],
    )
    # reordering the input reorders the output partitions
    _assert_quantities(
        add_quantities([Quantity(1, "kg"), Quantity(1, "can"), Quantity(1, "jar")]),
        [(1000.0, "g"), (1.0, "can"), (1.0, "jar")],
    )


def test_add_quantities_none_amount_mixed_with_numbers_counts_as_zero() -> None:
    _assert_quantities(
        add_quantities([Quantity(None, "can"), Quantity(2, "can"), Quantity(3, "can")]),
        [(5.0, "can")],
    )


def test_add_quantities_all_none_partition_emits_none() -> None:
    _assert_quantities(
        add_quantities([Quantity(None, "kg"), Quantity(None, "g")]), [(None, "g")]
    )
    _assert_quantities(
        add_quantities([Quantity(None, "can"), Quantity(None, "cans")]), [(None, "can")]
    )


def test_add_quantities_conserves_base_sum_per_known_dimension() -> None:
    _assert_quantities(
        add_quantities([Quantity(1, "kg"), Quantity(500, "g"), Quantity(2, "kg")]),
        [(3500.0, "g")],
    )


def test_add_quantities_conserves_raw_sum_per_opaque_token() -> None:
    _assert_quantities(
        add_quantities([Quantity(2, "can"), Quantity(3, "cans"), Quantity(1, "can")]),
        [(6.0, "can")],
    )


def test_add_quantities_none_units_merge_into_count_partition() -> None:
    _assert_quantities(
        add_quantities([Quantity(2, None), Quantity(3, "unit"), Quantity(1, "each")]),
        [(6.0, "unit")],
    )
