"""FX-05, change/02 fix-1: `GET /posts/mine` (ARCHITECTURE.md §6) — the
"Your posts" section on `/me`."""

from __future__ import annotations

from backend.tests.conftest import labeler_answer, make_umbrella, make_user, settle_jobs


async def _make_post(client, user, *, problem_text: str) -> int:
    created = await client.post(
        "/posts",
        headers=user["headers"],
        json={
            "problem_text": problem_text,
            "solutions": ["A solution long enough to satisfy the validator here."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_my_posts_lists_only_the_caller_s_own_posts_newest_first(client):
    mine = await make_user(client, email="mine@example.com", display_name="Mine")
    someone_else = await make_user(client, email="else@example.com", display_name="ElseUser")

    first = await _make_post(client, mine, problem_text="The first problem this author ever wrote down.")
    second = await _make_post(client, mine, problem_text="The second problem this author ever wrote down.")
    await _make_post(client, someone_else, problem_text="A problem belonging to a completely different author.")
    await settle_jobs()

    response = await client.get("/posts/mine", headers=mine["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert ids == [second, first], "newest first, and only this author's posts"


async def test_my_posts_never_returns_another_user_s_posts(client):
    author = await make_user(client, email="owner@example.com", display_name="Owner")
    outsider = await make_user(client, email="outsider@example.com", display_name="Outsider")
    await _make_post(client, author, problem_text="A problem only its own author should see listed.")
    await settle_jobs()

    response = await client.get("/posts/mine", headers=outsider["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


async def test_my_posts_paginates(client):
    user = await make_user(client, email="paginate@example.com", display_name="Paginate")
    for i in range(3):
        await _make_post(client, user, problem_text=f"Problem number {i} written for the pagination test.")
    await settle_jobs()

    over_limit = await client.get("/posts/mine?limit=500", headers=user["headers"])
    assert over_limit.status_code == 422

    first = (await client.get("/posts/mine?limit=2", headers=user["headers"])).json()
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None

    second = (
        await client.get(
            f"/posts/mine?limit=2&cursor={first['next_cursor']}", headers=user["headers"]
        )
    ).json()
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None

    seen = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
    assert len(seen) == 3, "no post repeated or skipped across pages"


async def test_my_posts_includes_filing_words_and_a_link_per_community(client):
    from backend.clients import ollama as ollama_client

    umbrella = await make_umbrella(
        name="Mine Umbrella", statement="A test umbrella for the my-posts endpoint."
    )
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    user = await make_user(client, email="filed@example.com", display_name="Filed")
    post_id = await _make_post(client, user, problem_text="A problem that the labeler will file under an umbrella.")
    await settle_jobs()

    response = await client.get("/posts/mine", headers=user["headers"])
    assert response.status_code == 200, response.text
    item = next(i for i in response.json()["items"] if i["id"] == post_id)
    community = item["communities"][0]
    assert community["umbrella_id"] == umbrella
    assert community["label_status"] == "Filed"
    assert community["link"] == f"/umbrellas/{umbrella}"
