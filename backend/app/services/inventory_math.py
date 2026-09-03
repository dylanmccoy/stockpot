"""Pure inventory math services (spec.md §4).

Pure: imports only ``units``, ``normalize``, and stdlib. **No ORM, no
``Session``.** Every function takes / returns the frozen dataclasses below. A
function **proposes**; the router **applies** inside the request transaction.

Phase status (``docs/plan.md`` §Independent contract-test gate):

- ``phase-4b`` — the frozen DTOs and ``add_to_inventory_calc`` (§4.4).
- ``phase-4d`` — ``aggregate`` / ``check_availability`` (§4.1 / §4.2).
- ``phase-4e`` — ``deduct_calc`` / ``_entry`` (§4.5).

The §7 availability and deduction oracle cases in ``tests/test_inventory_math.py``
were authored and locked at ``phase-4a`` and stay red until ``phase-4d`` /
``phase-4e`` land; the add-to-inventory oracle cases pass from ``phase-4b`` on.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.normalize import normalize_name
from app.units import Quantity, bucket_of, canon_unit, normalize_unit_token, to_base

# --------------------------------------------------------------------------- #
# Frozen DTOs (spec.md §4). Every service takes / returns these.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReqLine:
    """One recipe ingredient, multiplier already applied."""

    ingredient_id: int
    item: str
    normalized_name: str
    quantity: float | None  # * M already; None = to taste
    unit: str | None


@dataclass(frozen=True)
class StockRow:
    """One ``inventory_items`` row, ORM-free."""

    id: int
    match_name: str
    unit_bucket: str
    quantity_base: float


@dataclass(frozen=True)
class AvailabilityLineDTO:
    ingredient_id: int
    item: str
    need: float | None
    need_unit: str
    group_key: str
    group_unit: str
    group_need: float | None
    group_have: float | None
    group_short: float | None
    status: str  # ok | short | missing | to_taste | have_uncertain
    nettable: bool


@dataclass(frozen=True)
class InventoryDelta:
    """Proposal for the additive upsert (spec.md §4.4 / §5.5)."""

    match_name: str
    unit_bucket: str
    item: str
    normalized_name: str
    add_base: float  # >= 0, canonical
    display_unit: str | None
    canonical_added: Quantity  # (add_base, canon_unit(bucket))


@dataclass(frozen=True)
class RowDeduction:
    row_id: int
    new_quantity_base: float


@dataclass(frozen=True)
class DeductProposal:
    row_updates: list[RowDeduction]  # inventory rows to write
    log_entries: list[dict]  # the full CookLog.deductions list (all branches)


# --------------------------------------------------------------------------- #
# 4.4 add_to_inventory_calc
# --------------------------------------------------------------------------- #


def add_to_inventory_calc(
    match_name: str | None,
    display_item: str,
    amount: float,
    unit: str | None,
) -> InventoryDelta:
    """Propose the additive upsert for ``POST /api/inventory`` (spec.md §4.4).

    The canonical key is the normalized supplied ``match_name`` or, when it was
    not supplied, the normalized display item. A supplied value is always
    normalized — including an explicit ``""`` — so it can round-trip through the
    router's ``not delta.match_name`` -> 422 check (spec.md §1: "every value
    (default or supplied) is ``normalize_name``ed before store"; decision N5).
    ``amount`` is floored at 0 here; HTTP validation rejects a negative input
    separately.
    """
    # One normalized token, used everywhere. Note `bucket_of` maps a `None` *or*
    # empty token to the COUNT bucket, but `to_base` on a raw whitespace / "."
    # unit returns `None` — so a normalized-empty token is treated as no-unit
    # here to keep the two in step (spec.md §5.5: "None => COUNT bucket").
    tok = normalize_unit_token(unit)
    bucket = bucket_of(tok)
    canon = canon_unit(bucket)
    a = max(amount, 0.0)
    if bucket.startswith("opaque:") or not tok:
        add_base = a
    else:
        add_base = to_base(a, tok)[0]
    normalized_item = normalize_name(display_item)
    return InventoryDelta(
        match_name=(
            normalize_name(match_name) if match_name is not None else normalized_item
        ),
        unit_bucket=bucket,
        item=display_item,
        normalized_name=normalized_item,
        add_base=add_base,
        display_unit=unit,  # opaque token or known unit or None, as supplied
        canonical_added=Quantity(add_base, canon),
    )


# --------------------------------------------------------------------------- #
# 4.2 / 4.5 — not owned by phase-4b.
#
# Forward declarations so ``tests/test_inventory_math.py`` (the phase-4a locked
# oracle, which imports the whole §4 surface) collects and its add-to-inventory
# cases run. The bodies — and ``aggregate`` (§4.1) — land in phase-4d / phase-4e;
# the availability / deduction oracle cases stay red until then.
# --------------------------------------------------------------------------- #

_PHASE_4D = "aggregate / check_availability land in phase-4d (spec.md §4.1 / §4.2)"
_PHASE_4E = "deduct_calc / _entry land in phase-4e (spec.md §4.5)"


def check_availability(
    reqs: list[ReqLine], stock: list[StockRow]
) -> list[AvailabilityLineDTO]:
    raise NotImplementedError(_PHASE_4D)


def deduct_calc(reqs: list[ReqLine], stock: list[StockRow]) -> DeductProposal:
    raise NotImplementedError(_PHASE_4E)


def _entry(
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
    # Signature is the locked §4.5 / N7 contract (all eleven keys required, no
    # defaults); the body lands in phase-4e.
    raise NotImplementedError(_PHASE_4E)
