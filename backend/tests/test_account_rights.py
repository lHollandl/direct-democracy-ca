"""User sovereignty: export and deletion (CLAUDE.md §6, F-13, F-14, I-32)."""

from __future__ import annotations

from backend.db import session_scope
from backend.models import Amendment, City, Comment, Post, Solution, Vote
from backend.repositories import users as users_repo
from backend.services import export as export_service
from backend.services import export_iteration
from backend.tests.conftest import labeler_answer, make_umbrella, make_user, settle_jobs


async def _a_full_civic_record(client) -> dict:
    """One person with a post, a solution, an amendment, a comment, votes and a
    ballot vote, so deletion has something real to preserve."""
    from backend.clients import ollama as ollama_client

    umbrella = await make_umbrella(
        name="Pedestrian Safety", statement="Crossings near schools are unsafe."
    )
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    author = await make_user(client, email="author@example.com", display_name="Author")
    other = await make_user(client, email="other@example.com", display_name="Other")

    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school every morning.",
            "solutions": ["Paint a crosswalk and install a pedestrian refuge island in the median."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201
    await settle_jobs()

    page = (await client.get(f"/umbrellas/{umbrella}")).json()
    solution_id = page["solutions"][0]["id"]

    await client.put(
        "/votes",
        headers=other["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    amendment = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=other["headers"],
        json={
            "proposed_text": "Paint a crosswalk, install a refuge island, and add a flashing beacon.",
            "rationale": "A beacon is what actually slows the turning traffic.",
        },
    )
    assert amendment.status_code == 201, amendment.text
    comment = await client.post(
        "/comments",
        headers=other["headers"],
        json={
            "target_type": "solution",
            "target_id": solution_id,
            "text": "I cross here every day with my daughter.",
        },
    )
    assert comment.status_code == 201, comment.text
    return {
        "author": author,
        "other": other,
        "umbrella": umbrella,
        "solution_id": solution_id,
        "amendment_id": amendment.json()["id"],
        "comment_id": comment.json()["id"],
    }


async def test_export_contains_the_user_and_their_civic_record(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    world = await _a_full_civic_record(client)

    requested = await client.post("/me/export", headers=world["other"]["headers"])
    assert requested.status_code == 202
    export_id = requested.json()["id"]
    from backend.jobs import exports as export_job

    await export_job.build_export_task(export_id)

    downloaded = await client.get(f"/me/export/{export_id}", headers=world["other"]["headers"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-disposition"] == (
        f'attachment; filename="direct-democracy-ca-export-{world["other"]["id"]}.json"'
    )
    payload = downloaded.json()
    assert payload["account"]["email"] == "other@example.com"
    civic = payload["civic_record"]["iteration"]
    assert [a["id"] for a in civic["amendments_you_proposed"]] == [world["amendment_id"]]
    assert [c["id"] for c in civic["comments_you_wrote"]] == [world["comment_id"]]
    assert civic["workshop_votes"], "their own votes belong in their export"


async def test_an_export_is_only_ever_that_person_s(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    world = await _a_full_civic_record(client)
    requested = await client.post("/me/export", headers=world["other"]["headers"])
    export_id = requested.json()["id"]
    from backend.jobs import exports as export_job

    await export_job.build_export_task(export_id)

    response = await client.get(f"/me/export/{export_id}", headers=world["author"]["headers"])
    assert response.status_code == 403
    assert response.json()["error"] == "export_not_yours"


async def test_an_expired_export_is_refused_before_the_hourly_sweep_runs(client):
    """FIX-48 (LOW, audit demo-01 run 5): the window is EXPORT_FILE_HOURS,
    not that plus up to an hour. get_export refuses the moment expires_at
    has passed, whether or not expire_exports has run yet — the file on
    disk is left untouched here to prove the refusal doesn't depend on it."""
    from datetime import datetime, timedelta, timezone

    from backend.models import DataExport

    user = await make_user(client, email="waiting@example.com", display_name="Waiting")
    requested = await client.post("/me/export", headers=user["headers"])
    export_id = requested.json()["id"]
    from backend.jobs import exports as export_job

    await export_job.build_export_task(export_id)

    still_fresh = await client.get(f"/me/export/{export_id}", headers=user["headers"])
    assert still_fresh.status_code == 200

    async with session_scope() as session:
        row = await session.get(DataExport, export_id)
        assert row.file_path is not None, "the file has not been swept"
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.flush()

    expired = await client.get(f"/me/export/{export_id}", headers=user["headers"])
    assert expired.status_code == 410
    assert expired.json()["error"] == "export_expired"

    async with session_scope() as session:
        row = await session.get(DataExport, export_id)
        assert row.file_path is not None, "expire_exports has not run; the file is still there"


async def test_an_export_without_a_contributor_says_so(client):
    user = await make_user(client, email="lonely@example.com", display_name="Lonely")
    requested = await client.post("/me/export", headers=user["headers"])
    from backend.jobs import exports as export_job

    await export_job.build_export_task(requested.json()["id"])
    payload = (
        await client.get(f"/me/export/{requested.json()['id']}", headers=user["headers"])
    ).json()
    assert "note" in payload["civic_record"]
    assert "account data only" in payload["civic_record"]["note"]


async def test_deleting_an_account_erases_the_person_and_keeps_the_record(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    world = await _a_full_civic_record(client)
    user_id = world["other"]["id"]

    async with session_scope() as session:
        before = await users_repo.get(session, user_id)
        home_city, home_county = before.city_id, before.county_id

    response = await client.request(
        "DELETE",
        "/me",
        headers=world["other"]["headers"],
        json={"password": "Crosswalk1", "understand_this_cannot_be_undone": True},
    )
    assert response.status_code == 200

    async with session_scope() as session:
        after = await users_repo.get(session, user_id)
        assert after.email == f"deleted+{user_id}@invalid"
        assert after.password_hash == "!"
        assert after.real_name == ""
        assert after.display_name == "Former Community Member"
        assert after.date_of_birth.isoformat() == "1900-01-01"
        assert after.gender == "prefer_not_to_say"
        assert after.political_party == "prefer_not_to_say"
        assert after.last_active_at is None
        assert after.deleted_at is not None
        # Home city and county are kept, so the civic record stays in the right
        # community (CLAUDE.md §6).
        assert after.city_id == home_city
        assert after.county_id == home_county
        assert await session.get(City, home_city) is not None

        # Every civic row still resolves.
        assert await session.get(Amendment, world["amendment_id"]) is not None
        assert await session.get(Comment, world["comment_id"]) is not None
        assert await session.get(Solution, world["solution_id"]) is not None
        votes = (await session.execute(_votes_of(user_id))).scalars().all()
        assert votes, "their votes stay; the vote is part of the record"

    page = (await client.get(f"/umbrellas/{world['umbrella']}")).json()
    dominant = page["dominant_solutions"][0]
    assert dominant["amendments"][0]["author"] == "Former Community Member"
    assert dominant["discussion"][0]["author"] == "Former Community Member"


def _votes_of(user_id: int):
    from sqlalchemy import select

    return select(Vote).where(Vote.user_id == user_id)


async def test_deleting_requires_the_password_and_the_confirmation(client):
    user = await make_user(client, email="careful@example.com", display_name="Careful")
    wrong = await client.request(
        "DELETE",
        "/me",
        headers=user["headers"],
        json={"password": "NotIt12345", "understand_this_cannot_be_undone": True},
    )
    assert wrong.status_code == 401

    unconfirmed = await client.request(
        "DELETE",
        "/me",
        headers=user["headers"],
        json={"password": "Crosswalk1", "understand_this_cannot_be_undone": False},
    )
    assert unconfirmed.status_code == 200
    assert "Nothing was deleted" in unconfirmed.json()["message"]

    async with session_scope() as session:
        assert (await users_repo.get(session, user["id"])).deleted_at is None


async def test_a_deleted_account_cannot_sign_in(client):
    user = await make_user(client, email="gone@example.com", display_name="Gone")
    await client.request(
        "DELETE",
        "/me",
        headers=user["headers"],
        json={"password": "Crosswalk1", "understand_this_cannot_be_undone": True},
    )
    response = await client.post(
        "/auth/login", json={"email": "gone@example.com", "password": "Crosswalk1"}
    )
    assert response.status_code == 401


async def test_display_settings_change_what_everyone_sees(client):
    world = await _a_full_civic_record(client)
    for mode, expected in [
        ("real_name", "Real Other"),
        ("anonymous", "Anonymous Community Member"),
        ("display_name", "Other"),
    ]:
        changed = await client.patch(
            "/me/display", headers=world["other"]["headers"], json={"public_name_mode": mode}
        )
        assert changed.status_code == 200
        page = (await client.get(f"/umbrellas/{world['umbrella']}")).json()
        assert page["dominant_solutions"][0]["discussion"][0]["author"] == expected
