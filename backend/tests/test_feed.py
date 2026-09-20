"""feed-v1 (DEMOCRACY.md §12.1): search plus the four plain sorts."""

from __future__ import annotations

import pytest

from backend.tests.conftest import make_umbrella, make_user


@pytest.fixture
async def world(client):
    umbrella = await make_umbrella(name="Streetlights", statement="Streets are dark at night.")
    author = await make_user(client, email="author@example.com", display_name="Author")
    voters = [
        await make_user(client, email=f"voter{i}@example.com", display_name=f"Voter{i}")
        for i in range(4)
    ]
    return {"umbrella": umbrella, "author": author, "voters": voters}


async def _post(client, author, umbrella_id, *, problem_text, solution_text):
    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": problem_text,
            "solutions": [solution_text],
            "communities": [{"level": "city", "entity_id": 1, "umbrella_id": umbrella_id}],
            "category_choice": "author_selected",
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]
    detail = (await client.get(f"/posts/{post_id}")).json()
    solution_id = detail["communities"][0]["solution_ids"][0]
    return post_id, solution_id


async def _vote(client, user, solution_id, direction):
    response = await client.put(
        "/votes",
        headers=user["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": direction},
    )
    assert response.status_code == 200, response.text


async def _comment(client, user, solution_id, text):
    response = await client.post(
        "/comments",
        headers=user["headers"],
        json={"target_type": "solution", "target_id": solution_id, "text": text},
    )
    assert response.status_code == 201, response.text


async def _unvote(client, user, solution_id):
    response = await client.request(
        "DELETE",
        "/votes",
        headers=user["headers"],
        json={"target_type": "solution", "target_id": solution_id},
    )
    assert response.status_code == 200, response.text


async def test_each_sort_orders_by_its_declared_rule(client, world):
    umbrella, author, voters = world["umbrella"], world["author"], world["voters"]

    p1, s1 = await _post(
        client, author, umbrella,
        problem_text="The streetlight on Elm Street has been out for a month now.",
        solution_text="Replace the bulb and add it to the maintenance schedule.",
    )
    p2, s2 = await _post(
        client, author, umbrella,
        problem_text="Three more streetlights went dark on Oak Avenue last week.",
        solution_text="Send a crew to replace all three bulbs this week.",
    )
    p3, s3 = await _post(
        client, author, umbrella,
        problem_text="The crosswalk light at Pine and Third is flickering badly.",
        solution_text="Replace the flickering ballast before it fails completely.",
    )

    # Votes: p1 gets 3 (regardless of direction), p2 gets 1, p3 gets 0.
    await _vote(client, voters[0], s1, 1)
    await _vote(client, voters[1], s1, -1)
    await _vote(client, voters[2], s1, 1)
    await _vote(client, voters[0], s2, 1)

    # Comments: p2 gets 2, p3 gets 1, p1 gets 0. Discussion only opens on a
    # dominant solution (DEMOCRACY §6), so p3 is voted up just long enough to
    # comment, then the vote is withdrawn — its final vote_count stays 0.
    await _comment(client, voters[0], s2, "This has been a problem for weeks.")
    await _comment(client, voters[1], s2, "Agreed, it is very dark there at night.")
    await _vote(client, voters[3], s3, 1)
    await _comment(client, voters[0], s3, "Please fix this before someone is hurt.")
    await _unvote(client, voters[3], s3)

    newest = (await client.get("/feed?sort=newest")).json()
    assert [item["id"] for item in newest["items"]] == [p3, p2, p1]
    assert newest["sort"] == "newest"
    assert newest["ranking"] == "feed-v1"

    oldest = (await client.get("/feed?sort=oldest")).json()
    assert [item["id"] for item in oldest["items"]] == [p1, p2, p3]

    most_votes = (await client.get("/feed?sort=most_votes")).json()
    assert [item["id"] for item in most_votes["items"]] == [p1, p2, p3]
    by_id = {item["id"]: item for item in most_votes["items"]}
    assert by_id[p1]["vote_count"] == 3
    assert by_id[p2]["vote_count"] == 1
    assert by_id[p3]["vote_count"] == 0

    most_comments = (await client.get("/feed?sort=most_comments")).json()
    assert [item["id"] for item in most_comments["items"]] == [p2, p3, p1]
    by_id = {item["id"]: item for item in most_comments["items"]}
    assert by_id[p2]["comment_count"] == 2
    assert by_id[p3]["comment_count"] == 1
    assert by_id[p1]["comment_count"] == 0

    # Every card shows both counts, whatever the active sort.
    assert "vote_count" in newest["items"][0] and "comment_count" in newest["items"][0]


async def test_most_votes_counts_a_downvote_the_same_as_an_upvote(client, world):
    umbrella, author, voters = world["umbrella"], world["author"], world["voters"]

    up_heavy, s_up = await _post(
        client, author, umbrella,
        problem_text="The park restroom near the playground has been locked for weeks.",
        solution_text="Reopen it and put it on the daily cleaning round.",
    )
    down_heavy, s_down = await _post(
        client, author, umbrella,
        problem_text="The dog park gate latch is broken and does not stay closed.",
        solution_text="Replace the latch with a self-closing one.",
    )

    await _vote(client, voters[0], s_up, 1)
    await _vote(client, voters[1], s_up, 1)
    await _vote(client, voters[0], s_down, -1)
    await _vote(client, voters[1], s_down, -1)

    result = (await client.get("/feed?sort=most_votes&limit=2")).json()
    counts = {item["id"]: item["vote_count"] for item in result["items"]}
    assert counts[up_heavy] == 2
    assert counts[down_heavy] == 2, "a downvote must count the same as an upvote"


async def test_search_matches_problem_text_and_solution_text_without_reordering(client, world):
    umbrella, author, voters = world["umbrella"], world["author"], world["voters"]

    in_problem, s1 = await _post(
        client, author, umbrella,
        problem_text="A wombat has been spotted digging up the community garden beds.",
        solution_text="Install a low fence around the garden beds.",
    )
    in_solution, s2 = await _post(
        client, author, umbrella,
        problem_text="Something keeps digging holes in the community garden at night.",
        solution_text="Set up a motion light; it may be a wombat or a raccoon.",
    )
    unrelated, _ = await _post(
        client, author, umbrella,
        problem_text="The picnic tables in the park are splintering and need sanding.",
        solution_text="Sand and reseal every picnic table this spring.",
    )

    # Give the search-matched posts different vote counts to show sort order
    # (not relevance) still decides the order among matches.
    await _vote(client, voters[0], s1, 1)
    await _vote(client, voters[1], s1, 1)
    await _vote(client, voters[0], s2, 1)

    found = (await client.get("/feed?q=wombat&sort=most_votes")).json()
    ids = [item["id"] for item in found["items"]]
    assert set(ids) == {in_problem, in_solution}
    assert unrelated not in ids
    assert ids == [in_problem, in_solution], "search filters; the active sort still orders"


async def test_scope_all_widens_beyond_home_communities(client, world):
    umbrella, author = world["umbrella"], world["author"]
    outsider = await make_user(
        client, email="outsider@example.com", display_name="Outsider", city_id=2, county_id=2
    )

    post_id, _ = await _post(
        client, author, umbrella,
        problem_text="A water main break has flooded the intersection at 5th and Main.",
        solution_text="Dispatch a repair crew and post detour signage immediately.",
    )

    home_only = (
        await client.get("/feed", headers=outsider["headers"])
    ).json()
    assert post_id not in [item["id"] for item in home_only["items"]]
    assert home_only["filters"]["scope"] == "home"

    widened = (
        await client.get("/feed?scope=all", headers=outsider["headers"])
    ).json()
    assert post_id in [item["id"] for item in widened["items"]]
    assert widened["filters"]["scope"] == "all"


async def test_pagination_across_two_pages_for_a_date_sort_and_a_count_sort(client, world):
    umbrella, author, voters = world["umbrella"], world["author"], world["voters"]

    posts = []
    for i in range(3):
        post_id, solution_id = await _post(
            client, author, umbrella,
            problem_text=f"Pothole number {i} has opened up on Maple Street this week.",
            solution_text=f"Patch pothole {i} before it grows any larger.",
        )
        for voter in voters[: i + 1]:
            await _vote(client, voter, solution_id, 1)
        posts.append(post_id)

    # Date sort (newest): posts[2], posts[1], posts[0].
    first = (await client.get("/feed?sort=newest&limit=2")).json()
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    second = (
        await client.get(f"/feed?sort=newest&limit=2&cursor={first['next_cursor']}")
    ).json()
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    seen = [item["id"] for item in first["items"]] + [item["id"] for item in second["items"]]
    assert seen == [posts[2], posts[1], posts[0]]

    # Count sort (most_votes): posts[2] has 3 votes, posts[1] has 2, posts[0] has 1.
    v_first = (await client.get("/feed?sort=most_votes&limit=2")).json()
    assert len(v_first["items"]) == 2
    assert v_first["next_cursor"] is not None
    v_second = (
        await client.get(f"/feed?sort=most_votes&limit=2&cursor={v_first['next_cursor']}")
    ).json()
    assert len(v_second["items"]) == 1
    assert v_second["next_cursor"] is None
    v_seen = [item["id"] for item in v_first["items"]] + [item["id"] for item in v_second["items"]]
    assert v_seen == [posts[2], posts[1], posts[0]]
    assert len(set(v_seen)) == 3, "no post repeated or skipped across count-sort pages"
