"""C2-08: the AI suggests, the author decides, before anything is posted
(DEMOCRACY.md §4.1, §9.1; DATABASE.md §4.19)."""

from __future__ import annotations

import logging

from backend.clients import ollama as ollama_client
from backend.db import session_scope
from backend.errors import ExternalServiceDown
from backend.models import LabelPreview
from backend.tests.conftest import labeler_answer, make_umbrella, make_user, set_setting

PROBLEM_TEXT = "Streetlights on Elm Avenue have been dark for three weeks now."
SOLUTION_TEXT = "Replace the burnt-out bulbs and add a monthly inspection round."


async def _author(client):
    umbrella = await make_umbrella(
        name="Street Lighting", statement="Streetlights that are dark or flickering."
    )
    author = await make_user(client, email="preview-author@example.com", display_name="PreviewAuthor")
    return umbrella, author


async def test_a_suggestion_is_logged_before_it_is_shown(client):
    umbrella, author = await _author(client)
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    response = await client.post(
        "/posts/label-preview",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "communities": [{"level": "city", "entity_id": 1}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["communities"][0]["umbrella_id"] == umbrella
    assert body["main_category"] == "Public Safety"

    log = (await client.get("/ai/actions")).json()
    row = next(r for r in log["items"] if r["subject_type"] == "label_preview")
    assert row["subject_id"] == body["preview_id"]
    assert row["action_type"] == "label"
    assert row["human_outcome"] == "unreviewed"


async def test_the_action_row_exists_even_when_the_model_call_then_fails(client):
    umbrella, author = await _author(client)
    ollama_client.get_ollama().fail_with = ExternalServiceDown("down", code="ollama_unavailable")

    response = await client.post(
        "/posts/label-preview",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "communities": [{"level": "city", "entity_id": 1}],
        },
    )
    assert response.status_code == 503

    log = (await client.get("/ai/actions")).json()
    row = next(r for r in log["items"] if r["subject_type"] == "label_preview")
    assert row["output"] == {"status": "pending"}

    async with session_scope() as session:
        rows = (
            await session.execute(
                __import__("sqlalchemy").select(LabelPreview).where(
                    LabelPreview.user_id == author["id"]
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].ai_action_id == row["id"]
        assert rows[0].result is None


async def test_no_draft_text_is_stored_or_logged(client, caplog):
    umbrella, author = await _author(client)
    marker = "MARKER_ZXQ_NEVER_STORED_9182"
    problem_text = f"{marker} — a problem report that must never be stored verbatim."
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    with caplog.at_level(logging.DEBUG):
        response = await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={
                "problem_text": problem_text,
                "communities": [{"level": "city", "entity_id": 1}],
            },
        )
    assert response.status_code == 200, response.text
    assert marker not in caplog.text

    async with session_scope() as session:
        import sqlalchemy as sa
        from backend.models import AiAction

        preview_rows = (
            await session.execute(sa.select(LabelPreview).where(LabelPreview.user_id == author["id"]))
        ).scalars().all()
        for row in preview_rows:
            assert marker not in str(row.communities)
            assert marker not in str(row.result)
        action_rows = (
            await session.execute(
                sa.select(AiAction).where(AiAction.subject_type == "label_preview")
            )
        ).scalars().all()
        for row in action_rows:
            assert marker not in str(row.output)


async def test_the_rate_limit_comes_from_settings(client):
    umbrella, author = await _author(client)
    await set_setting("label_preview_max_per_hour", "1")
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    first = await client.post(
        "/posts/label-preview",
        headers=author["headers"],
        json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
    )
    assert first.status_code == 200

    second = await client.post(
        "/posts/label-preview",
        headers=author["headers"],
        json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
    )
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"


async def test_another_users_preview_id_is_refused(client):
    umbrella, author = await _author(client)
    other = await make_user(client, email="preview-other@example.com", display_name="PreviewOther")
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    preview = (
        await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
        )
    ).json()

    response = await client.post(
        "/posts",
        headers=other["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "solutions": [SOLUTION_TEXT],
            "communities": [{"level": "city", "entity_id": 1, "umbrella_id": umbrella}],
            "category_choice": "preview",
            "preview_id": preview["preview_id"],
            "main_category_id": preview["main_category_id"],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "preview_not_yours"


async def test_a_consumed_preview_is_refused(client):
    umbrella, author = await _author(client)
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    preview = (
        await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
        )
    ).json()
    payload = {
        "problem_text": PROBLEM_TEXT,
        "solutions": [SOLUTION_TEXT],
        "communities": [{"level": "city", "entity_id": 1, "umbrella_id": umbrella}],
        "category_choice": "preview",
        "preview_id": preview["preview_id"],
        "main_category_id": preview["main_category_id"],
    }
    first = await client.post("/posts", headers=author["headers"], json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/posts", headers=author["headers"], json=payload)
    assert second.status_code == 409
    assert second.json()["error"] == "preview_already_used"


async def test_changed_text_is_refused_with_409(client):
    umbrella, author = await _author(client)
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    preview = (
        await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
        )
    ).json()

    response = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT + " Some more text was added after the suggestion ran.",
            "solutions": [SOLUTION_TEXT],
            "communities": [{"level": "city", "entity_id": 1, "umbrella_id": umbrella}],
            "category_choice": "preview",
            "preview_id": preview["preview_id"],
            "main_category_id": preview["main_category_id"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == "preview_stale"


async def test_all_kept_is_confirmed_solutions_exist_immediately(client):
    umbrella, author = await _author(client)
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    preview = (
        await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={"problem_text": PROBLEM_TEXT, "communities": [{"level": "city", "entity_id": 1}]},
        )
    ).json()

    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "solutions": [SOLUTION_TEXT],
            "communities": [{"level": "city", "entity_id": 1, "umbrella_id": umbrella}],
            "category_choice": "preview",
            "preview_id": preview["preview_id"],
            "main_category_id": preview["main_category_id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["label_status"] == "labeled"

    # Solutions exist immediately — no background job, no settle_jobs.
    page = (await client.get(f"/umbrellas/{umbrella}")).json()
    assert any(s["version"] == 1 for s in page["solutions"])

    log = (await client.get("/ai/actions")).json()
    row = next(r for r in log["items"] if r["subject_type"] == "label_preview")
    assert row["human_outcome"] == "confirmed"


async def test_a_changed_umbrella_is_corrected_and_none_of_these_fit_is_needs_review(client):
    fits_umbrella = await make_umbrella(
        name="Suggested Umbrella", statement="Whatever the AI suggests.", category_slug="public_safety"
    )
    other_umbrella = await make_umbrella(
        name="Actually Chosen Umbrella", statement="What the author picks instead.",
        category_slug="public_safety",
    )
    second_umbrella = await make_umbrella(
        name="County Umbrella", statement="A county-level umbrella.", level="county", entity_id=1,
        category_slug="public_safety",
    )
    author = await make_user(client, email="mixed-author@example.com", display_name="MixedAuthor")
    ollama_client.get_ollama().responses["labeler.md"] = (
        '{"main_category":"Public Safety","umbrellas":['
        f'{{"community_level":"city","community_entity_id":1,"umbrella_id":{fits_umbrella}}},'
        f'{{"community_level":"county","community_entity_id":1,"umbrella_id":{second_umbrella}}}'
        '],"confidence":0.7}'
    )
    preview = (
        await client.post(
            "/posts/label-preview",
            headers=author["headers"],
            json={
                "problem_text": PROBLEM_TEXT,
                "communities": [
                    {"level": "city", "entity_id": 1},
                    {"level": "county", "entity_id": 1},
                ],
            },
        )
    ).json()
    assert preview["communities"][0]["umbrella_id"] == fits_umbrella
    assert preview["communities"][1]["umbrella_id"] == second_umbrella

    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "solutions": [SOLUTION_TEXT],
            "communities": [
                # Changed away from the AI's suggestion.
                {"level": "city", "entity_id": 1, "umbrella_id": other_umbrella},
                # "None of these fit" — the AI had suggested one.
                {"level": "county", "entity_id": 1, "umbrella_id": None},
            ],
            "category_choice": "preview",
            "preview_id": preview["preview_id"],
            "main_category_id": preview["main_category_id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["label_status"] == "needs_review"

    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    by_level = {c["community"]["level"]: c for c in post["communities"]}
    assert by_level["city"]["label_status"] == "Filed"
    assert by_level["city"]["label_shown_as"] == "AI-suggested, changed by author"
    assert "Not filed" in by_level["county"]["label_status"]
    assert by_level["county"]["label_shown_as"] == "AI-suggested, changed by author"

    log = (await client.get("/ai/actions")).json()
    row = next(r for r in log["items"] if r["subject_type"] == "label_preview")
    assert row["human_outcome"] == "corrected"


async def test_the_ai_category_choice_path_is_unchanged(client):
    """A regression check that `category_choice=ai` (background labeling)
    still works exactly as before this change."""
    umbrella, author = await _author(client)
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    from backend.tests.conftest import settle_jobs

    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": PROBLEM_TEXT,
            "solutions": [SOLUTION_TEXT],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["label_status"] == "pending"
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "labeled"
