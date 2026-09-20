"""C2-04: profile edits and email changes (ARCHITECTURE.md §6, DATABASE.md
§3.13)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from backend.clients import email as email_client
from backend.db import session_scope
from backend.models import EmailChangeRequest, UserHomeChange
from backend.repositories import users as users_repo
from backend.services import export as export_service
from backend.services import export_iteration
from backend.tests.conftest import labeler_answer, make_umbrella, make_user, settle_jobs


async def test_profile_fields_update_independently(client):
    user = await make_user(client, email="profile@example.com", display_name="ProfileBefore")
    response = await client.patch(
        "/me/profile", headers=user["headers"], json={"display_name": "ProfileAfter"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "ProfileAfter"
    assert response.json()["real_name"] == "Real ProfileBefore", (
        "an untouched field is left exactly as it was"
    )


async def test_display_name_must_stay_unique_among_live_users(client):
    await make_user(client, email="taken@example.com", display_name="TakenName")
    user = await make_user(client, email="wants-it@example.com", display_name="WantsIt")
    response = await client.patch(
        "/me/profile", headers=user["headers"], json={"display_name": "TakenName"}
    )
    assert response.status_code == 409
    assert response.json()["error"] == "display_name_taken"


async def test_a_rename_shows_on_an_existing_post_and_changes_no_hash(client):
    """DATABASE.md §3.2: author display is resolved at read time everywhere.
    A rename must never touch `content_hash` (CLAUDE.md Law 6)."""
    from backend.clients import ollama as ollama_client

    umbrella = await make_umbrella(
        name="Renamed Author Umbrella", statement="A test problem."
    )
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    author = await make_user(client, email="renamer@example.com", display_name="BeforeRename")

    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "A problem written before the author changes their display name.",
            "solutions": ["A solution proposed before the rename happens."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201
    await settle_jobs()
    post_id = created.json()["id"]

    before = (await client.get(f"/posts/{post_id}")).json()
    assert before["author"] == "BeforeRename"
    hash_before = before["content_hash"]

    renamed = await client.patch(
        "/me/profile", headers=author["headers"], json={"display_name": "AfterRename"}
    )
    assert renamed.status_code == 200, renamed.text

    after = (await client.get(f"/posts/{post_id}")).json()
    assert after["author"] == "AfterRename"
    assert after["content_hash"] == hash_before


async def test_email_change_confirms_to_the_new_address_and_notifies_the_old(client):
    user = await make_user(client, email="old@example.com", display_name="EmailChanger")
    email_client.sent_messages().clear()

    response = await client.post(
        "/me/email",
        headers=user["headers"],
        json={"new_email": "new@example.com", "password": "Crosswalk1"},
    )
    assert response.status_code == 200, response.text
    messages = email_client.sent_messages()
    assert any(m["to"] == "new@example.com" for m in messages)
    assert any(m["to"] == "old@example.com" for m in messages)

    # The old address keeps working until the token is used.
    still_old = await client.post(
        "/auth/login", json={"email": "old@example.com", "password": "Crosswalk1"}
    )
    assert still_old.status_code == 200

    token = re.search(
        r"token=([A-Za-z0-9_\-]+)",
        next(m["body"] for m in messages if m["to"] == "new@example.com"),
    ).group(1)
    confirmed = await client.post("/auth/confirm-email-change", json={"token": token})
    assert confirmed.status_code == 200, confirmed.text

    old_no_longer_works = await client.post(
        "/auth/login", json={"email": "old@example.com", "password": "Crosswalk1"}
    )
    assert old_no_longer_works.status_code == 401
    now_new = await client.post(
        "/auth/login", json={"email": "new@example.com", "password": "Crosswalk1"}
    )
    assert now_new.status_code == 200


async def test_email_change_requires_the_correct_password(client):
    user = await make_user(client, email="pwcheck@example.com", display_name="PwCheck")
    response = await client.post(
        "/me/email",
        headers=user["headers"],
        json={"new_email": "somewhere@example.com", "password": "WrongPassword1"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "bad_credentials"


async def test_email_change_refuses_an_address_already_in_use(client):
    await make_user(client, email="claimed@example.com", display_name="Claimed")
    user = await make_user(client, email="hopeful@example.com", display_name="Hopeful")
    response = await client.post(
        "/me/email",
        headers=user["headers"],
        json={"new_email": "claimed@example.com", "password": "Crosswalk1"},
    )
    assert response.status_code == 409
    assert response.json()["error"] == "email_taken"


async def test_a_newer_email_change_request_voids_the_older_one(client):
    user = await make_user(client, email="restart@example.com", display_name="Restart")
    email_client.sent_messages().clear()

    first = await client.post(
        "/me/email",
        headers=user["headers"],
        json={"new_email": "first-choice@example.com", "password": "Crosswalk1"},
    )
    assert first.status_code == 200
    first_token = re.search(
        r"token=([A-Za-z0-9_\-]+)",
        next(m["body"] for m in email_client.sent_messages() if m["to"] == "first-choice@example.com"),
    ).group(1)

    second = await client.post(
        "/me/email",
        headers=user["headers"],
        json={"new_email": "second-choice@example.com", "password": "Crosswalk1"},
    )
    assert second.status_code == 200

    voided = await client.post("/auth/confirm-email-change", json={"token": first_token})
    assert voided.status_code == 422
    assert voided.json()["error"] == "email_change_invalid"


async def test_export_includes_home_changes_and_pending_email_changes(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    user = await make_user(client, email="exportme@example.com", display_name="ExportMe")

    async with session_scope() as session:
        from backend.repositories import email_changes as email_changes_repo
        from backend.repositories import home_changes as home_changes_repo

        await home_changes_repo.add(
            session,
            user_id=user["id"],
            from_county_id=1,
            from_city_id=1,
            to_county_id=2,
            to_city_id=2,
        )
        await email_changes_repo.add(
            session,
            user_id=user["id"],
            new_email="pending-export@example.com",
            token_hash="1" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    requested = await client.post("/me/export", headers=user["headers"])
    from backend.jobs import exports as export_job

    await export_job.build_export_task(requested.json()["id"])
    payload = (
        await client.get(f"/me/export/{requested.json()['id']}", headers=user["headers"])
    ).json()
    assert payload["home_changes"][0] == {
        "from_county_id": 1,
        "from_city_id": 1,
        "to_county_id": 2,
        "to_city_id": 2,
        "changed_at": payload["home_changes"][0]["changed_at"],
    }
    assert payload["pending_email_changes"][0]["new_email"] == "pending-export@example.com"


async def test_deleting_the_account_removes_home_and_email_change_rows(client):
    export_service.register_contributor("iteration", export_iteration.contribute)
    user = await make_user(client, email="cleanup@example.com", display_name="Cleanup")

    async with session_scope() as session:
        from backend.repositories import email_changes as email_changes_repo
        from backend.repositories import home_changes as home_changes_repo

        await home_changes_repo.add(
            session,
            user_id=user["id"],
            from_county_id=1,
            from_city_id=1,
            to_county_id=2,
            to_city_id=2,
        )
        await email_changes_repo.add(
            session,
            user_id=user["id"],
            new_email="pending@example.com",
            token_hash="0" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    deleted = await client.request(
        "DELETE",
        "/me",
        headers=user["headers"],
        json={"password": "Crosswalk1", "understand_this_cannot_be_undone": True},
    )
    assert deleted.status_code == 200, deleted.text

    async with session_scope() as session:
        from sqlalchemy import select

        home_rows = (
            await session.execute(
                select(UserHomeChange).where(UserHomeChange.user_id == user["id"])
            )
        ).scalars().all()
        email_rows = (
            await session.execute(
                select(EmailChangeRequest).where(EmailChangeRequest.user_id == user["id"])
            )
        ).scalars().all()
        assert home_rows == []
        assert email_rows == []
