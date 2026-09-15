"""The labeler: filing a post into an umbrella (DEMOCRACY.md §9.1).

AI sorts and suggests. It never decides (CLAUDE.md §5): it cannot create an
umbrella, and everything it files can be confirmed or corrected by the author,
with the correction recorded.

The order of writes is fixed by ARCHITECTURE.md §7: the `ai_actions` row first,
then the `labels` row, then `post_communities.umbrella_id`, then the solutions,
then `label_status`. The log entry exists before the result is visible anywhere.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import ollama as ollama_client
from backend.errors import ExternalServiceDown
from backend.models import Post
from backend.repositories import posts as posts_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import community as community_service
from backend.services import solutions as solutions_service

log = logging.getLogger(__name__)

PROMPT_FILE = "labeler.md"


async def label_post(session: AsyncSession, post: Post) -> dict:
    """Label one post across every community its author selected."""
    community_rows = [
        row for row in await posts_repo.communities(session, post.id) if row.umbrella_id is None
    ]
    if not community_rows:
        await posts_repo.set_label_status(session, post.id, "labeled")
        return {"status": "labeled", "communities": 0}

    categories = await umbrellas_repo.categories(session)
    category_names = [c.name for c in categories]
    category_by_name = {c.name: c for c in categories}

    community_blocks = []
    umbrella_index: dict[tuple[str, int], dict[int, object]] = {}
    for row in community_rows:
        resolved = await community_service.resolve(
            session, row.community_level, row.community_entity_id
        )
        umbrellas = await umbrellas_repo.for_community(
            session, row.community_level, row.community_entity_id
        )
        umbrella_index[(row.community_level, row.community_entity_id)] = {
            u.id: u for u in umbrellas
        }
        listing = (
            "\n".join(f"{u.id} | {u.name} | {u.statement}" for u in umbrellas)
            or "(this community has no umbrellas yet)"
        )
        community_blocks.append(
            f"### {resolved.label}\n"
            f"community_level: {row.community_level}\n"
            f"community_entity_id: {row.community_entity_id}\n"
            f"{listing}\n"
        )

    variables = {
        "problem_text": post.problem_text,
        "categories": "\n".join(f"- {name}" for name in category_names),
        "communities": "\n".join(community_blocks),
    }
    client = ollama_client.get_ollama()

    try:
        raw, prompt = await client.generate(PROMPT_FILE, variables)
        parsed = ollama_client.parse_json_output(raw)
    except ExternalServiceDown:
        await posts_repo.set_label_status(session, post.id, "unlabeled")
        log.warning("labeling_unavailable", extra={"post_id": post.id})
        return {"status": "unlabeled", "reason": "the labelling service is unavailable"}
    except (ValueError, KeyError) as exc:
        prompt = ollama_client.load_prompt(PROMPT_FILE)
        await ai_log.record(
            session,
            action_type="label",
            subject_type="post",
            subject_id=post.id,
            model=client.model_label,
            prompt_file=PROMPT_FILE,
            prompt_hash=prompt.sha256,
            model_input=variables,
            output={"error": f"unparseable model output: {exc}", "raw": raw[:2000]},
        )
        await posts_repo.set_label_status(session, post.id, "unlabeled")
        log.warning("labeling_unparseable", extra={"post_id": post.id})
        return {"status": "unlabeled", "reason": "the model's answer could not be read"}

    main_category_name = str(parsed.get("main_category", "")).strip()
    category = category_by_name.get(main_category_name)
    confidence = parsed.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    # Small models sometimes answer for the same community twice, or invent a
    # community that was never listed. The first answer that names an umbrella
    # actually present in that community wins; everything else is ignored and
    # recorded, so the public log shows what the model really said (DEMOCRACY
    # §9.1 — both the repeated and the unlisted case land in this field; audit
    # demo-01 run 2 found the unlisted case was silently dropped).
    choices: dict[tuple[str, int], int | None] = {}
    duplicates: list[dict] = []
    for entry in parsed.get("umbrellas", []) or []:
        try:
            key = (str(entry["community_level"]), int(entry["community_entity_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        raw_id = entry.get("umbrella_id")
        chosen = (
            int(raw_id)
            if isinstance(raw_id, (int, str)) and str(raw_id).isdigit()
            else None
        )
        if key not in umbrella_index:
            # The model named a community the author never selected.
            duplicates.append({"community": f"{key[0]}:{key[1]}", "umbrella_id": chosen})
            continue
        resolves = chosen is not None and chosen in umbrella_index[key]
        if key in choices:
            duplicates.append({"community": f"{key[0]}:{key[1]}", "umbrella_id": chosen})
            if choices[key] is None and resolves:
                choices[key] = chosen
            continue
        choices[key] = chosen if resolves else None

    # The row exists before anything it produced is visible (Law 7).
    action = await ai_log.record(
        session,
        action_type="label",
        subject_type="post",
        subject_id=post.id,
        model=client.model_label,
        prompt_file=PROMPT_FILE,
        prompt_hash=prompt.sha256,
        model_input=variables,
        output={
            "main_category": main_category_name,
            "umbrellas": parsed.get("umbrellas", []),
            "confidence": confidence,
            "category_recognised": category is not None,
            "repeated_or_unlisted_communities": duplicates,
        },
        confidence=confidence,
    )


    filed = 0
    needs_review = 0
    for row in community_rows:
        key = (row.community_level, row.community_entity_id)
        candidates = umbrella_index.get(key, {})
        chosen_id = choices.get(key)
        umbrella = candidates.get(chosen_id) if chosen_id is not None else None

        await posts_repo.add_label(
            session,
            post_id=post.id,
            community_level=row.community_level,
            community_entity_id=row.community_entity_id,
            ai_action_id=action.id,
            main_category_id=category.id if category else None,
            umbrella_id=umbrella.id if umbrella else None,
            confidence=action.confidence,
            outcome="unreviewed",
        )
        row.main_category_id = category.id if category else None
        if umbrella is not None:
            row.umbrella_id = umbrella.id
            await session.flush()
            await solutions_service.create_from_post_community(
                session, post=post, umbrella=umbrella
            )
            filed += 1
        else:
            needs_review += 1

    status = "labeled" if needs_review == 0 else "needs_review"
    await posts_repo.set_label_status(session, post.id, status)
    await session.flush()
    log.info(
        "post_labeled",
        extra={
            "post_id": post.id,
            "status": status,
            "filed": filed,
            "needs_review": needs_review,
            "ai_action_id": action.id,
        },
    )
    return {
        "status": status,
        "filed": filed,
        "needs_review": needs_review,
        "ai_action_id": action.id,
        "main_category": main_category_name,
    }
