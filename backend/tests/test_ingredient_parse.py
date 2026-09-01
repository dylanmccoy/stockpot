"""Locked contract tests for ``app.services.ingredient_parse`` (spec.md §2.3).

R-7 independent contract-test gate: oracles are translated from the normative
spec, not an implementation. The implementation's exact regex is free, but it
must satisfy these tables and invariants. The implementation pass may add cases
but must not edit or delete the expected values here.

Contract (spec.md §2.3): callers skip blank/whitespace-only strings before
calling; for every non-blank input the parser never raises; ``item`` is always
non-empty; ``quantity`` is either a positive finite float or ``None`` (never 0,
negative, or non-finite).
"""

import math

import pytest

from app.services.ingredient_parse import parse_ingredient

REL = 1e-9
ABS = 1e-9

EXPECTED_KEYS = {"quantity", "unit", "item", "note"}


def _assert_quantity(actual, expected) -> None:
    if expected is None:
        assert actual is None
    else:
        assert isinstance(actual, float)
        assert actual == pytest.approx(expected, rel=REL, abs=ABS)


# --- spec.md §2.3 "Acceptance table (locked)" -------------------------------

ACCEPTANCE = [
    ("2 tbsp olive oil", 2.0, "tbsp", "olive oil", None),
    ("1 1/2 cups flour", 1.5, "cups", "flour", None),
    ("½ tsp salt", 0.5, "tsp", "salt", None),
    ("salt to taste", None, None, "salt", "to taste"),
    ("3 large eggs", 3.0, None, "large eggs", None),
    ("1 (14 oz) can tomatoes", 1.0, "can", "tomatoes", "14 oz"),
    ("asdfghjkl", None, None, "asdfghjkl", None),
]


@pytest.mark.parametrize("text,quantity,unit,item,note", ACCEPTANCE)
def test_locked_acceptance_table(text, quantity, unit, item, note) -> None:
    r = parse_ingredient(text)
    assert set(r) == EXPECTED_KEYS
    _assert_quantity(r["quantity"], quantity)
    assert r["unit"] == unit
    assert r["item"] == item
    assert r["note"] == note


# --- spec.md §2.3 deterministic adversarial corpus -------------------------
# Never raises; item non-empty; quantity is None or a positive finite float.

ADVERSARIAL = [
    "0 eggs",
    "-1 cup flour",
    "1/0 cup flour",
    "NaN cups flour",
    "1e309 cups flour",
    "not a quantity",
]


@pytest.mark.parametrize("text", ADVERSARIAL)
def test_adversarial_corpus_contract(text: str) -> None:
    r = parse_ingredient(text)  # must not raise
    assert set(r) == EXPECTED_KEYS
    assert isinstance(r["item"], str) and r["item"].strip() != ""
    q = r["quantity"]
    assert q is None or (isinstance(q, float) and math.isfinite(q) and q > 0)
    assert r["unit"] is None or isinstance(r["unit"], str)
    assert r["note"] is None or isinstance(r["note"], str)


# --- number forms ---------------------------------------------------------------

VULGAR_FRACTIONS = [
    ("½", 0.5),
    ("¼", 0.25),
    ("¾", 0.75),
    ("⅓", 1.0 / 3.0),
    ("⅔", 2.0 / 3.0),
    ("⅛", 0.125),
]


@pytest.mark.parametrize("glyph,value", VULGAR_FRACTIONS)
def test_unicode_vulgar_fraction_quantity(glyph: str, value: float) -> None:
    r = parse_ingredient(f"{glyph} cup sugar")
    _assert_quantity(r["quantity"], value)
    assert r["unit"] == "cup"
    assert r["item"] == "sugar"


def test_mixed_number_quantity() -> None:
    _assert_quantity(parse_ingredient("1 1/2 cups flour")["quantity"], 1.5)
    _assert_quantity(parse_ingredient("2 3/4 cups flour")["quantity"], 2.75)


def test_simple_fraction_quantity() -> None:
    _assert_quantity(parse_ingredient("3/4 tsp salt")["quantity"], 0.75)
    _assert_quantity(parse_ingredient("1/3 cup water")["quantity"], 1.0 / 3.0)


def test_decimal_and_integer_quantity() -> None:
    _assert_quantity(parse_ingredient("0.5 cup milk")["quantity"], 0.5)
    _assert_quantity(parse_ingredient("2 eggs")["quantity"], 2.0)


# --- unit handling ------------------------------------------------------------

def test_unit_stored_as_written_not_singularized() -> None:
    assert parse_ingredient("1 1/2 cups flour")["unit"] == "cups"     # not "cup"
    assert parse_ingredient("2 Tbsp. butter")["unit"] == "tbsp"       # lowered, "." stripped
    assert parse_ingredient("3 CLOVES garlic")["unit"] == "cloves"    # opaque unit, as written


def test_token_after_number_that_is_not_a_unit_word_stays_in_item() -> None:
    r = parse_ingredient("3 large eggs")
    assert r["unit"] is None
    assert r["item"] == "large eggs"


# --- item handling ----------------------------------------------------------

def test_no_leading_number_yields_bare_item() -> None:
    r = parse_ingredient("freshly ground black pepper")
    assert r["quantity"] is None
    assert r["unit"] is None
    assert r["item"] == "freshly ground black pepper"


def test_descriptors_are_kept_in_item() -> None:
    assert parse_ingredient("3 large eggs")["item"] == "large eggs"
    assert parse_ingredient("1 cup diced onion")["item"] == "diced onion"


def test_item_never_empty_when_only_quantity_and_unit_present() -> None:
    r = parse_ingredient("2 tbsp")
    assert isinstance(r["item"], str) and r["item"].strip() != ""


def test_garbage_falls_back_to_raw_line() -> None:
    assert parse_ingredient("asdfghjkl") == {
        "quantity": None,
        "unit": None,
        "item": "asdfghjkl",
        "note": None,
    }


# --- note handling ----------------------------------------------------------

def test_to_taste_sets_note_and_nulls_quantity() -> None:
    r = parse_ingredient("salt to taste")
    assert r["quantity"] is None
    assert r["note"] == "to taste"
    assert r["item"] == "salt"

    r2 = parse_ingredient("black pepper to taste")
    assert r2["quantity"] is None
    assert r2["note"] == "to taste"
    assert r2["item"] == "black pepper"


def test_to_taste_nulls_an_already_parsed_quantity() -> None:
    # spec.md §2.3: "a trailing / embedded 'to taste' -> note = 'to taste' and
    # quantity = None". A leading number IS parsed here, so this pins the "null
    # any quantity that was parsed" half — a suffix-only rule that leaves the
    # parsed quantity in place must fail.
    r = parse_ingredient("1 tsp salt to taste")
    assert r["quantity"] is None
    assert r["note"] == "to taste"
    assert r["item"] == "salt"


def test_embedded_to_taste_with_trailing_text() -> None:
    # "to taste" is not at the end of the string here; an endswith() check would
    # miss it. Note is still set and the parsed quantity is still nulled.
    r = parse_ingredient("2 tbsp olive oil to taste for the dressing")
    assert r["quantity"] is None
    assert r["note"] == "to taste"
    assert isinstance(r["item"], str) and "olive oil" in r["item"]


def test_trailing_parenthetical_becomes_note_without_parens() -> None:
    r = parse_ingredient("2 cups flour (sifted)")
    _assert_quantity(r["quantity"], 2.0)
    assert r["unit"] == "cups"
    assert r["item"] == "flour"
    assert r["note"] == "sifted"
