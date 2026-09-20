"""C2-05: changing home (DEMOCRACY.md §2.3 "Changing home", §10.3 ballot
eligibility)."""

from __future__ import annotations

from backend.db import session_scope
from backend.models import City
from backend.tests.conftest import make_umbrella, make_user, set_setting


async def _open_ballot(client, admin, *, level, entity_id, author, tag):
    """One dominant, qualified solution -> prepare -> open, in one
    community, authored and upvoted by `author` alone (so `author` is
    excluded from that community's jury pool and never gets drawn)."""
    umbrella = await make_umbrella(
        name=f"Home-change test problem ({tag})",
        statement="A test problem statement.",
        level=level,
        entity_id=entity_id,
    )
    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=author["headers"],
        json={"text": "A concrete proposed solution, long enough to pass validation."},
    )
    assert created.status_code == 201, created.text
    solution_id = created.json()["id"]
    vote = await client.put(
        "/votes",
        headers=author["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    assert vote.status_code == 200, vote.text

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
    return cycle_id, item_id


async def test_the_first_home_change_is_free(client):
    user = await make_user(client, email="firstmover@example.com", display_name="FirstMover")
    changed = await client.post(
        "/me/home", headers=user["headers"], json={"county_id": 2, "city_id": 2}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json() == {"county_id": 2, "city_id": 2, "message": changed.json()["message"]}


async def test_a_second_change_inside_the_cooldown_is_refused_with_the_date(client):
    user = await make_user(client, email="cooldown@example.com", display_name="Cooldown")
    first = await client.post(
        "/me/home", headers=user["headers"], json={"county_id": 2, "city_id": 2}
    )
    assert first.status_code == 200

    second = await client.post(
        "/me/home", headers=user["headers"], json={"county_id": 1, "city_id": 1}
    )
    assert second.status_code == 409
    assert second.json()["error"] == "home_change_refused"
    assert "again on" in second.json()["message"]

    status = (await client.get("/me/home", headers=user["headers"])).json()
    assert status["next_change_allowed_at"] is not None
    assert "again on" in status["refused_now_reason"]


async def test_cooldown_is_read_from_settings_not_a_constant(client):
    await set_setting("home_change_cooldown_days", "1")
    user = await make_user(client, email="shortcooldown@example.com", display_name="ShortCooldown")
    await client.post("/me/home", headers=user["headers"], json={"county_id": 2, "city_id": 2})
    status = (await client.get("/me/home", headers=user["headers"])).json()
    assert "every 1 days" in status["refused_now_reason"]


async def test_a_juror_finishes_service_before_moving(client):
    await set_setting("ballot_min_dominant_days", "0")
    umbrella = await make_umbrella(
        name="Jury Hold Home Change", statement="A test problem.", level="city", entity_id=1
    )
    admin = await make_user(
        client, email="jury-admin@example.com", display_name="JuryAdmin", admin=True
    )
    author = await make_user(client, email="jury-author@example.com", display_name="JuryAuthor")
    juror = await make_user(client, email="jury-juror@example.com", display_name="JuryJuror")

    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=author["headers"],
        json={"text": "A solution the juror will end up serving on."},
    )
    solution_id = created.json()["id"]
    await client.put(
        "/votes",
        headers=juror["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )

    prepared = await client.post(
        "/admin/cycles/prepare", headers=admin["headers"], json={"level": "city", "entity_id": 1}
    )
    cycle_id = prepared.json()["cycle_id"]
    duties = (await client.get("/juries/mine", headers=juror["headers"])).json()["duties"]
    assert duties, "the juror fixture must actually draw the test juror"

    refused = await client.post(
        "/me/home", headers=juror["headers"], json={"county_id": 2, "city_id": 2}
    )
    assert refused.status_code == 409
    assert refused.json()["error"] == "home_change_refused"
    assert "jury" in refused.json()["message"]

    # Once the cycle is published, the juror is free to move.
    opened = await client.post(f"/admin/cycles/{cycle_id}/open", headers=admin["headers"])
    assert opened.status_code == 200
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0]["ballot_item_id"]
    await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote", headers=juror["headers"], json={"choice": "yes"}
    )
    await client.post(f"/admin/cycles/{cycle_id}/close", headers=admin["headers"])
    published = await client.post(f"/admin/cycles/{cycle_id}/publish", headers=admin["headers"])
    assert published.status_code == 200

    now_allowed = await client.post(
        "/me/home", headers=juror["headers"], json={"county_id": 2, "city_id": 2}
    )
    assert now_allowed.status_code == 200, now_allowed.text


async def test_moving_mid_ballot_sits_it_out_in_old_and_new_city_but_not_county_or_state(client):
    await set_setting("ballot_min_dominant_days", "0")
    admin = await make_user(
        client, email="move-admin@example.com", display_name="MoveAdmin", admin=True
    )
    mover = await make_user(client, email="mover@example.com", display_name="Mover")
    city_b_resident = await make_user(
        client, email="cityb-resident@example.com", display_name="CityBResident", city_id=1
    )

    async with session_scope() as session:
        city_b = City(county_id=1, name="Second City In Santa Clara", incorporated=True)
        session.add(city_b)
        await session.flush()
        city_b_id = city_b.id

    me = (await client.get("/auth/me", headers=mover["headers"])).json()
    state_id = next(c["entity_id"] for c in me["home_communities"] if c["level"] == "state")

    city_a_cycle, city_a_item = await _open_ballot(
        client, admin, level="city", entity_id=1, author=mover, tag="city-a"
    )
    county_cycle, county_item = await _open_ballot(
        client, admin, level="county", entity_id=1, author=mover, tag="county"
    )
    state_cycle, state_item = await _open_ballot(
        client, admin, level="state", entity_id=state_id, author=mover, tag="state"
    )

    # city B's solution and ballot must be prepared by someone who is
    # already a member of city B *before* the mover moves in.
    async with session_scope() as session:
        from backend.repositories import users as users_repo

        row = await users_repo.get(session, city_b_resident["id"])
        row.city_id = city_b_id
        await session.flush()
    city_b_cycle, city_b_item = await _open_ballot(
        client, admin, level="city", entity_id=city_b_id, author=city_b_resident, tag="city-b"
    )

    moved = await client.post(
        "/me/home", headers=mover["headers"], json={"county_id": 1, "city_id": city_b_id}
    )
    assert moved.status_code == 200, moved.text

    # Old city: no longer a member at all.
    old_city_vote = await client.put(
        f"/cycles/{city_a_cycle}/ballot/{city_a_item}/vote",
        headers=mover["headers"],
        json={"choice": "yes"},
    )
    assert old_city_vote.status_code == 403
    assert old_city_vote.json()["error"] == "not_a_member"

    # New city: a member now, but joined after this ballot was prepared.
    new_city_vote = await client.put(
        f"/cycles/{city_b_cycle}/ballot/{city_b_item}/vote",
        headers=mover["headers"],
        json={"choice": "yes"},
    )
    assert new_city_vote.status_code == 403
    assert new_city_vote.json()["error"] == "joined_after_prepare"

    # County: unchanged by the move, membership dates to signup.
    county_vote = await client.put(
        f"/cycles/{county_cycle}/ballot/{county_item}/vote",
        headers=mover["headers"],
        json={"choice": "yes"},
    )
    assert county_vote.status_code == 200, county_vote.text

    # California: never affected by any move.
    state_vote = await client.put(
        f"/cycles/{state_cycle}/ballot/{state_item}/vote",
        headers=mover["headers"],
        json={"choice": "yes"},
    )
    assert state_vote.status_code == 200, state_vote.text


async def test_a_move_before_prepare_is_accepted(client):
    await set_setting("ballot_min_dominant_days", "0")
    admin = await make_user(
        client, email="early-admin@example.com", display_name="EarlyAdmin", admin=True
    )
    early_mover = await make_user(client, email="early-mover@example.com", display_name="EarlyMover")

    async with session_scope() as session:
        city_b = City(county_id=1, name="Third City In Santa Clara", incorporated=True)
        session.add(city_b)
        await session.flush()
        city_b_id = city_b.id

    moved = await client.post(
        "/me/home", headers=early_mover["headers"], json={"county_id": 1, "city_id": city_b_id}
    )
    assert moved.status_code == 200, moved.text

    cycle_id, item_id = await _open_ballot(
        client, admin, level="city", entity_id=city_b_id, author=early_mover, tag="early"
    )
    vote = await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=early_mover["headers"],
        json={"choice": "yes"},
    )
    assert vote.status_code == 200, vote.text


async def test_old_votes_and_posts_are_untouched_by_a_move(client):
    from backend.clients import ollama as ollama_client
    from backend.tests.conftest import labeler_answer, settle_jobs

    umbrella = await make_umbrella(
        name="Untouched By A Move", statement="A test problem.", level="city", entity_id=1
    )
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    author = await make_user(client, email="untouched@example.com", display_name="Untouched")
    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "A problem reported before this author moves away from this city.",
            "solutions": ["A solution proposed before the move."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201
    await settle_jobs()
    post_id = created.json()["id"]

    moved = await client.post(
        "/me/home", headers=author["headers"], json={"county_id": 2, "city_id": 2}
    )
    assert moved.status_code == 200, moved.text

    after = (await client.get(f"/posts/{post_id}")).json()
    assert after["communities"][0]["community"]["level"] == "city"
    assert after["communities"][0]["community"]["entity_id"] == 1, (
        "a post stays exactly where it was made, regardless of a later move (Law 6)"
    )
