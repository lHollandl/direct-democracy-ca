"""GET /cycles/mine (ARCHITECTURE.md §6, DEMOCRACY.md §12.2)."""

from __future__ import annotations

import pytest

from backend.tests.conftest import make_umbrella, make_user, set_setting

EXPECTED_KEYS = {
    "community",
    "cycle",
    "last_closed_at",
    "next_ballot_expected",
    "last_jury_drawn_at",
    "next_jury_draw_expected",
    "my_jury_status",
    "respond_by",
}


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
async def village(client):
    await set_setting("ballot_min_dominant_days", "0")
    umbrella = await make_umbrella(name="Restrooms", statement="Park restrooms are locked.")
    director = await make_user(
        client, email="mine-dir@example.com", display_name="MineDir", admin=True
    )
    people = [
        await make_user(client, email=f"mine-p{i}@example.com", display_name=f"MineP{i}")
        for i in range(5)
    ]
    return {"umbrella": umbrella, "director": director, "people": people}


def _city_entry(payload):
    return next(e for e in payload["communities"] if e["community"]["level"] == "city")


async def test_no_cycle_yet_for_a_fresh_community(client):
    person = await make_user(client, email="fresh@example.com", display_name="Fresh")
    payload = (await client.get("/cycles/mine", headers=person["headers"])).json()
    assert len(payload["communities"]) == 3, "one entry per home community: city, county, state"
    for entry in payload["communities"]:
        assert set(entry) == EXPECTED_KEYS
        assert entry["cycle"] is None
        assert entry["last_closed_at"] is None
        assert entry["last_jury_drawn_at"] is None
        assert entry["my_jury_status"] == "none"
        assert entry["respond_by"] is None
        assert entry["next_ballot_expected"] is not None
        assert entry["next_jury_draw_expected"] is not None


async def test_cycles_mine_requires_auth(client):
    response = await client.get("/cycles/mine")
    assert response.status_code == 401


async def test_every_jury_status_and_no_cross_juror_leak(client, village):
    author = village["people"][0]
    voters = village["people"][1:]
    await _dominant_solution(client, author, voters, village["umbrella"])

    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=village["director"]["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert prepared.status_code == 200, prepared.text
    cycle_id = prepared.json()["cycle_id"]

    duties = {}
    for person in voters:
        d = (await client.get("/juries/mine", headers=person["headers"])).json()["duties"]
        if d:
            duties[person["email"]] = d[0]["juror_id"]
    assert len(duties) == 3, "jury_size default"

    not_drawn_email = next(p["email"] for p in voters if p["email"] not in duties)
    not_drawn_person = next(p for p in voters if p["email"] == not_drawn_email)

    # Before anyone answers, someone not drawn at all reads "none".
    before = (await client.get("/cycles/mine", headers=not_drawn_person["headers"])).json()
    assert _city_entry(before)["my_jury_status"] == "none"

    accept_email, decline_email, leave_email = list(duties)
    accept_person = next(p for p in voters if p["email"] == accept_email)
    decline_person = next(p for p in voters if p["email"] == decline_email)
    leave_person = next(p for p in voters if p["email"] == leave_email)

    accepted = await client.post(
        f"/jurors/{duties[accept_email]}/accept", headers=accept_person["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    declined = await client.post(
        f"/jurors/{duties[decline_email]}/decline", headers=decline_person["headers"]
    )
    assert declined.status_code == 200, declined.text

    # accepted
    mine = (await client.get("/cycles/mine", headers=accept_person["headers"])).json()
    entry = _city_entry(mine)
    assert set(entry) == EXPECTED_KEYS
    assert entry["cycle"]["id"] == cycle_id
    assert entry["my_jury_status"] == "accepted"
    assert entry["respond_by"] is None

    # declined
    entry = _city_entry(
        (await client.get("/cycles/mine", headers=decline_person["headers"])).json()
    )
    assert entry["my_jury_status"] == "declined"

    # drawn, awaiting reply — respond_by is present
    entry = _city_entry(
        (await client.get("/cycles/mine", headers=leave_person["headers"])).json()
    )
    assert entry["my_jury_status"] == "drawn"
    assert entry["respond_by"] is not None

    # the only remaining eligible resident was drawn as the decline's
    # replacement, so they are now "drawn" too, not "none" any longer.
    entry = _city_entry(
        (await client.get("/cycles/mine", headers=not_drawn_person["headers"])).json()
    )
    assert entry["my_jury_status"] == "drawn"

    # Nobody's payload reveals another juror's identity or status.
    for headers in (accept_person["headers"], decline_person["headers"], leave_person["headers"]):
        payload = (await client.get("/cycles/mine", headers=headers)).json()
        for e in payload["communities"]:
            assert set(e) == EXPECTED_KEYS

    # Opening the ballot marks the still-silent jurors no_response.
    opened = await client.post(
        f"/admin/cycles/{cycle_id}/open", headers=village["director"]["headers"]
    )
    assert opened.status_code == 200, opened.text

    entry = _city_entry(
        (await client.get("/cycles/mine", headers=leave_person["headers"])).json()
    )
    assert entry["my_jury_status"] == "no_response"
    assert entry["cycle"]["state"] == "open"
    assert entry["cycle"]["expected_close"] is not None
