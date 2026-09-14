"""The workshop: posts, labeling, solutions, votes, amendments, comments."""

from __future__ import annotations

import json

import pytest

from backend.clients import ollama as ollama_client
from backend.db import session_scope
from backend.errors import ExternalServiceDown
from backend.jobs import labeling as labeling_job
from backend.repositories import posts as posts_repo
from backend.tests.conftest import (
    labeler_answer,
    make_umbrella,
    make_user,
    set_setting,
    settle_jobs,
)


@pytest.fixture
async def world(client):
    safety = await make_umbrella(
        name="Pedestrian Safety", statement="Crossings near schools are unsafe."
    )
    roads = await make_umbrella(
        name="Road Damage",
        statement="Streets have potholes.",
        category_slug="roads_and_infrastructure",
    )
    county = await make_umbrella(
        name="Transit Frequency",
        statement="Buses are infrequent.",
        level="county",
        entity_id=1,
        category_slug="public_transit",
    )
    author = await make_user(client, email="a@example.com", display_name="Ann")
    ben = await make_user(client, email="b@example.com", display_name="Ben")
    cara = await make_user(client, email="c@example.com", display_name="Cara")
    return {
        "safety": safety,
        "roads": roads,
        "county": county,
        "ann": author,
        "ben": ben,
        "cara": cara,
    }


async def _post(client, user, *, communities=None, choice="ai", solutions=None):
    return await client.post(
        "/posts",
        headers=user["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school every morning.",
            "solutions": solutions
            or ["Paint a crosswalk and install a pedestrian refuge island in the median."],
            "communities": communities or [{"level": "city", "entity_id": 1}],
            "category_choice": choice,
        },
    )


async def test_a_post_needs_at_least_one_solution(client, world):
    response = await client.post(
        "/posts",
        headers=world["ann"]["headers"],
        json={
            "problem_text": "A problem with no proposal attached to it at all, which is a complaint.",
            "solutions": [],
            "communities": [{"level": "city", "entity_id": 1}],
            "category_choice": "ai",
        },
    )
    assert response.status_code == 422


async def test_the_post_title_is_derived_and_cut_at_a_word(client, world):
    from backend.services.posts import derive_title

    long_text = "The intersection of Bird Avenue and West Virginia Street has no marked crosswalk at all"
    title = derive_title(long_text)
    assert len(title) <= 81
    assert not title.rstrip("…").endswith(" ")
    assert title.endswith("…")
    assert derive_title("Short problem text.") == "Short problem text."


async def test_labeling_files_the_post_and_creates_one_solution_per_text(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(
        client,
        world["ann"],
        solutions=[
            "Paint a crosswalk and install a pedestrian refuge island in the median.",
            "Station a crossing guard during school drop-off and pick-up hours.",
        ],
    )
    assert created.status_code == 201
    await settle_jobs()

    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "labeled"
    assert post["communities"][0]["umbrella_id"] == world["safety"]
    assert len(post["communities"][0]["solution_ids"]) == 2, (
        "one workshop solution per submitted solution text"
    )


async def test_a_post_to_two_communities_makes_a_solution_in_each(client, world):
    ollama = ollama_client.get_ollama()
    ollama.responses["labeler.md"] = json.dumps(
        {
            "main_category": "Public Safety",
            "umbrellas": [
                {"community_level": "city", "community_entity_id": 1, "umbrella_id": world["safety"]},
                {"community_level": "county", "community_entity_id": 1, "umbrella_id": world["county"]},
            ],
            "confidence": 0.8,
        }
    )
    created = await _post(
        client,
        world["ann"],
        communities=[
            {"level": "city", "entity_id": 1},
            {"level": "county", "entity_id": 1},
        ],
    )
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    filed = {c["community"]["level"]: c["umbrella_id"] for c in post["communities"]}
    assert filed == {"city": world["safety"], "county": world["county"]}
    ids = [sid for c in post["communities"] for sid in c["solution_ids"]]
    assert len(ids) == 2 and len(set(ids)) == 2, (
        "each community workshops its own copy, with its own votes"
    )


async def test_no_matching_umbrella_marks_the_post_for_review(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=None, level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "needs_review"
    assert post["communities"][0]["main_category"] == "Public Safety"
    assert post["communities"][0]["solution_ids"] == []


async def test_an_unreachable_model_leaves_the_post_unlabeled_for_retry(client, world):
    ollama = ollama_client.get_ollama()
    ollama.fail_with = ExternalServiceDown("down", code="ollama_unavailable")
    created = await _post(client, world["ann"])
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "unlabeled"

    ollama.fail_with = None
    ollama.responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    counts = await labeling_job.label_retry_task()
    assert counts["retried"] == 1 and counts["succeeded"] == 1
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "labeled"


async def test_unreadable_model_output_is_logged_as_a_failure_not_guessed(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = "I think this is about safety, probably."
    created = await _post(client, world["ann"])
    await settle_jobs()
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["label_status"] == "unlabeled"
    log = (await client.get("/ai/actions")).json()
    assert log["items"], "a failed AI action is still an AI action and is logged"
    assert "error" in log["items"][0]["output"]


async def test_the_author_can_confirm_or_correct_the_filing(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["roads"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    post_id = created.json()["id"]
    await settle_jobs()

    not_the_author = await client.post(
        f"/posts/{post_id}/label/confirm", headers=world["ben"]["headers"]
    )
    assert not_the_author.status_code == 403

    corrected = await client.post(
        f"/posts/{post_id}/label/correct",
        headers=world["ann"]["headers"],
        json={"level": "city", "entity_id": 1, "umbrella_id": world["safety"]},
    )
    assert corrected.status_code == 200
    assert corrected.json()["moved_to_umbrella"] == world["safety"]

    log = (await client.get("/ai/actions")).json()
    assert log["items"][0]["human_outcome"] == "corrected"


async def test_a_correction_leaves_voted_on_solutions_where_they_are(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["roads"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    post_id = created.json()["id"]
    await settle_jobs()
    page = (await client.get(f"/umbrellas/{world['roads']}")).json()
    solution_id = page["solutions"][0]["id"]
    await client.put(
        "/votes",
        headers=world["ben"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )

    corrected = await client.post(
        f"/posts/{post_id}/label/correct",
        headers=world["ann"]["headers"],
        json={"level": "city", "entity_id": 1, "umbrella_id": world["safety"]},
    )
    assert corrected.status_code == 200
    assert corrected.json()["left_in_place"] is True
    assert "already voted" in corrected.json()["note"]
    still_there = (await client.get(f"/umbrellas/{world['roads']}")).json()
    assert [s["id"] for s in still_there["solutions"]] == [solution_id]


async def test_picking_an_umbrella_skips_the_labeler_entirely(client, world):
    created = await client.post(
        "/posts",
        headers=world["ann"]["headers"],
        json={
            "problem_text": "Children cross four lanes of traffic to reach the school every morning.",
            "solutions": ["Paint a crosswalk and install a pedestrian refuge island."],
            "communities": [
                {"level": "city", "entity_id": 1, "umbrella_id": world["safety"]}
            ],
            "category_choice": "author_selected",
        },
    )
    assert created.status_code == 201
    assert created.json()["label_status"] == "labeled"
    assert not ollama_client.get_ollama().calls
    post = (await client.get(f"/posts/{created.json()['id']}")).json()
    assert post["communities"][0]["label_shown_as"] == "chosen by author"


async def test_a_member_posts_only_in_their_own_communities(client, world):
    outsider = await make_user(
        client, email="vallejo@example.com", display_name="Vallejo", city_id=2, county_id=2
    )
    response = await _post(client, outsider)
    assert response.status_code == 403
    assert response.json()["error"] == "not_a_member"


async def test_votes_drive_dominance_and_downvotes_never_hide(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    await settle_jobs()
    solution_id = (await client.get(f"/umbrellas/{world['safety']}")).json()["solutions"][0]["id"]

    up = await client.put(
        "/votes",
        headers=world["ben"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    assert up.json()["net_score"] == 1
    assert up.json()["is_dominant"] is True

    down = await client.put(
        "/votes",
        headers=world["cara"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": -1},
    )
    assert down.json()["net_score"] == 0
    assert down.json()["is_dominant"] is False

    page = (await client.get(f"/umbrellas/{world['safety']}")).json()
    assert [s["id"] for s in page["solutions"]] == [solution_id], (
        "a downvoted solution is still listed — downvotes never hide (CLAUDE.md §4)"
    )

    removed = await client.request(
        "DELETE",
        "/votes",
        headers=world["cara"]["headers"],
        json={"target_type": "solution", "target_id": solution_id},
    )
    assert removed.json()["net_score"] == 1


async def test_one_vote_per_person_per_item(client, world):
    solution_id = await _dominant_solution(client, world)
    for _ in range(3):
        await client.put(
            "/votes",
            headers=world["ben"]["headers"],
            json={"target_type": "solution", "target_id": solution_id, "direction": 1},
        )
    page = (await client.get(f"/umbrellas/{world['safety']}")).json()
    assert page["solutions"][0]["net_score"] == 1


async def _dominant_solution(client, world) -> int:
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    await settle_jobs()
    solution_id = (await client.get(f"/umbrellas/{world['safety']}")).json()["solutions"][0]["id"]
    await client.put(
        "/votes",
        headers=world["ben"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    return solution_id


async def test_amendments_need_a_dominant_solution_and_a_different_author(client, world):
    solution_id = await _dominant_solution(client, world)
    body = {
        "proposed_text": "Paint a crosswalk, install a refuge island, and add a flashing beacon.",
        "rationale": "A beacon is what actually slows the turning traffic down.",
    }
    by_author = await client.post(
        f"/solutions/{solution_id}/amendments", headers=world["ann"]["headers"], json=body
    )
    assert by_author.status_code == 403
    assert by_author.json()["error"] == "author_of_current_version"

    by_other = await client.post(
        f"/solutions/{solution_id}/amendments", headers=world["ben"]["headers"], json=body
    )
    assert by_other.status_code == 201


async def test_an_amendment_is_absorbed_and_supersedes_the_others(client, world):
    solution_id = await _dominant_solution(client, world)
    first = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=world["ben"]["headers"],
        json={
            "proposed_text": "Paint a crosswalk, install a refuge island, and add a flashing beacon.",
            "rationale": "A beacon is what actually slows the turning traffic down.",
        },
    )
    second = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=world["cara"]["headers"],
        json={
            "proposed_text": "Paint a crosswalk and lower the speed limit to twenty miles per hour.",
            "rationale": "Speed is the thing that makes the crossing dangerous here.",
        },
    )
    assert first.status_code == second.status_code == 201

    backed = await client.put(
        "/votes",
        headers=world["cara"]["headers"],
        json={"target_type": "amendment", "target_id": first.json()["id"], "direction": 1},
    )
    assert backed.json()["absorbed"] is True
    assert backed.json()["new_version"] == 2

    solution = (await client.get(f"/solutions/{solution_id}")).json()
    assert solution["current_version"] == 2
    assert "flashing beacon" in solution["text"]
    assert len(solution["versions"]) == 2, "version 1 is kept, with its own fingerprint"
    statuses = {a["id"]: a["status"] for a in solution["amendments"]}
    assert statuses[first.json()["id"]] == "absorbed"
    assert statuses[second.json()["id"]] == "superseded"


async def test_an_amendment_can_be_withdrawn_only_before_it_has_support(client, world):
    solution_id = await _dominant_solution(client, world)
    amendment = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=world["ben"]["headers"],
        json={
            "proposed_text": "Paint a crosswalk, install a refuge island, and add a flashing beacon.",
            "rationale": "A beacon is what actually slows the turning traffic down.",
        },
    )
    amendment_id = amendment.json()["id"]
    not_the_author = await client.post(
        f"/amendments/{amendment_id}/withdraw", headers=world["cara"]["headers"]
    )
    assert not_the_author.status_code == 403

    withdrawn = await client.post(
        f"/amendments/{amendment_id}/withdraw", headers=world["ben"]["headers"]
    )
    assert withdrawn.status_code == 200
    solution = (await client.get(f"/solutions/{solution_id}")).json()
    assert solution["amendments"][0]["status"] == "withdrawn", "nothing is deleted"


async def test_similar_amendments_are_flagged_and_people_decide(client, world):
    solution_id = await _dominant_solution(client, world)
    ollama = ollama_client.get_ollama()
    text_one = "Paint a crosswalk, install a refuge island, and add a flashing beacon."
    text_two = "Paint a crosswalk, add a refuge island, and install a flashing beacon."
    ollama.embeddings[text_one] = [1.0, 0.0, 0.0]
    ollama.embeddings[text_two] = [0.99, 0.14, 0.0]

    first = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=world["ben"]["headers"],
        json={"proposed_text": text_one, "rationale": "A beacon slows the turning traffic down."},
    )
    second = await client.post(
        f"/solutions/{solution_id}/amendments",
        headers=world["cara"]["headers"],
        json={"proposed_text": text_two, "rationale": "The same change, said a little differently."},
    )
    await settle_jobs()

    listing = (await client.get(f"/solutions/{solution_id}/amendments")).json()
    assert listing["similar_pairs"], "a pair above the threshold is flagged for people to settle"
    pair = listing["similar_pairs"][0]
    assert pair["decision"] == "pending"

    decided = await client.post(
        f"/similarity/{pair['id']}/decide",
        headers=world["ben"]["headers"],
        json={"choice": "same"},
    )
    assert decided.status_code == 200
    assert decided.json()["decision"] == "same", "either author pressing Same settles it"
    assert decided.json()["merged_amendment_id"] == second.json()["id"]


async def test_comments_nest_to_the_depth_cap(client, world):
    await set_setting("comment_max_depth", "2")
    solution_id = await _dominant_solution(client, world)
    parent_id = None
    depths = []
    for i in range(5):
        response = await client.post(
            "/comments",
            headers=world["ben"]["headers"],
            json={
                "target_type": "solution",
                "target_id": solution_id,
                "parent_id": parent_id,
                "text": f"Reply number {i}.",
            },
        )
        assert response.status_code == 201, response.text
        depths.append(response.json()["depth"])
        parent_id = response.json()["id"]
    assert max(depths) == 2
    deep = (await client.get(f"/umbrellas/{world['safety']}")).json()
    assert deep is not None


async def test_a_comment_can_be_edited_briefly_and_removed_softly(client, world):
    solution_id = await _dominant_solution(client, world)
    comment = await client.post(
        "/comments",
        headers=world["ben"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "text": "First thought."},
    )
    comment_id = comment.json()["id"]
    edited = await client.patch(
        f"/comments/{comment_id}",
        headers=world["ben"]["headers"],
        json={"text": "Second thought, within the edit window."},
    )
    assert edited.status_code == 200

    await set_setting("comment_edit_minutes", "0")
    too_late = await client.patch(
        f"/comments/{comment_id}",
        headers=world["ben"]["headers"],
        json={"text": "Third thought, too late."},
    )
    assert too_late.status_code == 409

    removed = await client.delete(f"/comments/{comment_id}", headers=world["ben"]["headers"])
    assert removed.status_code == 200
    thread = (await client.get(f"/solutions/{solution_id}")).json()["discussion"]
    assert thread[0]["removed"] is True
    assert thread[0]["text"] == "[removed by author]"


async def test_a_solution_is_editable_only_while_untouched(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    await settle_jobs()
    solution_id = (await client.get(f"/umbrellas/{world['safety']}")).json()["solutions"][0]["id"]

    fixed = await client.patch(
        f"/solutions/{solution_id}",
        headers=world["ann"]["headers"],
        json={"text": "Paint a crosswalk and install a pedestrian refuge island in the middle."},
    )
    assert fixed.status_code == 200

    await client.put(
        "/votes",
        headers=world["ben"]["headers"],
        json={"target_type": "solution", "target_id": solution_id, "direction": 1},
    )
    locked = await client.patch(
        f"/solutions/{solution_id}",
        headers=world["ann"]["headers"],
        json={"text": "Paint a crosswalk and something else entirely different from before."},
    )
    assert locked.status_code == 409
    assert locked.json()["error"] == "solution_locked"


async def test_the_feed_states_its_ordering_rule(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    await _post(client, world["ann"])
    feed = (await client.get("/feed", headers=world["ben"]["headers"])).json()
    assert feed["ranking"] == "feed-v0"
    assert "Newest first" in feed["explanation"]


async def test_posts_cannot_be_edited_or_deleted(client, world):
    created = await _post(client, world["ann"], choice="author_selected")
    assert created.status_code == 422, "author_selected needs an umbrella per community"
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    post_id = created.json()["id"]
    assert (await client.patch(f"/posts/{post_id}", json={})).status_code == 405
    assert (await client.delete(f"/posts/{post_id}")).status_code == 405


async def test_the_post_content_hash_never_changes(client, world):
    ollama_client.get_ollama().responses["labeler.md"] = labeler_answer(
        main_category="Public Safety", umbrella_id=world["safety"], level="city", entity_id=1
    )
    created = await _post(client, world["ann"])
    post_id = created.json()["id"]
    before = (await client.get(f"/posts/{post_id}")).json()["content_hash"]
    await settle_jobs()
    after = (await client.get(f"/posts/{post_id}")).json()["content_hash"]
    assert before == after

    async with session_scope() as session:
        post = await posts_repo.get(session, post_id)
        from backend.services import hashing

        assert post.content_hash == hashing.post_content_hash(
            problem_text=post.problem_text,
            author_id=post.author_id,
            created_at=post.created_at,
            ai_contribution_percentage=post.ai_contribution_percentage,
        )
