"""The whole civic process as one test (I-30, ARCHITECTURE.md §10).

seed -> post -> label (Ollama mocked) -> votes -> dominant -> prepare ->
jury holds one back -> open -> vote -> close -> publish -> the hash verifies ->
the JSON re-hashes to the same value.

If this test passes, a problem can become pressure on a government.
"""

from __future__ import annotations

import hashlib
import json

from backend.clients import ollama as ollama_client
from backend.services import export as export_service
from backend.services import export_iteration
from backend.services import hashing
from backend.tests.conftest import (
    labeler_answer,
    make_umbrella,
    make_user,
    set_setting,
    settle_jobs,
)


async def test_a_problem_becomes_a_published_result(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    # The walkthrough happens in one day, so the three-day dominance rule is
    # lowered the way a director would lower it: as a setting, not in code.
    await set_setting("ballot_min_dominant_days", "0")

    umbrella = await make_umbrella(
        name="Pedestrian Safety Near Schools",
        statement="Crossings near schools lack crosswalks and drivers speed through them.",
    )
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )

    director = await make_user(
        client, email="director@example.com", display_name="Director", admin=True
    )
    ben = await make_user(client, email="ben@example.com", display_name="Ben")
    cara = await make_user(client, email="cara@example.com", display_name="Cara")

    # --- post -------------------------------------------------------------
    created = await client.post(
        "/posts",
        headers=director["headers"],
        json={
            "problem_text": (
                "Children walking to Washington Elementary cross four lanes of traffic "
                "at an intersection with no marked crosswalk, twice a day."
            ),
            "solutions": [
                "Paint a high-visibility crosswalk and install a pedestrian refuge island in the median.",
                "Station a crossing guard during school drop-off and pick-up hours.",
            ],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201
    await settle_jobs()

    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "labeled"
    ai_log = (await client.get("/ai/actions")).json()
    assert ai_log["items"][0]["prompt_file"] == "labeler.md", (
        "the AI action was logged before its result was shown (CLAUDE.md Law 7)"
    )

    page = (await client.get(f"/umbrellas/{umbrella}")).json()
    crosswalk, guard = page["solutions"][0]["id"], page["solutions"][1]["id"]

    # --- votes and dominance ---------------------------------------------
    for voter in (ben, cara):
        for solution in (crosswalk, guard):
            vote = await client.put(
                "/votes",
                headers=voter["headers"],
                json={"target_type": "solution", "target_id": solution, "direction": 1},
            )
            assert vote.status_code == 200
    assert vote.json()["is_dominant"] is True

    # --- an amendment is absorbed ----------------------------------------
    amendment = await client.post(
        f"/solutions/{crosswalk}/amendments",
        headers=ben["headers"],
        json={
            "proposed_text": (
                "Paint a high-visibility crosswalk, install a pedestrian refuge island, "
                "and add a rapid-flashing beacon on both approaches."
            ),
            "rationale": "A crosswalk alone does not slow the turning traffic down.",
        },
    )
    assert amendment.status_code == 201
    absorbed = await client.put(
        "/votes",
        headers=cara["headers"],
        json={"target_type": "amendment", "target_id": amendment.json()["id"], "direction": 1},
    )
    assert absorbed.json()["absorbed"] is True
    assert absorbed.json()["new_version"] == 2

    # --- prepare ----------------------------------------------------------
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert prepared.status_code == 200, prepared.text
    cycle_id = prepared.json()["cycle_id"]
    assert prepared.json()["state"] == "jury_review"
    assert len(prepared.json()["items"]) == 2
    assert prepared.json()["items"][0]["version"] == 2, "the ballot text is the frozen version"

    ballot = (await client.get(f"/cycles/{cycle_id}/ballot")).json()
    assert [item["position"] for item in ballot["items"]] == [1, 2]
    guard_item = next(i for i in ballot["items"] if i["solution_id"] == guard)
    crosswalk_item = next(i for i in ballot["items"] if i["solution_id"] == crosswalk)

    # --- the jury ---------------------------------------------------------
    # The director authored both solutions and is an administrator, and Ben
    # wrote the absorbed version, so Cara is the one eligible juror.
    duties = (await client.get("/juries/mine", headers=cara["headers"])).json()["duties"]
    assert len(duties) == 1
    juror_id = duties[0]["juror_id"]
    assert (await client.get("/juries/mine", headers=ben["headers"])).json()["duties"] == []

    accepted = await client.post(f"/jurors/{juror_id}/accept", headers=cara["headers"])
    assert accepted.status_code == 200

    held = await client.post(
        f"/ballot-items/{guard_item['ballot_item_id']}/holdback",
        headers=cara["headers"],
        json={
            "juror_id": juror_id,
            "reason_category": "incomplete",
            "reason_text": (
                "It does not say who employs the crossing guard or for how long the "
                "money lasts, and the whole city is about to vote on it."
            ),
        },
    )
    assert held.status_code == 200

    # --- open, vote, close ------------------------------------------------
    opened = await client.post(f"/admin/cycles/{cycle_id}/open", headers=director["headers"])
    assert opened.status_code == 200
    assert opened.json()["jurors_seated"] == 1
    assert opened.json()["items_held_back"] == 1

    blocked = await client.put(
        f"/cycles/{cycle_id}/ballot/{guard_item['ballot_item_id']}/vote",
        headers=ben["headers"],
        json={"choice": "yes"},
    )
    assert blocked.status_code == 409

    for voter, choice in ((director, "yes"), (ben, "yes"), (cara, "no")):
        vote = await client.put(
            f"/cycles/{cycle_id}/ballot/{crosswalk_item['ballot_item_id']}/vote",
            headers=voter["headers"],
            json={"choice": choice},
        )
        assert vote.status_code == 200

    mine = (await client.get(f"/cycles/{cycle_id}/ballot", headers=cara["headers"])).json()
    assert next(
        i for i in mine["items"] if i["ballot_item_id"] == crosswalk_item["ballot_item_id"]
    )["my_vote"] == "no"

    closed = await client.post(f"/admin/cycles/{cycle_id}/close", headers=director["headers"])
    assert closed.status_code == 200
    results = {r["ballot_item_id"]: r for r in closed.json()["results"]}
    assert results[crosswalk_item["ballot_item_id"]]["result"] == "passed"
    assert results[guard_item["ballot_item_id"]]["result"] == "held_back"

    # --- publish and verify ----------------------------------------------
    published = await client.post(
        f"/admin/cycles/{cycle_id}/publish", headers=director["headers"]
    )
    assert published.status_code == 200
    stored_hash = published.json()["summary_hash"]
    document = published.json()["document"]

    assert document["header"]["members_who_voted"] == 3
    assert document["header"]["verification_mix"] == "3 voters: 3 unverified"
    assert "Residency is self-declared" in document["header"]["residency_note"]
    assert document["header"]["jury"] == "1 drawn, 0 replaced, 1 seated"
    assert document["results"][0]["result"] == "Passed"
    assert document["held_back"][0]["jury_reasons"][0]["juror"] == "Juror 1 of 1"
    assert len(document["how_this_was_produced"]) == 5
    for section in document["how_this_was_produced"]:
        assert section["settings_in_force"], "each paragraph prints the values in force"
        assert section["rule_version"]

    verified = await client.get("/summaries/city/1/1/verify")
    assert verified.status_code == 200
    assert verified.json()["match"] is True
    assert verified.json()["stored_hash"] == stored_hash

    # The JSON anyone can download re-hashes to the stored value with a plain
    # SHA-256, no platform code involved.
    downloaded = await client.get("/summaries/city/1/1/json")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == stored_hash
    assert json.loads(downloaded.text) == document
    assert hashing.summary_hash(json.loads(downloaded.text)) == stored_hash

    listed = (await client.get("/summaries/hashes")).json()
    assert listed["summaries"][0]["summary_hash"] == stored_hash

    pdf = await client.get("/summaries/city/1/1/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    # --- what happens afterwards -----------------------------------------
    solution = (await client.get(f"/solutions/{crosswalk}")).json()
    assert solution["last_ballot_result"] == "passed"
    assert solution["last_ballot_version"] == 2

    again = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert again.status_code == 200
    assert again.json()["items"] == [], (
        "nothing returns to the ballot unchanged, passed or held back alike"
    )
    assert again.json()["state"] == "prepared"
    assert again.json()["zero_item_note"]
    for considered in again.json()["considered"]:
        assert considered["conditions"]["newer_than_last_ballot_version"] is False

    empty = await client.post(
        f"/admin/cycles/{again.json()['cycle_id']}/publish", headers=director["headers"]
    )
    assert empty.status_code == 200, "a zero-item cycle goes straight from prepared to published"
    assert empty.json()["document"]["empty_note"] == "No solutions reached the ballot this cycle."

    # --- the record is public and complete --------------------------------
    admin_log = (await client.get("/admin/log")).json()
    actions = [row["action"] for row in admin_log["items"]]
    for expected in (
        "prepare_ballot",
        "open_ballot",
        "close_ballot",
        "publish_summary",
    ):
        assert expected in actions

    results_page = (await client.get("/results", headers=ben["headers"])).json()
    assert results_page["communities"][0]["most_recent"]["summary_hash"]


async def test_an_amendment_reopens_the_road_back_to_the_ballot(client):
    """A held-back solution returns once, and only once, it has a new version."""
    await set_setting("ballot_min_dominant_days", "0")
    umbrella = await make_umbrella(name="Parks", statement="Park restrooms are locked.")
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Parks and Recreation", umbrella_id=umbrella, level="city", entity_id=1
    )
    director = await make_user(
        client, email="d@example.com", display_name="Dee", admin=True
    )
    ben = await make_user(client, email="b@example.com", display_name="Ben")
    cara = await make_user(client, email="c@example.com", display_name="Cara")

    created = await client.post(
        "/posts",
        headers=ben["headers"],
        json={
            "problem_text": "The restrooms in the neighbourhood park have been locked for a year.",
            "solutions": ["Reopen the restrooms and put them on the daily cleaning round."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    await settle_jobs()
    solution_id = (await client.get(f"/umbrellas/{umbrella}")).json()["solutions"][0]["id"]
    for voter in (director, cara):
        await client.put(
            "/votes",
            headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )

    first = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    cycle_one = first.json()["cycle_id"]
    await client.post(f"/admin/cycles/{cycle_one}/open", headers=director["headers"])
    await client.post(f"/admin/cycles/{cycle_one}/close", headers=director["headers"])
    await client.post(f"/admin/cycles/{cycle_one}/publish", headers=director["headers"])

    blocked = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert blocked.json()["items"] == []
    await client.post(
        f"/admin/cycles/{blocked.json()['cycle_id']}/publish", headers=director["headers"]
    )

    amendment = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=cara["headers"],
        json={
            "proposed_text": (
                "Reopen the restrooms, put them on the daily cleaning round, and publish "
                "the cleaning schedule on the park noticeboard."
            ),
            "rationale": "A published schedule is what makes the promise checkable.",
        },
    )
    await client.put(
        "/votes",
        headers=director["headers"],
        json={"target_type": "amendment", "target_id": amendment.json()["id"], "direction": 1},
    )

    third = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert len(third.json()["items"]) == 1, "a new version is the way back onto the ballot"
    assert third.json()["items"][0]["version"] == 2
