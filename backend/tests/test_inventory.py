"""Inventory model + additive CRUD (spec.md §1, §4.4, §5.5; phase-4b).

Everything goes through HTTP on `auth_client`. The additive `POST` upsert, the
`GET` list, and `DELETE` are the phase-4b surface; `PATCH` arrives in phase-4c.
"""

import pytest
from fastapi.testclient import TestClient


def _post(client: TestClient, **body) -> object:
    return client.post("/api/inventory", json=body)


def _add(client: TestClient, **body) -> dict:
    resp = _post(client, **body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _list(client: TestClient) -> list[dict]:
    resp = client.get("/api/inventory")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# auth gate + basic shape
# --------------------------------------------------------------------------- #


def test_inventory_requires_auth(client: TestClient) -> None:
    assert client.get("/api/inventory").status_code == 401
    assert client.post("/api/inventory", json={"item": "Flour", "quantity": 1}).status_code == 401


def test_post_returns_read_shape(auth_client: TestClient) -> None:
    body = _add(auth_client, item="Milk", quantity=2, unit="l")
    assert body["item"] == "Milk"
    assert body["normalized_name"] == "milk"
    assert body["match_name"] == "milk"
    assert body["unit_bucket"] == "volume"
    assert body["quantity_base"] == pytest.approx(2000.0)
    assert body["display_unit"] == "l"
    assert body["display_quantity"] == pytest.approx(2.0)
    assert isinstance(body["id"], int)
    assert "updated_at" in body


# --------------------------------------------------------------------------- #
# additive POST — same (match_name, unit_bucket) sums quantity_base
# --------------------------------------------------------------------------- #


def test_two_posts_same_key_sum_quantity_base(auth_client: TestClient) -> None:
    a = _add(auth_client, item="Sugar", quantity=1, unit="kg")
    b = _add(auth_client, item="Sugar", quantity=2, unit="kg")
    assert a["id"] == b["id"]
    assert b["quantity_base"] == pytest.approx(3000.0)
    assert len(_list(auth_client)) == 1


def test_cross_unit_add_merges_via_quantity_base(auth_client: TestClient) -> None:
    """`1 kg` then `500 g` land on the one `(flour, mass)` row: 1500 g base."""
    _add(auth_client, item="Flour", quantity=1, unit="kg")
    row = _add(auth_client, item="Flour", quantity=500, unit="g")
    assert row["unit_bucket"] == "mass"
    assert row["quantity_base"] == pytest.approx(1500.0)
    # COALESCE(excluded.display_unit, existing) -> the later unit wins.
    assert row["display_unit"] == "g"
    assert row["display_quantity"] == pytest.approx(1500.0)
    assert len(_list(auth_client)) == 1


def test_incompatible_units_make_two_rows(auth_client: TestClient) -> None:
    """Same food, incompatible units -> two rows keyed by `unit_bucket`."""
    _add(auth_client, item="Tomatoes", quantity=2, unit="can")
    _add(auth_client, item="Tomatoes", quantity=1, unit="jar")
    rows = _list(auth_client)
    assert [r["unit_bucket"] for r in rows] == ["opaque:can", "opaque:jar"]
    assert {r["match_name"] for r in rows} == {"tomato"}


def test_casing_folds_to_one_row(auth_client: TestClient) -> None:
    """`"Flour"` then `"flour"` (same unit) hit one row; `item` is not touched
    on conflict (N5)."""
    first = _add(auth_client, item="Flour", quantity=1, unit="kg")
    second = _add(auth_client, item="flour", quantity=1, unit="kg")
    assert first["id"] == second["id"]
    assert second["item"] == "Flour"  # untouched on conflict
    assert second["quantity_base"] == pytest.approx(2000.0)
    assert len(_list(auth_client)) == 1


def test_surrounding_whitespace_and_casing_in_match_name_normalized(
    auth_client: TestClient,
) -> None:
    a = _add(auth_client, item="Canned Tomatoes", quantity=1, unit="can", match_name=" Tomato ")
    b = _add(auth_client, item="Whole Tomatoes", quantity=2, unit="can", match_name="TOMATO")
    assert a["match_name"] == "tomato"
    assert a["id"] == b["id"]
    assert b["quantity_base"] == pytest.approx(3.0)


def test_derived_match_name_uses_normalized_item(auth_client: TestClient) -> None:
    """No `match_name` supplied -> derived from `normalize_name(item)`."""
    row = _add(auth_client, item="Yellow Onions", quantity=3)
    assert row["match_name"] == "yellow onion"
    assert row["normalized_name"] == "yellow onion"
    assert row["unit_bucket"] == "count"  # unit omitted => COUNT
    assert row["display_unit"] is None
    assert row["display_quantity"] == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# validation — 422s
# --------------------------------------------------------------------------- #


def test_post_missing_item_or_quantity_is_422(auth_client: TestClient) -> None:
    assert _post(auth_client, quantity=1).status_code == 422
    assert _post(auth_client, item="Flour").status_code == 422
    assert _list(auth_client) == []


@pytest.mark.parametrize("match_name", ["  ", "!!!", "   \t ", ""])
def test_supplied_match_name_normalizing_to_empty_is_422(
    auth_client: TestClient, match_name: str
) -> None:
    """Every *supplied* value is normalized, an explicit `""` included; one that
    normalizes to `""` is a 422 (spec.md §1, N5). Only an omitted `match_name`
    falls back to the derived key."""
    resp = _post(auth_client, item="Flour", quantity=1, unit="kg", match_name=match_name)
    assert resp.status_code == 422, resp.text
    assert "match_name" in resp.json()["detail"]
    assert _list(auth_client) == []


def test_derived_match_name_empty_is_422(auth_client: TestClient) -> None:
    """`item` passes `min_length=1` but normalizes to `""` -> 422."""
    resp = _post(auth_client, item="!!!", quantity=1)
    assert resp.status_code == 422, resp.text
    assert _list(auth_client) == []


@pytest.mark.parametrize("quantity", [-1, -0.5, -1000.0])
def test_negative_quantity_is_422(auth_client: TestClient, quantity: float) -> None:
    """`ge=0`. The non-finite (`inf` / `nan`) cases need a raw JSON body and live
    in `test_validation.py`."""
    resp = _post(auth_client, item="Flour", quantity=quantity, unit="kg")
    assert resp.status_code == 422, resp.text
    assert _list(auth_client) == []


def test_zero_quantity_is_accepted(auth_client: TestClient) -> None:
    """`>= 0`: an inventory quantity may legitimately be zero."""
    row = _add(auth_client, item="Flour", quantity=0, unit="kg")
    assert row["quantity_base"] == pytest.approx(0.0)


@pytest.mark.parametrize("unit", ["   ", ".", "\t"])
def test_blank_unit_is_treated_as_count_not_a_500(
    auth_client: TestClient, unit: str
) -> None:
    """A unit that normalizes to `""` (not `None`) must not reach
    `to_base(...)[0]` on a `None` result — it is the no-unit / COUNT case."""
    row = _add(auth_client, item="Eggs", quantity=6, unit=unit)
    assert row["unit_bucket"] == "count"
    assert row["quantity_base"] == pytest.approx(6.0)


def test_conversion_overflow_to_infinity_is_rejected(auth_client: TestClient) -> None:
    """A finite request whose canonical conversion overflows to `+inf` is
    stopped at the DB boundary (finite `CHECK`), not stored as the source of
    truth (spec.md §1)."""
    resp = _post(auth_client, item="Flour", quantity=1e308, unit="kg")
    assert resp.status_code == 409, resp.text
    assert _list(auth_client) == []


# --------------------------------------------------------------------------- #
# GET list ordering
# --------------------------------------------------------------------------- #


def test_list_orders_by_match_name_then_unit_bucket(auth_client: TestClient) -> None:
    _add(auth_client, item="Zucchini", quantity=1)
    _add(auth_client, item="Apples", quantity=5)
    _add(auth_client, item="Tomatoes", quantity=2, unit="jar")
    _add(auth_client, item="Tomatoes", quantity=2, unit="can")
    _add(auth_client, item="Flour", quantity=1, unit="kg")
    rows = _list(auth_client)
    assert [(r["match_name"], r["unit_bucket"]) for r in rows] == [
        ("apple", "count"),
        ("flour", "mass"),
        ("tomato", "opaque:can"),
        ("tomato", "opaque:jar"),
        ("zucchini", "count"),
    ]


# --------------------------------------------------------------------------- #
# DELETE
# --------------------------------------------------------------------------- #


def test_delete_removes_row(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    assert auth_client.delete(f"/api/inventory/{row['id']}").status_code == 204
    assert _list(auth_client) == []


def test_delete_absent_row_is_404(auth_client: TestClient) -> None:
    assert auth_client.delete("/api/inventory/99999").status_code == 404


def test_delete_is_idempotent_second_call_404(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    assert auth_client.delete(f"/api/inventory/{row['id']}").status_code == 204
    assert auth_client.delete(f"/api/inventory/{row['id']}").status_code == 404


# --------------------------------------------------------------------------- #
# display_quantity across bucket kinds
# --------------------------------------------------------------------------- #


def test_display_quantity_opaque_bucket_equals_quantity_base(
    auth_client: TestClient,
) -> None:
    """Opaque bucket: `display_unit` is the raw token, `display_quantity ==
    quantity_base` (spec.md §4.4 locked oracle)."""
    row = _add(auth_client, item="Tomatoes", quantity=3, unit="cans")
    assert row["unit_bucket"] == "opaque:can"
    assert row["display_unit"] == "cans"
    assert row["quantity_base"] == pytest.approx(3.0)
    assert row["display_quantity"] == pytest.approx(3.0)


def test_display_quantity_count_no_preference(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Eggs", quantity=12)
    assert row["unit_bucket"] == "count"
    assert row["display_unit"] is None
    assert row["display_quantity"] == pytest.approx(12.0)


def test_display_quantity_recomputed_from_reduced_base_after_edit(
    auth_client: TestClient,
) -> None:
    """Placeholder for the add -> reduce -> GET path (cook lands in phase-5): a
    second additive POST changes `quantity_base`, and `display_quantity` tracks
    it in the preferred unit."""
    _add(auth_client, item="Flour", quantity=2, unit="kg")
    row = _add(auth_client, item="Flour", quantity=500, unit="g")
    assert row["quantity_base"] == pytest.approx(2500.0)
    assert row["display_unit"] == "g"
    assert row["display_quantity"] == pytest.approx(2500.0)
