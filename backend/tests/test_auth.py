"""Auth: rotation, reuse detection, the logout blacklist, and the age gate (F-23)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.clients import email as email_client
from backend.db import session_scope
from backend.repositories import users as users_repo
from backend.tests.conftest import make_user


async def test_signup_refuses_an_under_age_applicant_and_stores_nothing(client):
    response = await client.post(
        "/auth/signup",
        json={
            "email": "child@example.com",
            "password": "Crosswalk1",
            "real_name": "Too Young",
            "display_name": "TooYoung",
            "date_of_birth": (date.today() - timedelta(days=365 * 12)).isoformat(),
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 1,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"] == "too_young"
    async with session_scope() as session:
        assert await users_repo.by_email(session, "child@example.com") is None


async def test_signup_age_gate_reads_the_setting_not_a_constant(client):
    from backend.tests.conftest import set_setting

    await set_setting("min_signup_age", "21")
    response = await client.post(
        "/auth/signup",
        json={
            "email": "nineteen@example.com",
            "password": "Crosswalk1",
            "real_name": "Nineteen",
            "display_name": "Nineteen",
            "date_of_birth": (date.today() - timedelta(days=365 * 19)).isoformat(),
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 1,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 422
    assert "at least 21" in response.json()["message"]


@pytest.mark.parametrize(
    "password, problem",
    [("short1A", "8 characters"), ("alllowercase1", "capital"), ("NoDigitsHere", "number")],
)
async def test_password_policy(client, password, problem):
    response = await client.post(
        "/auth/signup",
        json={
            "email": f"pw{len(password)}@example.com",
            "password": password,
            "real_name": "Pass Word",
            "display_name": f"PW{len(password)}",
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 1,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 422
    assert problem in response.json()["message"]


async def test_writes_are_refused_until_the_email_is_confirmed(client):
    user = await make_user(client, email="unconfirmed@example.com", display_name="Unconfirmed", verify=False)
    response = await client.post(
        "/posts",
        headers=user["headers"],
        json={
            "problem_text": "A problem long enough to pass validation but from an unconfirmed account.",
            "solutions": ["A solution long enough to pass validation as well."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "email_not_verified"


async def test_a_verification_link_works_once(client):
    await make_user(client, email="once@example.com", display_name="Once", verify=False)
    token = re.search(r"token=([A-Za-z0-9_\-]+)", email_client.sent_messages()[-1]["body"]).group(1)
    assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 200
    second = await client.post("/auth/verify-email", json={"token": token})
    assert second.status_code == 422
    assert second.json()["error"] == "verification_invalid"


async def test_login_says_the_same_thing_for_an_unknown_address_and_a_wrong_password(client):
    await make_user(client, email="known@example.com", display_name="Known")
    unknown = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "Crosswalk1"}
    )
    wrong = await client.post(
        "/auth/login", json={"email": "known@example.com", "password": "WrongPass1"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json(), (
        "a different answer would let anyone enumerate who has an account"
    )


async def test_the_refresh_token_is_only_ever_in_a_cookie(client):
    await make_user(client, email="cookie@example.com", display_name="Cookie")
    login = await client.post(
        "/auth/login", json={"email": "cookie@example.com", "password": "Crosswalk1"}
    )
    assert "refresh_token" not in login.text
    cookie = login.cookies.get("refresh_token")
    assert cookie
    header = login.headers.get("set-cookie", "")
    assert "httponly" in header.lower()
    assert "samesite=strict" in header.lower()


async def test_refresh_rotates_and_reuse_revokes_the_whole_chain(client):
    await make_user(client, email="rotate@example.com", display_name="Rotate")
    login = await client.post(
        "/auth/login", json={"email": "rotate@example.com", "password": "Crosswalk1"}
    )
    first = login.cookies["refresh_token"]

    rotated = await client.post("/auth/refresh", cookies={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.cookies["refresh_token"]
    assert second != first, "a refresh must rotate the token"

    reused = await client.post("/auth/refresh", cookies={"refresh_token": first})
    assert reused.status_code == 401
    assert reused.json()["error"] == "refresh_reused"

    after = await client.post("/auth/refresh", cookies={"refresh_token": second})
    assert after.status_code == 401, (
        "detecting reuse must revoke the whole chain, including the newest token"
    )


async def test_logout_blacklists_the_access_token(client):
    user = await make_user(client, email="logout@example.com", display_name="Logout")
    assert (await client.get("/auth/me", headers=user["headers"])).status_code == 200
    assert (await client.post("/auth/logout", headers=user["headers"])).status_code == 200
    after = await client.get("/auth/me", headers=user["headers"])
    assert after.status_code == 401
    assert after.json()["error"] == "token_revoked"


async def test_password_reset_signs_every_session_out(client):
    user = await make_user(client, email="reset@example.com", display_name="Reset")
    asked = await client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    assert asked.status_code == 200
    token = re.search(r"token=([A-Za-z0-9_\-]+)", email_client.sent_messages()[-1]["body"]).group(1)

    done = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewCrossing2"}
    )
    assert done.status_code == 200
    assert (
        await client.post(
            "/auth/login", json={"email": "reset@example.com", "password": "Crosswalk1"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/auth/login", json={"email": "reset@example.com", "password": "NewCrossing2"}
        )
    ).status_code == 200
    used_again = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": "AnotherOne3"}
    )
    assert used_again.status_code == 422


async def test_forgot_password_says_the_same_thing_for_an_unknown_address(client):
    known = await client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert known.status_code == 200
    assert "If that address has an account" in known.json()["message"]


async def test_expired_verification_tokens_are_refused(client):
    await make_user(client, email="expired@example.com", display_name="Expired", verify=False)
    token = re.search(r"token=([A-Za-z0-9_\-]+)", email_client.sent_messages()[-1]["body"]).group(1)
    from backend.services import security

    async with session_scope() as session:
        row = await users_repo.email_verification_by_hash(
            session, security.token_fingerprint(token)
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    response = await client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 422


async def test_a_display_name_cannot_be_taken_twice(client):
    await make_user(client, email="first@example.com", display_name="SameName")
    response = await client.post(
        "/auth/signup",
        json={
            "email": "second@example.com",
            "password": "Crosswalk1",
            "real_name": "Second Person",
            "display_name": "samename",
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 1,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == "display_name_taken"


async def test_a_city_must_be_in_the_county_the_person_chose(client):
    response = await client.post(
        "/auth/signup",
        json={
            "email": "mismatch@example.com",
            "password": "Crosswalk1",
            "real_name": "Mismatch Person",
            "display_name": "Mismatch",
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 2,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"] == "city_county_mismatch"
