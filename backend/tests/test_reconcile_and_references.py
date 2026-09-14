"""Reconciliation, references, and the parts of the schema promise that only a
running database can show (DATABASE.md §7, DEMOCRACY.md §9.4)."""

from __future__ import annotations

from sqlalchemy import update

from backend.clients import ollama as ollama_client
from backend.clients import search as search_client
from backend.db import session_scope
from backend.jobs import reconcile as reconcile_job
from backend.models import Post, Solution
from backend.tests.conftest import FakeSearch, make_umbrella, make_user, set_setting


async def _a_voted_solution(client):
    umbrella = await make_umbrella(name="Parks", statement="Park restrooms are locked.")
    author = await make_user(client, email="a@example.com", display_name="Ann")
    ben = await make_user(client, email="b@example.com", display_name="Ben")
    created = await client.post(
        f"/umbrellas/{umbrella}/solutions",
        headers=author["headers"],
        json={"text": "Reopen the restrooms and put them on the daily cleaning round."},
    )
    solution_id = created.json()["id"]
    await client.put(
        "/votes",
        headers=ben["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    return umbrella, solution_id, author, ben


async def test_reconcile_finds_and_corrects_a_drifted_net_score(client):
    _umbrella, solution_id, _a, _b = await _a_voted_solution(client)
    async with session_scope() as session:
        await session.execute(
            update(Solution).where(Solution.id == solution_id).values(net_score=99)
        )

    async with session_scope() as session:
        report = await reconcile_job.run(session, correct=True)

    drift = [d for d in report["net_score_drift"] if d["id"] == solution_id]
    assert drift and drift[0]["stored"] == 99 and drift[0]["computed"] == 1
    async with session_scope() as session:
        assert (await session.get(Solution, solution_id)).net_score == 1
    assert not report["hash_mismatches"]
    assert not report["orphan_communities"]


async def test_reconcile_reports_a_hash_mismatch_and_never_repairs_it(client):
    _umbrella, solution_id, author, _ben = await _a_voted_solution(client)
    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "The restrooms in the neighbourhood park have been locked for a year.",
            "solutions": ["Reopen them and put them on the daily cleaning round."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    post_id = created.json()["id"]
    async with session_scope() as session:
        await session.execute(
            update(Post).where(Post.id == post_id).values(problem_text="Something else entirely.")
        )

    async with session_scope() as session:
        report = await reconcile_job.run(session, correct=True)

    mismatches = [m for m in report["hash_mismatches"] if m["table"] == "posts"]
    assert mismatches, "a changed post must show up as a mismatch"
    async with session_scope() as session:
        post = await session.get(Post, post_id)
        assert post.content_hash == mismatches[0]["stored"], (
            "a fingerprint is evidence, not something to quietly repair"
        )


async def test_reconcile_re_evaluates_dominance_against_todays_active_users(client):
    _umbrella, solution_id, _a, _b = await _a_voted_solution(client)
    async with session_scope() as session:
        await session.execute(
            update(Solution).where(Solution.id == solution_id).values(is_dominant=False)
        )
    async with session_scope() as session:
        report = await reconcile_job.run(session, correct=True)
    changes = [c for c in report["dominance_changes"] if c["solution_id"] == solution_id]
    assert changes and changes[0]["now"] is True
    assert changes[0]["active_users"] >= 1
    async with session_scope() as session:
        assert (await session.get(Solution, solution_id)).is_dominant is True


async def test_reconcile_reports_counts_before_and_after(client):
    await _a_voted_solution(client)
    async with session_scope() as session:
        report = await reconcile_job.run(session, correct=True)
    assert report["counts_before"]["solutions"] == 1
    assert report["counts_after"]["votes"] == 1
    assert "users" in report["counts_before"]


async def test_a_member_can_add_a_reference_and_the_community_can_reject_it(client):
    umbrella, _solution_id, author, ben = await _a_voted_solution(client)
    cara = await make_user(client, email="c@example.com", display_name="Cara")

    added = await client.post(
        f"/umbrellas/{umbrella}/references",
        headers=author["headers"],
        json={
            "url": "https://example.com/parks-budget",
            "title": "Parks budget",
            "note": "The maintenance line item this depends on.",
        },
    )
    assert added.status_code == 201
    reference_id = added.json()["id"]

    first = await client.put(
        f"/references/{reference_id}/feedback", headers=ben["headers"], json={"useful": False}
    )
    assert first.json()["status"] == "active", "one press is not a rejection"

    second = await client.put(
        f"/references/{reference_id}/feedback", headers=cara["headers"], json={"useful": False}
    )
    assert second.json()["status"] == "rejected"

    listing = (await client.get(f"/umbrellas/{umbrella}/references")).json()
    assert listing["active"] == []
    assert len(listing["rejected"]) == 1, "a rejected reference is still visible, never deleted"


async def test_a_bad_url_is_refused(client):
    umbrella, _s, author, _b = await _a_voted_solution(client)
    response = await client.post(
        f"/umbrellas/{umbrella}/references",
        headers=author["headers"],
        json={"url": "javascript:alert(1)", "title": "x", "note": "nope"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "bad_url"


async def test_the_recommender_logs_the_provider_the_queries_and_the_raw_results(client):
    umbrella, _s, author, _b = await _a_voted_solution(client)
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )

    fake = FakeSearch(configured=True)
    fake.results = [
        search_client.Result(
            title="City parks maintenance report",
            url="https://example.com/report",
            snippet="The annual report on park restroom closures.",
        )
    ]
    fake.raw = {"results": [{"title": "City parks maintenance report", "url": "https://example.com/report"}]}
    search_client.override_search(fake)

    ollama = ollama_client.get_ollama()
    ollama.responses["reference_queries.md"] = '{"queries": ["park restroom closures city report"]}'
    ollama.responses["reference_select.md"] = (
        '{"picks": [{"result_number": 1, "why": "It is the city\'s own account of why the '
        'restrooms are shut."}]}'
    )

    response = await client.post(
        f"/admin/umbrellas/{umbrella}/recommend-references", headers=director["headers"]
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["added"]) == 1

    listing = (await client.get(f"/umbrellas/{umbrella}/references")).json()
    assert listing["active"][0]["label"] == "Recommended by AI"
    assert listing["active"][0]["why"]

    log = (await client.get("/ai/actions?action_type=reference_recommend")).json()
    output = log["items"][0]["output"]
    assert output["provider"] == "fake"
    assert output["queries"] == ["park restroom closures city report"]
    assert output["raw_results"], "the provider's raw answer is kept (DEMOCRACY §9.4)"


async def test_the_recommender_respects_its_per_umbrella_limit(client):
    umbrella, _s, _a, _b = await _a_voted_solution(client)
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    await set_setting("references_ai_max_per_umbrella", "1")

    fake = FakeSearch(configured=True)
    fake.results = [
        search_client.Result(title=f"Result {i}", url=f"https://example.com/{i}", snippet="x")
        for i in range(3)
    ]
    search_client.override_search(fake)
    ollama = ollama_client.get_ollama()
    ollama.responses["reference_queries.md"] = '{"queries": ["anything"]}'
    ollama.responses["reference_select.md"] = (
        '{"picks": [{"result_number": 1, "why": "One."}, {"result_number": 2, "why": "Two."}]}'
    )

    first = await client.post(
        f"/admin/umbrellas/{umbrella}/recommend-references", headers=director["headers"]
    )
    assert len(first.json()["added"]) == 1, "the limit is a setting, and it is obeyed"

    second = await client.post(
        f"/admin/umbrellas/{umbrella}/recommend-references", headers=director["headers"]
    )
    assert second.status_code == 422
    assert second.json()["error"] == "reference_limit_reached"
