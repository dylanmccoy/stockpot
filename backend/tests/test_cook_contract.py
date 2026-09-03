"""Locked R-7 contract oracle for Phase 5 — cook, the deduction audit log, and
the cook race (``spec.md`` §4.5 / §5.4 / §6 / §7).

Authored black-box from the normative spec in a fresh context **before** the
Phase 5 production surface exists (``docs/plan.md`` §Independent contract-test
gate). At the time of writing there is:

* no ``POST /api/recipes/{id}/cook`` / ``GET /api/recipes/{id}/cook-logs`` route,
* no ``CookLog`` model / ``cook_logs`` table,
* no ``app.schemas.cook_logs`` module.

So this file **fails on collection** (the ``app.schemas.cook_logs`` import below)
until ``phase-5b`` lands — that failure *is* the lock. ``phase-5b`` may add
cases but must not edit or delete an expected value here; a case later found
wrong is changed only via a paired ``spec.md`` + test edit recorded per the gate.

Scope — the slice ``phase-4a`` explicitly deferred to ``phase-5a``:

* ``CookDeductionRead`` — the JSON shape of every ``deductions[]`` entry: all 11
  keys, ``extra="forbid"``, the 5-value ``reason`` ``Literal``, and ``null`` only
  where the §5.4 per-branch table permits it.
* ``POST /cook`` with ``deduct=true`` — every §7 *Deduction* outcome that is
  constructible over HTTP, the to-taste entry, ``multiplier`` scaling, the
  ``deduct=false`` log-only mode, ``404``, defaults, the ``CookLogRead`` body
  shape, and newest-first history.
* N7 — a stored entry with a stray key or an unlisted ``reason`` is a loud
  ``500`` on read, never a silent shape change.
* The cook race (§6) — a file-backed two-``cook`` interleave does not lose an
  update; ``BEGIN IMMEDIATE`` serializes the writers; a lock that outlasts
  ``busy_timeout`` surfaces as ``409 {"detail": "conflict"}``, never ``500``.

The §7 ascending-row-ID draw row is *not* reconstructed over HTTP: the
``(match_name, unit_bucket)`` uniqueness constraint makes two compatible stock
rows for one food unbuildable through the API. It stays locked as a pure-service
case in ``test_inventory_math.py``.

Numeric comparisons use ``pytest.approx`` per the §2 floating-tolerance rule.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import make_engine
from app.main import create_app

# Missing until ``phase-5b`` builds ``schemas/cook_logs.py`` — collection fails
# here, and that is the locked oracle.
from app.schemas.cook_logs import CookDeductionRead
from app.services.inventory_math import ReqLine, StockRow, deduct_calc

REL = 1e-9
ABS = 1e-9

# §5.4 — the exact five values of the ``reason`` ``Literal``.
ALLOWED_REASONS = (
    "ok",
    "clamped to 0",
    "to taste",
    "not in inventory",
    "have uncertain (incompatible unit)",
)

# §4.5 — ``_entry(...)`` carries all eleven keys on every branch.
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

# §5.4 — ``CookLogRead`` is exactly these keys.
COOK_LOG_READ_KEYS = {
    "id",
    "recipe_id",
    "recipe_title",
    "multiplier",
    "deducted",
    "cooked_at",
    "cooked_by",
    "deductions",
}


# --- §7 shorthand, mirroring ``test_inventory_math.py``'s ``R()`` / ``S()`` ---


def R(  # noqa: N802 - matches the sibling oracle's constructor name
    ingredient_id: int,
    item: str,
    norm: str,
    amount: float | None,
    unit: str | None,
) -> ReqLine:
    return ReqLine(
        ingredient_id=ingredient_id,
        item=item,
        normalized_name=norm,
        quantity=amount,
        unit=unit,
    )


def S(  # noqa: N802 - matches the sibling oracle's constructor name
    row_id: int, norm: str, bucket: str, base: float
) -> StockRow:
    return StockRow(id=row_id, match_name=norm, unit_bucket=bucket, quantity_base=base)


def _ok_entry(**overrides: object) -> dict:
    """A canonical ``reason="ok"`` deduction entry (all 11 keys populated), for
    mutation in the ``CookDeductionRead`` schema tests."""
    base = {
        "item": "Tomatoes",
        "normalized_name": "tomato",
        "requested": 3.0,
        "requested_unit": "can",
        "deducted": 3.0,
        "deducted_unit": "can",
        "inventory_unit": "can",
        "before": 5.0,
        "after": 2.0,
        "applied": True,
        "reason": "ok",
    }
    base.update(overrides)
    return base


# ===========================================================================
# A. ``CookDeductionRead`` — JSON shape of one ``deductions[]`` entry (§5.4)
# ===========================================================================


def test_cookdeductionread_accepts_a_canonical_ok_entry() -> None:
    model = CookDeductionRead.model_validate(_ok_entry())
    assert model.reason == "ok"
    assert model.applied is True
    assert set(model.model_dump().keys()) == ELEVEN_KEYS


@pytest.mark.parametrize("reason", ALLOWED_REASONS)
def test_cookdeductionread_allows_each_of_the_five_reasons(reason: str) -> None:
    """A payload legal for whichever branch the ``reason`` names (§5.4 table)."""
    if reason == "ok":
        payload = _ok_entry()
    elif reason == "clamped to 0":
        payload = _ok_entry(reason=reason, deducted=2.0, before=2.0, after=0.0)
    elif reason == "to taste":
        payload = _ok_entry(
            normalized_name=None,
            requested=None,
            requested_unit=None,
            deducted=None,
            deducted_unit=None,
            inventory_unit=None,
            before=None,
            after=None,
            applied=False,
            reason=reason,
        )
    else:  # "not in inventory" / "have uncertain (incompatible unit)"
        payload = _ok_entry(
            deducted=0.0, before=None, after=None, applied=False, reason=reason
        )
    assert CookDeductionRead.model_validate(payload).reason == reason


@pytest.mark.parametrize(
    "bad_reason",
    [
        "missing",  # an availability status, not a deduction reason
        "have uncertain",  # truncated
        "have uncertain (incompatible unit) ",  # trailing space
        "HAVE UNCERTAIN (INCOMPATIBLE UNIT)",  # wrong case
        "to_taste",  # underscore form
        "clamped",  # truncated
        "",
    ],
)
def test_cookdeductionread_rejects_an_unlisted_reason(bad_reason: str) -> None:
    with pytest.raises(ValidationError):
        CookDeductionRead.model_validate(_ok_entry(reason=bad_reason))


def test_cookdeductionread_forbids_an_extra_key() -> None:
    with pytest.raises(ValidationError):
        CookDeductionRead.model_validate({**_ok_entry(), "surprise": 1})


def test_cookdeductionread_forbids_a_renamed_key() -> None:
    """A drifted writer that renamed ``deducted`` -> ``deduped`` is a loud
    failure, not a silently-dropped field."""
    payload = _ok_entry()
    payload["deduped"] = payload.pop("deducted")
    with pytest.raises(ValidationError):
        CookDeductionRead.model_validate(payload)


@pytest.mark.parametrize("field", ["item", "applied", "reason"])
def test_cookdeductionread_rejects_null_in_a_never_null_field(field: str) -> None:
    """§5.4: ``item``, ``applied``, ``reason`` are set in every branch."""
    with pytest.raises(ValidationError):
        CookDeductionRead.model_validate(_ok_entry(**{field: None}))


@pytest.mark.parametrize(
    "field",
    [
        "normalized_name",
        "requested",
        "requested_unit",
        "deducted",
        "deducted_unit",
        "inventory_unit",
        "before",
        "after",
    ],
)
def test_cookdeductionread_permits_null_in_every_nullable_field(field: str) -> None:
    """The §5.4 "to taste" row nulls all eight of these at once, so each is
    individually nullable in the model."""
    payload = _ok_entry(**{field: None, "applied": False})
    assert getattr(CookDeductionRead.model_validate(payload), field) is None


# --- every real ``deduct_calc`` entry round-trips through the read model -----

_TOMATO_3_CAN_REQ = [R(1, "Tomatoes", "tomato", 3, "can")]
_SALT_TO_TASTE_REQ = [R(1, "Salt", "salt", None, None)]

_ROUNDTRIP_CASES = [
    pytest.param(_TOMATO_3_CAN_REQ, [S(10, "tomato", "opaque:can", 5)], "ok", id="ok"),
    pytest.param(
        _TOMATO_3_CAN_REQ, [S(10, "tomato", "opaque:can", 2)], "clamped to 0",
        id="clamped-to-0",
    ),
    pytest.param(_TOMATO_3_CAN_REQ, [], "not in inventory", id="not-in-inventory"),
    pytest.param(
        _TOMATO_3_CAN_REQ, [S(11, "tomato", "opaque:jar", 2)],
        "have uncertain (incompatible unit)", id="incompatible",
    ),
    pytest.param(_SALT_TO_TASTE_REQ, [], "to taste", id="to-taste"),
]


@pytest.mark.parametrize("reqs,stock,reason", _ROUNDTRIP_CASES)
def test_every_deduct_calc_entry_round_trips_through_cookdeductionread(
    reqs: list[ReqLine], stock: list[StockRow], reason: str
) -> None:
    proposal = deduct_calc(reqs, stock)
    assert proposal.log_entries, "each branch emits at least one entry"
    for entry in proposal.log_entries:
        assert set(entry.keys()) == ELEVEN_KEYS
        dumped = CookDeductionRead.model_validate(entry).model_dump()
        assert set(dumped.keys()) == ELEVEN_KEYS
        for key, value in entry.items():
            if isinstance(value, float):
                assert dumped[key] == pytest.approx(value, rel=REL, abs=ABS), key
            else:
                assert dumped[key] == value, key
    assert any(e["reason"] == reason for e in proposal.log_entries)


def test_to_taste_entry_nulls_exactly_the_fields_the_54_table_permits() -> None:
    (entry,) = deduct_calc(_SALT_TO_TASTE_REQ, []).log_entries
    CookDeductionRead.model_validate(entry)
    assert entry["item"] == "Salt"
    assert entry["applied"] is False
    assert entry["reason"] == "to taste"
    for key in (
        "normalized_name",
        "requested",
        "requested_unit",
        "deducted",
        "deducted_unit",
        "inventory_unit",
        "before",
        "after",
    ):
        assert entry[key] is None, key


@pytest.mark.parametrize(
    "stock,reason",
    [
        ([], "not in inventory"),
        ([S(11, "tomato", "opaque:jar", 2)], "have uncertain (incompatible unit)"),
    ],
)
def test_absent_and_incompatible_entries_null_only_before_and_after(
    stock: list[StockRow], reason: str
) -> None:
    (entry,) = deduct_calc(_TOMATO_3_CAN_REQ, stock).log_entries
    CookDeductionRead.model_validate(entry)
    assert entry["reason"] == reason
    assert entry["applied"] is False
    assert entry["before"] is None and entry["after"] is None
    # everything else is populated, canonical (§5.4 table)
    assert entry["normalized_name"] == "tomato"
    assert entry["requested"] == pytest.approx(3.0, rel=REL, abs=ABS)
    assert entry["requested_unit"] == "can"
    assert entry["deducted"] == pytest.approx(0.0, rel=REL, abs=ABS)
    assert entry["deducted_unit"] == "can"
    assert entry["inventory_unit"] == "can"


def test_applied_entry_populates_all_11_fields_and_holds_the_before_after_invariant() -> None:
    (entry,) = deduct_calc(_TOMATO_3_CAN_REQ, [S(10, "tomato", "opaque:can", 5)]).log_entries
    CookDeductionRead.model_validate(entry)
    assert entry["applied"] is True
    assert entry["reason"] == "ok"
    for key in ELEVEN_KEYS:
        assert entry[key] is not None, key
    assert entry["before"] - entry["deducted"] == pytest.approx(
        entry["after"], rel=REL, abs=ABS
    )
    assert entry["requested_unit"] == entry["deducted_unit"] == entry["inventory_unit"]


# ===========================================================================
# HTTP helpers + fixtures (§5.2 / §5.5 / §5.4)
# ===========================================================================

_PASSWORD = "correct horse battery"  # 8..128 chars
_REG_CODE = "cc"

TOMATO_3_CAN = {"item": "Tomatoes", "quantity": 3, "unit": "can"}
SALT_TO_TASTE = {"item": "Salt"}


def _register(client: TestClient, *, username: str = "cook", code: str = _REG_CODE) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": _PASSWORD, "code": code},
    )
    assert reg.status_code == 201, reg.text
    client.headers["Authorization"] = f"Bearer {reg.json()['token']}"


def _build_app(*, registration_code: str = _REG_CODE, database_url: str = "sqlite://") -> tuple[FastAPI, Engine]:
    settings = Settings(
        database_url=database_url,
        allow_registration=True,
        registration_code=registration_code,
    )
    engine = make_engine(database_url)
    return create_app(settings, engine), engine


def _mk_recipe(client: TestClient, ingredients: list[dict]) -> int:
    resp = client.post(
        "/api/recipes", json={"title": "Cook Contract", "ingredients": ingredients}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_inventory(client: TestClient, item: str, quantity: float, unit: str) -> dict:
    resp = client.post(
        "/api/inventory", json={"item": item, "quantity": quantity, "unit": unit}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _inventory_row(client: TestClient, match_name: str, unit_bucket: str) -> dict | None:
    for row in client.get("/api/inventory").json():
        if row["match_name"] == match_name and row["unit_bucket"] == unit_bucket:
            return row
    return None


def _assert_base(
    client: TestClient, match_name: str, unit_bucket: str, expected: float
) -> None:
    row = _inventory_row(client, match_name, unit_bucket)
    assert row is not None, f"no {match_name!r}/{unit_bucket!r} inventory row"
    assert row["quantity_base"] == pytest.approx(expected, rel=REL, abs=ABS)


def _assert_entry(
    actual: dict,
    *,
    item: str | None,
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
) -> None:
    assert set(actual.keys()) == ELEVEN_KEYS
    assert actual["reason"] in ALLOWED_REASONS
    assert actual["item"] == item
    assert actual["normalized_name"] == normalized_name
    assert actual["requested_unit"] == requested_unit
    assert actual["deducted_unit"] == deducted_unit
    assert actual["inventory_unit"] == inventory_unit
    assert actual["applied"] is applied
    assert actual["reason"] == reason
    for key, expected in (
        ("requested", requested),
        ("deducted", deducted),
        ("before", before),
        ("after", after),
    ):
        if expected is None:
            assert actual[key] is None, key
        else:
            assert actual[key] == pytest.approx(expected, rel=REL, abs=ABS), key
    # every entry the API hands back must satisfy its own read schema
    CookDeductionRead.model_validate(actual)


@pytest.fixture
def cook_client() -> Iterator[TestClient]:
    """An authed client over a fresh in-memory app. ``raise_server_exceptions``
    stays at its default (``True``) so a stray ``500`` on a happy path raises
    loudly rather than passing a status-code assertion (``conftest.auth_client``
    convention)."""
    app, engine = _build_app()
    with TestClient(app) as client:
        _register(client)
        yield client
    engine.dispose()


@pytest.fixture
def cook_env() -> Iterator[tuple[TestClient, Engine]]:
    """Authed client + its engine, with ``raise_server_exceptions=False`` so the
    N7 read-path failure surfaces as a ``500`` *response* rather than a re-raised
    exception. Used only by the N7 tests."""
    app, engine = _build_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        _register(client)
        yield client, engine
    engine.dispose()


# ===========================================================================
# B. ``POST /cook`` with ``deduct=true`` — every §7 Deduction outcome over HTTP
# ===========================================================================


def test_cook_not_in_inventory_logs_and_touches_nothing(cook_client: TestClient) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])

    resp = cook_client.post(
        f"/api/recipes/{rid}/cook", json={"multiplier": 1, "deduct": True}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["deducted"] is True
    assert body["multiplier"] == pytest.approx(1.0)

    (entry,) = body["deductions"]
    _assert_entry(
        entry,
        item="Tomatoes",
        normalized_name="tomato",
        requested=3.0,
        requested_unit="can",
        deducted=0.0,
        deducted_unit="can",
        inventory_unit="can",
        before=None,
        after=None,
        applied=False,
        reason="not in inventory",
    )
    assert cook_client.get("/api/inventory").json() == []


def test_cook_only_incompatible_bucket_is_uncertain_and_untouched(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 2, "jar")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    assert resp.status_code == 201, resp.text

    (entry,) = resp.json()["deductions"]
    _assert_entry(
        entry,
        item="Tomatoes",
        normalized_name="tomato",
        requested=3.0,
        requested_unit="can",
        deducted=0.0,
        deducted_unit="can",
        inventory_unit="can",
        before=None,
        after=None,
        applied=False,
        reason="have uncertain (incompatible unit)",
    )
    _assert_base(cook_client, "tomato", "opaque:jar", 2.0)


def test_cook_enough_compatible_deducts_and_reports_ok(cook_client: TestClient) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 5, "can")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    assert resp.status_code == 201, resp.text

    (entry,) = resp.json()["deductions"]
    _assert_entry(
        entry,
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
    _assert_base(cook_client, "tomato", "opaque:can", 2.0)


def test_cook_clamps_to_zero_when_compatible_stock_is_short(cook_client: TestClient) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 2, "can")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    assert resp.status_code == 201, resp.text

    (entry,) = resp.json()["deductions"]
    # §7: L(3, 2, 2, 0, true, "clamped to 0") — `requested` is the full need,
    # `deducted` is only what the row could cover.
    _assert_entry(
        entry,
        item="Tomatoes",
        normalized_name="tomato",
        requested=3.0,
        requested_unit="can",
        deducted=2.0,
        deducted_unit="can",
        inventory_unit="can",
        before=2.0,
        after=0.0,
        applied=True,
        reason="clamped to 0",
    )
    _assert_base(cook_client, "tomato", "opaque:can", 0.0)


def test_cook_compatible_bucket_wins_over_incompatible_then_clamps(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 1, "can")
    _add_inventory(cook_client, "Tomatoes", 9, "jar")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    assert resp.status_code == 201, resp.text

    (entry,) = resp.json()["deductions"]
    # §7: cook never silently spends a `jar` for a `can` — it draws the one
    # compatible unit and clamps the remainder.
    _assert_entry(
        entry,
        item="Tomatoes",
        normalized_name="tomato",
        requested=3.0,
        requested_unit="can",
        deducted=1.0,
        deducted_unit="can",
        inventory_unit="can",
        before=1.0,
        after=0.0,
        applied=True,
        reason="clamped to 0",
    )
    _assert_base(cook_client, "tomato", "opaque:can", 0.0)
    _assert_base(cook_client, "tomato", "opaque:jar", 9.0)


def test_cook_to_taste_line_yields_a_vacuous_entry_and_is_never_applied(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [SALT_TO_TASTE])

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    assert resp.status_code == 201, resp.text

    (entry,) = resp.json()["deductions"]
    _assert_entry(
        entry,
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


def test_cook_multiplier_scales_quantified_need_and_leaves_to_taste_null(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN, SALT_TO_TASTE])
    _add_inventory(cook_client, "Tomatoes", 10, "can")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 2})
    # R-1: the to-taste line must not hit `None * multiplier`.
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["multiplier"] == pytest.approx(2.0)

    tomato, salt = body["deductions"]  # first-seen group order: tomato, then salt
    _assert_entry(
        tomato,
        item="Tomatoes",
        normalized_name="tomato",
        requested=6.0,
        requested_unit="can",
        deducted=6.0,
        deducted_unit="can",
        inventory_unit="can",
        before=10.0,
        after=4.0,
        applied=True,
        reason="ok",
    )
    _assert_entry(
        salt,
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
    _assert_base(cook_client, "tomato", "opaque:can", 4.0)


def test_cook_deduct_false_writes_a_log_but_touches_no_stock(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 5, "can")

    resp = cook_client.post(
        f"/api/recipes/{rid}/cook", json={"multiplier": 1, "deduct": False}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["deducted"] is False
    assert body["deductions"] == []
    _assert_base(cook_client, "tomato", "opaque:can", 5.0)

    logs = cook_client.get(f"/api/recipes/{rid}/cook-logs")
    assert logs.status_code == 200
    assert len(logs.json()) == 1
    assert logs.json()[0]["deducted"] is False
    assert logs.json()[0]["deductions"] == []


def test_cook_defaults_multiplier_1_and_deduct_true(cook_client: TestClient) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 5, "can")

    resp = cook_client.post(f"/api/recipes/{rid}/cook", json={})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["multiplier"] == pytest.approx(1.0)
    assert body["deducted"] is True
    _assert_base(cook_client, "tomato", "opaque:can", 2.0)


def test_cook_201_body_is_the_full_cooklogread_shape(cook_client: TestClient) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 5, "can")

    body = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1}).json()
    assert set(body) == COOK_LOG_READ_KEYS
    assert isinstance(body["id"], int)
    assert body["recipe_id"] == rid
    assert body["recipe_title"] == "Cook Contract"
    assert body["multiplier"] == pytest.approx(1.0)
    assert body["deducted"] is True
    assert body["cooked_at"].endswith("+00:00") or body["cooked_at"].endswith("Z")
    # §5.4: cooked_by is a UserMini
    assert set(body["cooked_by"]) == {"id", "username"}
    assert body["cooked_by"]["username"] == "cook"
    assert isinstance(body["deductions"], list)


def test_cook_unknown_recipe_is_404(cook_client: TestClient) -> None:
    resp = cook_client.post("/api/recipes/999999/cook", json={"multiplier": 1})
    assert resp.status_code == 404


def test_cook_logs_unknown_recipe_is_404(cook_client: TestClient) -> None:
    assert cook_client.get("/api/recipes/999999/cook-logs").status_code == 404


def test_cook_logs_return_newest_first_with_the_full_read_shape(
    cook_client: TestClient,
) -> None:
    rid = _mk_recipe(cook_client, [TOMATO_3_CAN])
    _add_inventory(cook_client, "Tomatoes", 10, "can")

    first = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})
    second = cook_client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 2})
    assert first.status_code == 201 and second.status_code == 201

    logs = cook_client.get(f"/api/recipes/{rid}/cook-logs")
    assert logs.status_code == 200
    rows = logs.json()
    assert len(rows) == 2
    # order_by(cooked_at DESC, id DESC)
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    assert [r["multiplier"] for r in rows] == pytest.approx([2.0, 1.0])

    newest = rows[0]
    assert set(newest) == COOK_LOG_READ_KEYS
    assert newest["recipe_id"] == rid
    assert newest["recipe_title"] == "Cook Contract"
    # §7: every datetime read carries an explicit UTC designator
    assert newest["cooked_at"].endswith("+00:00") or newest["cooked_at"].endswith("Z")
    assert set(newest["cooked_by"]) == {"id", "username"}
    assert newest["cooked_by"]["username"] == "cook"
    for entry in newest["deductions"]:
        CookDeductionRead.model_validate(entry)


# ===========================================================================
# C. N7 — a drifted stored entry is a loud 500 on read (§5.4)
# ===========================================================================


def _tamper_first_stored_deduction(
    engine: Engine, mutate: Callable[[dict], None]
) -> None:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, deductions FROM cook_logs ORDER BY id LIMIT 1")
        ).one()
        raw = row.deductions
        entries = json.loads(raw) if isinstance(raw, str) else list(raw)
        mutate(entries[0])
        conn.execute(
            text("UPDATE cook_logs SET deductions = :d WHERE id = :i"),
            {"d": json.dumps(entries), "i": row.id},
        )


def test_stored_entry_with_an_unknown_key_is_500_on_read(
    cook_env: tuple[TestClient, Engine],
) -> None:
    client, engine = cook_env
    rid = _mk_recipe(client, [TOMATO_3_CAN])
    _add_inventory(client, "Tomatoes", 5, "can")
    assert client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1}).status_code == 201
    assert client.get(f"/api/recipes/{rid}/cook-logs").status_code == 200  # clean first

    _tamper_first_stored_deduction(engine, lambda e: e.__setitem__("mystery", 1))

    assert client.get(f"/api/recipes/{rid}/cook-logs").status_code == 500


def test_stored_entry_with_an_unlisted_reason_is_500_on_read(
    cook_env: tuple[TestClient, Engine],
) -> None:
    client, engine = cook_env
    rid = _mk_recipe(client, [TOMATO_3_CAN])
    _add_inventory(client, "Tomatoes", 5, "can")
    assert client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1}).status_code == 201

    _tamper_first_stored_deduction(engine, lambda e: e.__setitem__("reason", "made up"))

    assert client.get(f"/api/recipes/{rid}/cook-logs").status_code == 500


# ===========================================================================
# D. The cook race (§6 / §7 test_concurrency.py intent)
# ===========================================================================

# The serialization test lowers busy_timeout so it does not sit out the 5 s
# production default; a genuine lock wait still has to take a real fraction of it.
_TEST_BUSY_TIMEOUT_MS = 200
_LOCK_WAIT_FLOOR_S = 0.08  # below this, no real busy-wait happened
_LOCK_WAIT_CEILING_S = 4.0  # above this, we are hitting the 5 s production default


def _build_file_app(
    db_path: Path, *, busy_timeout_ms: int | None = None
) -> tuple[FastAPI, Engine]:
    url = f"sqlite:///{db_path}"
    app, engine = _build_app(registration_code="race", database_url=url)
    if busy_timeout_ms is not None:
        # Registered after make_engine's own `connect` listener, so this PRAGMA
        # runs last and lowers the 5000 ms default for the test.
        @event.listens_for(engine, "connect")
        def _lower_busy_timeout(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            cur.close()

    return app, engine


def _seed_cook_fixture(client: TestClient) -> int:
    """Recipe needing 1 can of tomato; inventory holds 5 cans."""
    _register(client, username="racer", code="race")
    rid = _mk_recipe(client, [{"item": "Tomatoes", "quantity": 1, "unit": "can"}])
    _add_inventory(client, "Tomatoes", 5, "can")
    return rid


def test_begin_immediate_serializes_two_writers_on_the_cook_row(tmp_path) -> None:
    """The interleave that loses an update is unconstructable: a cook's inventory
    write takes the RESERVED lock at ``BEGIN IMMEDIATE``; a second writer blocks
    and, once ``busy_timeout`` elapses, raises ``database is locked`` — after a
    real wait, not instantly. After the first commits, the second's retry reads
    the committed value (freshness)."""
    app, engine = _build_file_app(
        tmp_path / "cook-serialize.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app) as client:
            _seed_cook_fixture(client)

        first = engine.connect()
        second = engine.connect()
        try:
            first_txn = first.begin()  # BEGIN IMMEDIATE via the listener
            first.execute(
                text(
                    "UPDATE inventory_items SET quantity_base = 4 "
                    "WHERE match_name = 'tomato'"
                )
            )

            started = time.monotonic()
            with pytest.raises(OperationalError) as excinfo:
                with second.begin():
                    second.execute(
                        text(
                            "UPDATE inventory_items SET quantity_base = 999 "
                            "WHERE match_name = 'tomato'"
                        )
                    )
            elapsed = time.monotonic() - started

            orig = str(excinfo.value.orig)
            assert "database is locked" in orig or "database is busy" in orig, orig
            assert _LOCK_WAIT_FLOOR_S <= elapsed < _LOCK_WAIT_CEILING_S, elapsed

            first_txn.commit()

            fresh = second.execute(
                text("SELECT quantity_base FROM inventory_items WHERE match_name = 'tomato'")
            ).scalar_one()
            assert fresh == pytest.approx(4.0)
        finally:
            first.close()
            second.close()
    finally:
        engine.dispose()


def test_cook_request_maps_a_held_lock_to_409_not_500(tmp_path) -> None:
    """An ``OperationalError: database is locked`` raised anywhere in the cook
    request — here at its opening ``BEGIN IMMEDIATE`` — converts to
    ``409 {"detail": "conflict"}`` through the global handler, never a ``500``."""
    app, engine = _build_file_app(
        tmp_path / "cook-409.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            rid = _seed_cook_fixture(client)

            holder = engine.connect()
            try:
                holder_txn = holder.begin()
                holder.execute(
                    text(
                        "UPDATE inventory_items SET quantity_base = quantity_base "
                        "WHERE match_name = 'tomato'"
                    )
                )

                resp = client.post(f"/api/recipes/{rid}/cook", json={"multiplier": 1})

                assert resp.status_code == 409, resp.text
                assert resp.json() == {"detail": "conflict"}
                holder_txn.rollback()
            finally:
                holder.close()
    finally:
        engine.dispose()


def test_two_concurrent_cook_requests_do_not_lose_an_update(tmp_path) -> None:
    """Coarse smoke (not the guard): two real HTTP cooks on the same recipe over
    a file-backed DB serialize on the write lock — final ``quantity_base`` is
    ``5 - 1 - 1`` and both ``CookLog`` rows carry an honest before/after chain."""
    app, engine = _build_file_app(tmp_path / "cook-race.db")  # production 5 s busy_timeout
    try:
        with TestClient(app) as client:
            rid = _seed_cook_fixture(client)
            token = client.headers["Authorization"]

            results: dict[int, object] = {}

            def cook(key: int) -> None:
                worker = TestClient(app)
                worker.headers["Authorization"] = token
                results[key] = worker.post(
                    f"/api/recipes/{rid}/cook", json={"multiplier": 1}
                )

            threads = [threading.Thread(target=cook, args=(k,)) for k in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            assert results[0].status_code == 201, results[0].text
            assert results[1].status_code == 201, results[1].text

            _assert_base(client, "tomato", "opaque:can", 3.0)  # no lost update

            rows = client.get(f"/api/recipes/{rid}/cook-logs").json()
            assert len(rows) == 2
            pairs = sorted(
                (r["deductions"][0]["before"], r["deductions"][0]["after"]) for r in rows
            )
            assert pairs == [(4.0, 3.0), (5.0, 4.0)]
    finally:
        engine.dispose()
