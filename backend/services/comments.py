"""Threaded discussion (DEMOCRACY.md §6).

Comments exist on two things only: an umbrella's problem, and each dominant
solution. Not on posts, not on non-dominant solutions, not on amendments, not
on references — on a non-dominant solution you upvote it or propose a better
one.

Nothing is hidden by score. A deleted comment keeps its row and its replies;
its text is replaced.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound, ValidationFailed
from backend.models import Comment, User
from backend.repositories import comments as comments_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import ai_log
from backend.services import hashing
from backend.services import settings as settings_service
from backend.services.display import author_displays

log = logging.getLogger(__name__)

MIN_TEXT = 1
MAX_TEXT = 2000
REMOVED_TEXT = "[removed by author]"


async def create(
    session: AsyncSession,
    *,
    author: User,
    target_type: str,
    target_id: int,
    parent_id: int | None,
    text: str,
) -> Comment:
    clean = text.strip()
    if not MIN_TEXT <= len(clean) <= MAX_TEXT:
        raise ValidationFailed(
            f"A comment can be up to {MAX_TEXT:,} characters.", code="bad_comment_text"
        )
    level, entity_id = await target_community(session, target_type, target_id)
    from backend.deps import require_member

    await require_member(session, author, level, entity_id)

    max_depth = int(await settings_service.get(session, "comment_max_depth"))
    depth = 0
    replying_to: str | None = None
    if parent_id is not None:
        parent = await comments_repo.get(session, parent_id)
        if parent is None:
            raise NotFound("That comment does not exist.", code="comment_not_found")
        if (parent.target_type, parent.target_id) != (target_type, target_id):
            raise ValidationFailed(
                "That reply belongs to a different discussion.", code="comment_wrong_target"
            )
        # Deeper replies attach to the depth-cap comment with "replying to @name".
        if parent.depth >= max_depth:
            displays = await author_displays(session, [parent.author_id])
            replying_to = displays.get(parent.author_id)
            while parent.parent_id is not None and parent.depth > max_depth:
                grandparent = await comments_repo.get(session, parent.parent_id)
                if grandparent is None:
                    break
                parent = grandparent
            depth = parent.depth
            parent_id = parent.id
        else:
            depth = parent.depth + 1
            parent_id = parent.id

    body = f"replying to @{replying_to}: {clean}" if replying_to else clean
    now = datetime.now(timezone.utc)
    comment = await comments_repo.add(
        session,
        target_type=target_type,
        target_id=target_id,
        parent_id=parent_id,
        depth=depth,
        author_id=author.id,
        text_body=body,
        net_score=0,
        ai_contribution_percentage=0,
        content_hash=hashing.comment_content_hash(
            target_type=target_type,
            target_id=target_id,
            author_id=author.id,
            text=body,
            created_at=now,
        ),
        created_at=now,
    )
    log.info("comment_created", extra={"comment_id": comment.id, "depth": depth})
    return comment


async def target_community(
    session: AsyncSession, target_type: str, target_id: int
) -> tuple[str, int]:
    """Also enforces where comments may exist at all (DEMOCRACY.md §6)."""
    if target_type == "umbrella":
        umbrella = await umbrellas_repo.get(session, target_id)
        if umbrella is None:
            raise NotFound("That umbrella does not exist.", code="umbrella_not_found")
        return umbrella.community_level, umbrella.community_entity_id
    if target_type == "solution":
        solution = await solutions_repo.get(session, target_id)
        if solution is None or solution.deleted_at is not None:
            raise NotFound("That solution does not exist.", code="solution_not_found")
        if not solution.is_dominant:
            raise Conflict(
                "Discussion opens once a solution becomes dominant. Until then you "
                "can upvote it, or propose a better one.",
                code="solution_not_dominant",
            )
        umbrella = await umbrellas_repo.get(session, solution.umbrella_id)
        if umbrella is None:
            raise NotFound("That solution's umbrella is missing.", code="umbrella_not_found")
        return umbrella.community_level, umbrella.community_entity_id
    raise ValidationFailed(
        "Discussion happens on an umbrella's problem and on dominant solutions.",
        code="bad_comment_target",
    )


async def edit(session: AsyncSession, *, comment: Comment, user: User, text: str) -> Comment:
    if comment.author_id != user.id:
        raise Forbidden("You can only edit your own comment.", code="not_the_author")
    if comment.removed_at is not None:
        raise Conflict("That comment was removed.", code="comment_removed")
    minutes = int(await settings_service.get(session, "comment_edit_minutes"))
    if datetime.now(timezone.utc) - comment.created_at > timedelta(minutes=minutes):
        raise Conflict(
            f"Comments can be edited for {minutes} minutes after posting. After that "
            "they stay as written, so the discussion is not rewritten underneath "
            "the people who replied.",
            code="edit_window_closed",
        )
    clean = text.strip()
    if not MIN_TEXT <= len(clean) <= MAX_TEXT:
        raise ValidationFailed(
            f"A comment can be up to {MAX_TEXT:,} characters.", code="bad_comment_text"
        )
    comment.text_body = clean
    comment.edited_at = datetime.now(timezone.utc)
    await session.flush()
    return comment


async def remove(session: AsyncSession, *, comment: Comment, user: User) -> Comment:
    """Soft: the row stays, the text is replaced, the replies remain."""
    if comment.author_id != user.id:
        raise Forbidden("You can only remove your own comment.", code="not_the_author")
    if comment.removed_at is None:
        comment.text_body = REMOVED_TEXT
        comment.removed_at = datetime.now(timezone.utc)
        await session.flush()
    return comment


async def thread(
    session: AsyncSession, *, target_type: str, target_id: int, viewer_id: int | None
) -> list[dict]:
    """The whole discussion as a tree. Within each thread: net score
    descending, ties oldest first (DEMOCRACY.md §6)."""
    rows = await comments_repo.for_target(session, target_type, target_id)
    displays = await author_displays(session, [row.author_id for row in rows])
    my_votes = (
        await votes_repo.user_votes_on(session, viewer_id, "comment", [r.id for r in rows])
        if viewer_id
        else {}
    )
    by_parent: dict[int | None, list] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)
    for children in by_parent.values():
        children.sort(key=lambda c: (-c.net_score, c.created_at, c.id))

    def build(parent_id: int | None) -> list[dict]:
        out = []
        for row in by_parent.get(parent_id, []):
            out.append(
                {
                    "id": row.id,
                    "author": displays.get(row.author_id, "Former Community Member"),
                    "text": row.text_body,
                    "depth": row.depth,
                    "net_score": row.net_score,
                    "my_vote": my_votes.get(row.id),
                    "created_at": row.created_at,
                    "edited": row.edited_at is not None,
                    "removed": row.removed_at is not None,
                    "ai_influence": ai_log.influence(row.ai_contribution_percentage),
                    "replies": build(row.id),
                }
            )
        return out

    return build(None)


async def require_comment(session: AsyncSession, comment_id: int) -> Comment:
    comment = await comments_repo.get(session, comment_id)
    if comment is None:
        raise NotFound("That comment does not exist.", code="comment_not_found")
    return comment
