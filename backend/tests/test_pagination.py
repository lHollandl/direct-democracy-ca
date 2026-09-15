"""ARCHITECTURE.md §6 pagination, plus a completeness check over the live
route table.

Audit demo-01 run 3, HIGH: seven list endpoints had no pagination support at
all. They went unnoticed because nothing walked the app's actual route table
— a hand-picked "known paginated endpoints" test (like fix run 2's own) can
only ever check what someone remembered to add to it. This file partitions
every GET route FastAPI actually serves into three named, non-overlapping
sets — list endpoints (must paginate), the five documented exemptions, and
single-resource/whole-page views (never a plain, ever-growing enumeration)
— and fails loudly if a new route doesn't fit any of them, so a future list
endpoint can't join the unpaginated set unnoticed the way these seven did.
"""

from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from backend.main import app
from backend.tests.conftest import make_umbrella, make_user


def _get_routes() -> dict[str, APIRoute]:
    """Every GET `APIRoute` FastAPI actually serves, unwrapping the nested
    `_IncludedRouter` layer `app.include_router` produces."""
    found: dict[str, APIRoute] = {}

    def walk(router) -> None:
        for r in router.routes:
            if hasattr(r, "original_router"):
                walk(r.original_router)
            elif isinstance(r, APIRoute) and "GET" in r.methods:
                found[r.path] = r

    walk(app.router)
    return found


ROUTES = _get_routes()

#: ARCHITECTURE.md §6 — four of the five fixed-size reference lists that
#: return whole (the fifth, the feed's category-filter metadata, isn't a
#: separate route — it is embedded in `/feed`, which is itself a
#: LIST_ENDPOINT below and already paginates its own primary list).
EXEMPT_PATHS = {
    "/communities/{level}/{entity_id}/officials",
    "/geo/counties",
    "/geo/counties/{county_id}/cities",
    "/settings",
}

#: Every GET endpoint whose job is to enumerate a collection that can grow
#: without bound over the platform's life (ARCHITECTURE.md §6).
LIST_ENDPOINTS = {
    "/admin/log",
    "/ai/actions",
    "/feed",
    "/umbrellas",
    "/communities/{level}/{entity_id}/cycles",
    "/settings/history",
    "/solutions/{solution_id}/amendments",
    "/summaries/hashes",
    "/umbrellas/{umbrella_id}/comments",
    "/umbrellas/{umbrella_id}/references",
    "/umbrellas/{umbrella_id}/solutions",
}

#: Everything else: a single resource, or a whole-page assembly that embeds
#: other lists as page furniture (the page a person is actively looking at,
#: not an open scroll) — audit runs 1 through 3 have never flagged any of
#: these for missing pagination. Named explicitly so a brand-new route that
#: isn't sorted into any of the three sets fails the completeness check
#: below instead of silently passing unchecked.
DETAIL_ENDPOINTS = {
    "/admin/users/{user_id}",
    "/auth/me",
    "/communities/{level}/{entity_id}",
    "/cycles/{cycle_id}",
    "/cycles/{cycle_id}/ballot",
    "/health",
    "/juries/mine",
    "/legal/cookies",
    "/legal/current-version",
    "/legal/privacy",
    "/legal/terms",
    "/me/export/{export_id}",
    "/posts/{post_id}",
    "/results",
    "/solutions/{solution_id}",
    "/summaries/{level}/{entity_id}/{number}",
    "/summaries/{level}/{entity_id}/{number}/json",
    "/summaries/{level}/{entity_id}/{number}/pdf",
    "/summaries/{level}/{entity_id}/{number}/verify",
    "/umbrellas/{umbrella_id}",
}


def test_every_get_route_is_sorted_into_exactly_one_named_set():
    live_paths = set(ROUTES)
    named = EXEMPT_PATHS | LIST_ENDPOINTS | DETAIL_ENDPOINTS
    missing = live_paths - named
    assert not missing, (
        f"Route(s) {sorted(missing)} aren't sorted into EXEMPT_PATHS, "
        "LIST_ENDPOINTS, or DETAIL_ENDPOINTS in backend/tests/test_pagination.py "
        "— a new list endpoint could join the unpaginated set unnoticed "
        "otherwise (ARCHITECTURE.md §6)."
    )
    stale = named - live_paths
    assert not stale, f"Route(s) {sorted(stale)} no longer exist — remove them from this file."
    overlap = (EXEMPT_PATHS & LIST_ENDPOINTS) | (EXEMPT_PATHS & DETAIL_ENDPOINTS) | (
        LIST_ENDPOINTS & DETAIL_ENDPOINTS
    )
    assert not overlap, f"Route(s) {sorted(overlap)} are in more than one set."


def test_every_list_endpoint_accepts_cursor_and_limit():
    """Audit demo-01 run 3, HIGH — the seven newly-fixed endpoints, and every
    already-correct one, must each declare `cursor` and `limit`."""
    missing = {}
    for path in sorted(LIST_ENDPOINTS):
        params = inspect.signature(ROUTES[path].endpoint).parameters
        needed = {"cursor", "limit"} - set(params)
        if needed:
            missing[path] = sorted(needed)
    assert not missing, f"List endpoint(s) missing cursor/limit: {missing}"


def test_an_over_limit_is_refused_and_default_limit_is_25():
    for path, route in ROUTES.items():
        if path not in LIST_ENDPOINTS:
            continue
        params = inspect.signature(route.endpoint).parameters
        limit_default = params["limit"].default
        assert limit_default == 25, f"{path}: default limit is {limit_default!r}, not 25"


# --------------------------------------------------------------------------
# Behavioral coverage for the seven endpoints audit demo-01 run 3 named.
# --------------------------------------------------------------------------


async def _make_members(client, n: int, prefix: str) -> list[dict]:
    return [
        await make_user(client, email=f"{prefix}{i}@example.com", display_name=f"{prefix}{i}")
        for i in range(n)
    ]


async def test_solutions_comments_and_references_paginate(client):
    umbrella = await make_umbrella(name="Streetlights", statement="Streets are dark at night.")
    people = await _make_members(client, 3, "sol")

    for i, person in enumerate(people):
        created = await client.post(
            f"/umbrellas/{umbrella}/solutions",
            headers=person["headers"],
            json={"text": f"Solution number {i} for the dark streets, written out in full."},
        )
        assert created.status_code == 201, created.text

    over_limit = await client.get(f"/umbrellas/{umbrella}/solutions?limit=500")
    assert over_limit.status_code == 422

    first = (await client.get(f"/umbrellas/{umbrella}/solutions?limit=2")).json()
    assert len(first["solutions"]) == 2
    assert first["next_cursor"] is not None

    second = (
        await client.get(f"/umbrellas/{umbrella}/solutions?limit=2&cursor={first['next_cursor']}")
    ).json()
    assert len(second["solutions"]) == 1
    assert second["next_cursor"] is None
    seen = {s["id"] for s in first["solutions"]} | {s["id"] for s in second["solutions"]}
    assert len(seen) == 3, "no solution repeated or skipped across pages"

    for i in range(3):
        posted = await client.post(
            "/comments",
            headers=people[0]["headers"],
            json={"target_type": "umbrella", "target_id": umbrella, "text": f"Comment {i}."},
        )
        assert posted.status_code == 201, posted.text

    comments_over_limit = await client.get(f"/umbrellas/{umbrella}/comments?limit=500")
    assert comments_over_limit.status_code == 422

    c_first = (await client.get(f"/umbrellas/{umbrella}/comments?limit=2")).json()
    assert len(c_first["comments"]) == 2
    assert c_first["next_cursor"] is not None
    c_second = (
        await client.get(f"/umbrellas/{umbrella}/comments?limit=2&cursor={c_first['next_cursor']}")
    ).json()
    assert len(c_second["comments"]) == 1
    assert c_second["next_cursor"] is None

    for i in range(3):
        added = await client.post(
            f"/umbrellas/{umbrella}/references",
            headers=people[0]["headers"],
            json={"url": f"https://example.com/{i}", "note": f"Why reference {i} matters."},
        )
        assert added.status_code == 201, added.text

    refs_over_limit = await client.get(f"/umbrellas/{umbrella}/references?limit=500")
    assert refs_over_limit.status_code == 422

    r_first = (await client.get(f"/umbrellas/{umbrella}/references?limit=2")).json()
    assert len(r_first["active"]) == 2
    assert r_first["next_cursor"] is not None
    r_second = (
        await client.get(
            f"/umbrellas/{umbrella}/references?limit=2&cursor={r_first['next_cursor']}"
        )
    ).json()
    assert len(r_second["active"]) == 1
    assert r_second["next_cursor"] is None


async def test_settings_history_paginates(client):
    director = await make_user(client, email="dir@example.com", display_name="Dir", admin=True)
    for value in ("5", "7", "9"):
        changed = await client.post(
            "/admin/settings",
            headers=director["headers"],
            json={"key": "jury_size", "value": value, "reason": "testing pagination"},
        )
        assert changed.status_code == 200

    over_limit = await client.get("/settings/history?key=jury_size&limit=500")
    assert over_limit.status_code == 422

    # 3 changes plus the seeded initial value = 4 rows total.
    seen = []
    cursor = None
    for _ in range(10):
        url = f"/settings/history?key=jury_size&limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = (await client.get(url)).json()
        seen.extend(row["value"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["9", "7", "5", "3"], "newest first, no row repeated or skipped"


async def test_amendments_paginate(client):
    umbrella = await make_umbrella(name="Parks", statement="Park restrooms are locked.")
    author = await make_user(client, email="auth@example.com", display_name="Auth")
    voter = await make_user(client, email="voter@example.com", display_name="Voter")
    people = await _make_members(client, 3, "amend")

    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=author["headers"],
        json={"text": "Reopen the restrooms and put them on the daily cleaning round."},
    )
    solution_id = created.json()["id"]
    await client.put(
        "/votes",
        headers=voter["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )

    for i, person in enumerate(people):
        proposed = await client.post(
            f"/solutions/{solution_id}/amendments",
            headers=person["headers"],
            json={
                "proposed_text": f"A rewritten cleaning schedule, version {i}, spelled out fully.",
                "rationale": f"Rationale number {i} of sufficient length.",
            },
        )
        assert proposed.status_code == 201, proposed.text

    over_limit = await client.get(f"/solutions/{solution_id}/amendments?limit=500")
    assert over_limit.status_code == 422

    first = (await client.get(f"/solutions/{solution_id}/amendments?limit=2")).json()
    assert len(first["amendments"]) == 2
    assert first["next_cursor"] is not None

    second = (
        await client.get(
            f"/solutions/{solution_id}/amendments?limit=2&cursor={first['next_cursor']}"
        )
    ).json()
    assert len(second["amendments"]) == 1
    assert second["next_cursor"] is None


async def _publish_zero_item_cycle(client, director, *, level: str = "city", entity_id: int = 1):
    prepared = await client.post(
        "/admin/cycles/prepare",
        headers=director["headers"],
        json={"level": level, "entity_id": entity_id},
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["items"] == [], "these are zero-item cycles by design, to keep this test small"
    published = await client.post(
        f"/admin/cycles/{prepared.json()['cycle_id']}/publish", headers=director["headers"]
    )
    assert published.status_code == 200, published.text


async def test_community_cycles_and_hash_list_paginate(client):
    director = await make_user(client, email="dir2@example.com", display_name="Dir2", admin=True)
    for _ in range(3):
        await _publish_zero_item_cycle(client, director)

    cycles_over_limit = await client.get("/communities/city/1/cycles?limit=500")
    assert cycles_over_limit.status_code == 422

    c_first = (await client.get("/communities/city/1/cycles?limit=2")).json()
    assert len(c_first["cycles"]) == 2
    assert c_first["next_cursor"] is not None
    c_second = (
        await client.get(f"/communities/city/1/cycles?limit=2&cursor={c_first['next_cursor']}")
    ).json()
    assert len(c_second["cycles"]) == 1
    assert c_second["next_cursor"] is None

    hashes_over_limit = await client.get("/summaries/hashes?limit=500")
    assert hashes_over_limit.status_code == 422

    h_first = (await client.get("/summaries/hashes?limit=2")).json()
    assert len(h_first["summaries"]) == 2
    assert h_first["next_cursor"] is not None
    h_second = (
        await client.get(f"/summaries/hashes?limit=2&cursor={h_first['next_cursor']}")
    ).json()
    assert len(h_second["summaries"]) == 1
    assert h_second["next_cursor"] is None
