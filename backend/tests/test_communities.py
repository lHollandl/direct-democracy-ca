"""Unincorporated residents (change/02, C2-02): `communities.py::home_communities`
is the one function that derives membership, and every place that checks
membership uses it. An unincorporated resident belongs to two communities —
county and California — never a city."""

from __future__ import annotations

from backend.tests.conftest import make_umbrella, make_user, set_setting


async def _walk_community(client, *, level, entity_id, county_id, admin, tag):
    """post a solution -> vote -> comment -> ballot, all as one unincorporated
    resident, entirely inside one community."""
    umbrella = await make_umbrella(
        name=f"Test problem ({tag})",
        statement="A test problem statement for the walkthrough.",
        level=level,
        entity_id=entity_id,
    )
    resident = await make_user(
        client,
        email=f"uninc-{tag}@example.com",
        display_name=f"UnincResident{tag.title()}",
        city_id=None,
        county_id=county_id,
    )
    voters = [
        await make_user(
            client,
            email=f"uninc-{tag}-v{i}@example.com",
            display_name=f"UnincVoter{tag.title()}{i}",
            city_id=None,
            county_id=county_id,
        )
        for i in range(1)
    ]

    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=resident["headers"],
        json={
            "text": "A concrete proposed solution to the test problem, long "
            "enough to pass the minimum length check."
        },
    )
    assert created.status_code == 201, created.text
    solution_id = created.json()["id"]

    for voter in voters:
        vote = await client.put(
            "/votes",
            headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )
        assert vote.status_code == 200, vote.text

    comment = await client.post(
        "/comments",
        headers=resident["headers"],
        json={
            "target_type": "umbrella",
            "target_id": umbrella,
            "text": "A comment from an unincorporated resident.",
        },
    )
    assert comment.status_code == 201, comment.text

    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=admin["headers"],
        json={"level": level, "entity_id": entity_id},
    )
    assert prepared.status_code == 200, prepared.text
    cycle_id = prepared.json()["cycle_id"]

    opened = await client.post(f"/admin/cycles/{cycle_id}/open", headers=admin["headers"])
    assert opened.status_code == 200, opened.text

    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]
    ballot_vote = await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=resident["headers"],
        json={"choice": "yes"},
    )
    assert ballot_vote.status_code == 200, ballot_vote.text

    return resident, umbrella


async def test_unincorporated_resident_walks_post_vote_comment_ballot_in_county_and_state(
    client,
):
    await set_setting("ballot_min_dominant_days", "0")
    admin = await make_user(
        client, email="uninc-admin@example.com", display_name="UnincAdmin", admin=True
    )

    probe = await make_user(
        client,
        email="uninc-probe@example.com",
        display_name="UnincProbe",
        city_id=None,
        county_id=1,
    )
    me = (await client.get("/auth/me", headers=probe["headers"])).json()
    assert {c["level"] for c in me["home_communities"]} == {"county", "state"}, (
        "an unincorporated resident is a member of exactly two communities "
        "(DEMOCRACY.md §2.3)"
    )
    state_id = next(c["entity_id"] for c in me["home_communities"] if c["level"] == "state")

    resident_county, _ = await _walk_community(
        client, level="county", entity_id=1, county_id=1, admin=admin, tag="county"
    )
    resident_state, _ = await _walk_community(
        client, level="state", entity_id=state_id, county_id=1, admin=admin, tag="state"
    )

    # --- refused in any city ----------------------------------------------
    city_umbrella = await make_umbrella(
        name="City-only problem", statement="A city-scoped problem.", level="city", entity_id=1
    )
    refused_solution = await client.post(
        f"/umbrellas/{city_umbrella}/solutions",
        headers=resident_county["headers"],
        json={"text": "This should be refused: the resident has no city membership."},
    )
    assert refused_solution.status_code == 403
    assert refused_solution.json()["error"] == "not_a_member"

    refused_comment = await client.post(
        "/comments",
        headers=resident_state["headers"],
        json={
            "target_type": "umbrella",
            "target_id": city_umbrella,
            "text": "Also refused: no city membership.",
        },
    )
    assert refused_comment.status_code == 403
    assert refused_comment.json()["error"] == "not_a_member"

    refused_post = await client.post(
        "/posts",
        headers=resident_county["headers"],
        json={
            "problem_text": "An unincorporated resident tries to post in a city they "
            "are not a member of.",
            "solutions": ["A solution that should never be created."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert refused_post.status_code == 403
    assert refused_post.json()["error"] == "not_a_member"
