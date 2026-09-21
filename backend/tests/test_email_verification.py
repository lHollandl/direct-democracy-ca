"""Change/02 fix-1, FX-03: resend verification (ARCHITECTURE.md §6).

The `demo_link` field this endpoint's response carries is ARCHITECTURE.md §4
"Demo mail" (FX-04); `test_demo_mail.py` covers the four EMAIL_BACKEND ×
ALLOW_TEST_DATA combinations across all three endpoints that carry it.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from backend.clients import email as email_client
from backend.config.settings_env import get_env_settings
from backend.db import session_scope
from backend.repositories import users as users_repo
from backend.tests.conftest import make_user


async def _clear_resend_wait(user_id: int) -> None:
    """Back-date the account's latest verification token past
    `VERIFY_RESEND_MINUTES` so a test can resend right after signup without
    tripping the rate limit that behavior itself is proving elsewhere."""
    async with session_scope() as session:
        latest = await users_repo.latest_email_verification(session, user_id)
        env = get_env_settings()
        latest.created_at = datetime.now(timezone.utc) - timedelta(
            minutes=env.VERIFY_RESEND_MINUTES + 1
        )


async def test_resend_issues_a_new_token_and_voids_the_old_one(client):
    user = await make_user(client, email="resend@example.com", display_name="Resend", verify=False)
    first_body = email_client.sent_messages()[-1]["body"]
    old_token = re.search(r"token=([A-Za-z0-9_\-]+)", first_body).group(1)

    await _clear_resend_wait(user["id"])
    response = await client.post("/me/resend-verification", headers=user["headers"])
    assert response.status_code == 200, response.text

    old_use = await client.post("/auth/verify-email", json={"token": old_token})
    assert old_use.status_code == 422
    assert old_use.json()["error"] == "verification_invalid"

    new_body = email_client.sent_messages()[-1]["body"]
    new_token = re.search(r"token=([A-Za-z0-9_\-]+)", new_body).group(1)
    confirmed = await client.post("/auth/verify-email", json={"token": new_token})
    assert confirmed.status_code == 200, confirmed.text


async def test_resend_refuses_a_second_request_inside_the_wait(client):
    """Signup itself sends the first verification token, so even the very
    first resend request is within `VERIFY_RESEND_MINUTES` of it."""
    user = await make_user(client, email="ratelimited@example.com", display_name="RateLimited", verify=False)
    first = await client.post("/me/resend-verification", headers=user["headers"])
    assert first.status_code == 429
    assert "Retry-After" in first.headers

    await _clear_resend_wait(user["id"])
    second = await client.post("/me/resend-verification", headers=user["headers"])
    assert second.status_code == 200, second.text
    third = await client.post("/me/resend-verification", headers=user["headers"])
    assert third.status_code == 429
    assert "Retry-After" in third.headers


async def test_resend_is_allowed_again_once_the_wait_has_passed(client):
    user = await make_user(client, email="patient@example.com", display_name="Patient", verify=False)
    await _clear_resend_wait(user["id"])
    second = await client.post("/me/resend-verification", headers=user["headers"])
    assert second.status_code == 200, second.text

    await _clear_resend_wait(user["id"])
    third = await client.post("/me/resend-verification", headers=user["headers"])
    assert third.status_code == 200, third.text


async def test_resend_refuses_an_already_verified_account(client):
    user = await make_user(client, email="already@example.com", display_name="Already")
    response = await client.post("/me/resend-verification", headers=user["headers"])
    assert response.status_code == 409
    assert response.json()["error"] == "already_verified"
