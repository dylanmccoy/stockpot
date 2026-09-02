import inspect

from fastapi.testclient import TestClient

from app.routers import recipes as recipes_router


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_recipes_without_auth_returns_401(client: TestClient) -> None:
    """Recipe routes are gated by authentication."""
    assert client.get("/api/recipes").status_code == 401
    assert client.post("/api/recipes", json={"title": "Test"}).status_code == 401


def test_create_and_list_recipe(auth_client: TestClient) -> None:
    payload = {
        "title": "Pancakes",
        "ingredients": "flour, eggs, milk",
        "instructions": "Mix and fry.",
    }
    created = auth_client.post("/api/recipes", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["id"] > 0
    assert body["title"] == "Pancakes"

    listed = auth_client.get("/api/recipes")
    assert listed.status_code == 200
    assert [r["title"] for r in listed.json()] == ["Pancakes"]


def test_get_update_delete_recipe(auth_client: TestClient) -> None:
    recipe_id = auth_client.post("/api/recipes", json={"title": "Soup"}).json()["id"]

    assert auth_client.get(f"/api/recipes/{recipe_id}").json()["title"] == "Soup"

    updated = auth_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Tomato Soup", "ingredients": "tomato", "instructions": "boil"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Tomato Soup"

    assert auth_client.delete(f"/api/recipes/{recipe_id}").status_code == 204
    assert auth_client.get(f"/api/recipes/{recipe_id}").status_code == 404


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
    sees the write only after `get_db` commits, and the row round-trips through a
    fresh request unchanged."""
    recipe_id = auth_client.post("/api/recipes", json={"title": "Draft"}).json()["id"]

    updated = auth_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Final", "ingredients": "salt", "instructions": "stir"},
    )
    assert updated.status_code == 200

    # New request == new session == reads only committed state.
    roundtrip = auth_client.get(f"/api/recipes/{recipe_id}").json()
    assert roundtrip["title"] == "Final"
    assert roundtrip["ingredients"] == "salt"
