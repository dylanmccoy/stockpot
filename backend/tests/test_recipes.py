"""Recipe CRUD contract (spec.md §5.2, §7).

Everything goes through HTTP on `auth_client`. The two places that reach into
the engine directly are checking for rows the API deliberately cannot show —
orphaned ingredient children after a PUT or a DELETE.
"""

import inspect
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.routers import recipes as recipes_router


def _ingredient_row_count(engine: Engine, recipe_id: int | None = None) -> int:
    sql = "SELECT count(*) FROM recipe_ingredients"
    params: dict = {}
    if recipe_id is not None:
        sql += " WHERE recipe_id = :rid"
        params["rid"] = recipe_id
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_recipes_without_auth_returns_401(client: TestClient) -> None:
    """Recipe routes are gated by authentication."""
    assert client.get("/api/recipes").status_code == 401
    assert client.post("/api/recipes", json={"title": "Test"}).status_code == 401


def test_create_and_list_recipe(auth_client: TestClient) -> None:
    payload = {
        "title": "Pancakes",
        "notes": "Weekend breakfast.",
        "prep_time": 10,
        "cook_time": 15,
        "servings": 4,
        "cuisine": "American",
        "source_url": "grandma's index card",
        "tags": ["breakfast", "quick"],
        "steps": ["Mix.", "Fry."],
        "ingredients": ["1 1/2 cups flour", "3 large eggs", "salt to taste"],
    }
    created = auth_client.post("/api/recipes", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["id"] > 0
    assert body["title"] == "Pancakes"
    assert body["notes"] == "Weekend breakfast."
    assert body["prep_time"] == 10
    assert body["cook_time"] == 15
    assert body["servings"] == 4
    assert body["cuisine"] == "American"
    assert body["source_url"] == "grandma's index card"
    assert body["tags"] == ["breakfast", "quick"]
    assert body["steps"] == ["Mix.", "Fry."]
    assert body["photo_path"] is None
    assert body["created_by"]["username"] == "tester"

    listed = auth_client.get("/api/recipes")
    assert listed.status_code == 200
    assert [r["title"] for r in listed.json()] == ["Pancakes"]


def test_list_orders_newest_first(auth_client: TestClient) -> None:
    """`created_at DESC, id DESC` — the id tiebreak matters because three
    same-request-fast creates can share a timestamp."""
    for title in ("first", "second", "third"):
        assert auth_client.post("/api/recipes", json={"title": title}).status_code == 201

    assert [r["title"] for r in auth_client.get("/api/recipes").json()] == [
        "third",
        "second",
        "first",
    ]


def test_string_ingredients_are_parsed_and_keep_raw_text(auth_client: TestClient) -> None:
    body = auth_client.post(
        "/api/recipes",
        json={
            "title": "Parsed",
            "ingredients": ["2 tbsp olive oil", "1 (14 oz) can tomatoes", "salt to taste"],
        },
    ).json()
    oil, tomatoes, salt = body["ingredients"]

    assert [i["position"] for i in body["ingredients"]] == [0, 1, 2]

    assert oil["quantity"] == 2.0
    assert oil["unit"] == "tbsp"
    assert oil["item"] == "olive oil"
    assert oil["note"] is None
    assert oil["normalized_name"] == "olive oil"
    assert oil["raw_text"] == "2 tbsp olive oil"

    assert tomatoes["quantity"] == 1.0
    assert tomatoes["unit"] == "can"
    assert tomatoes["item"] == "tomatoes"
    assert tomatoes["note"] == "14 oz"
    assert tomatoes["normalized_name"] == "tomato"
    assert tomatoes["raw_text"] == "1 (14 oz) can tomatoes"

    # A to-taste line: no quantity, and the note records why.
    assert salt["quantity"] is None
    assert salt["note"] == "to taste"
    assert salt["item"] == "salt"


def test_object_ingredients_store_no_raw_text(auth_client: TestClient) -> None:
    body = auth_client.post(
        "/api/recipes",
        json={
            "title": "Structured",
            "ingredients": [
                {"quantity": 500, "unit": "g", "item": "Plain Flour", "note": "sifted"}
            ],
        },
    ).json()
    (flour,) = body["ingredients"]

    assert flour["position"] == 0
    assert flour["quantity"] == 500
    assert flour["unit"] == "g"
    assert flour["item"] == "Plain Flour"
    assert flour["note"] == "sifted"
    assert flour["normalized_name"] == "plain flour"
    assert flour["raw_text"] is None


def test_blank_string_ingredients_are_skipped(auth_client: TestClient) -> None:
    """Positions stay contiguous across the skipped elements."""
    body = auth_client.post(
        "/api/recipes",
        json={"title": "Sparse", "ingredients": ["", "  ", "2 eggs", "\t\n", "1 cup milk"]},
    ).json()

    assert [i["item"] for i in body["ingredients"]] == ["eggs", "milk"]
    assert [i["position"] for i in body["ingredients"]] == [0, 1]


def test_mixed_string_and_object_elements_share_one_position_sequence(
    auth_client: TestClient,
) -> None:
    body = auth_client.post(
        "/api/recipes",
        json={
            "title": "Mixed",
            "ingredients": [
                "2 tbsp olive oil",
                {"quantity": 3, "unit": "cloves", "item": "garlic"},
                "salt to taste",
            ],
        },
    ).json()

    assert [i["position"] for i in body["ingredients"]] == [0, 1, 2]
    assert [i["raw_text"] for i in body["ingredients"]] == [
        "2 tbsp olive oil",
        None,
        "salt to taste",
    ]


def test_author_unit_normalizes_identically_on_both_input_paths(
    auth_client: TestClient,
) -> None:
    """`{"unit": "Tbsp."}` and the pasted line `2 Tbsp. butter` persist the same
    author's unit — lower-cased, one trailing `.` stripped, never singularized."""
    body = auth_client.post(
        "/api/recipes",
        json={
            "title": "Butter",
            "ingredients": [
                {"quantity": 2, "unit": "Tbsp.", "item": "butter"},
                "2 Tbsp. butter",
                {"quantity": 1, "unit": "cups", "item": "milk"},
            ],
        },
    ).json()
    structured, pasted, plural = body["ingredients"]

    assert structured["unit"] == "tbsp"
    assert pasted["unit"] == "tbsp"
    assert structured["unit"] == pasted["unit"]
    # No singularization: the stored unit is display text.
    assert plural["unit"] == "cups"


def test_degenerate_object_unit_becomes_null(auth_client: TestClient) -> None:
    """`""` and `"."` carry no unit once normalized."""
    body = auth_client.post(
        "/api/recipes",
        json={
            "title": "Unitless",
            "ingredients": [
                {"quantity": 1, "unit": "", "item": "egg"},
                {"quantity": 1, "unit": ".", "item": "lemon"},
            ],
        },
    ).json()

    assert [i["unit"] for i in body["ingredients"]] == [None, None]


def test_object_ingredient_requires_a_non_empty_item(auth_client: TestClient) -> None:
    whitespace = auth_client.post(
        "/api/recipes",
        json={"title": "Blank item", "ingredients": [{"quantity": 1, "item": "   "}]},
    )
    assert whitespace.status_code == 422
    assert whitespace.json()["detail"] == "ingredient object requires a non-empty item"

    missing = auth_client.post(
        "/api/recipes", json={"title": "No item", "ingredients": [{"quantity": 1}]}
    )
    assert missing.status_code == 422


def test_unknown_ingredient_key_is_rejected_by_name(auth_client: TestClient) -> None:
    """`extra="forbid"` on `RecipeIngredientIn`: a mistyped key must not return
    201 with a silently to-taste row (spec.md §5.2)."""
    response = auth_client.post(
        "/api/recipes",
        json={"title": "Typo", "ingredients": [{"item": "flour", "qty": 500}]},
    )
    assert response.status_code == 422, response.text
    assert "qty" in response.text
    assert auth_client.get("/api/recipes").json() == []


def test_pasted_line_over_200_chars_is_truncated_before_parsing(
    auth_client: TestClient,
) -> None:
    """R-4: the single length guard. The recipe still creates, and every stored
    string field fits its column."""
    line = "2 cups " + ("x" * 400)
    response = auth_client.post(
        "/api/recipes", json={"title": "Long", "ingredients": [line]}
    )
    assert response.status_code == 201, response.text
    (row,) = response.json()["ingredients"]

    assert row["raw_text"] == line[:200]
    assert len(row["raw_text"]) == 200
    assert row["quantity"] == 2.0
    assert row["unit"] == "cups"
    assert len(row["item"]) <= 200
    assert row["note"] is None or len(row["note"]) <= 200
    assert len(row["normalized_name"]) <= 200


def test_object_item_over_200_chars_is_rejected_not_truncated(
    auth_client: TestClient,
) -> None:
    """Only pasted lines are truncated; object elements are Pydantic-bounded."""
    response = auth_client.post(
        "/api/recipes",
        json={"title": "Long item", "ingredients": [{"item": "x" * 201}]},
    )
    assert response.status_code == 422


def test_title_only_recipe_is_legal(auth_client: TestClient) -> None:
    """Zero-content recipes are legal, permanently — capture now, fill later."""
    response = auth_client.post("/api/recipes", json={"title": "Someday"})
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["ingredients"] == []
    assert body["steps"] == []
    assert body["tags"] == []
    assert body["notes"] == ""


def test_get_update_delete_recipe(auth_client: TestClient) -> None:
    recipe_id = auth_client.post("/api/recipes", json={"title": "Soup"}).json()["id"]

    assert auth_client.get(f"/api/recipes/{recipe_id}").json()["title"] == "Soup"

    updated = auth_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Tomato Soup", "steps": ["boil"], "ingredients": ["3 cans tomatoes"]},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Tomato Soup"
    assert updated.json()["steps"] == ["boil"]

    assert auth_client.delete(f"/api/recipes/{recipe_id}").status_code == 204
    assert auth_client.get(f"/api/recipes/{recipe_id}").status_code == 404


def test_put_replaces_ingredients_without_leaving_orphans(
    auth_client: TestClient, test_engine: Engine
) -> None:
    recipe_id = auth_client.post(
        "/api/recipes",
        json={"title": "Stew", "ingredients": ["1 onion", "2 carrots", "3 cans tomatoes"]},
    ).json()["id"]
    assert _ingredient_row_count(test_engine) == 3

    replaced = auth_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Stew", "ingredients": ["1 potato"]},
    )
    assert replaced.status_code == 200
    assert [i["item"] for i in replaced.json()["ingredients"]] == ["potato"]
    assert [i["position"] for i in replaced.json()["ingredients"]] == [0]

    # No orphans: the whole table holds exactly the one surviving row.
    assert _ingredient_row_count(test_engine) == 1
    assert auth_client.get(f"/api/recipes/{recipe_id}").json()["ingredients"] == (
        replaced.json()["ingredients"]
    )


def test_put_to_an_empty_ingredient_list_clears_the_children(
    auth_client: TestClient, test_engine: Engine
) -> None:
    recipe_id = auth_client.post(
        "/api/recipes", json={"title": "Stew", "ingredients": ["1 onion"]}
    ).json()["id"]

    cleared = auth_client.put(f"/api/recipes/{recipe_id}", json={"title": "Stew"})
    assert cleared.status_code == 200
    assert cleared.json()["ingredients"] == []
    assert _ingredient_row_count(test_engine) == 0


def test_ingredient_ids_may_churn_on_put(auth_client: TestClient) -> None:
    """No API contract depends on ingredient ID stability; positions are the
    stable handle."""
    created = auth_client.post(
        "/api/recipes", json={"title": "Churn", "ingredients": ["1 onion", "2 carrots"]}
    ).json()

    replaced = auth_client.put(
        f"/api/recipes/{created['id']}",
        json={"title": "Churn", "ingredients": ["1 onion", "2 carrots"]},
    ).json()

    assert [i["item"] for i in replaced["ingredients"]] == ["onion", "carrots"]
    assert [i["position"] for i in replaced["ingredients"]] == [0, 1]


def test_delete_cascades_ingredients(auth_client: TestClient, test_engine: Engine) -> None:
    recipe_id = auth_client.post(
        "/api/recipes", json={"title": "Doomed", "ingredients": ["1 onion", "2 carrots"]}
    ).json()["id"]
    assert _ingredient_row_count(test_engine, recipe_id) == 2

    assert auth_client.delete(f"/api/recipes/{recipe_id}").status_code == 204
    assert _ingredient_row_count(test_engine) == 0


def test_delete_missing_recipe_is_404(auth_client: TestClient) -> None:
    assert auth_client.delete("/api/recipes/9999").status_code == 404
    assert auth_client.put("/api/recipes/9999", json={"title": "Ghost"}).status_code == 404


def test_ingredient_positions_are_stable_across_reads(auth_client: TestClient) -> None:
    items = ["1 onion", "2 carrots", "3 cans tomatoes", "salt to taste", "1 bay leaf"]
    recipe_id = auth_client.post(
        "/api/recipes", json={"title": "Stew", "ingredients": items}
    ).json()["id"]

    detail = auth_client.get(f"/api/recipes/{recipe_id}").json()["ingredients"]
    listed = auth_client.get("/api/recipes").json()[0]["ingredients"]

    assert [i["position"] for i in detail] == [0, 1, 2, 3, 4]
    assert detail == listed


def test_create_recipe_rejects_blank_title(auth_client: TestClient) -> None:
    assert auth_client.post("/api/recipes", json={"title": ""}).status_code == 422


def test_recipe_write_handlers_never_commit() -> None:
    """spec.md §6: routers never call `commit()` — `get_db` owns the single
    unit of work and its rollback is what makes a failed request leave nothing
    persisted. A handler that commits (or `refresh()`es, reopening a second
    `BEGIN IMMEDIATE`) breaks that guarantee. Lock the rule at the source so a
    regression fails here rather than silently in production."""
    for name in ("create_recipe", "update_recipe", "delete_recipe"):
        src = inspect.getsource(getattr(recipes_router, name))
        assert ".commit(" not in src, f"{name} must not call commit()"
        assert ".refresh(" not in src, f"{name} must not call refresh()"


def test_update_is_atomic_with_the_request_transaction(auth_client: TestClient) -> None:
    """A recipe update and any same-request failure resolve together: the client
    sees the write only after the request transaction commits, and the row
    round-trips through a fresh request unchanged."""
    recipe_id = auth_client.post("/api/recipes", json={"title": "Draft"}).json()["id"]

    updated = auth_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Final", "ingredients": ["1 tsp salt"], "steps": ["stir"]},
    )
    assert updated.status_code == 200

    # New request == new session == reads only committed state.
    roundtrip = auth_client.get(f"/api/recipes/{recipe_id}").json()
    assert roundtrip["title"] == "Final"
    assert roundtrip["steps"] == ["stir"]
    assert [i["item"] for i in roundtrip["ingredients"]] == ["salt"]


def _assert_explicit_utc(value: str) -> datetime:
    assert value.endswith("+00:00") or value.endswith("Z"), value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def test_recipe_timestamps_carry_an_explicit_utc_offset(auth_client: TestClient) -> None:
    """`created_at` / `updated_at` round-trip through SQLite with their offset
    intact (spec.md §Mechanical defaults, §3.2 `UtcDateTime`)."""
    created = auth_client.post("/api/recipes", json={"title": "Timestamped"})
    assert created.status_code == 201, created.text
    body = created.json()

    _assert_explicit_utc(body["created_at"])
    _assert_explicit_utc(body["updated_at"])

    # Same value on a re-read through a fresh session.
    reread = auth_client.get(f"/api/recipes/{body['id']}").json()
    assert reread["created_at"] == body["created_at"]
    assert reread["updated_at"] == body["updated_at"]


def test_created_at_equals_updated_at_on_create_and_a_put_advances_it(
    auth_client: TestClient,
) -> None:
    created = auth_client.post("/api/recipes", json={"title": "Fresh"}).json()
    assert created["created_at"] == created["updated_at"]

    updated = auth_client.put(
        f"/api/recipes/{created['id']}", json={"title": "Revised"}
    ).json()

    assert updated["created_at"] == created["created_at"]
    assert _assert_explicit_utc(updated["updated_at"]) > _assert_explicit_utc(
        updated["created_at"]
    )


def test_put_that_only_changes_ingredients_still_advances_updated_at(
    auth_client: TestClient,
) -> None:
    """The `recipes` row itself stays clean here, so a bare `onupdate` would not
    fire."""
    created = auth_client.post(
        "/api/recipes", json={"title": "Same title", "ingredients": ["1 onion"]}
    ).json()

    updated = auth_client.put(
        f"/api/recipes/{created['id']}",
        json={"title": "Same title", "ingredients": ["2 onions"]},
    ).json()

    assert _assert_explicit_utc(updated["updated_at"]) > _assert_explicit_utc(
        created["updated_at"]
    )


def test_created_by_is_not_reassigned_on_update(auth_client: TestClient) -> None:
    created = auth_client.post("/api/recipes", json={"title": "Attributed"}).json()
    updated = auth_client.put(
        f"/api/recipes/{created['id']}", json={"title": "Still attributed"}
    ).json()

    assert updated["created_by"] == created["created_by"]
    assert updated["created_by"]["username"] == "tester"


def test_tags_and_steps_round_trip_as_sent(auth_client: TestClient) -> None:
    """Stored as sent — no dedupe, no case-fold (spec.md §Mechanical defaults)."""
    tags = ["Dinner", "dinner", "quick"]
    steps = ["Preheat.", "Bake.", "Preheat."]
    body = auth_client.post(
        "/api/recipes", json={"title": "Bake", "tags": tags, "steps": steps}
    ).json()

    assert body["tags"] == tags
    assert body["steps"] == steps
    assert auth_client.get(f"/api/recipes/{body['id']}").json()["tags"] == tags


# --------------------------------------------------------------------------- #
# Availability — GET /api/recipes/{id}/availability (spec.md §5.3, §7).
# --------------------------------------------------------------------------- #


def _availability_recipe(auth_client: TestClient) -> int:
    """A recipe with a canonical-unit line, a to-taste line, and a second
    quantified line whose stock is driven to zero — one recipe covering the
    `ok` / `to_taste` / `missing` branches under `multiplier=2`."""
    return auth_client.post(
        "/api/recipes",
        json={
            "title": "Availability fixture",
            "ingredients": [
                {"item": "Flour", "quantity": 1, "unit": "kg"},
                "salt to taste",
                {"item": "Sugar", "quantity": 200, "unit": "g"},
            ],
        },
    ).json()["id"]


def test_availability_scales_by_multiplier_and_reports_canonical_groups(
    auth_client: TestClient,
) -> None:
    recipe_id = _availability_recipe(auth_client)

    # Flour: 2000 g in stock — exactly covers 1 kg * 2.
    auth_client.post("/api/inventory", json={"item": "Flour", "quantity": 2000, "unit": "g"})
    # Sugar: added then driven to quantity_base = 0 (zero stock is absent, §7).
    sugar = auth_client.post(
        "/api/inventory", json={"item": "Sugar", "quantity": 500, "unit": "g"}
    ).json()
    assert (
        auth_client.patch(
            f"/api/inventory/{sugar['id']}", json={"quantity": 0, "unit": "g"}
        ).status_code
        == 200
    )

    report = auth_client.get(f"/api/recipes/{recipe_id}/availability?multiplier=2")
    assert report.status_code == 200, report.text
    body = report.json()

    assert body["recipe_id"] == recipe_id
    assert body["multiplier"] == 2.0
    assert body["all_available"] is False  # Sugar is missing

    lines = {line["item"]: line for line in body["lines"]}

    flour = lines["Flour"]
    assert flour["status"] == "ok"
    assert flour["need"] == 2000.0  # 1 kg * 2, in the group's canonical unit
    assert flour["need_unit"] == "g"
    assert flour["group_unit"] == "g"
    assert flour["group_need"] == 2000.0
    assert flour["group_have"] == 2000.0
    assert flour["group_short"] == 0.0
    # The per-line shape carries only `group_*` aggregates, never bare have/short.
    assert "have" not in flour
    assert "short" not in flour

    salt = lines["salt"]
    assert salt["status"] == "to_taste"  # survived `* 2` with no TypeError
    assert salt["need"] is None
    assert salt["group_need"] is None
    assert salt["group_have"] is None
    assert salt["group_short"] is None

    sugar_line = lines["Sugar"]
    assert sugar_line["status"] == "missing"  # quantity_base == 0 is absent
    assert sugar_line["need"] == 400.0  # 200 g * 2
    assert sugar_line["group_have"] == 0.0
    assert sugar_line["group_short"] == 400.0


def test_availability_of_a_title_only_recipe_is_empty_and_all_available(
    auth_client: TestClient,
) -> None:
    recipe_id = auth_client.post("/api/recipes", json={"title": "Nothing yet"}).json()["id"]

    body = auth_client.get(f"/api/recipes/{recipe_id}/availability").json()

    assert body["lines"] == []
    assert body["all_available"] is True
    assert body["multiplier"] == 1.0


def test_availability_of_a_missing_recipe_is_404(auth_client: TestClient) -> None:
    assert auth_client.get("/api/recipes/999999/availability").status_code == 404
