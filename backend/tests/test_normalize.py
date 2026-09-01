"""Locked contract tests for ``app.normalize`` (spec.md §2.1).

R-7 independent contract-test gate: these oracles are translated from the
normative spec, not from an implementation. The implementation pass may add
cases but must not edit or delete the expected values here.

Deliberately NOT asserted (D1): global idempotence of ``normalize_name``. The
small open-vocabulary heuristic may map ``"buses" -> "bus" -> "bu"`` on repeated
calls; callers normalize source text exactly once.
"""

import pytest

from app.normalize import normalize_name

# --- spec.md §2.1 "Locked normalization oracles (R-7)" -----------------------

LOCKED_ORACLES = [
    ("  Diced Tomatoes! ", "tomato"),      # trim, case, punctuation, descriptor, irregular
    ("large eggs", "egg"),                 # descriptor + trailing -s
    ("chopped   red onions", "red onion"), # whitespace + final-token-only singularization
    ("fresh tomatoes", "fresh tomato"),    # identity-bearing word retained
    ("ground beef", "ground beef"),        # identity-bearing word retained
    ("berries", "berry"),                  # -ies rule
    ("boxes", "box"),                      # -xes rule
    ("potatoes", "potato"),                # irregular map before suffix rules
    ("glass", "glass"),                    # terminal -ss retained
    ("Chef's   choice", "chefs choice"),   # punctuation removal + whitespace
    ("!!!", ""),                           # valid degenerate result
]


@pytest.mark.parametrize("raw,expected", LOCKED_ORACLES)
def test_locked_normalization_oracles(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


# --- LEADING_DESCRIPTORS: stripped when leading (spec.md §2.1 step 4) --------

LEADING_DESCRIPTORS = [
    "diced", "chopped", "minced", "sliced", "shredded", "grated", "crushed",
    "cubed", "julienned", "large", "small", "medium", "jumbo", "boneless",
    "skinless", "ripe", "peeled",
]


@pytest.mark.parametrize("descriptor", LEADING_DESCRIPTORS)
def test_leading_descriptor_is_stripped(descriptor: str) -> None:
    assert normalize_name(f"{descriptor} onion") == "onion"


def test_stacked_leading_descriptors_all_stripped() -> None:
    assert normalize_name("diced peeled ripe onion") == "onion"


def test_descriptor_only_input_is_degenerate_empty() -> None:
    assert normalize_name("diced") == ""
    assert normalize_name("large chopped") == ""


def test_descriptor_not_stripped_when_not_leading() -> None:
    # "diced" is only dropped from the front; mid-phrase it stays.
    assert normalize_name("red diced onion") == "red diced onion"


# --- identity-bearing words: never stripped (spec.md §2.1 "Not stripped") ----

IDENTITY_BEARING = [
    "fresh", "dried", "ground", "cooked", "raw",
    "smoked", "frozen", "canned", "roasted", "toasted",
]


@pytest.mark.parametrize("word", IDENTITY_BEARING)
def test_identity_bearing_word_retained(word: str) -> None:
    assert normalize_name(f"{word} beef") == f"{word} beef"


# --- singularization: final token only --------------------------------------

def test_only_final_token_is_singularized() -> None:
    # "oats" would singularize to "oat" if the rule touched non-final tokens.
    assert normalize_name("oats bar") == "oats bar"
    # locked oracle "Chef's choice" already shows a non-final "chefs" untouched;
    # this is the positive form of the same contract.
    assert normalize_name("chopped green onions") == "green onion"


# --- _singularize_token rule table, exercised via normalize_name ------------

IRREGULAR = [
    ("tomatoes", "tomato"),
    ("potatoes", "potato"),
    ("leaves", "leaf"),
    ("loaves", "loaf"),
    ("halves", "half"),
    ("knives", "knife"),
    ("wolves", "wolf"),
]

SUFFIX_RULES = [
    ("berries", "berry"),      # -ies -> -y
    ("cherries", "cherry"),    # -ies -> -y
    ("glasses", "glass"),      # -ses -> drop -es
    ("boxes", "box"),          # -xes -> drop -es
    ("fizzes", "fizz"),        # -zes -> drop -es
    ("peaches", "peach"),      # -ches -> drop -es
    ("squashes", "squash"),    # -shes -> drop -es
    ("dishes", "dish"),        # -shes -> drop -es
    ("mangoes", "mango"),      # -oes -> -o
    ("heroes", "hero"),        # -oes -> -o
    ("eggs", "egg"),           # trailing -s (not -ss) -> drop -s
    ("onions", "onion"),       # trailing -s (not -ss) -> drop -s
    ("glass", "glass"),        # ends -ss -> unchanged
    ("grass", "grass"),        # ends -ss -> unchanged
    ("beef", "beef"),          # no trailing -s -> unchanged
]


@pytest.mark.parametrize("raw,expected", IRREGULAR)
def test_irregular_singularization_map(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw,expected", SUFFIX_RULES)
def test_singularization_suffix_rules(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


# --- punctuation / whitespace ---------------------------------------------------

def test_punctuation_dropped_whitespace_collapsed() -> None:
    assert normalize_name("Chef's   choice") == "chefs choice"
    assert normalize_name("  spaced    out   name  ") == "spaced out name"


def test_hyphen_is_preserved() -> None:
    assert normalize_name("extra-virgin olive oil") == "extra-virgin olive oil"


# --- degenerate results -------------------------------------------------------

@pytest.mark.parametrize("raw", ["!!!", "", "   ", "@#$%^&*()", "  ...  "])
def test_degenerate_input_returns_empty_string(raw: str) -> None:
    assert normalize_name(raw) == ""
