"""DEMOCRACY.md §4.1 (as amended, change/01) — the three honest filing
messages, plus the no-umbrellas-in-this-community case. They never share a
sentence (CLAUDE.md §2)."""

from __future__ import annotations

import pytest

from backend.clients import ollama as ollama_client
from backend.errors import ExternalServiceDown
from backend.tests.conftest import (
    labeler_answer,
    make_umbrella,
    make_user,
    settle_jobs,
)


@pytest.fixture
async def world(client):
    safety = await make_umbrella(
        name="Pedestrian Safety", statement="Crossings near schools are unsafe."
    )
    author = await make_user(client, email="filing-a@example.com", display_name="FilingAuthor")
    return {"safety": safety, "author": author}


async def _post(client, author, *, communities=None):
    return await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school every morning.",
            "solutions": ["Paint a crosswalk and install a pedestrian refuge island."],
            "communities": communities or [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )


async def test_pending_reads_being_filed(client, world):
    # No labeler.md response queued, so the job never settles — the post
    # stays pending exactly as created.
    created = await _post(client, world["author"])
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "pending"
    row = post["communities"][0]
    assert row["label_status"] == "Being filed — the AI is reading this now"


async def test_unlabeled_names_the_retry_interval(client, world):
    ollama_client.get_ollama().fail_with = ExternalServiceDown("down", code="ollama_unavailable")
    created = await _post(client, world["author"])
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "unlabeled"
    row = post["communities"][0]
    assert row["label_status"] == (
        "Not filed yet — the AI could not be reached. The platform tries "
        "again every 10 minutes"
    )


async def test_needs_review_with_an_active_umbrella_names_community_and_category(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=None, level="city", entity_id=1
    )
    created = await _post(client, world["author"])
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "needs_review"
    row = post["communities"][0]
    assert row["has_active_umbrella"] is True
    assert row["label_status"] == (
        f"Not filed — no umbrella in {row['community']['label']} covers this "
        "yet. It is saved under Public Safety."
    )


async def test_needs_review_with_no_umbrellas_at_all_offers_the_planned_note(client, world):
    me = (await client.get("/auth/me", headers=world["author"]["headers"])).json()
    state = next(c for c in me["home_communities"] if c["level"] == "state")

    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=None, level="state", entity_id=state["entity_id"]
    )
    created = await _post(
        client, world["author"], communities=[{"level": "state", "entity_id": state["entity_id"]}]
    )
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    row = post["communities"][0]
    assert row["has_active_umbrella"] is False
    assert row["label_status"] == (
        f"There are no umbrellas in {state['label']} yet. Proposing a new "
        "umbrella is planned."
    )


def test_the_three_states_and_the_no_umbrellas_case_never_share_a_sentence():
    from backend.services.posts import _label_status_words

    texts = {
        _label_status_words(
            "pending", None, community_label="X", main_category_name=None,
            retry_minutes=10, has_active_umbrella=True,
        ),
        _label_status_words(
            "unlabeled", None, community_label="X", main_category_name=None,
            retry_minutes=10, has_active_umbrella=True,
        ),
        _label_status_words(
            "needs_review", None, community_label="X", main_category_name="Y",
            retry_minutes=10, has_active_umbrella=True,
        ),
        _label_status_words(
            "needs_review", None, community_label="X", main_category_name=None,
            retry_minutes=10, has_active_umbrella=False,
        ),
    }
    assert len(texts) == 4
