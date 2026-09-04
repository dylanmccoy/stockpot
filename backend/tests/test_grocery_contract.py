"""Locked R-7 contract oracle for Phase 6 — grocery-line mutation (N6), submit,
and the submit race (``spec.md`` §4.3 / §5.6 / §6 / §7).

Authored black-box from the normative spec in a fresh context **before** the
Phase 6 production surface exists (``docs/plan.md`` §Independent contract-test
gate). At the time of writing there is:

* no ``routers/grocery.py`` (``/api/grocery`` routes),
* no ``GroceryList`` / ``GroceryListItem`` model or tables,
* no ``app.schemas.grocery`` module.

So this file **fails on collection** (the ``app.schemas.grocery`` import below)
until ``phase-6b`` lands, and does not fully pass until ``phase-6d`` (submit) /
``phase-6e`` (archive) — that staged failure *is* the lock. Later phases may add
cases but must not edit or delete an expected value here; a case later found
wrong is changed only via a paired ``spec.md`` + test edit recorded per the gate.

The consolidated-shortfall arithmetic itself (§7 *Grocery generation*) is locked
as a pure-service oracle in ``test_inventory_math.py``. This file exercises only
the parts that need HTTP:

* **N6** — ``PATCH .../items/{id}``: ``quantity`` + ``unit`` are an atomic pair
  (exactly one present in the body -> ``422 "quantity and unit must be set
  together"``); any ``item`` / ``quantity`` / ``unit`` edit reclassifies the
  line ``source -> "manual"``, ``nettable -> true``; a ``checked``-only PATCH
  does not.
* **submit** (§5.6) — forward-only; already-applied lines skipped; canonical
  ``applied_*``; list ``status`` unchanged; a checked ``quantity=null`` line
  skipped; a checked ``nettable=false`` line with a real quantity is added;
  nothing eligible -> ``200`` no-op; ``IntegrityError`` / lock timeout -> ``409``
  with the whole transaction rolled back.
* **the submit race** (§6) — two concurrent submits apply each checked line at
  most once; a lock that outlasts ``busy_timeout`` surfaces as
  ``409 {"detail": "conflict"}``, never ``500``.

Numeric comparisons use ``pytest.approx`` per the §2 floating-tolerance rule.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.database import make_engine
from app.main import create_app

# Missing until ``phase-6b`` builds ``schemas/grocery.py`` — collection fails
# here, and that is the locked oracle.
from app.schemas.grocery import GroceryListItemRead, GroceryListRead

REL = 1e-9
ABS = 1e-9

# §5.6 — the exact key sets of the two read schemas.
GROCERY_LIST_READ_KEYS = {
    "id",
    "name",
    "status",
    "source_recipe_ids",
    "created_at",
    "created_by",
    "items",
}
GROCERY_ITEM_READ_KEYS = {
    "id",
    "item",
    "normalized_name",
    "quantity",
    "unit",
    "checked",
    "checked_at",
    "submitted_at",
    "source",
    "nettable",
    "added_to_inventory",
    "applied_quantity",
    "applied_unit",
}

_PASSWORD = "correct horse battery"  # 8..128 chars
_REG_CODE = "gc"


# ===========================================================================
# HTTP helpers + fixtures (§5.2 / §5.5 / §5.6)
# ===========================================================================


def _register(
    client: TestClient, *, username: str = "shopper", code: str = _REG_CODE
) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": _PASSWORD, "code": code},
    )
    assert reg.status_code == 201, reg.text
    client.headers["Authorization"] = f"Bearer {reg.json()['token']}"


def _build_app(
    *, registration_code: str = _REG_CODE, database_url: str = "sqlite://"
) -> tuple[FastAPI, Engine]:
    settings = Settings(
        database_url=database_url,
        allow_registration=True,
        registration_code=registration_code,
    )
    engine = make_engine(database_url)
    return create_app(settings, engine), engine


def _mk_recipe(client: TestClient, ingredients: list[dict]) -> int:
    resp = client.post(
        "/api/recipes", json={"title": "Grocery Contract", "ingredients": ingredients}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_inventory(client: TestClient, item: str, quantity: float, unit: str) -> dict:
    resp = client.post(
        "/api/inventory", json={"item": item, "quantity": quantity, "unit": unit}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _inventory_row(
    client: TestClient, match_name: str, unit_bucket: str
) -> dict | None:
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


def _mk_grocery(client: TestClient, recipe_ids: list[int]) -> dict:
    resp = client.post("/api/grocery", json={"recipe_ids": recipe_ids})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _get_grocery(client: TestClient, gid: int) -> dict:
    resp = client.get(f"/api/grocery/{gid}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _items(client: TestClient, gid: int) -> list[dict]:
    return _get_grocery(client, gid)["items"]


def _line_by_norm(items: list[dict], norm: str) -> dict:
    matches = [it for it in items if it["normalized_name"] == norm]
    assert len(matches) == 1, f"expected exactly one {norm!r} line, got {len(matches)}"
    return matches[0]


def _add_manual(client: TestClient, gid: int, item: str):
    """Add an amount-less manual line (``GroceryListItemIn`` still requires the
    ``quantity`` / ``unit`` keys; both may be ``null``)."""
    return client.post(
        f"/api/grocery/{gid}/items",
        json={"item": item, "quantity": None, "unit": None},
    )


def _patch_item(client: TestClient, gid: int, item_id: int, body: dict):
    return client.patch(f"/api/grocery/{gid}/items/{item_id}", json=body)


def _submit(client: TestClient, gid: int):
    return client.post(f"/api/grocery/{gid}/submit")


@pytest.fixture
def grocery_client() -> Iterator[TestClient]:
    """An authed client over a fresh in-memory app. ``raise_server_exceptions``
    stays at its default (``True``) so a stray ``500`` on a happy path raises
    loudly rather than passing a status-code assertion."""
    app, engine = _build_app()
    with TestClient(app) as client:
        _register(client)
        yield client
    engine.dispose()


# --- shared line/list builders -------------------------------------------------


def _generated_flour_500g(client: TestClient) -> tuple[int, dict]:
    """A grocery list from a `Flour 500 g` recipe with no matching stock: one
    generated line, ``500 g``, canonical, ``source="generated"``,
    ``nettable=true``. Returns ``(list_id, that_line)``."""
    rid = _mk_recipe(client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gl = _mk_grocery(client, [rid])
    line = _line_by_norm(gl["items"], "flour")
    assert line["source"] == "generated"
    assert line["quantity"] == pytest.approx(500.0)
    assert line["unit"] == "g"
    assert line["nettable"] is True
    return gl["id"], line


def _generated_two_mass_lines(client: TestClient) -> int:
    """A grocery list with two independent generated lines — ``flour 500 g`` and
    ``sugar 200 g`` — no matching stock. Returns the list id."""
    rid = _mk_recipe(
        client,
        [
            {"item": "Flour", "quantity": 500, "unit": "g"},
            {"item": "Sugar", "quantity": 200, "unit": "g"},
        ],
    )
    return _mk_grocery(client, [rid])["id"]


def _generated_nonnettable_tomato_line(client: TestClient) -> tuple[int, dict]:
    """§N3: need 3 can, stock 1 can + 1 jar -> a generated ``2 can`` line with
    ``nettable=false``. Inventory is seeded *before* generation. Returns
    ``(list_id, that_line)``."""
    _add_inventory(client, "Tomatoes", 1, "can")
    _add_inventory(client, "Tomatoes", 1, "jar")
    rid = _mk_recipe(client, [{"item": "Tomatoes", "quantity": 3, "unit": "can"}])
    gl = _mk_grocery(client, [rid])
    line = _line_by_norm(gl["items"], "tomato")
    assert line["source"] == "generated"
    assert line["quantity"] == pytest.approx(2.0)
    assert line["unit"] == "can"
    assert line["nettable"] is False
    return gl["id"], line


# ===========================================================================
# 0. Read-schema shape (§5.6)
# ===========================================================================


def test_grocery_read_shapes_match_the_56_schemas(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    gl = _get_grocery(grocery_client, gid)

    assert set(gl) == GROCERY_LIST_READ_KEYS
    assert gl["status"] == "active"
    assert gl["items"] == sorted(gl["items"], key=lambda it: it["id"])  # ordered by id
    GroceryListRead.model_validate(gl)

    assert set(line) == GROCERY_ITEM_READ_KEYS
    assert line["checked"] is False
    assert line["checked_at"] is None
    assert line["submitted_at"] is None
    assert line["added_to_inventory"] is False
    assert line["applied_quantity"] is None
    assert line["applied_unit"] is None
    GroceryListItemRead.model_validate(line)


# ===========================================================================
# A. N6 — the grocery-line mutation contract (PATCH .../items/{id}, §5.6 / §7)
# ===========================================================================


def test_patch_unit_only_is_422_atomic_pair(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    resp = _patch_item(grocery_client, gid, line["id"], {"unit": "kg"})
    assert resp.status_code == 422, resp.text
    assert "quantity and unit must be set together" in resp.text
    # rejected, so the line is untouched
    after = _line_by_norm(_items(grocery_client, gid), "flour")
    assert after["quantity"] == pytest.approx(500.0)
    assert after["unit"] == "g"
    assert after["source"] == "generated"


def test_patch_quantity_only_is_422_atomic_pair(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    resp = _patch_item(grocery_client, gid, line["id"], {"quantity": 200})
    assert resp.status_code == 422, resp.text
    assert "quantity and unit must be set together" in resp.text
    after = _line_by_norm(_items(grocery_client, gid), "flour")
    assert after["quantity"] == pytest.approx(500.0)
    assert after["source"] == "generated"


def test_patch_quantity_and_unit_together_sets_as_sent_and_reclassifies(
    grocery_client: TestClient,
) -> None:
    """§7 ``test_grocery.py`` row: on a generated ``500 g`` line,
    ``PATCH {quantity:0.5, unit:"kg"}`` -> ``200``, stored exactly as sent (no
    conversion), ``source="manual"``, ``nettable=true`` (N6). This line is
    already ``nettable=true``; the genuine ``false -> true`` flip on a
    ``quantity``/``unit`` edit is locked by
    ``test_patch_quantity_unit_edit_flips_nettable_on_a_non_nettable_line``."""
    gid, line = _generated_flour_500g(grocery_client)
    assert line["nettable"] is True
    resp = _patch_item(
        grocery_client, gid, line["id"], {"quantity": 0.5, "unit": "kg"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity"] == pytest.approx(0.5)  # stored exactly as sent
    assert body["unit"] == "kg"
    assert body["source"] == "manual"
    assert body["nettable"] is True  # regression guard: must not drop to false
    GroceryListItemRead.model_validate(body)


def test_patch_quantity_unit_edit_flips_nettable_on_a_non_nettable_line(
    grocery_client: TestClient,
) -> None:
    """§5.6 L1473-76: "Any ``item`` / ``quantity`` / ``unit`` edit reclassifies
    the line ``source -> "manual"``, ``nettable -> true``." Proven here as a
    real ``false -> true`` transition on the generated ``nettable=false``
    (uncertain-shortfall) line."""
    gid, line = _generated_nonnettable_tomato_line(grocery_client)
    assert line["nettable"] is False
    resp = _patch_item(
        grocery_client, gid, line["id"], {"quantity": 4, "unit": "can"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity"] == pytest.approx(4.0)
    assert body["unit"] == "can"
    assert body["source"] == "manual"
    assert body["nettable"] is True


def test_patch_quantity_and_unit_may_both_be_null(grocery_client: TestClient) -> None:
    """§5.6: "values may be null; both keys must appear together" — the atomic
    pair is about *presence* in the body, not about being non-null. Whether a
    pure null/null edit also reclassifies the line is deliberately left unlocked
    here (the §5.6 "any quantity/unit edit reclassifies" rule does not
    unambiguously cover a no-value edit); that is `phase-6c`'s to pin down."""
    gid, line = _generated_flour_500g(grocery_client)
    resp = _patch_item(
        grocery_client, gid, line["id"], {"quantity": None, "unit": None}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quantity"] is None
    assert resp.json()["unit"] is None


def test_patch_quantity_without_unit_is_422_even_alongside_another_key(
    grocery_client: TestClient,
) -> None:
    """§5.6: the atomic-pair rule keys off ``quantity`` / ``unit`` presence
    only — a third field in the same body does not excuse a missing ``unit``."""
    gid, line = _generated_flour_500g(grocery_client)
    resp = _patch_item(
        grocery_client, gid, line["id"], {"item": "bread flour", "quantity": 200}
    )
    assert resp.status_code == 422, resp.text
    assert "quantity and unit must be set together" in resp.text
    after = _line_by_norm(_items(grocery_client, gid), "flour")
    assert after["item"] == "Flour"  # whole PATCH rejected, nothing applied
    assert after["source"] == "generated"


def test_patch_item_text_reclassifies_and_recomputes_normalized_name(
    grocery_client: TestClient,
) -> None:
    """An ``item`` edit on a generated ``nettable=false`` line reclassifies it
    ``source="manual"``, ``nettable=true`` and recomputes ``normalized_name``
    (N6)."""
    gid, line = _generated_nonnettable_tomato_line(grocery_client)
    resp = _patch_item(grocery_client, gid, line["id"], {"item": "almond flour"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["item"] == "almond flour"
    assert body["normalized_name"] == "almond flour"
    assert body["source"] == "manual"
    assert body["nettable"] is True


def test_patch_checked_only_does_not_reclassify(grocery_client: TestClient) -> None:
    """A ``checked``-only PATCH sets ``checked`` / ``checked_at`` and leaves
    ``source`` / ``nettable`` untouched (N6)."""
    gid, line = _generated_nonnettable_tomato_line(grocery_client)
    resp = _patch_item(grocery_client, gid, line["id"], {"checked": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checked"] is True
    assert body["checked_at"] is not None
    assert body["source"] == "generated"
    assert body["nettable"] is False


def test_patch_checked_false_clears_checked_at(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    _patch_item(grocery_client, gid, line["id"], {"checked": True})
    resp = _patch_item(grocery_client, gid, line["id"], {"checked": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["checked"] is False
    assert resp.json()["checked_at"] is None


def test_patch_has_no_inventory_side_effect(grocery_client: TestClient) -> None:
    """§5.6: nothing reaches stock until ``submit``."""
    gid, line = _generated_flour_500g(grocery_client)
    _patch_item(grocery_client, gid, line["id"], {"quantity": 2, "unit": "kg"})
    _patch_item(grocery_client, gid, line["id"], {"checked": True})
    assert _inventory_row(grocery_client, "flour", "mass") is None


def test_patch_unknown_list_or_line_is_404(grocery_client: TestClient) -> None:
    assert _patch_item(grocery_client, 999999, 1, {"checked": True}).status_code == 404
    gid, _ = _generated_flour_500g(grocery_client)
    assert _patch_item(grocery_client, gid, 999999, {"checked": True}).status_code == 404


# ===========================================================================
# B. submit — forward-only application into inventory (§5.6)
# ===========================================================================


def test_submit_freezes_checked_line_with_canonical_applied_fields(
    grocery_client: TestClient,
) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    # edit to 0.5 kg (now manual), check, submit
    _patch_item(grocery_client, gid, line["id"], {"quantity": 0.5, "unit": "kg"})
    _patch_item(grocery_client, gid, line["id"], {"checked": True})

    resp = _submit(grocery_client, gid)
    assert resp.status_code == 200, resp.text
    gl = resp.json()
    GroceryListRead.model_validate(gl)
    assert gl["status"] == "active"  # submit does NOT archive

    out = _line_by_norm(gl["items"], "flour")
    assert out["added_to_inventory"] is True
    assert out["submitted_at"] is not None
    # canonical: 0.5 kg -> 500 g
    assert out["applied_quantity"] == pytest.approx(500.0)
    assert out["applied_unit"] == "g"
    _assert_base(grocery_client, "flour", "mass", 500.0)


def test_submit_is_forward_only_and_skips_already_applied_lines(
    grocery_client: TestClient,
) -> None:
    gid = _generated_two_mass_lines(grocery_client)
    items = _items(grocery_client, gid)
    flour = _line_by_norm(items, "flour")
    sugar = _line_by_norm(items, "sugar")

    _patch_item(grocery_client, gid, flour["id"], {"checked": True})
    r1 = _submit(grocery_client, gid)
    assert r1.status_code == 200, r1.text
    flour_1 = _line_by_norm(r1.json()["items"], "flour")
    assert flour_1["added_to_inventory"] is True
    applied_q1 = flour_1["applied_quantity"]
    submitted_at_1 = flour_1["submitted_at"]
    _assert_base(grocery_client, "flour", "mass", 500.0)
    assert _inventory_row(grocery_client, "sugar", "mass") is None

    # a second submit picks up only the newly-checked line; flour is untouched
    _patch_item(grocery_client, gid, sugar["id"], {"checked": True})
    r2 = _submit(grocery_client, gid)
    assert r2.status_code == 200, r2.text
    flour_2 = _line_by_norm(r2.json()["items"], "flour")
    sugar_2 = _line_by_norm(r2.json()["items"], "sugar")
    assert flour_2["applied_quantity"] == pytest.approx(applied_q1)
    assert flour_2["submitted_at"] == submitted_at_1
    assert sugar_2["added_to_inventory"] is True
    _assert_base(grocery_client, "flour", "mass", 500.0)  # not doubled
    _assert_base(grocery_client, "sugar", "mass", 200.0)


def test_submit_does_not_change_list_status(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    _patch_item(grocery_client, gid, line["id"], {"checked": True})
    assert _submit(grocery_client, gid).json()["status"] == "active"
    # re-submit with nothing newly eligible: still a 200 no-op, still active
    again = _submit(grocery_client, gid)
    assert again.status_code == 200
    assert again.json()["status"] == "active"


def test_submit_with_nothing_checked_is_a_200_no_op(
    grocery_client: TestClient,
) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    resp = _submit(grocery_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "flour")
    assert out["added_to_inventory"] is False
    assert out["submitted_at"] is None
    assert _inventory_row(grocery_client, "flour", "mass") is None


def test_submit_skips_a_checked_line_whose_quantity_is_null(
    grocery_client: TestClient,
) -> None:
    gid, _ = _generated_flour_500g(grocery_client)
    made = _add_manual(grocery_client, gid, "Bay leaf")
    assert made.status_code == 201, made.text
    leaf = made.json()
    assert leaf["quantity"] is None
    _patch_item(grocery_client, gid, leaf["id"], {"checked": True})

    resp = _submit(grocery_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "bay leaf")
    assert out["added_to_inventory"] is False
    assert out["submitted_at"] is None
    assert _inventory_row(grocery_client, "bay leaf", "count") is None


def test_submit_adds_a_checked_nettable_false_line_that_has_a_real_quantity(
    grocery_client: TestClient,
) -> None:
    """§5.6: the ``nettable=false`` flag informs the shopper; it does not block
    submit. A checked non-nettable line with a real quantity is applied."""
    gid, line = _generated_nonnettable_tomato_line(grocery_client)
    _patch_item(grocery_client, gid, line["id"], {"checked": True})

    resp = _submit(grocery_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "tomato")
    assert out["added_to_inventory"] is True
    assert out["applied_quantity"] == pytest.approx(2.0)
    assert out["applied_unit"] == "can"
    # the compatible `can` bucket went 1 -> 1 + 2
    _assert_base(grocery_client, "tomato", "opaque:can", 3.0)
    _assert_base(grocery_client, "tomato", "opaque:jar", 1.0)  # untouched


def test_submit_unknown_list_is_404(grocery_client: TestClient) -> None:
    assert grocery_client.post("/api/grocery/999999/submit").status_code == 404


def test_submit_on_a_non_active_list_is_409(grocery_client: TestClient) -> None:
    gid, line = _generated_flour_500g(grocery_client)
    assert grocery_client.post(f"/api/grocery/{gid}/archive").status_code == 200
    # an archived list rejects both the check and the submit
    assert _patch_item(grocery_client, gid, line["id"], {"checked": True}).status_code == 409
    assert _submit(grocery_client, gid).status_code == 409


def test_frozen_line_rejects_further_patch_and_delete(
    grocery_client: TestClient,
) -> None:
    """§5.6: once ``added_to_inventory`` a line is frozen -> ``PATCH`` / item
    ``DELETE`` return ``409``; an unfrozen sibling still ``DELETE``s ``204``."""
    gid = _generated_two_mass_lines(grocery_client)
    items = _items(grocery_client, gid)
    flour = _line_by_norm(items, "flour")
    sugar = _line_by_norm(items, "sugar")

    _patch_item(grocery_client, gid, flour["id"], {"checked": True})
    assert _submit(grocery_client, gid).status_code == 200
    assert _line_by_norm(_items(grocery_client, gid), "flour")["added_to_inventory"]

    assert _patch_item(grocery_client, gid, flour["id"], {"checked": False}).status_code == 409
    assert grocery_client.delete(
        f"/api/grocery/{gid}/items/{flour['id']}"
    ).status_code == 409
    # the still-unfrozen sugar line deletes cleanly
    assert grocery_client.delete(
        f"/api/grocery/{gid}/items/{sugar['id']}"
    ).status_code == 204


# ===========================================================================
# C. The submit race (§6 / §7 test_concurrency.py intent)
# ===========================================================================

# Lower busy_timeout for the serialization test so it does not sit out the 5 s
# production default; a genuine lock wait still takes a real fraction of it.
_TEST_BUSY_TIMEOUT_MS = 200


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


def _seed_submit_fixture(client: TestClient) -> tuple[int, int]:
    """A grocery list with one checked, eligible generated line — ``Flour
    500 g``, no matching stock. Returns ``(list_id, item_id)``."""
    _register(client, username="racer", code="race")
    rid = _mk_recipe(client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gl = _mk_grocery(client, [rid])
    line = _line_by_norm(gl["items"], "flour")
    resp = _patch_item(client, gl["id"], line["id"], {"checked": True})
    assert resp.status_code == 200, resp.text
    return gl["id"], line["id"]


def _seed_two_checked_lines(client: TestClient) -> int:
    """A grocery list with two checked, eligible generated lines — ``Flour
    500 g`` and ``Sugar 200 g``, no matching stock. Returns the list id."""
    _register(client, username="racer", code="race")
    rid = _mk_recipe(
        client,
        [
            {"item": "Flour", "quantity": 500, "unit": "g"},
            {"item": "Sugar", "quantity": 200, "unit": "g"},
        ],
    )
    gl = _mk_grocery(client, [rid])
    for norm in ("flour", "sugar"):
        line = _line_by_norm(gl["items"], norm)
        assert (
            _patch_item(client, gl["id"], line["id"], {"checked": True}).status_code
            == 200
        )
    return gl["id"]


def test_submit_request_maps_a_held_lock_to_409_not_500(tmp_path) -> None:
    """An ``OperationalError: database is locked`` raised inside the submit
    request — here at its opening ``BEGIN IMMEDIATE`` — converts to
    ``409 {"detail": "conflict"}`` through the global handler, never ``500``.
    The write must not land."""
    app, engine = _build_file_app(
        tmp_path / "grocery-409.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            gid, _ = _seed_submit_fixture(client)

            holder = engine.connect()
            try:
                holder_txn = holder.begin()  # BEGIN IMMEDIATE — holds the write lock
                # Any held write lock blocks submit at its own opening
                # BEGIN IMMEDIATE, before its first statement. `inventory_items`
                # is an established table (phase-4b) and submit's upsert target.
                holder.execute(
                    text("UPDATE inventory_items SET quantity_base = quantity_base")
                )

                resp = client.post(f"/api/grocery/{gid}/submit")
                assert resp.status_code == 409, resp.text
                assert resp.json() == {"detail": "conflict"}

                holder_txn.rollback()
            finally:
                holder.close()

            # transaction rolled back: the line never froze, stock never moved
            line = _line_by_norm(_items(client, gid), "flour")
            assert line["added_to_inventory"] is False
            assert _inventory_row(client, "flour", "mass") is None
    finally:
        engine.dispose()


def test_submit_lock_failure_rolls_back_the_whole_transaction(tmp_path) -> None:
    """§6: "A mid-operation failure rolls back the whole thing — ... no
    partly-submitted grocery list." A lock held for the duration of the submit
    request fails it with ``409`` and leaves **both** checked lines unfrozen and
    inventory completely untouched — not the first line applied and the second
    lost."""
    app, engine = _build_file_app(
        tmp_path / "grocery-rollback.db", busy_timeout_ms=_TEST_BUSY_TIMEOUT_MS
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            gid = _seed_two_checked_lines(client)

            holder = engine.connect()
            try:
                holder_txn = holder.begin()  # BEGIN IMMEDIATE — holds the write lock
                holder.execute(
                    text("UPDATE inventory_items SET quantity_base = quantity_base")
                )
                resp = client.post(f"/api/grocery/{gid}/submit")
                assert resp.status_code == 409, resp.text
                assert resp.json() == {"detail": "conflict"}
                holder_txn.rollback()
            finally:
                holder.close()

            items = _items(client, gid)
            for norm in ("flour", "sugar"):
                line = _line_by_norm(items, norm)
                assert line["added_to_inventory"] is False, norm
                assert line["submitted_at"] is None, norm
                assert line["applied_quantity"] is None, norm
            assert client.get("/api/inventory").json() == []
    finally:
        engine.dispose()


def test_two_concurrent_submits_apply_the_checked_line_at_most_once(
    tmp_path,
) -> None:
    """The guard: two real HTTP submits of the same list race over a file-backed
    DB. ``BEGIN IMMEDIATE`` serializes them, so the checked line is applied
    exactly once — inventory reflects one application, not two, and the line is
    frozen once with a canonical ``applied_quantity``."""
    app, engine = _build_file_app(tmp_path / "grocery-race.db")  # 5 s busy_timeout
    try:
        with TestClient(app) as client:
            gid, _ = _seed_submit_fixture(client)
            token = client.headers["Authorization"]

            results: dict[int, object] = {}

            def submit(key: int) -> None:
                worker = TestClient(app)
                worker.headers["Authorization"] = token
                results[key] = worker.post(f"/api/grocery/{gid}/submit")

            threads = [threading.Thread(target=submit, args=(k,)) for k in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            for r in results.values():
                assert r.status_code in (200, 409), r.text
            assert any(r.status_code == 200 for r in results.values())

            line = _line_by_norm(_items(client, gid), "flour")
            assert line["added_to_inventory"] is True
            assert line["applied_quantity"] == pytest.approx(500.0)
            _assert_base(client, "flour", "mass", 500.0)  # applied once, not 1000
    finally:
        engine.dispose()
