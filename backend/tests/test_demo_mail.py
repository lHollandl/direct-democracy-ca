"""Change/02 fix-1, FX-04: demo mail (ARCHITECTURE.md §4).

`demo_link` is present on signup, resend-verification, and email-change only
when `EMAIL_BACKEND=console` **and** `ALLOW_TEST_DATA=true` — never in the
other three combinations, and never anywhere but the console email itself.
Resend-verification's own demo_link plumbing (FX-03) is covered in
`test_email_verification.py`; this file adds the two pre-existing endpoints
and the cross-cutting log-leak guarantee.
"""

from __future__ import annotations

import re

import pytest

from backend.config.settings_env import get_env_settings
from backend.services import account as account_service
from backend.services import auth as auth_service
from backend.tests.conftest import make_user


def _demo_settings(**overrides):
    return get_env_settings().model_copy(
        update={"EMAIL_BACKEND": "console", "ALLOW_TEST_DATA": True, **overrides}
    )


async def _signup(client, *, email: str, display_name: str):
    return await client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "Crosswalk1",
            "real_name": "Demo Person",
            "display_name": display_name,
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": 1,
            "city_id": 1,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )


@pytest.mark.parametrize(
    "email_backend, allow_test_data",
    [("console", False), ("smtp", True), ("smtp", False)],
)
async def test_demo_link_is_absent_outside_the_demo_combination(
    client, monkeypatch, email_backend, allow_test_data
):
    settings = _demo_settings(EMAIL_BACKEND=email_backend, ALLOW_TEST_DATA=allow_test_data)
    monkeypatch.setattr(auth_service, "get_env_settings", lambda: settings)
    monkeypatch.setattr(account_service, "get_env_settings", lambda: settings)

    signup = await _signup(
        client,
        email=f"demo-{email_backend}-{allow_test_data}@example.com",
        display_name=f"Demo{email_backend}{allow_test_data}",
    )
    assert signup.status_code == 201, signup.text
    assert signup.json().get("demo_link") is None

    verified_user = await make_user(
        client,
        email=f"demo-change-{email_backend}-{allow_test_data}@example.com",
        display_name=f"DemoChange{email_backend}{allow_test_data}",
    )
    change = await client.post(
        "/me/email",
        headers=verified_user["headers"],
        json={
            "new_email": f"new-{email_backend}-{allow_test_data}@example.com",
            "password": "Crosswalk1",
        },
    )
    assert change.status_code == 200, change.text
    assert change.json().get("demo_link") is None


async def test_demo_link_is_present_in_the_demo_combination(client, monkeypatch):
    settings = _demo_settings()
    monkeypatch.setattr(auth_service, "get_env_settings", lambda: settings)
    monkeypatch.setattr(account_service, "get_env_settings", lambda: settings)

    signup = await _signup(client, email="demo-on@example.com", display_name="DemoOn")
    assert signup.status_code == 201, signup.text
    assert signup.json()["demo_link"] is not None
    assert "verify-email?token=" in signup.json()["demo_link"]

    verified_user = await make_user(client, email="demo-on-3@example.com", display_name="DemoOnThree")
    change = await client.post(
        "/me/email",
        headers=verified_user["headers"],
        json={"new_email": "demo-on-3-new@example.com", "password": "Crosswalk1"},
    )
    assert change.status_code == 200, change.text
    assert "confirm-email-change?token=" in change.json()["demo_link"]


async def test_demo_link_never_reaches_a_log_line_beyond_the_console_email(client, monkeypatch, caplog):
    settings = _demo_settings()
    monkeypatch.setattr(auth_service, "get_env_settings", lambda: settings)

    with caplog.at_level("INFO"):
        signup = await _signup(client, email="demo-log@example.com", display_name="DemoLog")
    assert signup.status_code == 201, signup.text
    token = re.search(r"token=([A-Za-z0-9_\-]+)", signup.json()["demo_link"]).group(1)
    for record in caplog.records:
        for field, value in record.__dict__.items():
            if field == "email_body":
                continue
            assert token not in str(value), (
                f"the demo link's token leaked into log field {field!r} "
                f"on a {record.name!r} record"
            )
