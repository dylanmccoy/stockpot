"""Global cook-log reads — `routers/cook_logs.py`, prefix `/api/cook-logs` (spec.md §5.4).

Companion to `test_cook_contract.py` (the locked R-7 oracle, which covers the
per-recipe `POST /cook` + `GET /api/recipes/{id}/cook-logs` surface). This file
covers only the Phase 5c additions:

* `GET /api/cook-logs` — newest-first pagination across every recipe
  (`limit` / `offset` / `total`), and the `422` at the range edges.
* `GET /api/cook-logs/{log_id}` — one row by id, `404` when absent.
* Both reads outlive the recipe: after `DELETE /api/recipes/{id}` the log still
  resolves with `recipe_id` null and the `recipe_title` snapshot intact.
* Auth is required on both.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _mk_recipe(client: TestClient, title: str) -> int:
    resp = client.post("/api/recipes", json={"title": title, "ingredients": []})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _cook(client: TestClient, recipe_id: int) -> dict:
    """Log-only cook (`deduct=false`) so no inventory setup is needed."""
    resp = client.post(f"/api/recipes/{recipe_id}/cook", json={"deduct": False})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# GET /api/cook-logs — the global feed
# --------------------------------------------------------------------------- #


def test_global_feed_is_newest_first_across_recipes(auth_client: TestClient) -> None:
    r1 = _mk_recipe(auth_client, "Soup")
    r2 = _mk_recipe(auth_client, "Stew")

    # Interleave cooks between the two recipes; capture creation order.
    created = [
        _cook(auth_client, r1)["id"],
        _cook(auth_client, r2)["id"],
        _cook(auth_client, r1)["id"],
        _cook(auth_client, r2)["id"],
        _cook(auth_client, r1)["id"],
    ]

    body = auth_client.get("/api/cook-logs").json()
    assert body["total"] == 5
    assert body["limit"] == 50
    assert body["offset"] == 0
    got = [row["id"] for row in body["items"]]
    # `cooked_at DESC, id DESC` — timestamps may tie, so id is the real tiebreak;
    # newest-created id comes first.
    assert got == sorted(created, reverse=True)
    # Feed spans both recipes.
    assert {row["recipe_id"] for row in body["items"]} == {r1, r2}


def test_pagination_windows_the_feed(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, "Curry")
    ids_newest_first = [_cook(auth_client, rid)["id"] for _ in range(5)][::-1]

    page1 = auth_client.get("/api/cook-logs?limit=2&offset=0").json()
    assert page1["total"] == 5
    assert page1["limit"] == 2 and page1["offset"] == 0
    assert [r["id"] for r in page1["items"]] == ids_newest_first[0:2]

    page2 = auth_client.get("/api/cook-logs?limit=2&offset=2").json()
    assert page2["total"] == 5
    assert [r["id"] for r in page2["items"]] == ids_newest_first[2:4]

    page3 = auth_client.get("/api/cook-logs?limit=2&offset=4").json()
    assert [r["id"] for r in page3["items"]] == ids_newest_first[4:5]

    # offset past the end is an empty page, not an error; total still full count.
    past = auth_client.get("/api/cook-logs?limit=2&offset=99").json()
    assert past["items"] == [] and past["total"] == 5


def test_empty_feed(auth_client: TestClient) -> None:
    body = auth_client.get("/api/cook-logs").json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_limit_and_offset_range_is_enforced(auth_client: TestClient) -> None:
    for query in ("limit=0", "limit=201", "limit=-1", "offset=-1"):
        resp = auth_client.get(f"/api/cook-logs?{query}")
        assert resp.status_code == 422, f"{query}: {resp.text}"

    # The inclusive edges are accepted.
    assert auth_client.get("/api/cook-logs?limit=1&offset=0").status_code == 200
    assert auth_client.get("/api/cook-logs?limit=200").status_code == 200


def test_global_feed_requires_auth(client: TestClient) -> None:
    assert client.get("/api/cook-logs").status_code == 401


# --------------------------------------------------------------------------- #
# GET /api/cook-logs/{log_id} — by-id detail
# --------------------------------------------------------------------------- #


def test_get_one_by_id(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, "Chili")
    posted = _cook(auth_client, rid)

    got = auth_client.get(f"/api/cook-logs/{posted['id']}")
    assert got.status_code == 200
    assert got.json() == posted


def test_get_one_404_when_absent(auth_client: TestClient) -> None:
    assert auth_client.get("/api/cook-logs/999999").status_code == 404


def test_get_one_requires_auth(client: TestClient) -> None:
    assert client.get("/api/cook-logs/1").status_code == 401


# --------------------------------------------------------------------------- #
# Both reads survive recipe deletion (spec.md §1, §5.4)
# --------------------------------------------------------------------------- #


def test_reads_resolve_after_the_recipe_is_deleted(auth_client: TestClient) -> None:
    rid = _mk_recipe(auth_client, "Ragu")
    log_id = _cook(auth_client, rid)["id"]

    assert auth_client.delete(f"/api/recipes/{rid}").status_code == 204

    detail = auth_client.get(f"/api/cook-logs/{log_id}").json()
    assert detail["recipe_id"] is None
    assert detail["recipe_title"] == "Ragu"  # snapshot stands

    feed = auth_client.get("/api/cook-logs").json()
    assert feed["total"] == 1
    (row,) = feed["items"]
    assert row["id"] == log_id
    assert row["recipe_id"] is None
    assert row["recipe_title"] == "Ragu"
