"""Pure inventory math services (spec.md §4).

Pure: imports only ``units``, ``normalize``, and stdlib. **No ORM, no
``Session``.** Every function takes / returns the frozen dataclasses below —
except ``deduct_calc`` / ``_entry``, whose log entries are plain ``dict``s by
the §4.5 / N7 contract (``DeductProposal.log_entries: list[dict]``). A function
**proposes**; the router **applies** inside the request transaction.

Phase status (``docs/plan.md`` §Independent contract-test gate):

- ``phase-4b`` — the frozen DTOs and ``add_to_inventory_calc`` (§4.4).
- ``phase-4d`` — ``aggregate`` / ``check_availability`` (§4.1 / §4.2).
- ``phase-4e`` — ``deduct_calc`` / ``_entry`` (§4.5).

The §7 oracle cases in ``tests/test_inventory_math.py`` were authored and locked
at ``phase-4a``: add-to-inventory passes from ``phase-4b`` on, availability from
``phase-4d`` on, and deduction from ``phase-4e`` on.
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
# 4.1 aggregate
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GroupAgg:
    """One ``aggregate`` group, keyed by ``(normalized_name, bucket)`` (§4.1)."""

    norm: str
    bucket: str
    need_base: float  # Σ own_need_base over quantified members (canonical unit)
    members: list[tuple[int, float]]  # (ingredient_id, own_need_base), position order
    to_taste_members: list[int]  # ingredient ids with quantity is None, position order
    display_item: str  # first member's item, any kind (decision S4)


def _own_need_base(quantity: float, unit: str | None) -> float:
    """One requirement's need in the group's canonical unit.

    ``to_base`` already handles every known token — including the bare COUNT
    tokens (``None`` / ``unit`` / ``dozen`` / ``pair``). It returns ``None`` only
    for an opaque / unknown unit, where the raw amount *is* the canonical amount
    (spec.md §4.1: "``to_base(qty*M, unit).amount`` (known dims) or ``qty*M``
    (opaque / count)").
    """
    converted = to_base(quantity, unit)
    return quantity if converted is None else converted[0]


def aggregate(reqs: list[ReqLine], M: float = 1.0) -> dict[tuple[str, str], GroupAgg]:
    """Group requirements by ``(normalized_name, bucket_of(unit))`` (spec.md §4.1).

    ``ReqLine.quantity`` already has the recipe multiplier folded in (the router
    builds it that way), so ``M`` defaults to ``1.0``; ``check_availability`` /
    cook call this without it. Groups are returned in first-seen order; within a
    group ``members`` and ``to_taste_members`` keep stored (position) order.
    """
    groups: dict[tuple[str, str], dict] = {}
    for ing in reqs:
        key = (ing.normalized_name, bucket_of(ing.unit))
        slot = groups.get(key)
        if slot is None:
            slot = groups[key] = {
                "members": [],
                "to_taste": [],
                "need_base": 0.0,
                "display_item": ing.item,  # first writer wins (decision S4)
            }
        if ing.quantity is None:
            slot["to_taste"].append(ing.ingredient_id)
            continue
        own = _own_need_base(ing.quantity * M, ing.unit)
        slot["members"].append((ing.ingredient_id, own))
        slot["need_base"] += own
    return {
        key: GroupAgg(
            norm=key[0],
            bucket=key[1],
            need_base=slot["need_base"],
            members=slot["members"],
            to_taste_members=slot["to_taste"],
            display_item=slot["display_item"],
        )
        for key, slot in groups.items()
    }


# --------------------------------------------------------------------------- #
# 4.2 check_availability
# --------------------------------------------------------------------------- #


def check_availability(
    reqs: list[ReqLine], stock: list[StockRow]
) -> list[AvailabilityLineDTO]:
    """Per-ingredient availability against current stock (spec.md §4.2).

    One line per requirement. To-taste members of a group emit first (vacuous
    line, decision SD1), then the quantified members repeat the group's ``group_*``
    / ``status`` / ``nettable`` verbatim — stock is aggregated once per group,
    never spent per member.
    """
    items = {r.ingredient_id: r.item for r in reqs}
    out: list[AvailabilityLineDTO] = []
    for g in aggregate(reqs).values():
        canon = canon_unit(g.bucket)
        group_key = f"{g.norm}|{g.bucket}"

        for ing_id in g.to_taste_members:
            out.append(
                AvailabilityLineDTO(
                    ingredient_id=ing_id,
                    item=items[ing_id],
                    need=None,
                    need_unit=canon,
                    group_key=group_key,
                    group_unit=canon,
                    group_need=None,
                    group_have=None,
                    group_short=None,
                    status="to_taste",
                    nettable=False,
                )
            )

        if not g.members:  # group had only to-taste rows
            continue

        pos = [r for r in stock if r.match_name == g.norm and r.quantity_base > 0]
        compat = [r for r in pos if r.unit_bucket == g.bucket]
        incomp = [r for r in pos if r.unit_bucket != g.bucket]

        if compat:
            have = sum(r.quantity_base for r in compat)  # already canonical
            short = g.need_base - have
            if short <= 0:
                gstatus, nettable, ghave, gshort = "ok", True, have, 0.0
            elif incomp:
                gstatus, nettable, ghave, gshort = "have_uncertain", False, have, short
            else:
                gstatus, nettable, ghave, gshort = "short", True, have, short
        elif incomp:
            gstatus, nettable, ghave, gshort = "have_uncertain", False, 0.0, g.need_base
        else:
            gstatus, nettable, ghave, gshort = "missing", False, 0.0, g.need_base

        for ing_id, own_need_base in g.members:
            out.append(
                AvailabilityLineDTO(
                    ingredient_id=ing_id,
                    item=items[ing_id],
                    need=own_need_base,
                    need_unit=canon,
                    group_key=group_key,
                    group_unit=canon,
                    group_need=g.need_base,
                    group_have=ghave,
                    group_short=gshort,
                    status=gstatus,
                    nettable=nettable,
                )
            )
    return out


# --------------------------------------------------------------------------- #
# 4.5 deduct_calc
# --------------------------------------------------------------------------- #


def deduct_calc(reqs: list[ReqLine], stock: list[StockRow]) -> DeductProposal:
    """Propose the inventory draw-down for ``POST /api/recipes/{id}/cook`` (spec.md §4.5).

    Pure: builds a working copy ``live`` of every stock row's ``quantity_base``
    and never mutates ``stock``. Per ``(normalized_name, bucket)`` group it draws
    the compatible bucket down in **ascending row-id order** (decision SD2),
    clamping each row at zero and logging ``"clamped to 0"`` for any unmet
    remainder — even when incompatible-bucket stock exists (cook does **not**
    take the #N3 uncertainty split). To-taste members emit one vacuous entry and
    no row update.

    ``requested`` is carried only on the first log entry of a group; ``None`` on
    the rest. Every entry is a plain ``dict`` with all eleven keys (``_entry``).
    """
    items = {r.ingredient_id: r.item for r in reqs}
    live = {r.id: r.quantity_base for r in stock}
    row_updates: list[RowDeduction] = []
    log: list[dict] = []

    for g in aggregate(reqs).values():
        canon = canon_unit(g.bucket)

        for ing_id in g.to_taste_members:
            log.append(
                _entry(
                    item=items[ing_id],
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
            )

        if not g.members:  # group had only to-taste rows
            continue

        pos = [r for r in stock if r.match_name == g.norm and live[r.id] > 0]
        compat = sorted(
            (r for r in pos if r.unit_bucket == g.bucket), key=lambda r: r.id
        )

        if not pos:
            log.append(
                _entry(
                    item=g.display_item,
                    normalized_name=g.norm,
                    requested=g.need_base,
                    requested_unit=canon,
                    deducted=0.0,
                    deducted_unit=canon,
                    inventory_unit=canon,
                    before=None,
                    after=None,
                    applied=False,
                    reason="not in inventory",
                )
            )
            continue
        if not compat:
            log.append(
                _entry(
                    item=g.display_item,
                    normalized_name=g.norm,
                    requested=g.need_base,
                    requested_unit=canon,
                    deducted=0.0,
                    deducted_unit=canon,
                    inventory_unit=canon,
                    before=None,
                    after=None,
                    applied=False,
                    reason="have uncertain (incompatible unit)",
                )
            )
            continue

        remaining = g.need_base
        for i, r in enumerate(compat):
            before = live[r.id]
            take = min(remaining, before)
            live[r.id] = before - take
            remaining -= take
            row_updates.append(RowDeduction(r.id, live[r.id]))
            log.append(
                _entry(
                    item=g.display_item,
                    normalized_name=g.norm,
                    requested=(g.need_base if i == 0 else None),
                    requested_unit=canon,
                    deducted=take,
                    deducted_unit=canon,
                    inventory_unit=canon,
                    before=before,
                    after=live[r.id],
                    applied=True,
                    reason=("ok" if remaining <= 0 else "clamped to 0"),
                )
            )
            if remaining <= 0:
                break

    return DeductProposal(row_updates=row_updates, log_entries=log)


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
    """One ``CookLog.deductions`` entry as a plain ``dict`` (spec.md §4.5 / N7).

    Signature names all eleven keys as required keyword args (no defaults) — a
    missing one is a ``TypeError`` at cook time, not a silently absent key. The
    returned dict always carries all eleven keys, ``None`` where the branch does
    not populate one; the read path validates each through ``CookDeductionRead``
    (§5.4).
    """
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
