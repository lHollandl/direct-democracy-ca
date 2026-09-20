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
from backend.models import LabelPreview, Post, User
from backend.repositories import label_previews as label_previews_repo
from backend.repositories import posts as posts_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import communities as community_service
from backend.services import hashing
from backend.services import settings as settings_service
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
    chosen_umbrellas: dict[tuple[str, int], int | None] | None = None,
    preview_id: int | None = None,
    main_category_id: int | None = None,
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
    if category_choice not in ("ai", "author_selected", "preview"):
        raise ValidationFailed(
            "Choose whether the platform files this for you, you pick the "
            "umbrella, or you review its suggestion.",
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

    preview_row: LabelPreview | None = None
    if category_choice == "preview":
        if preview_id is None or main_category_id is None:
            raise ValidationFailed(
                "A reviewed suggestion needs its preview id and main category.",
                code="preview_required",
            )
        preview_row = await label_previews_repo.get(session, preview_id)
        if preview_row is None:
            raise NotFound("That suggestion does not exist.", code="preview_not_found")
        if preview_row.user_id != author.id:
            raise Forbidden(
                "That suggestion belongs to someone else.", code="preview_not_yours"
            )
        if preview_row.consumed_post_id is not None:
            raise Conflict(
                "That suggestion has already been used.", code="preview_already_used"
            )
        expected_hash = hashing.label_preview_input_hash(
            problem_text=problem, communities=communities
        )
        if preview_row.input_hash != expected_hash:
            raise Conflict(
                "Your text changed — run the suggestion again.", code="preview_stale"
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
    elif category_choice == "preview":
        await _apply_preview_choice(
            session,
            post=post,
            author=author,
            communities=communities,
            chosen=chosen_umbrellas,
            preview=preview_row,
            main_category_id=main_category_id,
        )
    else:
        _schedule_labeling(session, post.id)

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


def _schedule_labeling(session: AsyncSession, post_id: int, *, name_prefix: str = "label_post") -> None:
    """The service that owns the transaction schedules the job (ARCHITECTURE.md
    §7): labeling runs after this session commits, so it never opens against a
    post row that does not exist yet (demo-01 bug)."""
    from backend.jobs import labeling as labeling_job
    from backend.jobs import runner

    runner.spawn_after_commit(
        session,
        lambda: labeling_job.label_post_task(post_id),
        name=f"{name_prefix}:{post_id}",
    )


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


async def _apply_preview_choice(
    session: AsyncSession,
    *,
    post: Post,
    author: User,
    communities: list[tuple[str, int]],
    chosen: dict[tuple[str, int], int | None],
    preview: LabelPreview,
    main_category_id: int,
) -> None:
    """The author reviewed the AI's suggestion on the draft before posting
    (DEMOCRACY.md §4.1, §9.1). Every community gets a label row pointing at
    the preview's `ai_action_id`; the outcome is `confirmed_by_author` when
    the author kept the suggestion, `corrected_by_author` otherwise —
    including a community left at "none of these fit" when the AI had
    suggested an umbrella. Solutions are created in this same transaction
    for every community the author gave an umbrella to."""
    suggested_by_key = {
        (c["level"], c["entity_id"]): c["umbrella_id"]
        for c in (preview.result or {}).get("communities", [])
    }
    preview_confidence = (preview.result or {}).get("confidence")
    all_confirmed = True
    for level, entity_id in communities:
        key = (level, entity_id)
        umbrella_id = chosen.get(key)
        umbrella = None
        if umbrella_id is not None:
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
        kept = umbrella_id == suggested_by_key.get(key)
        outcome = "confirmed_by_author" if kept else "corrected_by_author"
        all_confirmed = all_confirmed and kept

        row = await posts_repo.community(session, post.id, level, entity_id)
        row.main_category_id = main_category_id
        await posts_repo.add_label(
            session,
            post_id=post.id,
            community_level=level,
            community_entity_id=entity_id,
            ai_action_id=preview.ai_action_id,
            main_category_id=main_category_id,
            umbrella_id=umbrella.id if umbrella else None,
            confidence=preview_confidence,
            outcome=outcome,
        )
        if umbrella is not None:
            row.umbrella_id = umbrella.id
            await session.flush()
            await solutions_service.create_from_post_community(
                session, post=post, umbrella=umbrella
            )

    await _refresh_label_status(session, post)
    await label_previews_repo.mark_consumed(session, preview.id, post.id)
    await ai_log.record_outcome(
        session,
        action_id=preview.ai_action_id,
        outcome="confirmed" if all_confirmed else "corrected",
        user_id=author.id,
    )
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

    retry_minutes = int(await settings_service.get(session, "label_retry_minutes"))

    community_views = []
    for row in communities:
        resolved = await community_service.resolve(
            session, row.community_level, row.community_entity_id
        )
        label = labels.get((row.community_level, row.community_entity_id))
        umbrella = umbrellas.get(row.umbrella_id) if row.umbrella_id else None
        main_category_name = (
            categories[row.main_category_id].name
            if row.main_category_id in categories
            else None
        )
        has_active_umbrella = bool(
            await umbrellas_repo.for_community(
                session, row.community_level, row.community_entity_id
            )
        )
        community_views.append(
            {
                "community": resolved.as_dict(),
                "umbrella_id": row.umbrella_id,
                "umbrella_name": umbrella.name if umbrella else None,
                "main_category": main_category_name,
                "label_status": _label_status_words(
                    post.label_status,
                    row.umbrella_id,
                    community_label=resolved.label,
                    main_category_name=main_category_name,
                    retry_minutes=retry_minutes,
                    has_active_umbrella=has_active_umbrella,
                ),
                "has_active_umbrella": has_active_umbrella,
                "label_outcome": label.outcome if label else None,
                "label_shown_as": _label_words(label, category_choice=post.category_choice),
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


def _label_status_words(
    status: str,
    umbrella_id: int | None,
    *,
    community_label: str,
    main_category_name: str | None,
    retry_minutes: int,
    has_active_umbrella: bool,
) -> str:
    """DEMOCRACY.md §4.1 — the three honest filing states, plus the
    no-umbrellas-in-this-community case. They never share a sentence
    (CLAUDE.md §2, transparency about weakness)."""
    if umbrella_id is not None:
        return "Filed"
    if status == "pending":
        return "Being filed — the AI is reading this now"
    if status == "unlabeled":
        return (
            "Not filed yet — the AI could not be reached. The platform tries "
            f"again every {retry_minutes} minutes"
        )
    if status == "needs_review":
        if not has_active_umbrella:
            return (
                f"There are no umbrellas in {community_label} yet. Proposing "
                "a new umbrella is planned."
            )
        return (
            f"Not filed — no umbrella in {community_label} covers this yet. "
            f"It is saved under {main_category_name}."
        )
    return status


def _label_words(label, *, category_choice: str) -> str | None:
    if label is None:
        return None
    if category_choice == "preview":
        # DEMOCRACY.md §9.1 — the author reviewed the suggestion before
        # posting, so the wording says so rather than reusing the
        # background-labeling sentence (audit-visible distinction between
        # the two AI-filing paths).
        return {
            "unreviewed": "AI-suggested, not yet reviewed by the author",
            "confirmed_by_author": "AI-suggested, kept by author",
            "corrected_by_author": "AI-suggested, changed by author",
        }.get(label.outcome, label.outcome)
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
    scope: str | None,
    community: str | None,
    category: str | None,
    q: str | None,
    sort: str,
    cursor: str | None,
    limit: int,
) -> dict:
    """`GET /feed` — feed-v1 (DEMOCRACY.md §12.1)."""
    community_filter = None
    if community:
        level, _, raw_id = community.partition(":")
        resolved = await community_service.resolve(session, level, int(raw_id))
        community_filter = (resolved.level, resolved.entity_id)

    home_keys = None
    if community_filter is None and scope != "all" and viewer is not None:
        home_keys = [c.key for c in await community_service.home_communities(session, viewer)]

    category_id = None
    if category:
        row = await umbrellas_repo.category_by_slug(session, category)
        category_id = row.id if row else -1

    rows, next_cursor = await posts_repo.feed_page(
        session,
        sort=sort,
        cursor=cursor,
        limit=limit,
        community=community_filter,
        main_category_id=category_id,
        community_keys=home_keys,
        query=q,
    )
    displays = await author_displays(session, [row.author_id for row in rows])
    items = []
    for row in rows:
        communities = await posts_repo.communities(session, row.id)
        items.append(
            {
                "id": row.id,
                "title": derive_title(row.problem_text),
                "problem_text": row.problem_text,
                "author": displays.get(row.author_id, "Former Community Member"),
                "created_at": row.created_at,
                "label_status": row.label_status,
                "ai_influence": ai_log.influence(row.ai_contribution_percentage),
                "vote_count": row.vote_count,
                "comment_count": row.comment_count,
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
        "next_cursor": next_cursor,
        "filters": {
            "community": community,
            "category": category,
            "q": q,
            "scope": "all" if home_keys is None else "home",
            "default": "your home communities" if home_keys else "all of California",
        },
    }


async def request_relabel(session: AsyncSession, post: Post) -> None:
    """`POST /admin/posts/{id}/relabel` — the director forcing a retry
    (DEMOCRACY.md §13). The service that owns the transaction schedules the
    job (ARCHITECTURE.md §7)."""
    _schedule_labeling(session, post.id, name_prefix="relabel")


async def request_relabel_as_admin(session: AsyncSession, *, post: Post, admin: User) -> None:
    """Relabels and writes the admin log row in one service call
    (ARCHITECTURE.md §2/§10)."""
    from backend.services import admin_log

    old_status = post.label_status
    await request_relabel(session, post)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="force_relabel",
        subject_type="post",
        subject_id=post.id,
        old_value={"label_status": old_status},
    )


async def require_post(session: AsyncSession, post_id: int) -> Post:
    post = await posts_repo.get(session, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFound("That post does not exist.", code="post_not_found")
    return post
