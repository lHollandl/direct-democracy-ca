"""The promises in CLAUDE.md §2, §3 and §5, checked against the running API."""

from __future__ import annotations

from backend.clients import ollama as ollama_client
from backend.services import settings as settings_service
from backend.tests.conftest import labeler_answer, make_umbrella, make_user, settle_jobs


async def test_every_setting_democracy_names_is_public_with_its_meaning(client):
    response = await client.get("/settings")
    assert response.status_code == 200
    payload = response.json()
    published = {row["key"] for row in payload["settings"]}
    assert published == set(settings_service.REQUIRED_KEYS)
    for row in payload["settings"]:
        assert row["value"] is not None, f"{row['key']} has no value in force"
        assert row["meaning"], f"{row['key']} is published without an explanation"
        assert row["defined_in"].startswith("DEMOCRACY.md")
    assert payload["rules_version"]


async def test_changing_a_setting_appends_a_row_and_is_logged(client):
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    changed = await client.post(
        "/admin/settings",
        headers=director["headers"],
        json={"key": "jury_size", "value": "5", "reason": "Bigger community, bigger jury."},
    )
    assert changed.status_code == 200
    assert changed.json()["old_value"] == 3 and changed.json()["new_value"] == 5

    history = (await client.get("/settings/history?key=jury_size")).json()
    assert len(history) == 2, "a change is a new row, never an update"
    assert history[0]["value"] == "5" and history[1]["value"] == "3"
    assert history[0]["reason"] == "Bigger community, bigger jury."
    assert history[0]["changed_by"] == "Dir"

    log = (await client.get("/admin/log")).json()
    assert log["items"][0]["action"] == "change_setting"
    assert log["items"][0]["old_value"] == {"key": "jury_size", "value": 3}
    assert log["items"][0]["new_value"] == {"key": "jury_size", "value": 5}


async def test_umbrellas_paginate_and_refuse_an_over_limit(client):
    """MEDIUM, audit demo-01 run 2: `GET /umbrellas` returned a bare list with
    no `next_cursor` and accepted any `limit`. ARCHITECTURE §6 names five
    fixed-size reference lists as the only pagination exemptions — umbrellas
    is not one of them, since it "grows without bound once the proposal
    system lands"."""
    for name in ("Crosswalks", "Potholes", "Streetlights"):
        await make_umbrella(name=name, statement=f"{name} need attention.")

    over_limit = await client.get("/umbrellas?community=city:1&limit=500")
    assert over_limit.status_code == 422

    first_page = await client.get("/umbrellas?community=city:1&limit=2")
    assert first_page.status_code == 200
    page = first_page.json()
    assert len(page["umbrellas"]) == 2
    assert page["next_cursor"] is not None

    second_page = (
        await client.get(f"/umbrellas?community=city:1&limit=2&cursor={page['next_cursor']}")
    ).json()
    assert len(second_page["umbrellas"]) == 1
    assert second_page["next_cursor"] is None

    seen_ids = {u["id"] for u in page["umbrellas"]} | {u["id"] for u in second_page["umbrellas"]}
    assert len(seen_ids) == 3, "no umbrella repeated or skipped across pages"


async def test_a_bad_setting_value_reads_in_plain_words(client):
    """LOW, audit demo-01 run 2: the message read "must be a int" (CLAUDE §8
    — plain language over jargon)."""
    director = await make_user(
        client, email="dir2@example.com", display_name="Dir2", admin=True
    )
    response = await client.post(
        "/admin/settings",
        headers=director["headers"],
        json={"key": "jury_size", "value": "not-a-number", "reason": "testing"},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "The value for jury_size must be a whole number."


async def test_an_unknown_setting_is_refused(client):
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    response = await client.post(
        "/admin/settings",
        headers=director["headers"],
        json={
            "key": "secret_boost",
            "value": "9",
            "reason": "Trying to invent a setting that no document names.",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unknown_setting"


async def test_the_ai_log_records_the_model_the_prompt_file_and_its_hash(client):
    umbrella = await make_umbrella(name="Safety", statement="Crossings are unsafe.")
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    author = await make_user(client, email="a@example.com", display_name="Ann")
    await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school each day.",
            "solutions": ["Paint a crosswalk and install a pedestrian refuge island here."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    await settle_jobs()

    log = (await client.get("/ai/actions")).json()
    row = log["items"][0]
    assert row["action_type"] == "label"
    assert row["model"].startswith("ollama:")
    assert row["prompt_file"] == "labeler.md"
    assert len(row["prompt_hash"]) == 64
    assert len(row["input_hash"]) == 64
    assert row["demo_build"] == "demo-01"
    assert row["human_outcome"] == "unreviewed"
    assert "AI never decides anything here" in log["explanation"]

    filtered = (await client.get("/ai/actions?subject_type=post&subject_id=1")).json()
    assert len(filtered["items"]) == 1


async def test_the_umbrella_page_shows_what_ai_did_to_it(client):
    umbrella = await make_umbrella(name="Safety", statement="Crossings are unsafe.")
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=umbrella, level="city", entity_id=1
    )
    author = await make_user(client, email="a@example.com", display_name="Ann")
    created = await client.post(
        "/posts",
        headers=author["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school each day.",
            "solutions": ["Paint a crosswalk and install a pedestrian refuge island here."],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    await settle_jobs()
    await client.post(f"/posts/{created.json()['id']}/label/confirm", headers=author["headers"])

    page = (await client.get(f"/umbrellas/{umbrella}")).json()
    sentence = page["problem"]["ai_action_list"]["sentence"]
    assert "AI on this umbrella" in sentence
    assert "1 confirmed" in sentence
    assert page["solutions"][0]["ai_influence"]["ai_contribution_percentage"] == 0
    assert "0%" in page["solutions"][0]["ai_influence"]["label"]
    assert "cannot be detected" in page["solutions"][0]["ai_influence"]["explanation"]


async def test_the_ranking_rule_is_printed_where_it_applies(client):
    umbrella = await make_umbrella(name="Safety", statement="Crossings are unsafe.")
    page = (await client.get(f"/umbrellas/{umbrella}")).json()
    assert page["ordering"]["version"] == "solutions-v0"
    assert "Nothing is ever hidden" in page["ordering"]["explanation"]

    comments = (await client.get(f"/umbrellas/{umbrella}/comments")).json()
    assert comments["ordering"]["version"] == "comments-v0"

    user = await make_user(client, email="a@example.com", display_name="Ann")
    feed = (await client.get("/feed", headers=user["headers"])).json()
    assert feed["ranking"] == "feed-v0"


async def test_the_community_page_explains_who_counts_as_active(client):
    await make_user(client, email="a@example.com", display_name="Ann")
    response = await client.get("/communities/city/1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_users"] == 1
    assert "email is verified" in payload["active_user_definition"]
    assert payload["officials"], "the officials directory is part of the community page"


async def test_the_legal_pages_are_marked_draft(client):
    for path in ("/legal/privacy", "/legal/terms", "/legal/cookies"):
        payload = (await client.get(path)).json()
        assert payload["is_draft"] is True
        assert "not been reviewed by a lawyer" in payload["draft_warning"]
        assert payload["version"]


async def test_the_reference_recommender_says_no_rather_than_inventing(client):
    umbrella = await make_umbrella(name="Safety", statement="Crossings are unsafe.")
    director = await make_user(
        client, email="dir@example.com", display_name="Dir", admin=True
    )
    response = await client.post(
        f"/admin/umbrellas/{umbrella}/recommend-references", headers=director["headers"]
    )
    assert response.status_code == 503
    assert response.json()["error"] == "search_not_configured"
    assert (await client.get(f"/umbrellas/{umbrella}/references")).json()["active"] == []
