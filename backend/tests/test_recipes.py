from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_and_list_recipe(client: TestClient) -> None:
    payload = {
        "title": "Pancakes",
        "ingredients": "flour, eggs, milk",
        "instructions": "Mix and fry.",
    }
    created = client.post("/api/recipes", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["id"] > 0
    assert body["title"] == "Pancakes"

    listed = client.get("/api/recipes")
    assert listed.status_code == 200
    assert [r["title"] for r in listed.json()] == ["Pancakes"]


def test_get_update_delete_recipe(client: TestClient) -> None:
    recipe_id = client.post("/api/recipes", json={"title": "Soup"}).json()["id"]

    assert client.get(f"/api/recipes/{recipe_id}").json()["title"] == "Soup"

    updated = client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Tomato Soup", "ingredients": "tomato", "instructions": "boil"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Tomato Soup"

    assert client.delete(f"/api/recipes/{recipe_id}").status_code == 204
    assert client.get(f"/api/recipes/{recipe_id}").status_code == 404


def test_create_recipe_rejects_blank_title(client: TestClient) -> None:
    assert client.post("/api/recipes", json={"title": ""}).status_code == 422
