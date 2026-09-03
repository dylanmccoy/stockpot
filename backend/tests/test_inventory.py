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


def _patch(client: TestClient, item_id: int, **body) -> object:
    return client.patch(f"/api/inventory/{item_id}", json=body)


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


# --------------------------------------------------------------------------- #
# PATCH — absolute replacement, model_fields_set-driven (spec.md §5.5)
# --------------------------------------------------------------------------- #


def test_patch_requires_auth(client: TestClient) -> None:
    assert client.patch("/api/inventory/1", json={"quantity": 1, "unit": "kg"}).status_code == 401


def test_patch_absent_row_is_404(auth_client: TestClient) -> None:
    assert _patch(auth_client, 99999, quantity=1, unit="kg").status_code == 404


def test_patch_empty_body_is_200_noop(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity_base"] == pytest.approx(1000.0)
    assert body["item"] == "Flour"
    assert body["updated_at"] == row["updated_at"]  # untouched on a no-op


@pytest.mark.parametrize(
    ("amount", "unit", "expected_base"),
    [(200, "g", 200.0), (0.2, "kg", 200.0)],
)
def test_patch_quantity_is_absolute_canonical_set(
    auth_client: TestClient, amount: float, unit: str, expected_base: float
) -> None:
    """Every §5.5 example row: `{quantity, unit}` sets `quantity_base` absolutely
    in the bucket's canonical unit — it does not add."""
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")  # 1000 g
    resp = _patch(auth_client, row["id"], quantity=amount, unit=unit)
    assert resp.status_code == 200, resp.text
    assert resp.json()["quantity_base"] == pytest.approx(expected_base)


def test_patch_unit_is_display_only(auth_client: TestClient) -> None:
    """`{unit: "kg"}` changes only the display preference: `quantity_base`
    untouched, `display_quantity` recomputed via `from_base`."""
    row = _add(auth_client, item="Flour", quantity=1500, unit="g")
    resp = _patch(auth_client, row["id"], unit="kg")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity_base"] == pytest.approx(1500.0)
    assert body["display_unit"] == "kg"
    assert body["display_quantity"] == pytest.approx(1.5)


def test_patch_quantity_without_unit_is_422(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], quantity=200)
    assert resp.status_code == 422, resp.text
    assert "unit is required" in resp.json()["detail"]
    assert _list(auth_client)[0]["quantity_base"] == pytest.approx(1000.0)


def test_patch_quantity_zero_is_accepted(auth_client: TestClient) -> None:
    """`>= 0` and `max(body.quantity, 0.0)`: zero is a legitimate absolute set,
    consistent with `POST` (ticket's "0 -> 422" contradicts spec §5.5)."""
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], quantity=0, unit="kg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["quantity_base"] == pytest.approx(0.0)


def test_patch_unit_changing_bucket_is_422(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")  # mass row
    resp = _patch(auth_client, row["id"], unit="can")
    assert resp.status_code == 422, resp.text
    assert "bucket" in resp.json()["detail"]


def test_patch_unit_null_on_non_count_row_is_422(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], unit=None)
    assert resp.status_code == 422, resp.text
    assert "bucket" in resp.json()["detail"]


def test_patch_unit_null_on_count_row_clears_preference(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Eggs", quantity=6, unit="each")
    assert row["unit_bucket"] == "count"
    resp = _patch(auth_client, row["id"], unit=None)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_unit"] is None
    assert body["display_quantity"] == pytest.approx(6.0)


@pytest.mark.parametrize("field", ["item", "quantity", "match_name"])
def test_patch_present_and_null_is_422(auth_client: TestClient, field: str) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], **{field: None})
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == f"{field} cannot be null"


def test_patch_match_name_normalizing_to_empty_is_422(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], match_name="!!!")
    assert resp.status_code == 422, resp.text
    assert "match_name normalizes to empty" in resp.json()["detail"]


def test_patch_match_name_is_normalized_before_store(auth_client: TestClient) -> None:
    row = _add(auth_client, item="All-Purpose", quantity=1, unit="kg", match_name="ap")
    for supplied in (" Flour ", "FLOUR"):
        resp = _patch(auth_client, row["id"], match_name=supplied)
        assert resp.status_code == 200, resp.text
        assert resp.json()["match_name"] == "flour"


def test_patch_match_name_colliding_with_other_bucket_row_is_409(
    auth_client: TestClient,
) -> None:
    _add(auth_client, item="Bread Flour", quantity=1, unit="kg", match_name="flour")
    other = _add(auth_client, item="Cake Flour", quantity=1, unit="kg", match_name="cake flour")
    resp = _patch(auth_client, other["id"], match_name="flour")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "match_name already in use for this bucket"


def test_patch_match_name_to_its_own_current_value_is_fine(auth_client: TestClient) -> None:
    """The `(nm, bucket)` clash check excludes the row itself."""
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], match_name="flour")
    assert resp.status_code == 200, resp.text
    assert resp.json()["match_name"] == "flour"


def test_patch_item_rename_recomputes_normalized_name(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], item=" Bread Flour ")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["item"] == " Bread Flour "
    assert body["normalized_name"] == "bread flour"
    assert body["match_name"] == "flour"  # match_name not dragged along


def test_patch_match_name_repoints_the_upsert_key(auth_client: TestClient) -> None:
    """Editing `match_name` re-points the recipe↔inventory match key: after the
    re-point, an additive `POST` on the new name merges into this row, and the
    old name is now free for a fresh row. (Availability/cook read this key in
    phases 4d/5.)"""
    row = _add(auth_client, item="White Sugar", quantity=500, unit="g", match_name="salt")
    assert _patch(auth_client, row["id"], match_name="sugar").status_code == 200

    merged = _add(auth_client, item="Caster Sugar", quantity=100, unit="g", match_name="sugar")
    assert merged["id"] == row["id"]
    assert merged["quantity_base"] == pytest.approx(600.0)

    fresh = _add(auth_client, item="Table Salt", quantity=1, unit="g", match_name="salt")
    assert fresh["id"] != row["id"]
    assert {r["match_name"] for r in _list(auth_client)} == {"sugar", "salt"}


def test_patch_reduced_base_recomputes_display_quantity_on_get(
    auth_client: TestClient,
) -> None:
    """add -> reduce -> GET: `display_quantity` tracks the reduced `quantity_base`
    in the preferred unit. (Cook lands in phase-5; PATCH is the reducer here.)"""
    row = _add(auth_client, item="Flour", quantity=2, unit="kg")  # 2000 g, pref kg
    assert _patch(auth_client, row["id"], quantity=750, unit="g").status_code == 200
    got = _list(auth_client)[0]
    assert got["quantity_base"] == pytest.approx(750.0)
    assert got["display_unit"] == "g"
    assert got["display_quantity"] == pytest.approx(750.0)


def test_patch_updates_updated_at(auth_client: TestClient) -> None:
    row = _add(auth_client, item="Flour", quantity=1, unit="kg")
    resp = _patch(auth_client, row["id"], unit="kg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated_at"] >= row["updated_at"]
