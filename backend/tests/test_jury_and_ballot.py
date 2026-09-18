"""The jury and the ballot in the cases the documents single out (DEMOCRACY §8, §10)."""

from __future__ import annotations

import pytest

from backend.db import session_scope
from backend.repositories import cycles as cycles_repo
from backend.tests.conftest import make_umbrella, make_user, set_setting


async def _dominant_solution(client, author, voters, umbrella) -> int:
    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=author["headers"],
        json={"text": "Reopen the restrooms and put them on the daily cleaning round."},
    )
    solution_id = created.json()["id"]
    for voter in voters:
        await client.put(
            "/votes",
            headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )
    return solution_id


@pytest.fixture
async def town(client):
    await set_setting("ballot_min_dominant_days", "0")
    umbrella = await make_umbrella(name="Parks", statement="Park restrooms are locked.")
    director = await make_user(client, email="dir@example.com", display_name="Dir", admin=True)
    people = [
        await make_user(client, email=f"p{i}@example.com", display_name=f"Person{i}")
        for i in range(5)
    ]
    return {"umbrella": umbrella, "director": director, "people": people}


async def test_the_draw_excludes_authors_and_administrators_and_is_logged(client, town):
    author = town["people"][0]
    solution_id = await _dominant_solution(client, author, town["people"][1:], town["umbrella"])

    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert prepared.status_code == 200
    cycle_id = prepared.json()["cycle_id"]

    async with session_scope() as session:
        jury = await cycles_repo.jury_for_cycle(session, cycle_id)
        jurors = await cycles_repo.jurors(session, jury.id)
        pool = set(jury.eligible_pool)
        assert author["id"] not in pool, "the author of a qualified solution cannot judge it"
        assert town["director"]["id"] not in pool, "administrators are not drawn"
        assert len(jury.random_bytes) == 64, "the draw records the randomness it used"
        assert jury.size_requested == 3
        assert len(jurors) == 3
        assert {j.user_id for j in jurors} <= pool


async def test_declining_draws_a_replacement_immediately(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    drawn = []
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties:
            drawn.append((person, duties[0]["juror_id"]))
    assert len(drawn) == 3

    person, juror_id = drawn[0]
    declined = await client.post(f"/jurors/{juror_id}/decline", headers=person["headers"])
    assert declined.status_code == 200
    assert declined.json()["replacement_drawn"] is True

    async with session_scope() as session:
        jury = await cycles_repo.jury_for_cycle(session, cycle_id)
        jurors = await cycles_repo.jurors(session, jury.id)
        assert len(jurors) == 4
        assert any(j.status == "declined" for j in jurors)
        assert any(j.status == "drawn" for j in jurors)


async def test_jury_review_days_is_consulted_for_would_close_on(client, town):
    """FIX-42 (MEDIUM, audit demo-01 run 5): `jury_review_days` is seeded and
    readable but was consulted by nothing (DEMOCRACY §10.1, §8.2). Both
    `GET /juries/mine` and `GET /cycles/{id}` now show "would close on
    <jury_review_started_at + jury_review_days>", the same shape the ballot
    window already used for `would_close_on`."""
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    async with session_scope() as session:
        cycle = await cycles_repo.get(session, cycle_id)
        started_at = cycle.jury_review_started_at
        review_days = int(cycle.settings_snapshot["jury_review_days"])
    assert started_at is not None

    duty = None
    for person in town["people"]:
        found = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if found:
            duty = found[0]
            break
    assert duty is not None
    assert duty["would_close_on"] is not None
    from datetime import datetime, timedelta

    close_on = datetime.fromisoformat(duty["would_close_on"])
    expected = started_at + timedelta(days=review_days)
    assert close_on == expected

    cycle_view = (
        await client.get(f"/cycles/{cycle_id}", headers=town["director"]["headers"])
    ).json()
    assert cycle_view["jury_review_would_close_on"] is not None
    assert datetime.fromisoformat(cycle_view["jury_review_would_close_on"]) == expected

    opened = await client.post(f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"])
    assert opened.status_code == 200
    assert opened.json()["would_close_on"] is not None
    reopened_view = (
        await client.get(f"/cycles/{cycle_id}", headers=town["director"]["headers"])
    ).json()
    assert reopened_view["would_close_on"] is not None


async def test_the_published_header_counts_drawn_replaced_and_seated(client, town):
    """DEMOCRACY §11.2 item 1 — "4 drawn, 1 replaced, 2 seated": every person
    ever drawn for the current jury, including the one a decline replaced."""
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    drawn = []
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties:
            drawn.append((person, duties[0]["juror_id"]))
    assert len(drawn) == 3

    declining, decline_id = drawn[0]
    declined = await client.post(f"/jurors/{decline_id}/decline", headers=declining["headers"])
    assert declined.json()["replacement_drawn"] is True

    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        for duty in duties:
            if duty["status"] == "drawn":
                await client.post(f"/jurors/{duty['juror_id']}/accept", headers=person["headers"])

    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"]
    )
    assert opened.status_code == 200
    assert opened.json()["jurors_drawn"] == 4, "3 original draws plus the one replacement"
    assert opened.json()["jurors_seated"] == 3

    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0]["ballot_item_id"]
    for person in town["people"]:
        await client.put(
            f"/cycles/{cycle_id}/ballot/{item_id}/vote",
            headers=person["headers"],
            json={"choice": "yes"},
        )
    await client.post(f"/admin/cycles/{cycle_id}/close", headers=town["director"]["headers"])
    published = await client.post(
        f"/admin/cycles/{cycle_id}/publish", headers=town["director"]["headers"]
    )
    assert published.status_code == 200
    header = published.json()["document"]["header"]
    assert header["jury"] == "4 drawn, 1 replaced, 3 seated"
    assert header["jurors_drawn"] == 4
    assert header["jurors_replaced"] == 1
    assert header["jurors_seated"] == 3


async def test_a_juror_who_never_answers_is_not_seated_and_not_replaced(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    accepted = 0
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties and accepted < 2:
            await client.post(f"/jurors/{duties[0]['juror_id']}/accept", headers=person["headers"])
            accepted += 1

    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"]
    )
    assert opened.json()["jurors_drawn"] == 3
    assert opened.json()["jurors_seated"] == 2

    async with session_scope() as session:
        jury = await cycles_repo.jury_for_cycle(session, cycle_id)
        jurors = await cycles_repo.jurors(session, jury.id)
        assert sum(1 for j in jurors if j.status == "no_response") == 1
        assert jury.seated_count == 2


async def test_one_holdback_out_of_two_seated_jurors_is_not_a_majority(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]

    seated = []
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties and len(seated) < 2:
            await client.post(f"/jurors/{duties[0]['juror_id']}/accept", headers=person["headers"])
            seated.append((person, duties[0]["juror_id"]))

    person, juror_id = seated[0]
    held = await client.post(
        f"/ballot-items/{item_id}/holdback",
        headers=person["headers"],
        json={
            "juror_id": juror_id,
            "reason_category": "incomplete",
            "reason_text": "One juror out of two is not more than half of the seated jury.",
        },
    )
    assert held.status_code == 200

    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"]
    )
    assert opened.json()["items_held_back"] == 0, "one of two is not more than half"


async def test_a_minority_holdback_is_still_published(client, town):
    """MEDIUM, audit demo-01 run 2: a hold-back that did not reach a majority
    used to be stored and never surfaced anywhere, even though the endpoint
    tells every juror their reason will be published (DEMOCRACY.md §8.3,
    §11.2 item 2). Every hold-back is published now, on the solution page
    from the moment the ballot opens and in the summary."""
    author = town["people"][0]
    solution_id = await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]

    seated = []
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties and len(seated) < 2:
            await client.post(f"/jurors/{duties[0]['juror_id']}/accept", headers=person["headers"])
            seated.append((person, duties[0]["juror_id"]))

    # A solution page has no jury notes before the ballot opens.
    before = (await client.get(f"/solutions/{solution_id}")).json()
    assert before["jury_notes"] is None

    person, juror_id = seated[0]
    held = await client.post(
        f"/ballot-items/{item_id}/holdback",
        headers=person["headers"],
        json={
            "juror_id": juror_id,
            "reason_category": "incomplete",
            "reason_text": "The repainting schedule is sound but the timeline is missing.",
        },
    )
    assert held.status_code == 200
    assert "published with the results" in held.json()["note"]

    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"]
    )
    assert opened.json()["items_held_back"] == 0, "one of two seated is not a majority"

    page = (await client.get(f"/solutions/{solution_id}")).json()
    assert page["jury_notes"] is not None
    assert page["jury_notes"]["seated"] == 2
    assert len(page["jury_notes"]["notes"]) == 1
    note = page["jury_notes"]["notes"][0]
    assert note["category"] == "incomplete"
    assert note["reason"] == "The repainting schedule is sound but the timeline is missing."
    assert "of 2" in note["juror"]

    for voter in town["people"]:
        await client.put(
            f"/cycles/{cycle_id}/ballot/{item_id}/vote",
            headers=voter["headers"],
            json={"choice": "yes"},
        )
    await client.post(f"/admin/cycles/{cycle_id}/close", headers=town["director"]["headers"])
    published = await client.post(
        f"/admin/cycles/{cycle_id}/publish", headers=town["director"]["headers"]
    )
    assert published.status_code == 200
    result_entry = published.json()["document"]["results"][0]
    assert result_entry["result"] == "Passed"
    assert result_entry["juror_concerns"]["reasons"][0]["reason"] == (
        "The repainting schedule is sound but the timeline is missing."
    )
    assert result_entry["juror_concerns"]["reasons"][0]["category"] == "incomplete"
    assert "1 of 2" in result_entry["juror_concerns"]["label"]


async def test_both_seated_jurors_holding_back_stops_the_item(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]

    seated = []
    for person in town["people"]:
        duties = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if duties and len(seated) < 2:
            await client.post(f"/jurors/{duties[0]['juror_id']}/accept", headers=person["headers"])
            seated.append((person, duties[0]["juror_id"]))
    for person, juror_id in seated:
        await client.post(
            f"/ballot-items/{item_id}/holdback",
            headers=person["headers"],
            json={
                "juror_id": juror_id,
                "reason_category": "not_actionable",
                "reason_text": "Two of two seated jurors is more than half of the jury.",
            },
        )

    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"]
    )
    assert opened.json()["items_held_back"] == 1
    assert opened.json()["items_votable"] == 0


async def test_the_cycle_state_machine_refuses_a_jump(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    early_close = await client.post(
        f"/admin/cycles/{cycle_id}/close", headers=town["director"]["headers"]
    )
    assert early_close.status_code == 409

    early_publish = await client.post(
        f"/admin/cycles/{cycle_id}/publish", headers=town["director"]["headers"]
    )
    assert early_publish.status_code == 409
    assert early_publish.json()["error"] == "cycle_wrong_state", (
        "a ballot with items goes through jury review and a vote before it is published"
    )

    second = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert second.status_code == 409
    assert second.json()["error"] == "cycle_already_open"


async def test_a_redraw_is_logged_with_its_reason(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    redrawn = await client.post(
        f"/admin/cycles/{cycle_id}/redraw-jury",
        headers=town["director"]["headers"],
        json={"reason": "The first draw picked three people from the same household."},
    )
    assert redrawn.status_code == 200
    log = (await client.get("/admin/log")).json()
    assert log["items"][0]["action"] == "redraw_jury"
    assert "same household" in log["items"][0]["reason"]


async def test_a_redraw_keeps_the_previous_draw_inspectable(client, town):
    """HIGH, audit demo-01 run 2: `redraw` used to mark the outgoing jurors
    `replaced` and then delete the whole jury row, destroying the first
    draw's pool, drawn ids, timestamp and random bytes before anyone could
    read the `replaced` status DEMOCRACY.md §8.1 and §13 promise stays
    inspectable. No draw is ever deleted now."""
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]

    async with session_scope() as session:
        first_jury = await cycles_repo.jury_for_cycle(session, cycle_id)
        first_jury_id = first_jury.id
        first_pool = list(first_jury.eligible_pool)
        first_random_bytes = first_jury.random_bytes
        first_jurors_before = {j.user_id: j.status for j in await cycles_repo.jurors(session, first_jury_id)}
        assert set(first_jurors_before.values()) == {"drawn"}

    redrawn = await client.post(
        f"/admin/cycles/{cycle_id}/redraw-jury",
        headers=town["director"]["headers"],
        json={"reason": "The first draw picked three people from the same household."},
    )
    assert redrawn.status_code == 200
    second_jury_id = redrawn.json()["jury_id"]
    assert second_jury_id != first_jury_id

    async with session_scope() as session:
        # The first draw's row still exists, superseded rather than deleted.
        first_jury_after = await cycles_repo.get_jury(session, first_jury_id)
        assert first_jury_after is not None, "the previous draw is kept, never deleted"
        assert first_jury_after.superseded_at is not None
        assert first_jury_after.eligible_pool == first_pool, "the first draw's pool is unchanged"
        assert first_jury_after.random_bytes == first_random_bytes
        assert (
            first_jury_after.redrawn_reason
            == "The first draw picked three people from the same household."
        )
        first_jurors_after = await cycles_repo.jurors(session, first_jury_id)
        assert {j.status for j in first_jurors_after} == {"replaced"}, (
            "replaced is now an observable, permanent status on the superseded row"
        )

        second_jury = await cycles_repo.get_jury(session, second_jury_id)
        assert second_jury.superseded_at is None, "the new draw is the current one"
        assert second_jury.eligible_pool, "the second draw has its own pool and random bytes"
        assert second_jury.random_bytes != first_random_bytes

        # jury_for_cycle resolves to the current draw only.
        current = await cycles_repo.jury_for_cycle(session, cycle_id)
        assert current.id == second_jury_id

    view = (await client.get(f"/cycles/{cycle_id}")).json()
    by_id = {j["jury_id"]: j for j in view["juries"]}
    assert set(by_id) == {first_jury_id, second_jury_id}, "every draw is shown, not only the current one"
    assert by_id[first_jury_id]["status"] == "superseded"
    assert by_id[first_jury_id]["redrawn_reason"] == (
        "The first draw picked three people from the same household."
    )
    assert {j["status"] for j in by_id[first_jury_id]["jurors"]} == {"replaced"}
    assert by_id[second_jury_id]["status"] == "current"


async def test_a_ballot_vote_needs_membership_and_an_open_ballot(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]

    too_early = await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=author["headers"],
        json={"choice": "yes"},
    )
    assert too_early.status_code == 409

    await client.post(f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"])
    outsider = await make_user(
        client, email="out@example.com", display_name="Out", city_id=2, county_id=2
    )
    refused = await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=outsider["headers"],
        json={"choice": "yes"},
    )
    assert refused.status_code == 403

    assert (await client.get(f"/cycles/{cycle_id}/ballot")).status_code == 200, (
        "anyone may read a ballot; only members vote on it"
    )


async def test_a_tie_fails_and_the_quorum_is_respected(client, town):
    author = town["people"][0]
    await _dominant_solution(client, author, town["people"][1:], town["umbrella"])
    await set_setting("ballot_quorum_min", "3")
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=town["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_id = prepared.json()["cycle_id"]
    item_id = (await client.get(f"/cycles/{cycle_id}/ballot")).json()["items"][0][
        "ballot_item_id"
    ]
    await client.post(f"/admin/cycles/{cycle_id}/open", headers=town["director"]["headers"])

    await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=town["people"][1]["headers"],
        json={"choice": "yes"},
    )
    await client.put(
        f"/cycles/{cycle_id}/ballot/{item_id}/vote",
        headers=town["people"][2]["headers"],
        json={"choice": "no"},
    )
    closed = await client.post(
        f"/admin/cycles/{cycle_id}/close", headers=town["director"]["headers"]
    )
    assert closed.json()["results"][0]["result"] == "failed", "a tie fails, and quorum was 3"
