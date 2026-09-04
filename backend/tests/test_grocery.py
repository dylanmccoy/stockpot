"""Grocery generation + list read/delete/mutation/submit (spec.md §5.6,
`phase-6b`-`6d`).

Archive is `phase-6e`'s; the locked N6/submit/race contract oracle lives in
`test_grocery_contract.py` (`phase-6a`) and stays partially failing until it
lands — see that file's module docstring. This file covers the HTTP wiring
phase-6b/6c/6d actually ship: `POST` generation (consolidation, netting,
canonical units), `GET` (list + single, `?status`), `DELETE` (cascade), manual
item add / line edit (N6) / line delete, and `submit` (forward-only apply into
inventory, freeze).

The consolidated-shortfall arithmetic itself is locked as a pure-service oracle
in `test_inventory_math.py::test_generate_lines_oracle` — this file does not
re-derive those cases, only exercises the HTTP layer around `generate_lines`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _mk_recipe(client: TestClient, ingredients: list[dict], title: str = "Recipe") -> int:
    resp = client.post("/api/recipes", json={"title": title, "ingredients": ingredients})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_inventory(client: TestClient, item: str, quantity: float, unit: str) -> dict:
    resp = client.post(
        "/api/inventory", json={"item": item, "quantity": quantity, "unit": unit}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _mk_grocery(
    client: TestClient,
    recipe_ids: list[int],
    *,
    name: str | None = None,
    multipliers: dict[int, float] | None = None,
) -> dict:
    body: dict = {"recipe_ids": recipe_ids}
    if name is not None:
        body["name"] = name
    if multipliers is not None:
        body["multipliers"] = multipliers
    resp = client.post("/api/grocery", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _line_by_norm(items: list[dict], norm: str) -> dict:
    matches = [it for it in items if it["normalized_name"] == norm]
    assert len(matches) == 1, f"expected exactly one {norm!r} line, got {len(matches)}"
    return matches[0]


def _item_row_count(engine: Engine, list_id: int | None = None) -> int:
    sql = "SELECT count(*) FROM grocery_list_items"
    params: dict = {}
    if list_id is not None:
        sql += " WHERE grocery_list_id = :lid"
        params["lid"] = list_id
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


# ===========================================================================
# Generation: consolidation + netting across recipes, canonical units
# ===========================================================================


def test_generate_from_two_recipes_consolidates_and_nets_against_stock(
    auth_client: TestClient,
) -> None:
    """Two recipes each need `flour`, in different known units; partial
    compatible stock nets against the consolidated total (spec.md §4.3)."""
    r1 = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    r2 = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 0.3, "unit": "kg"}])
    _add_inventory(auth_client, "Flour", 200, "g")  # 200 g compatible stock

    gl = _mk_grocery(auth_client, [r1, r2])
    assert gl["status"] == "active"
    assert gl["source_recipe_ids"] == [r1, r2]
    assert gl["name"].startswith("Groceries ")

    line = _line_by_norm(gl["items"], "flour")
    assert line["source"] == "generated"
    assert line["checked"] is False
    assert line["added_to_inventory"] is False
    assert line["nettable"] is True
    assert line["unit"] == "g"
    # need: 500 g + 300 g = 800 g; stock 200 g compatible -> shortfall 600 g
    assert line["quantity"] == pytest.approx(600.0)


def test_generate_applies_multipliers_per_recipe(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Sugar", "quantity": 100, "unit": "g"}])
    gl = _mk_grocery(auth_client, [rid], multipliers={rid: 3})
    line = _line_by_norm(gl["items"], "sugar")
    assert line["quantity"] == pytest.approx(300.0)
    assert line["unit"] == "g"


def test_to_taste_ingredient_survives_multiplier_scaling(auth_client: TestClient) -> None:
    """A to-taste ingredient (`quantity=None`) must never hit `None * multiplier`
    (R-1) and emits a `quantity=null, unit=null` line (§4.3 "entirely to taste")."""
    rid = _mk_recipe(auth_client, [{"item": "Salt", "quantity": None, "unit": None}])
    gl = _mk_grocery(auth_client, [rid], multipliers={rid: 3})

    line = _line_by_norm(gl["items"], "salt")
    assert line["quantity"] is None
    assert line["unit"] is None
    assert line["nettable"] is False
    assert line["source"] == "generated"


def test_food_cooked_to_zero_stock_still_produces_full_need_line(
    auth_client: TestClient,
) -> None:
    """A `quantity_base=0` inventory row is not positive stock — the §4.3 "no
    positive stock at all" branch fires: full need, canonical, `nettable=true`."""
    row = _add_inventory(auth_client, "Tomatoes", 2, "can")
    patched = auth_client.patch(
        f"/api/inventory/{row['id']}", json={"quantity": 0, "unit": "can"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["quantity_base"] == 0

    rid = _mk_recipe(auth_client, [{"item": "Tomatoes", "quantity": 2, "unit": "can"}])
    gl = _mk_grocery(auth_client, [rid])

    line = _line_by_norm(gl["items"], "tomato")
    assert line["quantity"] == pytest.approx(2.0)
    assert line["unit"] == "can"
    assert line["nettable"] is True


def test_n3_incompatible_stock_present_makes_the_shortfall_non_nettable(
    auth_client: TestClient,
) -> None:
    """#N3: need 3 can, stock 1 can + 1 jar -> a 2 can line, `nettable=false`."""
    _add_inventory(auth_client, "Tomatoes", 1, "can")
    _add_inventory(auth_client, "Tomatoes", 1, "jar")
    rid = _mk_recipe(auth_client, [{"item": "Tomatoes", "quantity": 3, "unit": "can"}])

    gl = _mk_grocery(auth_client, [rid])
    line = _line_by_norm(gl["items"], "tomato")
    assert line["quantity"] == pytest.approx(2.0)
    assert line["unit"] == "can"
    assert line["nettable"] is False


def test_n3_only_compatible_stock_is_nettable(auth_client: TestClient) -> None:
    """#N3: need 3 can, stock 1 can only (no incompatible bucket) -> `nettable=true`."""
    _add_inventory(auth_client, "Tomatoes", 1, "can")
    rid = _mk_recipe(auth_client, [{"item": "Tomatoes", "quantity": 3, "unit": "can"}])

    gl = _mk_grocery(auth_client, [rid])
    line = _line_by_norm(gl["items"], "tomato")
    assert line["quantity"] == pytest.approx(2.0)
    assert line["unit"] == "can"
    assert line["nettable"] is True


def test_fully_covered_requirement_emits_no_line(auth_client: TestClient) -> None:
    _add_inventory(auth_client, "Tomatoes", 5, "can")
    rid = _mk_recipe(auth_client, [{"item": "Tomatoes", "quantity": 2, "unit": "can"}])
    gl = _mk_grocery(auth_client, [rid])
    assert gl["items"] == []


# ===========================================================================
# Read + delete
# ===========================================================================


def test_get_single_list_and_unknown_is_404(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 1, "unit": "kg"}])
    gid = _mk_grocery(auth_client, [rid])["id"]

    resp = auth_client.get(f"/api/grocery/{gid}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == gid

    assert auth_client.get("/api/grocery/999999").status_code == 404


def test_list_grocery_lists_orders_newest_first_and_filters_by_status(
    auth_client: TestClient,
) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 1, "unit": "kg"}])
    first = _mk_grocery(auth_client, [rid], name="First")["id"]
    second = _mk_grocery(auth_client, [rid], name="Second")["id"]

    all_lists = auth_client.get("/api/grocery").json()
    ids = [gl["id"] for gl in all_lists]
    assert ids.index(second) < ids.index(first)  # created_at DESC, id DESC

    active_only = auth_client.get("/api/grocery", params={"status": "active"}).json()
    assert {gl["id"] for gl in active_only} == {first, second}

    archived_only = auth_client.get("/api/grocery", params={"status": "archived"}).json()
    assert archived_only == []


def test_delete_grocery_list_cascades_items(
    auth_client: TestClient, test_engine: Engine
) -> None:
    rid = _mk_recipe(
        auth_client,
        [
            {"item": "Flour", "quantity": 1, "unit": "kg"},
            {"item": "Sugar", "quantity": 1, "unit": "kg"},
        ],
    )
    gid = _mk_grocery(auth_client, [rid])["id"]
    assert _item_row_count(test_engine, gid) == 2

    resp = auth_client.delete(f"/api/grocery/{gid}")
    assert resp.status_code == 204, resp.text
    assert _item_row_count(test_engine) == 0
    assert auth_client.get(f"/api/grocery/{gid}").status_code == 404


def test_delete_unknown_grocery_list_is_404(auth_client: TestClient) -> None:
    assert auth_client.delete("/api/grocery/999999").status_code == 404


# ===========================================================================
# Manual item add + line editing (N6) + line delete (phase-6c)
# ===========================================================================


def _add_item(client: TestClient, gid: int, **body: object) -> dict:
    resp = client.post(f"/api/grocery/{gid}/items", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _patch_item(client: TestClient, gid: int, item_id: int, **body: object):
    return client.patch(f"/api/grocery/{gid}/items/{item_id}", json=body)


def test_manual_item_add_stores_amounts_as_typed(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 1, "unit": "kg"}])
    gid = _mk_grocery(auth_client, [rid])["id"]

    item = _add_item(auth_client, gid, item="Bay leaf", quantity=3, unit="leaf")
    assert item["item"] == "Bay leaf"
    assert item["normalized_name"] == "bay leaf"
    assert item["quantity"] == pytest.approx(3.0)
    assert item["unit"] == "leaf"
    assert item["source"] == "manual"
    assert item["nettable"] is True
    assert item["checked"] is False
    assert item["added_to_inventory"] is False


def test_manual_item_add_to_unknown_list_is_404(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/grocery/999999/items", json={"item": "Salt", "quantity": None, "unit": None}
    )
    assert resp.status_code == 404


def test_checking_off_a_line_does_not_touch_inventory(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = _patch_item(auth_client, gid, line["id"], checked=True)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checked"] is True
    assert body["checked_at"] is not None
    assert body["added_to_inventory"] is False

    assert auth_client.get("/api/inventory").json() == []


def test_n6_unit_only_patch_on_generated_line_is_422(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")
    assert line["quantity"] == pytest.approx(500.0)
    assert line["unit"] == "g"

    resp = _patch_item(auth_client, gid, line["id"], unit="kg")
    assert resp.status_code == 422
    assert "quantity and unit must be set together" in resp.text


def test_n6_quantity_only_patch_on_generated_line_is_422(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = _patch_item(auth_client, gid, line["id"], quantity=200)
    assert resp.status_code == 422
    assert "quantity and unit must be set together" in resp.text


def test_n6_quantity_and_unit_patch_reclassifies_to_manual(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = _patch_item(auth_client, gid, line["id"], quantity=0.5, unit="kg")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity"] == pytest.approx(0.5)  # stored as typed, no conversion
    assert body["unit"] == "kg"
    assert body["source"] == "manual"
    assert body["nettable"] is True


def test_n6_item_edit_on_non_nettable_generated_line_reclassifies_to_manual(
    auth_client: TestClient,
) -> None:
    """#N3-style non-nettable generated line: an `item` edit still reclassifies
    and recomputes `normalized_name` (N6)."""
    _add_inventory(auth_client, "Tomatoes", 1, "can")
    _add_inventory(auth_client, "Tomatoes", 1, "jar")
    rid = _mk_recipe(auth_client, [{"item": "Tomatoes", "quantity": 3, "unit": "can"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "tomato")
    assert line["nettable"] is False

    resp = _patch_item(auth_client, gid, line["id"], item="almond flour")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["item"] == "almond flour"
    assert body["normalized_name"] == "almond flour"
    assert body["source"] == "manual"
    assert body["nettable"] is True


def test_n6_checked_only_patch_does_not_reclassify(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = _patch_item(auth_client, gid, line["id"], checked=True)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "generated"
    assert body["nettable"] is True
    assert body["quantity"] == pytest.approx(500.0)
    assert body["unit"] == "g"


def test_patch_item_to_null_is_422(auth_client: TestClient) -> None:
    """`item` is typed nullable in `GroceryListItemUpdate` (spec.md §5.6), but a
    line's substance can't sensibly go null -- explicit `{"item": null}` is
    rejected rather than violating the non-nullable `item` column."""
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = _patch_item(auth_client, gid, line["id"], item=None)
    assert resp.status_code == 422
    assert "item cannot be null" in resp.text


def test_patch_unknown_list_or_line_is_404(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    assert _patch_item(auth_client, 999999, line["id"], checked=True).status_code == 404
    assert _patch_item(auth_client, gid, 999999, checked=True).status_code == 404


def test_delete_unfrozen_line_is_204(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    resp = auth_client.delete(f"/api/grocery/{gid}/items/{line['id']}")
    assert resp.status_code == 204, resp.text
    assert auth_client.get(f"/api/grocery/{gid}").json()["items"] == []


def test_delete_unknown_list_or_line_is_404(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    assert auth_client.delete(f"/api/grocery/999999/items/{line['id']}").status_code == 404
    assert auth_client.delete(f"/api/grocery/{gid}/items/999999").status_code == 404


# ===========================================================================
# Submit (phase-6d)
# ===========================================================================


def _submit(client: TestClient, gid: int):
    return client.post(f"/api/grocery/{gid}/submit")


def _inventory_row(client: TestClient, normalized_name: str, unit_bucket: str) -> dict | None:
    rows = [
        r
        for r in client.get("/api/inventory").json()
        if r["normalized_name"] == normalized_name and r["unit_bucket"] == unit_bucket
    ]
    assert len(rows) <= 1, rows
    return rows[0] if rows else None


def test_submit_applies_the_edited_value_not_the_generated_one(
    auth_client: TestClient,
) -> None:
    """Edit a generated `500 g` line to `0.5 kg` before checking it: submit
    applies the edited value, not the original generated one."""
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")

    _patch_item(auth_client, gid, line["id"], quantity=0.5, unit="kg")
    _patch_item(auth_client, gid, line["id"], checked=True)

    resp = _submit(auth_client, gid)
    assert resp.status_code == 200, resp.text
    row = _inventory_row(auth_client, "flour", "mass")
    assert row is not None
    assert row["quantity_base"] == pytest.approx(500.0)  # 0.5 kg canonical, not 500 kg


def test_submit_freezes_the_line_and_raises_inventory(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")
    _patch_item(auth_client, gid, line["id"], checked=True)

    resp = _submit(auth_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "flour")
    assert out["added_to_inventory"] is True
    assert out["applied_quantity"] == pytest.approx(500.0)
    assert out["applied_unit"] == "g"
    row = _inventory_row(auth_client, "flour", "mass")
    assert row is not None
    assert row["quantity_base"] == pytest.approx(500.0)


def test_patch_and_delete_a_frozen_line_are_409(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")
    _patch_item(auth_client, gid, line["id"], checked=True)
    assert _submit(auth_client, gid).status_code == 200

    assert _patch_item(auth_client, gid, line["id"], checked=False).status_code == 409
    assert auth_client.delete(f"/api/grocery/{gid}/items/{line['id']}").status_code == 409


def test_unchecking_before_submit_is_a_no_op(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")
    _patch_item(auth_client, gid, line["id"], checked=True)
    _patch_item(auth_client, gid, line["id"], checked=False)

    resp = _submit(auth_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "flour")
    assert out["added_to_inventory"] is False
    assert _inventory_row(auth_client, "flour", "mass") is None


def test_submit_does_not_archive_and_a_further_check_resubmits_only_the_new_line(
    auth_client: TestClient,
) -> None:
    """`submit` never changes `list.status`, and is forward-only: checking a
    further line and re-submitting applies only the newly-eligible one."""
    rid = _mk_recipe(
        auth_client,
        [
            {"item": "Flour", "quantity": 500, "unit": "g"},
            {"item": "Sugar", "quantity": 200, "unit": "g"},
        ],
    )
    gid = _mk_grocery(auth_client, [rid])["id"]
    items = auth_client.get(f"/api/grocery/{gid}").json()["items"]
    flour = _line_by_norm(items, "flour")
    sugar = _line_by_norm(items, "sugar")

    _patch_item(auth_client, gid, flour["id"], checked=True)
    first = _submit(auth_client, gid)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "active"  # submit never archives

    _patch_item(auth_client, gid, sugar["id"], checked=True)
    second = _submit(auth_client, gid)
    assert second.status_code == 200, second.text
    out_items = second.json()["items"]
    assert _line_by_norm(out_items, "flour")["added_to_inventory"] is True
    assert _line_by_norm(out_items, "sugar")["added_to_inventory"] is True
    assert _inventory_row(auth_client, "flour", "mass")["quantity_base"] == pytest.approx(500.0)
    assert _inventory_row(auth_client, "sugar", "mass")["quantity_base"] == pytest.approx(200.0)


def test_submit_with_nothing_checked_is_a_200_no_op(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]

    resp = _submit(auth_client, gid)
    assert resp.status_code == 200, resp.text
    out = _line_by_norm(resp.json()["items"], "flour")
    assert out["added_to_inventory"] is False
    assert _inventory_row(auth_client, "flour", "mass") is None


def test_sequential_double_submit_is_idempotent(auth_client: TestClient) -> None:
    """Submitting the same already-applied (frozen) line again does not
    double-add it into inventory."""
    rid = _mk_recipe(auth_client, [{"item": "Flour", "quantity": 500, "unit": "g"}])
    gid = _mk_grocery(auth_client, [rid])["id"]
    line = _line_by_norm(auth_client.get(f"/api/grocery/{gid}").json()["items"], "flour")
    _patch_item(auth_client, gid, line["id"], checked=True)

    first = _submit(auth_client, gid)
    second = _submit(auth_client, gid)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    row = _inventory_row(auth_client, "flour", "mass")
    assert row is not None
    assert row["quantity_base"] == pytest.approx(500.0)


def test_submit_unknown_list_is_404(auth_client: TestClient) -> None:
    assert _submit(auth_client, 999999).status_code == 404
