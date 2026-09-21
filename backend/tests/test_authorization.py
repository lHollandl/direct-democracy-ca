"""Every endpoint's 401 and 403 paths (F-23, ARCHITECTURE.md §10).

Two questions asked of every endpoint that changes anything: does it refuse a
caller with no session, and does it refuse a caller who has a session but no
right to do this?
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app
from backend.tests.conftest import make_umbrella, make_user

#: (method, path, body) for every endpoint that requires a signed-in caller.
SIGNED_IN_ONLY = [
    ("GET", "/auth/me", None),
    ("PATCH", "/me/display", {"public_name_mode": "anonymous"}),
    ("POST", "/me/resend-verification", None),
    ("POST", "/me/export", None),
    ("GET", "/me/export/1", None),
    ("DELETE", "/me", {"password": "x", "understand_this_cannot_be_undone": True}),
    ("POST", "/posts", {
        "problem_text": "A problem long enough to be accepted by the validator here.",
        "solutions": ["A solution long enough to be accepted by the validator here."],
        "communities": [{"level": "city", "entity_id": 1}],
        "category_choice": "ai",
    }),
    ("POST", "/posts/label-preview", {
        "problem_text": "A problem long enough to be accepted by the validator here.",
        "communities": [{"level": "city", "entity_id": 1}],
    }),
    ("POST", "/posts/1/label/confirm", None),
    ("POST", "/posts/1/label/correct", {"level": "city", "entity_id": 1, "umbrella_id": 1}),
    ("POST", "/umbrellas/1/solutions", {"text": "A solution long enough to be accepted here."}),
    ("POST", "/umbrellas/1/references", {"url": "https://example.com", "note": "why"}),
    ("PATCH", "/solutions/1", {"text": "A replacement long enough to be accepted here."}),
    ("POST", "/solutions/1/amendments", {
        "proposed_text": "A replacement long enough to be accepted by the validator.",
        "rationale": "A rationale of the right length.",
    }),
    ("POST", "/amendments/1/withdraw", None),
    ("POST", "/similarity/1/decide", {"choice": "same"}),
    ("POST", "/comments", {"target_type": "umbrella", "target_id": 1, "text": "hello"}),
    ("PATCH", "/comments/1", {"text": "hello again"}),
    ("DELETE", "/comments/1", None),
    ("PUT", "/votes", {"target_type": "solution", "target_id": 1, "direction": 1}),
    ("DELETE", "/votes", {"target_type": "solution", "target_id": 1}),
    ("PUT", "/references/1/feedback", {"useful": True}),
    ("PUT", "/cycles/1/ballot/1/vote", {"choice": "yes"}),
    ("GET", "/juries/mine", None),
    ("POST", "/jurors/1/accept", None),
    ("POST", "/jurors/1/decline", None),
    ("POST", "/ballot-items/1/holdback", {
        "juror_id": 1,
        "reason_category": "other",
        "reason_text": "A reason long enough to satisfy the twenty character minimum.",
    }),
    ("GET", "/results", None),
]

ADMIN_ONLY = [
    ("POST", "/admin/settings", {"key": "jury_size", "value": "5", "reason": "because"}),
    ("POST", "/admin/cycles/prepare", {"level": "city", "entity_id": 1}),
    ("POST", "/admin/cycles/1/redraw-jury", {"reason": "because"}),
    ("POST", "/admin/cycles/1/open", None),
    ("POST", "/admin/cycles/1/close", None),
    ("POST", "/admin/cycles/1/publish", None),
    ("POST", "/admin/umbrellas/1/recommend-references", None),
    ("POST", "/admin/posts/1/relabel", None),
    ("GET", "/admin/users/1", None),
]

PUBLIC = [
    "/settings",
    "/settings/history",
    "/ai/actions",
    "/admin/log",
    "/geo/counties",
    "/legal/privacy",
    "/legal/terms",
    "/legal/cookies",
    "/summaries/hashes",
]


def _get_write_routes() -> dict[tuple[str, str], APIRoute]:
    """Every non-GET `APIRoute` FastAPI actually serves, keyed by (method,
    path) — unwrapping the nested `_IncludedRouter` layer, the same way
    test_pagination.py walks the live route table."""
    found: dict[tuple[str, str], APIRoute] = {}

    def walk(router) -> None:
        for r in router.routes:
            if hasattr(r, "original_router"):
                walk(r.original_router)
            elif isinstance(r, APIRoute):
                for method in r.methods:
                    if method in ("POST", "PUT", "PATCH", "DELETE"):
                        found[(method, r.path)] = r

    walk(app.router)
    return found


WRITE_ROUTES = _get_write_routes()

#: Public by specification — account creation and session management need no
#: session yet (ARCHITECTURE.md §4).
PUBLIC_WRITE_PATHS = {
    ("POST", "/auth/signup"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/verify-email"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/confirm-email-change"),
}

#: Every write that needs a signed-in caller but not a verified or admin one
#: — including the own-account endpoints (`PATCH /me/display`, `PATCH
#: /me/profile`, `POST /me/email`, `POST /me/resend-verification`, `POST
#: /me/export`, `DELETE /me`) ARCHITECTURE.md §4 exempts from the
#: verified-email gate by design: a person's rights over their own data
#: cannot depend on our verification email having arrived (audit demo-01 run
#: 4, document ambiguity 3) — and a mistyped signup email must be fixable,
#: and a new link askable, even though the account can never verify without
#: one.
SIGNED_IN_WRITE_PATHS = {
    ("PATCH", "/me/display"),
    ("PATCH", "/me/profile"),
    ("POST", "/me/email"),
    ("POST", "/me/resend-verification"),
    ("POST", "/me/home"),
    ("POST", "/me/export"),
    ("DELETE", "/me"),
    ("POST", "/posts"),
    ("POST", "/posts/label-preview"),
    ("POST", "/posts/{post_id}/label/confirm"),
    ("POST", "/posts/{post_id}/label/correct"),
    ("POST", "/umbrellas/{umbrella_id}/solutions"),
    ("POST", "/umbrellas/{umbrella_id}/references"),
    ("PATCH", "/solutions/{solution_id}"),
    ("POST", "/solutions/{solution_id}/amendments"),
    ("POST", "/amendments/{amendment_id}/withdraw"),
    ("POST", "/similarity/{similarity_id}/decide"),
    ("POST", "/comments"),
    ("PATCH", "/comments/{comment_id}"),
    ("DELETE", "/comments/{comment_id}"),
    ("PUT", "/votes"),
    ("DELETE", "/votes"),
    ("PUT", "/references/{reference_id}/feedback"),
    ("PUT", "/cycles/{cycle_id}/ballot/{item_id}/vote"),
    ("POST", "/jurors/{juror_id}/accept"),
    ("POST", "/jurors/{juror_id}/decline"),
    ("POST", "/ballot-items/{item_id}/holdback"),
}

#: Every write that needs `is_admin` (DEMOCRACY.md §13).
ADMIN_WRITE_PATHS = {
    ("POST", "/admin/settings"),
    ("POST", "/admin/cycles/prepare"),
    ("POST", "/admin/cycles/{cycle_id}/redraw-jury"),
    ("POST", "/admin/cycles/{cycle_id}/open"),
    ("POST", "/admin/cycles/{cycle_id}/close"),
    ("POST", "/admin/cycles/{cycle_id}/publish"),
    ("POST", "/admin/umbrellas/{umbrella_id}/recommend-references"),
    ("POST", "/admin/posts/{post_id}/relabel"),
}


def test_every_write_endpoint_is_sorted_into_exactly_one_named_set():
    """Audit demo-01 run 4, document ambiguity 5: `SIGNED_IN_ONLY` and
    `ADMIN_ONLY` above are hand-maintained lists of literal test requests, so
    a newly added endpoint could ship with no 401/403 coverage and nothing
    would notice — the exact gap `test_pagination.py` closed for list
    endpoints by walking the live route table instead of a remembered list.
    This does the same thing for every write endpoint: every one must be
    public by specification, need only a signed-in caller, or need an
    administrator, and a route that fits none of the three fails loudly
    instead of silently passing unchecked."""
    live = set(WRITE_ROUTES)
    named = PUBLIC_WRITE_PATHS | SIGNED_IN_WRITE_PATHS | ADMIN_WRITE_PATHS
    missing = live - named
    assert not missing, (
        f"Route(s) {sorted(missing)} aren't sorted into PUBLIC_WRITE_PATHS, "
        "SIGNED_IN_WRITE_PATHS, or ADMIN_WRITE_PATHS in "
        "backend/tests/test_authorization.py — a new write endpoint could ship "
        "with no 401/403 coverage otherwise."
    )
    stale = named - live
    assert not stale, f"Route(s) {sorted(stale)} no longer exist — remove them from this file."
    overlap = (
        (PUBLIC_WRITE_PATHS & SIGNED_IN_WRITE_PATHS)
        | (PUBLIC_WRITE_PATHS & ADMIN_WRITE_PATHS)
        | (SIGNED_IN_WRITE_PATHS & ADMIN_WRITE_PATHS)
    )
    assert not overlap, f"Route(s) {sorted(overlap)} are in more than one set."


@pytest.mark.parametrize("method, path, body", SIGNED_IN_ONLY)
async def test_signed_out_callers_are_refused(client, method, path, body):
    response = await client.request(method, path, json=body)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    assert response.json()["error"] in ("not_signed_in", "unauthorized")


@pytest.mark.parametrize("method, path, body", ADMIN_ONLY)
async def test_admin_endpoints_refuse_a_signed_out_caller(client, method, path, body):
    response = await client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize("method, path, body", ADMIN_ONLY)
async def test_admin_endpoints_refuse_an_ordinary_member(client, method, path, body):
    member = await make_user(client, email="member@example.com", display_name="Member")
    response = await client.request(method, path, headers=member["headers"], json=body)
    assert response.status_code == 403, f"{method} {path} answered {response.status_code}"
    assert response.json()["error"] == "not_admin"


@pytest.mark.parametrize("path", PUBLIC)
async def test_the_transparency_pages_need_no_account(client, path):
    response = await client.get(path)
    assert response.status_code == 200, f"{path} answered {response.status_code}"


async def test_an_unverified_account_is_refused_every_write(client):
    user = await make_user(
        client, email="unverified@example.com", display_name="Unverified", verify=False
    )
    for method, path, body in SIGNED_IN_ONLY:
        if method == "GET" or path in (
            "/me/export",
            "/me/export/1",
            "/me",
            "/auth/me",
            "/me/display",
            "/me/resend-verification",
        ):
            continue
        response = await client.request(method, path, headers=user["headers"], json=body)
        assert response.status_code in (403, 404, 409, 422), f"{method} {path}"
        if response.status_code == 403:
            assert response.json()["error"] in ("email_not_verified", "not_a_member")


async def test_a_member_of_another_community_can_read_but_not_act(client):
    umbrella = await make_umbrella(name="Safety", statement="Crossings are unsafe.")
    outsider = await make_user(
        client, email="vallejo@example.com", display_name="Vallejo", city_id=2, county_id=2
    )
    assert (await client.get(f"/umbrellas/{umbrella}")).status_code == 200

    response = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=outsider["headers"],
        json={"text": "A solution from somebody who does not live in this city at all."},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "not_a_member"

    comment = await client.post(
        "/comments",
        headers=outsider["headers"],
        json={"target_type": "umbrella", "target_id": umbrella, "text": "From out of town."},
    )
    assert comment.status_code == 403


async def test_an_expired_or_forged_token_is_refused(client):
    for token in ("not-a-jwt", "a.b.c", ""):
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


async def test_an_administrator_cannot_see_anyone_s_ballot_vote(client):
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    member = await make_user(client, email="mem@example.com", display_name="Mem")
    response = await client.get(f"/admin/users/{member['id']}", headers=director["headers"])
    assert response.status_code == 200
    payload = response.json()
    assert "jury_history" in payload
    assert isinstance(payload["ballot_votes"], str)
    assert "Not available" in payload["ballot_votes"]
    body = response.text.lower()
    assert '"choice"' not in body and '"yes"' not in body
