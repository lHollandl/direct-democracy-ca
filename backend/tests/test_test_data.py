"""backend/services/test_data.py (ARCHITECTURE.md §3, change/01 C1-14)."""

from __future__ import annotations

import pytest

from backend.db import session_scope
from backend.errors import Conflict
from backend.repositories import users as users_repo
from backend.services import test_data as test_data_service
from backend.tests.conftest import make_umbrella, make_user, set_setting


@pytest.fixture(autouse=True)
def allow_test_data(monkeypatch):
    """Both the signup check and the service's own guard read
    ALLOW_TEST_DATA through get_env_settings() — patch both call sites."""
    from backend.config.settings_env import get_env_settings
    from backend.services import auth as auth_service

    allowed = get_env_settings().model_copy(update={"ALLOW_TEST_DATA": True})
    monkeypatch.setattr(auth_service, "get_env_settings", lambda: allowed)
    monkeypatch.setattr(test_data_service, "get_env_settings", lambda: allowed)


async def test_purge_removes_only_test_authored_rows(client):
    umbrella = await make_umbrella(name="Streetlights", statement="Streets are dark at night.")
    t1 = await make_user(client, email="t01@test.example.com", display_name="[TEST] One")
    t2 = await make_user(client, email="t02@test.example.com", display_name="[TEST] Two")
    real = await make_user(client, email="real@example.com", display_name="RealUser")

    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=t1["headers"],
        json={"text": "Replace the bulb and add it to the maintenance schedule."},
    )
    solution_id = created.json()["id"]
    for voter in (t2, real):
        await client.put(
            "/votes",
            headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )
    await client.post(
        "/comments",
        headers=t2["headers"],
        json={"target_type": "solution", "target_id": solution_id, "text": "A test comment."},
    )
    await client.post(
        "/comments",
        headers=real["headers"],
        json={"target_type": "solution", "target_id": solution_id, "text": "A real comment."},
    )

    async with session_scope() as session:
        report = await test_data_service.impact_report(session)
    assert report["test_accounts"] == 2
    assert report["solutions"] == 1
    assert report["comments"] == 1  # t2's own; real's is a foreign row, not owned
    assert len(report["foreign_rows"]) == 2  # real's vote and real's comment

    async with session_scope() as session:
        with pytest.raises(Conflict) as excinfo:
            await test_data_service.purge(session, force=False)
        assert excinfo.value.code == "foreign_rows_present"

    async with session_scope() as session:
        real_user = await users_repo.by_email(session, "real@example.com")
        assert real_user is not None, "refused purge must not have changed anything"

    async with session_scope() as session:
        result = await test_data_service.purge(session, force=True)
    assert result["test_accounts"] == 2
    assert result["deleted"]["solutions"] == 1
    assert result["deleted"]["accounts"] == 2
    assert len(result["foreign_rows_deleted"]) == 2

    async with session_scope() as session:
        assert await users_repo.by_email(session, "t01@test.example.com") is None
        assert await users_repo.by_email(session, "t02@test.example.com") is None
        assert await users_repo.by_email(session, "real@example.com") is not None

    solution_gone = await client.get(f"/solutions/{solution_id}")
    assert solution_gone.status_code == 404


async def test_purge_never_touches_a_solution_that_reached_a_ballot(client):
    """DATABASE.md §4.15, CLAUDE.md Law 6 — once a test solution is frozen
    onto a ballot item it is part of the permanent civic record's shape,
    even though the voters behind it were fake. Not overridable with
    --force, unlike an ordinary foreign row."""
    await set_setting("ballot_min_dominant_days", "0")
    umbrella = await make_umbrella(name="Streetlights", statement="Streets are dark at night.")
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    t1 = await make_user(client, email="t01@test.example.com", display_name="[TEST] One")
    voters = [
        await make_user(client, email=f"t{i:02d}@test.example.com", display_name=f"[TEST] {i}")
        for i in range(2, 6)
    ]

    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=t1["headers"],
        json={"text": "Replace the bulb and add it to the maintenance schedule."},
    )
    solution_id = created.json()["id"]
    for voter in voters:
        await client.put(
            "/votes",
            headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )

    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": "city", "entity_id": 1},
    )
    assert prepared.status_code == 200, prepared.text
    assert any(item["solution_id"] == solution_id for item in prepared.json()["items"])

    async with session_scope() as session:
        report = await test_data_service.impact_report(session)
    assert any("appears on ballot item" in row for row in report["foreign_rows"])

    async with session_scope() as session:
        with pytest.raises(Conflict) as excinfo:
            await test_data_service.purge(session, force=True)
        assert excinfo.value.code == "jury_participation_present"

    async with session_scope() as session:
        assert await users_repo.by_email(session, "t01@test.example.com") is not None


async def test_purge_is_a_no_op_with_no_test_accounts(client):
    await make_user(client, email="alone@example.com", display_name="Alone")
    async with session_scope() as session:
        report = await test_data_service.impact_report(session)
        assert report == {
            "test_accounts": 0,
            "posts": 0,
            "solutions": 0,
            "comments": 0,
            "amendments": 0,
            "foreign_rows": [],
        }
        result = await test_data_service.purge(session, force=False)
        assert result == {"test_accounts": 0, "deleted": {}, "foreign_rows_deleted": []}


async def test_purge_refuses_when_test_data_is_not_allowed(client, monkeypatch):
    from backend.config.settings_env import get_env_settings

    disallowed = get_env_settings().model_copy(update={"ALLOW_TEST_DATA": False})
    monkeypatch.setattr(test_data_service, "get_env_settings", lambda: disallowed)

    async with session_scope() as session:
        with pytest.raises(Conflict) as excinfo:
            await test_data_service.purge(session, force=False)
        assert excinfo.value.code == "test_data_disabled"
