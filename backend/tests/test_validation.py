"""Numeric-bound validation on the request surface (spec.md §7, `test_validation.py`).

Phase 3 owns the recipe half of that row. The inventory `POST`/`PATCH`, `cook`
`multiplier`, grocery `multipliers`, and `availability?multiplier=` cases land
with the phases that add those endpoints (4-6).

The non-finite cases are sent as the raw JSON literals `Infinity` / `NaN` rather
than through `json=`: httpx encodes with `allow_nan=False` and would refuse to
serialize them client-side, so the request would never reach the bound under
test. Python's `json.loads` — what Starlette parses with — accepts them, so the
server really does see a non-finite float, and `allow_inf_nan=False` on the
schema is what rejects it.
"""


import pytest
from fastapi.testclient import TestClient

# JSON literals a quantity must never accept: zero, negative, and the two
# non-finite floats. `null` is legitimate (to taste) and is covered in
# `test_recipes.py`.
REJECTED_QUANTITIES = ["0", "-1", "-0.5", "Infinity", "-Infinity", "NaN"]


def _send_raw(client: TestClient, method: str, url: str, body: str):
    """Send a hand-built JSON body, bypassing httpx's `allow_nan=False`."""
    return client.request(
        method, url, content=body, headers={"Content-Type": "application/json"}
    )


@pytest.mark.parametrize("quantity", REJECTED_QUANTITIES)
def test_recipe_ingredient_quantity_rejects_non_positive_and_non_finite(
    auth_client: TestClient, quantity: str
) -> None:
    response = _send_raw(
        auth_client,
        "POST",
        "/api/recipes",
        '{"title": "Bad quantity", "ingredients": [{"item": "flour", "quantity": %s}]}'
        % quantity,
    )
    assert response.status_code == 422, response.text
    # Nothing was written on the way to the rejection.
    assert auth_client.get("/api/recipes").json() == []


@pytest.mark.parametrize("quantity", REJECTED_QUANTITIES)
def test_recipe_ingredient_quantity_bound_also_applies_to_put(
    auth_client: TestClient, quantity: str
) -> None:
    created = auth_client.post(
        "/api/recipes", json={"title": "Good", "ingredients": [{"item": "flour", "quantity": 1}]}
    ).json()

    response = _send_raw(
        auth_client,
        "PUT",
        f"/api/recipes/{created['id']}",
        '{"title": "Good", "ingredients": [{"item": "flour", "quantity": %s}]}' % quantity,
    )
    assert response.status_code == 422, response.text

    # The rejected PUT left the stored ingredient untouched.
    assert auth_client.get(f"/api/recipes/{created['id']}").json()["ingredients"] == (
        created["ingredients"]
    )


@pytest.mark.parametrize("servings", REJECTED_QUANTITIES)
def test_recipe_servings_rejects_non_positive_and_non_finite(
    auth_client: TestClient, servings: str
) -> None:
    response = _send_raw(
        auth_client,
        "POST",
        "/api/recipes",
        '{"title": "Bad servings", "servings": %s}' % servings,
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["prep_time", "cook_time"])
def test_recipe_times_reject_negative_minutes(auth_client: TestClient, field: str) -> None:
    assert (
        auth_client.post("/api/recipes", json={"title": "Bad time", field: -1}).status_code
        == 422
    )
    # Zero is a legitimate answer to "how long does the prep take".
    assert (
        auth_client.post("/api/recipes", json={"title": "No time", field: 0}).status_code
        == 201
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "x" * 201),
        ("cuisine", "x" * 101),
        ("source_url", "x" * 501),
        ("tags", ["x" * 51]),
        ("tags", ["tag"] * 101),
        ("steps", ["x" * 2001]),
        ("steps", ["step"] * 101),
    ],
)
def test_recipe_string_and_list_bounds_are_enforced(
    auth_client: TestClient, field: str, value: object
) -> None:
    response = auth_client.post("/api/recipes", json={"title": "Bounded", field: value})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tags", ["x" * 50]),
        ("tags", ["tag"] * 100),
        ("steps", ["x" * 2000]),
        ("steps", ["step"] * 100),
    ],
)
def test_recipe_list_bounds_accept_their_maximum(
    auth_client: TestClient, field: str, value: object
) -> None:
    """The caps are inclusive — 100 items of 50/2000 chars is legal."""
    response = auth_client.post("/api/recipes", json={"title": "At the cap", field: value})
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("field", ["unit", "note"])
def test_ingredient_object_string_bounds_are_enforced(
    auth_client: TestClient, field: str
) -> None:
    over = {"unit": "x" * 31, "note": "x" * 201}[field]
    response = auth_client.post(
        "/api/recipes",
        json={"title": "Bounded", "ingredients": [{"item": "flour", field: over}]},
    )
    assert response.status_code == 422, response.text


# Inventory `quantity` is `>= 0` (zero is legitimate), so `"0"` is dropped from
# the rejected set here — `test_inventory.py` asserts zero is a 201.
REJECTED_INVENTORY_QUANTITIES = ["-1", "-0.5", "Infinity", "-Infinity", "NaN"]


@pytest.mark.parametrize("quantity", REJECTED_INVENTORY_QUANTITIES)
def test_inventory_post_quantity_rejects_negative_and_non_finite(
    auth_client: TestClient, quantity: str
) -> None:
    response = _send_raw(
        auth_client,
        "POST",
        "/api/inventory",
        '{"item": "Flour", "quantity": %s, "unit": "kg"}' % quantity,
    )
    assert response.status_code == 422, response.text
    assert auth_client.get("/api/inventory").json() == []


@pytest.mark.parametrize("quantity", REJECTED_INVENTORY_QUANTITIES)
def test_inventory_patch_quantity_rejects_negative_and_non_finite(
    auth_client: TestClient, quantity: str
) -> None:
    """`>= 0`, `allow_inf_nan=False` on the PATCH body too. `"0"` stays out of the
    rejected set — spec §5.5 does `max(body.quantity, 0.0)`, so a PATCH to zero is
    a 200 (`test_inventory.py::test_patch_quantity_zero_is_accepted`)."""
    created = auth_client.post(
        "/api/inventory", json={"item": "Flour", "quantity": 1, "unit": "kg"}
    ).json()
    response = _send_raw(
        auth_client,
        "PATCH",
        f"/api/inventory/{created['id']}",
        '{"quantity": %s, "unit": "kg"}' % quantity,
    )
    assert response.status_code == 422, response.text
    # The rejected PATCH left the stored quantity untouched.
    assert auth_client.get("/api/inventory").json()[0]["quantity_base"] == 1000.0


# `availability?multiplier=` — `Query(1.0, gt=0)`, `allow_inf_nan=False`
# (spec.md §5.3). Same rejected set as a recipe quantity: zero, negative, and the
# two non-finite floats. It rides in the query string, so no raw-body helper.
@pytest.mark.parametrize("multiplier", ["0", "-1", "-0.5", "inf", "-inf", "nan"])
def test_availability_multiplier_rejects_non_positive_and_non_finite(
    auth_client: TestClient, multiplier: str
) -> None:
    recipe_id = auth_client.post("/api/recipes", json={"title": "Scale me"}).json()["id"]

    response = auth_client.get(
        f"/api/recipes/{recipe_id}/availability", params={"multiplier": multiplier}
    )
    assert response.status_code == 422, response.text
