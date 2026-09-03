"""Locked contract tests for ``app.services.inventory_math`` (spec.md §4 / §7).

R-7 independent contract-test gate (``docs/plan.md`` §Independent contract-test
gate). These oracles are translated from the normative spec — §4 (service
signatures / algorithms) and §7 (the locked availability, deduction,
add-to-inventory, and interpretation-independent tables) — **not** from an
implementation. No Phase 4 production code existed when this file was authored.
The implementation passes (`phase-4b`/`-4c`/`-4d`/`-4e`) may *add* cases but must
not edit or delete an expected value here; a case later found wrong changes only
via a paired ``spec.md`` + test edit recorded per the gate.

Scope of this file at `phase-4a`: the Phase 4 pure-service surface only —
``check_availability``, ``add_to_inventory_calc``, ``deduct_calc``, ``_entry``.
The §7 **grocery-generation** rows are authored later by `phase-6a` (they need
``generate_lines``, built in `phase-6b`); the ``CookDeductionRead`` JSON
round-trip is authored by `phase-5a` (it needs ``app.schemas.cook_logs``, built
in `phase-5b`). Adding them here would make `phase-4e`'s "full file green" gate
unreachable, since neither module exists at Phase 4 close.

Until ``phase-4b``/``-4d``/``-4e`` land this file is expected to error on
collection / fail — that is the whole point of a locked oracle.

All numeric field comparisons use ``pytest.approx(expected, rel=1e-9, abs=1e-9)``
per the §2 floating-tolerance rule; conversion results are never compared by
exact binary-float equality.
"""

from __future__ import annotations

import pytest

from app.services.inventory_math import (
    AvailabilityLineDTO,
    DeductProposal,
    InventoryDelta,
    ReqLine,
    RowDeduction,
    StockRow,
    _entry,
    add_to_inventory_calc,
    check_availability,
    deduct_calc,
)
from app.units import Quantity, bucket_of

REL = 1e-9
ABS = 1e-9


def _approx_or_none(v: float | None) -> object:
    return v if v is None else pytest.approx(v, rel=REL, abs=ABS)


# ---------------------------------------------------------------------------
# spec shorthand constructors (§7 tables)
# ---------------------------------------------------------------------------


def R(id: int, item: str, norm: str, amount: float | None, unit: str | None) -> ReqLine:
    """``R(id, item, norm, amount, unit)`` from the §7 availability table."""
    return ReqLine(
        ingredient_id=id,
        item=item,
        normalized_name=norm,
        quantity=amount,
        unit=unit,
    )


def S(id: int, norm: str, bucket: str, base: float) -> StockRow:
    """``S(id, norm, bucket, base)`` from the §7 availability table."""
    return StockRow(id=id, match_name=norm, unit_bucket=bucket, quantity_base=base)


def A(
    ing_id: int,
    item: str,
    norm: str,
    need: float | None,
    unit: str,
    group_need: float | None,
    group_have: float | None,
    group_short: float | None,
    status: str,
    nettable: bool,
) -> AvailabilityLineDTO:
    """One ``AvailabilityLineDTO``.

    Per the §7 shorthand: ``need_unit == group_unit == unit`` (the group's
    canonical unit), and ``group_key = f"{norm}|{bucket_of(unit)}"`` — the
    canonical unit round-trips through ``bucket_of`` back to the group's bucket.
    """
    return AvailabilityLineDTO(
        ingredient_id=ing_id,
        item=item,
        need=need,
        need_unit=unit,
        group_key=f"{norm}|{bucket_of(unit)}",
        group_unit=unit,
        group_need=group_need,
        group_have=group_have,
        group_short=group_short,
        status=status,
        nettable=nettable,
    )


# ---------------------------------------------------------------------------
# comparison helpers (numeric fields via approx, everything else exact)
# ---------------------------------------------------------------------------


def assert_avail_eq(actual: AvailabilityLineDTO, expected: AvailabilityLineDTO) -> None:
    assert isinstance(actual, AvailabilityLineDTO)
    assert actual.ingredient_id == expected.ingredient_id
    assert actual.item == expected.item
    assert actual.need_unit == expected.need_unit
    assert actual.group_key == expected.group_key
    assert actual.group_unit == expected.group_unit
    assert actual.status == expected.status
    assert actual.nettable is expected.nettable
    assert actual.need == _approx_or_none(expected.need)
    assert actual.group_need == _approx_or_none(expected.group_need)
    assert actual.group_have == _approx_or_none(expected.group_have)
    assert actual.group_short == _approx_or_none(expected.group_short)


def assert_avail_list_eq(
    actual: list[AvailabilityLineDTO], expected: list[AvailabilityLineDTO]
) -> None:
    assert [type(x) for x in actual] == [AvailabilityLineDTO] * len(expected)
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert_avail_eq(a, e)


def assert_rows_eq(actual: list[RowDeduction], expected: list[RowDeduction]) -> None:
    assert [type(x) for x in actual] == [RowDeduction] * len(expected)
    assert [x.row_id for x in actual] == [x.row_id for x in expected]
    for a, e in zip(actual, expected):
        assert a.new_quantity_base == _approx_or_none(e.new_quantity_base)


ELEVEN_KEYS = {
    "item",
    "normalized_name",
    "requested",
    "requested_unit",
    "deducted",
    "deducted_unit",
    "inventory_unit",
    "before",
    "after",
    "applied",
    "reason",
}


def entry(
    *,
    item: str,
    normalized_name: str | None,
    requested: float | None,
    requested_unit: str | None,
    deducted: float | None,
    deducted_unit: str | None,
    inventory_unit: str | None,
    before: float | None,
    after: float | None,
    applied: bool,
    reason: str,
) -> dict:
    return {
        "item": item,
        "normalized_name": normalized_name,
        "requested": requested,
        "requested_unit": requested_unit,
        "deducted": deducted,
        "deducted_unit": deducted_unit,
        "inventory_unit": inventory_unit,
        "before": before,
        "after": after,
        "applied": applied,
        "reason": reason,
    }


def L(
    requested: float | None,
    deducted: float | None,
    before: float | None,
    after: float | None,
    applied: bool,
    reason: str,
) -> dict:
    """§7 deduction shorthand: ``item="Tomatoes"``, ``normalized_name="tomato"``,
    canonical ``requested_unit == deducted_unit == inventory_unit == "can"``."""
    return entry(
        item="Tomatoes",
        normalized_name="tomato",
        requested=requested,
        requested_unit="can",
        deducted=deducted,
        deducted_unit="can",
        inventory_unit="can",
        before=before,
        after=after,
        applied=applied,
        reason=reason,
    )


def assert_entry_eq(actual: dict, expected: dict) -> None:
    assert set(actual.keys()) == ELEVEN_KEYS
    for k in (
        "item",
        "normalized_name",
        "requested_unit",
        "deducted_unit",
        "inventory_unit",
        "applied",
        "reason",
    ):
        assert actual[k] == expected[k], k
    for k in ("requested", "deducted", "before", "after"):
        assert actual[k] == _approx_or_none(expected[k]), k


def assert_log_eq(actual: list[dict], expected: list[dict]) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert_entry_eq(a, e)


def all_available_of(lines: list[AvailabilityLineDTO]) -> bool:
    """The router's rule (§4.2 / §7): every line with ``status != "to_taste"``
    has ``status == "ok"``; an empty or all-to-taste report is ``True``."""
    return all(ln.status == "ok" for ln in lines if ln.status != "to_taste")


# ===========================================================================
# §7 — Availability
# ===========================================================================

TOM = dict(id=1, item="Tomatoes", norm="tomato")
_MISSING_REQS = [R(1, "Tomatoes", "tomato", 3, "can")]

AVAILABILITY_CASES = [
    pytest.param(
        [R(1, "Tomatoes", "tomato", 3, "can")],
        [],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 0, 3, "missing", False)],
        False,
        id="missing",
    ),
    pytest.param(
        _MISSING_REQS,
        [S(10, "tomato", "opaque:can", 1)],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 1, 2, "short", True)],
        False,
        id="compatible-short",
    ),
    pytest.param(
        _MISSING_REQS,
        [S(10, "tomato", "opaque:can", 1), S(11, "tomato", "opaque:jar", 1)],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 1, 2, "have_uncertain", False)],
        False,
        id="mixed-bucket-uncertain-short",
    ),
    pytest.param(
        _MISSING_REQS,
        [S(10, "tomato", "opaque:can", 3), S(11, "tomato", "opaque:jar", 1)],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 3, 0, "ok", True)],
        True,
        id="compatible-covers-despite-other-bucket",
    ),
    pytest.param(
        _MISSING_REQS,
        [S(11, "tomato", "opaque:jar", 1)],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 0, 3, "have_uncertain", False)],
        False,
        id="only-incompatible",
    ),
    pytest.param(
        _MISSING_REQS,
        [S(10, "tomato", "opaque:can", 0)],
        [A(1, "Tomatoes", "tomato", 3, "can", 3, 0, 3, "missing", False)],
        False,
        id="zero-stock-is-absent",
    ),
    pytest.param(
        [
            R(1, "Tomatoes", "tomato", 2, "can"),
            R(2, "Canned tomato", "tomato", 1, "can"),
        ],
        [S(10, "tomato", "opaque:can", 2)],
        [
            A(1, "Tomatoes", "tomato", 2, "can", 3, 2, 1, "short", True),
            A(2, "Canned tomato", "tomato", 1, "can", 3, 2, 1, "short", True),
        ],
        False,
        id="duplicate-members-aggregate-once",
    ),
    pytest.param(
        [R(1, "Flour", "flour", 1, "kg")],
        [S(10, "flour", "mass", 500)],
        [A(1, "Flour", "flour", 1000, "g", 1000, 500, 500, "short", True)],
        False,
        id="canonical-mass",
    ),
    pytest.param(
        [R(1, "Salt", "salt", None, "can")],
        [],
        [A(1, "Salt", "salt", None, "can", None, None, None, "to_taste", False)],
        True,
        id="to-taste",
    ),
    # extra required case from the §7 ``test_inventory_math.py`` row:
    # ``clove`` need vs ``bulb`` stock -> ``have_uncertain``.
    pytest.param(
        [R(1, "Garlic", "garlic", 3, "clove")],
        [S(10, "garlic", "opaque:bulb", 1)],
        [A(1, "Garlic", "garlic", 3, "clove", 3, 0, 3, "have_uncertain", False)],
        False,
        id="clove-need-vs-bulb-stock",
    ),
    pytest.param(
        [],
        [],
        [],
        True,
        id="empty-recipe",
    ),
    # §7 Availability prose: "Groups are emitted in first-seen order. Within a
    # group, to-taste lines are emitted first in their stored order, followed by
    # quantified members in stored order, matching §4.2." Locks both orderings
    # against a naive per-requirement (input-order) emitter: R3 (to-taste) is
    # stored last yet emits first within the egg group, and the egg group emits
    # ahead of flour because R1 is the first requirement.
    pytest.param(
        [
            R(1, "Eggs", "egg", 3, None),
            R(2, "Flour", "flour", 100, "g"),
            R(3, "Eggs", "egg", None, None),
        ],
        [],
        [
            A(3, "Eggs", "egg", None, "unit", None, None, None, "to_taste", False),
            A(1, "Eggs", "egg", 3, "unit", 3, 0, 3, "missing", False),
            A(2, "Flour", "flour", 100, "g", 100, 0, 100, "missing", False),
        ],
        False,
        id="group-and-to-taste-emission-order",
    ),
]


@pytest.mark.parametrize("reqs,stock,expected,expected_all", AVAILABILITY_CASES)
def test_check_availability_oracle(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected: list[AvailabilityLineDTO],
    expected_all: bool,
) -> None:
    lines = check_availability(reqs, stock)
    assert_avail_list_eq(lines, expected)
    assert all_available_of(lines) is expected_all


@pytest.mark.parametrize("reqs,stock,expected,expected_all", AVAILABILITY_CASES)
def test_check_availability_group_fields_identical_per_member(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected: list[AvailabilityLineDTO],
    expected_all: bool,
) -> None:
    """Interpretation-independent: every quantified member of a group repeats the
    exact same ``group_*`` / ``status`` / ``nettable`` — stock is never spent
    once per member."""
    lines = check_availability(reqs, stock)
    by_group: dict[str, list[AvailabilityLineDTO]] = {}
    for ln in lines:
        if ln.status != "to_taste":
            by_group.setdefault(ln.group_key, []).append(ln)
    for members in by_group.values():
        first = members[0]
        for m in members:
            assert m.group_need == _approx_or_none(first.group_need)
            assert m.group_have == _approx_or_none(first.group_have)
            assert m.group_short == _approx_or_none(first.group_short)
            assert m.status == first.status
            assert m.nettable is first.nettable


@pytest.mark.parametrize("reqs,stock,expected,expected_all", AVAILABILITY_CASES)
def test_check_availability_per_line_need_sums_to_group_need(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected: list[AvailabilityLineDTO],
    expected_all: bool,
) -> None:
    """§5.3: "A client summing per-line ``need`` recovers ``group_need``." Holds
    across every quantified member of a ``group_key``; to-taste lines (``need``
    is ``None``) are excluded."""
    lines = check_availability(reqs, stock)
    by_group: dict[str, list[AvailabilityLineDTO]] = {}
    for ln in lines:
        if ln.status != "to_taste":
            by_group.setdefault(ln.group_key, []).append(ln)
    for members in by_group.values():
        total = sum(m.need for m in members)
        assert total == _approx_or_none(members[0].group_need)


def test_check_availability_input_reorder_is_stable() -> None:
    """Reordering inventory input does not change availability values."""
    reqs = _MISSING_REQS
    stock = [S(10, "tomato", "opaque:can", 1), S(11, "tomato", "opaque:jar", 1)]
    assert_avail_list_eq(
        check_availability(reqs, list(reversed(stock))),
        check_availability(reqs, stock),
    )


# ===========================================================================
# §7 — Deduction
# ===========================================================================

_DED_REQS = [R(1, "Tomatoes", "tomato", 3, "can")]

DEDUCTION_CASES = [
    pytest.param(
        _DED_REQS,
        [],
        [],
        [L(3, 0, None, None, False, "not in inventory")],
        id="not-in-inventory",
    ),
    pytest.param(
        _DED_REQS,
        [S(11, "tomato", "opaque:jar", 2)],
        [],
        [L(3, 0, None, None, False, "have uncertain (incompatible unit)")],
        id="only-incompatible",
    ),
    pytest.param(
        _DED_REQS,
        [S(10, "tomato", "opaque:can", 5)],
        [RowDeduction(10, 2)],
        [L(3, 3, 5, 2, True, "ok")],
        id="enough-compatible",
    ),
    pytest.param(
        _DED_REQS,
        [S(10, "tomato", "opaque:can", 2)],
        [RowDeduction(10, 0)],
        [L(3, 2, 2, 0, True, "clamped to 0")],
        id="clamp-compatible",
    ),
    pytest.param(
        _DED_REQS,
        [S(10, "tomato", "opaque:can", 1), S(11, "tomato", "opaque:jar", 9)],
        [RowDeduction(10, 0)],
        [L(3, 1, 1, 0, True, "clamped to 0")],
        id="compatible-wins-over-incompatible",
    ),
    pytest.param(
        _DED_REQS,
        [S(20, "tomato", "opaque:can", 2), S(10, "tomato", "opaque:can", 2)],
        [RowDeduction(10, 0), RowDeduction(20, 1)],
        [
            L(3, 2, 2, 0, True, "clamped to 0"),
            L(None, 1, 2, 1, True, "ok"),
        ],
        id="ascending-row-id-draw",
    ),
    # extra required case from the §7 ``test_inventory_math.py`` row:
    # kg-from-g — stock ``2000 g``, recipe ``1 kg`` -> deducted 1000, after 1000, all g.
    pytest.param(
        [R(1, "Flour", "flour", 1, "kg")],
        [S(10, "flour", "mass", 2000)],
        [RowDeduction(10, 1000)],
        [
            entry(
                item="Flour",
                normalized_name="flour",
                requested=1000,
                requested_unit="g",
                deducted=1000,
                deducted_unit="g",
                inventory_unit="g",
                before=2000,
                after=1000,
                applied=True,
                reason="ok",
            )
        ],
        id="kg-from-g",
    ),
    # §7: a to-taste requirement -> no row update, one vacuous "to taste" entry.
    pytest.param(
        [R(1, "Salt", "salt", None, None)],
        [],
        [],
        [
            entry(
                item="Salt",
                normalized_name=None,
                requested=None,
                requested_unit=None,
                deducted=None,
                deducted_unit=None,
                inventory_unit=None,
                before=None,
                after=None,
                applied=False,
                reason="to taste",
            )
        ],
        id="to-taste",
    ),
]


@pytest.mark.parametrize("reqs,stock,expected_rows,expected_log", DEDUCTION_CASES)
def test_deduct_calc_oracle(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected_rows: list[RowDeduction],
    expected_log: list[dict],
) -> None:
    proposal = deduct_calc(reqs, stock)
    assert isinstance(proposal, DeductProposal)
    assert_rows_eq(proposal.row_updates, expected_rows)
    assert_log_eq(proposal.log_entries, expected_log)


@pytest.mark.parametrize("reqs,stock,expected_rows,expected_log", DEDUCTION_CASES)
def test_deduct_calc_entries_have_all_11_keys(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected_rows: list[RowDeduction],
    expected_log: list[dict],
) -> None:
    """Every deduction log entry is a ``dict`` carrying exactly the 11 keys, in
    every branch, with ``None`` where a branch does not populate one (N7). The
    ``CookDeductionRead`` Pydantic round-trip over these same entries is authored
    by `phase-5a` once ``app.schemas.cook_logs`` exists."""
    proposal = deduct_calc(reqs, stock)
    assert proposal.log_entries, "each oracle case emits at least one entry"
    for ent in proposal.log_entries:
        assert isinstance(ent, dict)
        assert set(ent.keys()) == ELEVEN_KEYS


@pytest.mark.parametrize("reqs,stock,expected_rows,expected_log", DEDUCTION_CASES)
def test_deduct_calc_invariants(
    reqs: list[ReqLine],
    stock: list[StockRow],
    expected_rows: list[RowDeduction],
    expected_log: list[dict],
) -> None:
    """§7 interpretation-independent checks for deduction:

    - never a negative ``new_quantity_base``;
    - for every applied entry, ``before - deducted == after`` within tolerance.
    """
    proposal = deduct_calc(reqs, stock)
    for row in proposal.row_updates:
        assert row.new_quantity_base >= 0
    for ent in proposal.log_entries:
        if ent["applied"]:
            assert ent["before"] - ent["deducted"] == pytest.approx(
                ent["after"], rel=REL, abs=ABS
            )


def test_deduct_calc_requested_only_on_first_row_of_group() -> None:
    """``requested`` is set on the first row of a group, ``None`` after."""
    proposal = deduct_calc(
        _DED_REQS,
        [S(20, "tomato", "opaque:can", 2), S(10, "tomato", "opaque:can", 2)],
    )
    requested = [e["requested"] for e in proposal.log_entries]
    assert requested[0] == pytest.approx(3, rel=REL, abs=ABS)
    assert requested[1:] == [None]


def test_deduct_calc_draw_order_is_ascending_row_id_not_input_order() -> None:
    """Deduction order is determined by ascending row id, not input order."""
    forward = deduct_calc(
        _DED_REQS,
        [S(10, "tomato", "opaque:can", 2), S(20, "tomato", "opaque:can", 2)],
    )
    reverse = deduct_calc(
        _DED_REQS,
        [S(20, "tomato", "opaque:can", 2), S(10, "tomato", "opaque:can", 2)],
    )
    assert_rows_eq(forward.row_updates, [RowDeduction(10, 0), RowDeduction(20, 1)])
    assert_rows_eq(reverse.row_updates, forward.row_updates)
    assert_log_eq(reverse.log_entries, forward.log_entries)


# ===========================================================================
# §4.5 / N7 — the ``_entry`` helper contract
# ===========================================================================

_ENTRY_KWARGS = dict(
    item="Tomatoes",
    normalized_name="tomato",
    requested=3.0,
    requested_unit="can",
    deducted=3.0,
    deducted_unit="can",
    inventory_unit="can",
    before=5.0,
    after=2.0,
    applied=True,
    reason="ok",
)


def test_entry_returns_all_11_keys() -> None:
    result = _entry(**_ENTRY_KWARGS)
    assert isinstance(result, dict)
    assert set(result.keys()) == ELEVEN_KEYS


@pytest.mark.parametrize("missing", sorted(ELEVEN_KEYS))
def test_entry_requires_every_kwarg(missing: str) -> None:
    """``_entry`` names all 11 params as required — omitting one is a
    ``TypeError`` at cook time, not a silently missing key (N7)."""
    kwargs = {k: v for k, v in _ENTRY_KWARGS.items() if k != missing}
    with pytest.raises(TypeError):
        _entry(**kwargs)


# ===========================================================================
# §7 — Add-to-inventory proposal
# ===========================================================================

ADD_TO_INVENTORY_CASES = [
    pytest.param(
        (None, "Flour", 1, "kg"),
        InventoryDelta(
            match_name="flour",
            unit_bucket="mass",
            item="Flour",
            normalized_name="flour",
            add_base=1000,
            display_unit="kg",
            canonical_added=Quantity(1000, "g"),
        ),
        id="derive-match-name-known-mass",
    ),
    pytest.param(
        (" Tomatoes ", "Canned Tomatoes", 2, "cans"),
        InventoryDelta(
            match_name="tomato",
            unit_bucket="opaque:can",
            item="Canned Tomatoes",
            normalized_name="canned tomato",
            add_base=2,
            display_unit="cans",
            canonical_added=Quantity(2, "can"),
        ),
        id="canonicalize-match-name-opaque",
    ),
    pytest.param(
        ("flour", "Flour", -2, "g"),
        InventoryDelta(
            match_name="flour",
            unit_bucket="mass",
            item="Flour",
            normalized_name="flour",
            add_base=0,
            display_unit="g",
            canonical_added=Quantity(0, "g"),
        ),
        id="negative-amount-pure-service-clamp",
    ),
]


@pytest.mark.parametrize("inputs,expected", ADD_TO_INVENTORY_CASES)
def test_add_to_inventory_calc_oracle(
    inputs: tuple, expected: InventoryDelta
) -> None:
    match_name, display_item, amount, unit = inputs
    delta = add_to_inventory_calc(match_name, display_item, amount, unit)
    assert isinstance(delta, InventoryDelta)
    assert delta.match_name == expected.match_name
    assert delta.unit_bucket == expected.unit_bucket
    assert delta.item == expected.item
    assert delta.normalized_name == expected.normalized_name
    assert delta.display_unit == expected.display_unit
    assert delta.add_base == pytest.approx(expected.add_base, rel=REL, abs=ABS)
    assert delta.canonical_added.unit == expected.canonical_added.unit
    assert delta.canonical_added.amount == pytest.approx(
        expected.canonical_added.amount, rel=REL, abs=ABS
    )


def test_add_to_inventory_calc_never_negative_add_base() -> None:
    """§7 interpretation-independent: the pure-service clamp floors ``add_base``
    at 0 (HTTP validation rejects the negative input separately)."""
    for amount in (-1000.0, -1e-9, 0.0):
        delta = add_to_inventory_calc("flour", "Flour", amount, "g")
        assert delta.add_base >= 0
        assert delta.canonical_added.amount >= 0
