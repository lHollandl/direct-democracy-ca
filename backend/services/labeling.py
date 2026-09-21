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
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import ollama as ollama_client
from backend.errors import ExternalServiceDown, Forbidden, RateLimited, ValidationFailed
from backend.models import Post, User
from backend.repositories import label_previews as label_previews_repo
from backend.repositories import posts as posts_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import communities as community_service
from backend.services import hashing
from backend.services import settings as settings_service
from backend.services import solutions as solutions_service

log = logging.getLogger(__name__)

PROMPT_FILE = "labeler.md"


async def _prompt_variables(
    session: AsyncSession, *, problem_text: str, communities: list[tuple[str, int]]
) -> tuple[dict, dict[tuple[str, int], dict[int, object]], dict[str, object]]:
    """Everything the labeler prompt needs, for a post or for a draft alike."""
    categories = await umbrellas_repo.categories(session)
    category_names = [c.name for c in categories]
    category_by_name = {c.name: c for c in categories}

    community_blocks = []
    umbrella_index: dict[tuple[str, int], dict[int, object]] = {}
    for level, entity_id in communities:
        resolved = await community_service.resolve(session, level, entity_id)
        umbrellas = await umbrellas_repo.for_community(session, level, entity_id)
        umbrella_index[(level, entity_id)] = {u.id: u for u in umbrellas}
        listing = (
            "\n".join(f"{u.id} | {u.name} | {u.statement}" for u in umbrellas)
            or "(this community has no umbrellas yet)"
        )
        community_blocks.append(
            f"### {resolved.label}\n"
            f"community_level: {level}\n"
            f"community_entity_id: {entity_id}\n"
            f"{listing}\n"
        )

    variables = {
        "problem_text": problem_text,
        "categories": "\n".join(f"- {name}" for name in category_names),
        "communities": "\n".join(community_blocks),
    }
    return variables, umbrella_index, category_by_name


def _read_choices(
    parsed: dict, umbrella_index: dict[tuple[str, int], dict[int, object]]
) -> tuple[dict[tuple[str, int], int | None], list[dict]]:
    """Small models sometimes answer for the same community twice, or invent a
    community that was never listed. The first answer that names an umbrella
    actually present in that community wins; everything else is ignored and
    recorded, so the public log shows what the model really said (DEMOCRACY
    §9.1 — both the repeated and the unlisted case land in this field; audit
    demo-01 run 2 found the unlisted case was silently dropped)."""
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
    return choices, duplicates


async def label_post(session: AsyncSession, post: Post) -> dict:
    """Label one post across every community its author selected."""
    community_rows = [
        row for row in await posts_repo.communities(session, post.id) if row.umbrella_id is None
    ]
    if not community_rows:
        await posts_repo.set_label_status(session, post.id, "labeled")
        return {"status": "labeled", "communities": 0}

    communities = [(row.community_level, row.community_entity_id) for row in community_rows]
    variables, umbrella_index, category_by_name = await _prompt_variables(
        session, problem_text=post.problem_text, communities=communities
    )
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

    choices, duplicates = _read_choices(parsed, umbrella_index)

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


async def preview(
    session: AsyncSession,
    *,
    user: User,
    problem_text: str,
    communities: list[tuple[str, int]],
) -> dict:
    """`POST /posts/label-preview` (DEMOCRACY.md §4.1, §9.1) — the labeler
    runs on a draft, before anything is posted.

    Order: insert `label_previews` -> log the `ai_actions` row -> call the
    model -> store `result`. The row is written before its result is shown
    (Law 7) — and, unlike `label_post`'s background retry, it must survive
    even when the model call that follows then fails, so the public log
    still shows that a suggestion was attempted. That needs an explicit
    commit here, a deliberate exception to one-transaction-per-call: without
    it, an error response would roll back the very row this function exists
    to guarantee. No draft text is stored anywhere — only its hash
    (DATABASE.md §4.19).
    """
    from backend.services import posts as posts_service

    problem = problem_text.strip()
    if not posts_service.MIN_PROBLEM <= len(problem) <= posts_service.MAX_PROBLEM:
        raise ValidationFailed(
            f"Describe the problem in between {posts_service.MIN_PROBLEM} and "
            f"{posts_service.MAX_PROBLEM:,} characters.",
            code="bad_problem_text",
        )
    if not communities:
        raise ValidationFailed(
            "Choose at least one of your communities first.", code="no_community"
        )
    for level, entity_id in communities:
        await community_service.resolve(session, level, entity_id)
        if not await community_service.is_member(session, user, level, entity_id):
            raise Forbidden(
                "You can only post in your own city, your county and California.",
                code="not_a_member",
            )

    max_per_hour = int(await settings_service.get(session, "label_preview_max_per_hour"))
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    used = await label_previews_repo.count_since(session, user.id, since)
    if used >= max_per_hour:
        raise RateLimited(
            f"You've asked for {max_per_hour} suggestions in the last hour, which "
            "is the most this platform allows right now. Choose an umbrella "
            "yourself, or try again later.",
            3600,
        )

    sorted_communities = sorted(
        ({"level": level, "entity_id": entity_id} for level, entity_id in communities),
        key=lambda c: (c["level"], c["entity_id"]),
    )
    input_hash = hashing.label_preview_input_hash(problem_text=problem, communities=communities)
    preview_row = await label_previews_repo.add(
        session, user_id=user.id, input_hash=input_hash, communities=sorted_communities
    )

    variables, umbrella_index, category_by_name = await _prompt_variables(
        session, problem_text=problem, communities=communities
    )
    client = ollama_client.get_ollama()
    prompt = ollama_client.load_prompt(PROMPT_FILE)

    action = await ai_log.record(
        session,
        action_type="label",
        subject_type="label_preview",
        subject_id=preview_row.id,
        model=client.model_label,
        prompt_file=PROMPT_FILE,
        prompt_hash=prompt.sha256,
        model_input=variables,
        output={"status": "pending"},
    )
    await label_previews_repo.set_ai_action(session, preview_row.id, action.id)
    await session.commit()

    try:
        raw, _prompt = await client.generate(PROMPT_FILE, variables)
        parsed = ollama_client.parse_json_output(raw)
    except ExternalServiceDown:
        log.warning("label_preview_unavailable", extra={"preview_id": preview_row.id})
        raise
    except (ValueError, KeyError) as exc:
        log.warning("label_preview_unparseable", extra={"preview_id": preview_row.id})
        raise ExternalServiceDown(
            "The AI could not be reached just now.", code="ollama_unavailable"
        ) from exc

    main_category_name = str(parsed.get("main_category", "")).strip()
    category = category_by_name.get(main_category_name)
    confidence = parsed.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    choices, duplicates = _read_choices(parsed, umbrella_index)

    # Every umbrella carries its own main category, so the form can show a
    # suggestion under the category it actually belongs to rather than under
    # the model's single overall guess, which may name a different one
    # (change/02 fix-1, FX-01).
    category_by_id = await umbrellas_repo.categories_by_ids(
        session,
        [u.main_category_id for candidates in umbrella_index.values() for u in candidates.values()],
    )

    def _category_name(umbrella) -> str | None:
        row = category_by_id.get(umbrella.main_category_id)
        return row.name if row else None

    per_community = []
    for level, entity_id in communities:
        key = (level, entity_id)
        candidates = umbrella_index.get(key, {})
        chosen_id = choices.get(key)
        umbrella = candidates.get(chosen_id) if chosen_id is not None else None
        per_community.append(
            {
                "level": level,
                "entity_id": entity_id,
                "umbrella_id": umbrella.id if umbrella else None,
                "umbrella_name": umbrella.name if umbrella else None,
                "umbrella_main_category": _category_name(umbrella) if umbrella else None,
                "active_umbrellas": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "statement": u.statement,
                        "main_category": _category_name(u),
                    }
                    for u in sorted(candidates.values(), key=lambda u: u.name)
                ],
            }
        )

    result = {
        "main_category_id": category.id if category else None,
        "main_category": main_category_name,
        "confidence": confidence,
        "communities": per_community,
        "repeated_or_unlisted_communities": duplicates,
    }
    await label_previews_repo.set_result(session, preview_row.id, result)
    await session.commit()

    log.info(
        "label_preview_suggested",
        extra={"preview_id": preview_row.id, "ai_action_id": action.id},
    )
    return {"preview_id": preview_row.id, **result}


async def load_post_for_job(session: AsyncSession, post_id: int) -> Post | None:
    """`backend/jobs/labeling.py` may call services only (ARCHITECTURE.md
    §2); it never reaches `posts_repo` itself."""
    return await posts_repo.get(session, post_id)


async def mark_unlabeled(session: AsyncSession, post_id: int) -> None:
    await posts_repo.set_label_status(session, post_id, "unlabeled")


async def posts_awaiting_labels(
    session: AsyncSession, *, stale_before: datetime
) -> list[Post]:
    return await posts_repo.posts_awaiting_labels(session, stale_before=stale_before)
