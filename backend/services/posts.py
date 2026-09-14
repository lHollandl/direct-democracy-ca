"""Posts: a citizen's problem report plus at least one proposed solution.

CLAUDE.md Law 1: a post cannot be saved without at least one solution. Citizens
propose what they want done; they do not only complain. Enforced here and in
the schema.

DEMOCRACY.md §4.1: the post, its solution texts and its communities are written
in one transaction; labeling runs afterwards in the background. A post cannot be
edited or deleted in Demo 1 — its problem text is hashed at creation and is
immutable (Law 6).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound, ValidationFailed
from backend.models import Post, User
from backend.repositories import posts as posts_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import community as community_service
from backend.services import hashing
from backend.services import solutions as solutions_service
from backend.services.display import author_display, author_displays

log = logging.getLogger(__name__)

MIN_PROBLEM = 20
MAX_PROBLEM = 5000
TITLE_LENGTH = 80


def derive_title(problem_text: str) -> str:
    """DEMOCRACY.md §4.2 — the first 80 characters, cut at a word boundary.
    Derived, never stored, never editable."""
    text = " ".join(problem_text.split())
    if len(text) <= TITLE_LENGTH:
        return text
    cut = text[:TITLE_LENGTH]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "…"


async def create(
    session: AsyncSession,
    *,
    author: User,
    problem_text: str,
    solution_texts: list[str],
    communities: list[tuple[str, int]],
    category_choice: str,
    chosen_umbrellas: dict[tuple[str, int], int] | None = None,
) -> Post:
    """One transaction: `posts` + `post_solutions` + `post_communities` (Law 5)."""
    problem = problem_text.strip()
    if not MIN_PROBLEM <= len(problem) <= MAX_PROBLEM:
        raise ValidationFailed(
            f"Describe the problem in between {MIN_PROBLEM} and {MAX_PROBLEM:,} characters.",
            code="bad_problem_text",
        )
    if not solution_texts:
        raise ValidationFailed(
            "Every post needs at least one proposed solution. This platform is not "
            "a place to complain without proposing something.",
            code="no_solution",
        )
    cleaned = [solutions_service.validate_text(text) for text in solution_texts]
    if not communities:
        raise ValidationFailed(
            "Choose at least one of your communities to post this in.",
            code="no_community",
        )
    if category_choice not in ("ai", "author_selected"):
        raise ValidationFailed(
            "Choose whether the platform files this for you or you pick the umbrella.",
            code="bad_category_choice",
        )

    chosen_umbrellas = chosen_umbrellas or {}
    for level, entity_id in communities:
        await community_service.resolve(session, level, entity_id)
        if not await community_service.is_member(session, author, level, entity_id):
            raise Forbidden(
                "You can only post in your own city, your county and California.",
                code="not_a_member",
            )
    if category_choice == "author_selected":
        missing = [c for c in communities if c not in chosen_umbrellas]
        if missing:
            raise ValidationFailed(
                "Pick an umbrella for every community you selected, or let the "
                "platform file it for you.",
                code="umbrella_not_chosen",
            )

    now = datetime.now(timezone.utc)
    post = await posts_repo.add(
        session,
        author_id=author.id,
        problem_text=problem,
        category_choice=category_choice,
        label_status="pending",
        ai_contribution_percentage=0,
        content_hash=hashing.post_content_hash(
            problem_text=problem,
            author_id=author.id,
            created_at=now,
            ai_contribution_percentage=0,
        ),
        created_at=now,
    )
    for position, text in enumerate(cleaned, start=1):
        await posts_repo.add_solution_text(
            session,
            post_id=post.id,
            position=position,
            text_body=text,
            ai_contribution_percentage=0,
            content_hash=hashing.post_solution_content_hash(
                post_id=post.id, position=position, text=text, created_at=now
            ),
            created_at=now,
        )
    for level, entity_id in communities:
        await posts_repo.add_community(
            session,
            post_id=post.id,
            community_level=level,
            community_entity_id=entity_id,
            umbrella_id=None,
            main_category_id=None,
        )

    if category_choice == "author_selected":
        await _apply_author_choice(session, post=post, chosen=chosen_umbrellas)

    log.info(
        "post_created",
        extra={
            "post_id": post.id,
            "author_id": author.id,
            "communities": len(communities),
            "solution_texts": len(cleaned),
            "category_choice": category_choice,
        },
    )
    return post


async def _apply_author_choice(
    session: AsyncSession, *, post: Post, chosen: dict[tuple[str, int], int]
) -> None:
    """"Pick an existing umbrella" — recorded as `author_selected` (§4.1)."""
    for (level, entity_id), umbrella_id in chosen.items():
        umbrella = await umbrellas_repo.get(session, umbrella_id)
        if umbrella is None or umbrella.status != "active":
            raise NotFound(
                "That umbrella is not available to post in.", code="umbrella_not_found"
            )
        if (umbrella.community_level, umbrella.community_entity_id) != (level, entity_id):
            raise ValidationFailed(
                "That umbrella belongs to a different community.",
                code="umbrella_wrong_community",
            )
        row = await posts_repo.community(session, post.id, level, entity_id)
        if row is None:
            continue
        row.umbrella_id = umbrella.id
        row.main_category_id = umbrella.main_category_id
        await posts_repo.add_label(
            session,
            post_id=post.id,
            community_level=level,
            community_entity_id=entity_id,
            ai_action_id=None,
            main_category_id=umbrella.main_category_id,
            umbrella_id=umbrella.id,
            confidence=None,
            outcome="author_selected",
        )
        await solutions_service.create_from_post_community(
            session, post=post, umbrella=umbrella
        )
    await posts_repo.set_label_status(session, post.id, "labeled")
    await session.flush()


async def confirm_label(session: AsyncSession, *, post: Post, user: User) -> dict:
    """One tap. Records `confirmed_by_author` on every AI label of this post."""
    if post.author_id != user.id:
        raise Forbidden("Only the author can confirm the filing.", code="not_the_author")
    confirmed = 0
    for label in await posts_repo.labels_for_post(session, post.id):
        if label.ai_action_id is None or label.outcome != "unreviewed":
            continue
        label.outcome = "confirmed_by_author"
        await ai_log.record_outcome(
            session, action_id=label.ai_action_id, outcome="confirmed", user_id=user.id
        )
        confirmed += 1
    await session.flush()
    return {"confirmed": confirmed}


async def correct_label(
    session: AsyncSession,
    *,
    post: Post,
    user: User,
    level: str,
    entity_id: int,
    umbrella_id: int,
) -> dict:
    """The author corrects where a post was filed (DEMOCRACY.md §4.1, §9.1).

    Solutions already created move to the new umbrella only while they have
    zero votes and zero amendments; otherwise they stay where they are and the
    correction is recorded but creates nothing new.
    """
    if post.author_id != user.id:
        raise Forbidden("Only the author can correct the filing.", code="not_the_author")
    umbrella = await umbrellas_repo.get(session, umbrella_id)
    if umbrella is None or umbrella.status != "active":
        raise NotFound("That umbrella is not available.", code="umbrella_not_found")
    if (umbrella.community_level, umbrella.community_entity_id) != (level, entity_id):
        raise ValidationFailed(
            "That umbrella belongs to a different community.", code="umbrella_wrong_community"
        )
    row = await posts_repo.community(session, post.id, level, entity_id)
    if row is None:
        raise NotFound("This post was not sent to that community.", code="post_community_not_found")
    if row.umbrella_id == umbrella.id:
        raise Conflict("It is already filed there.", code="already_filed_there")

    previous_umbrella_id = row.umbrella_id
    label = await posts_repo.latest_label(session, post.id, level, entity_id)
    moved: list = []
    created: list = []
    if previous_umbrella_id is None:
        row.umbrella_id = umbrella.id
        row.main_category_id = umbrella.main_category_id
        created = await solutions_service.create_from_post_community(
            session, post=post, umbrella=umbrella
        )
        movable = True
    else:
        movable, moved = await solutions_service.move_if_untouched(
            session,
            post_id=post.id,
            from_umbrella_id=previous_umbrella_id,
            to_umbrella=umbrella,
        )
        if movable:
            row.umbrella_id = umbrella.id
            row.main_category_id = umbrella.main_category_id

    if label is not None and label.outcome == "unreviewed":
        label.outcome = "corrected_by_author"
        label.corrected_umbrella_id = umbrella.id
        await ai_log.record_outcome(
            session, action_id=label.ai_action_id, outcome="corrected", user_id=user.id
        )
    else:
        await posts_repo.add_label(
            session,
            post_id=post.id,
            community_level=level,
            community_entity_id=entity_id,
            ai_action_id=None,
            main_category_id=umbrella.main_category_id,
            umbrella_id=previous_umbrella_id,
            confidence=None,
            outcome="corrected_by_author",
            corrected_umbrella_id=umbrella.id,
        )

    await _refresh_label_status(session, post)
    await session.flush()
    return {
        "moved_to_umbrella": umbrella.id if movable else previous_umbrella_id,
        "solutions_moved": [s.id for s in moved] if movable else [],
        "solutions_created": [s.id for s in created],
        "left_in_place": not movable,
        "note": (
            None
            if movable
            else (
                "People have already voted on or amended the solutions that were "
                "filed here, so they stay where they are. Your correction is "
                "recorded, and new posts will be filed under the umbrella you chose."
            )
        ),
    }


async def _refresh_label_status(session: AsyncSession, post: Post) -> None:
    rows = await posts_repo.communities(session, post.id)
    if all(row.umbrella_id is not None for row in rows):
        await posts_repo.set_label_status(session, post.id, "labeled")
    elif any(row.main_category_id is not None and row.umbrella_id is None for row in rows):
        await posts_repo.set_label_status(session, post.id, "needs_review")


async def view(session: AsyncSession, post: Post) -> dict:
    """Everything `GET /posts/{id}` shows."""
    communities = await posts_repo.communities(session, post.id)
    umbrellas = await umbrellas_repo.by_ids(
        session, [c.umbrella_id for c in communities if c.umbrella_id]
    )
    categories = await umbrellas_repo.categories_by_ids(
        session, [c.main_category_id for c in communities if c.main_category_id]
    )
    labels = {
        (label.community_level, label.community_entity_id): label
        for label in await posts_repo.labels_for_post(session, post.id)
    }
    solutions = await solutions_repo.for_post(session, post.id)
    solutions_by_umbrella: dict[int, list[int]] = {}
    for solution in solutions:
        solutions_by_umbrella.setdefault(solution.umbrella_id, []).append(solution.id)

    community_views = []
    for row in communities:
        resolved = await community_service.resolve(
            session, row.community_level, row.community_entity_id
        )
        label = labels.get((row.community_level, row.community_entity_id))
        umbrella = umbrellas.get(row.umbrella_id) if row.umbrella_id else None
        community_views.append(
            {
                "community": resolved.as_dict(),
                "umbrella_id": row.umbrella_id,
                "umbrella_name": umbrella.name if umbrella else None,
                "main_category": (
                    categories[row.main_category_id].name
                    if row.main_category_id in categories
                    else None
                ),
                "label_status": _label_status_words(post.label_status, row.umbrella_id),
                "label_outcome": label.outcome if label else None,
                "label_shown_as": _label_words(label),
                "confidence": float(label.confidence) if label and label.confidence else None,
                "solution_ids": solutions_by_umbrella.get(row.umbrella_id or -1, []),
            }
        )

    texts = await posts_repo.solution_texts(session, post.id)
    return {
        "id": post.id,
        "title": derive_title(post.problem_text),
        "problem_text": post.problem_text,
        "author": await author_display(session, post.author_id),
        "author_id": post.author_id,
        "created_at": post.created_at,
        "content_hash": post.content_hash,
        "label_status": post.label_status,
        "category_choice": post.category_choice,
        "ai_influence": ai_log.influence(post.ai_contribution_percentage),
        "communities": community_views,
        "solution_texts": [
            {
                "id": row.id,
                "position": row.position,
                "text": row.text_body,
                "content_hash": row.content_hash,
            }
            for row in texts
        ],
        "immutable_note": (
            "Posts cannot be edited or deleted in this build. The problem text was "
            "fingerprinted when it was created. The solutions evolve in the workshop."
        ),
    }


def _label_status_words(status: str, umbrella_id: int | None) -> str:
    if umbrella_id is not None:
        return "Filed"
    return {
        "pending": "Being filed",
        "unlabeled": "Waiting to be filed — the platform will try again shortly",
        "needs_review": "No umbrella in this community covers this yet",
        "labeled": "Filed",
    }.get(status, status)


def _label_words(label) -> str | None:
    if label is None:
        return None
    return {
        "unreviewed": "AI-labeled, not yet reviewed by the author",
        "confirmed_by_author": "AI-labeled, confirmed by author",
        "corrected_by_author": "AI-labeled, corrected by author",
        "author_selected": "chosen by author",
    }.get(label.outcome, label.outcome)


async def feed(
    session: AsyncSession,
    *,
    viewer: User | None,
    community: str | None,
    category: str | None,
    cursor: int | None,
    limit: int,
) -> dict:
    """`GET /feed` — feed-v0, newest first (DEMOCRACY.md §12)."""
    community_filter = None
    if community:
        level, _, raw_id = community.partition(":")
        resolved = await community_service.resolve(session, level, int(raw_id))
        community_filter = (resolved.level, resolved.entity_id)

    category_id = None
    if category:
        row = await umbrellas_repo.category_by_slug(session, category)
        category_id = row.id if row else -1

    home_keys = None
    if community_filter is None and viewer is not None:
        home_keys = [c.key for c in await community_service.home_communities(session, viewer)]

    rows = await posts_repo.feed_page(
        session,
        cursor=cursor,
        limit=limit,
        community=community_filter,
        main_category_id=category_id,
        community_keys=home_keys,
    )
    displays = await author_displays(session, [p.author_id for p in rows])
    items = []
    for post in rows:
        communities = await posts_repo.communities(session, post.id)
        items.append(
            {
                "id": post.id,
                "title": derive_title(post.problem_text),
                "problem_text": post.problem_text,
                "author": displays.get(post.author_id, "Former Community Member"),
                "created_at": post.created_at,
                "label_status": post.label_status,
                "ai_influence": ai_log.influence(post.ai_contribution_percentage),
                "communities": [
                    {
                        "level": c.community_level,
                        "entity_id": c.community_entity_id,
                        "umbrella_id": c.umbrella_id,
                    }
                    for c in communities
                ],
            }
        )
    return {
        "items": items,
        "next_cursor": rows[-1].id if len(rows) == limit else None,
        "filters": {
            "community": community,
            "category": category,
            "default": (
                "your home communities" if home_keys else "everything, newest first"
            ),
        },
    }


async def require_post(session: AsyncSession, post_id: int) -> Post:
    post = await posts_repo.get(session, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFound("That post does not exist.", code="post_not_found")
    return post
