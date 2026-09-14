"""Solutions and their versions (DEMOCRACY.md §4.3, DATABASE.md §4.7, §4.8).

A solution lives inside exactly one umbrella. It is created either from a post,
when that post-community receives its umbrella, or directly on an umbrella page
by a member of that community.

Once posted a solution is community-owned (CLAUDE.md §6): the author is
recorded and displayed, and has no special rights over amendments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound, ValidationFailed
from backend.models import Post, PostSolution, Solution, Umbrella, User
from backend.repositories import posts as posts_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import hashing

log = logging.getLogger(__name__)

MIN_TEXT = 20
MAX_TEXT = 5000


def validate_text(text: str, what: str = "A solution") -> str:
    stripped = text.strip()
    if len(stripped) < MIN_TEXT:
        raise ValidationFailed(
            f"{what} needs at least {MIN_TEXT} characters so people can tell what it proposes.",
            code="text_too_short",
        )
    if len(stripped) > MAX_TEXT:
        raise ValidationFailed(
            f"{what} can be at most {MAX_TEXT:,} characters.", code="text_too_long"
        )
    return stripped


async def create_from_post_community(
    session: AsyncSession, *, post: Post, umbrella: Umbrella
) -> list[Solution]:
    """One `solutions` row and one version-1 row per `post_solutions` row.

    Called in the same transaction that sets `post_communities.umbrella_id`
    (DATABASE.md §4.7). A post going to three communities with two solution
    texts produces six solutions, because each community workshops it
    separately (DEMOCRACY.md §4.1).
    """
    created: list[Solution] = []
    for text_row in await posts_repo.solution_texts(session, post.id):
        existing = (
            await solutions_repo.for_post_community(session, post.id, umbrella.id)
        )
        if any(s.post_solution_id == text_row.id for s in existing):
            continue
        created.append(
            await _insert(
                session,
                umbrella_id=umbrella.id,
                author_id=post.author_id,
                text=text_row.text_body,
                post_id=post.id,
                post_solution=text_row,
            )
        )
    log.info(
        "solutions_created_from_post",
        extra={"post_id": post.id, "umbrella_id": umbrella.id, "created": len(created)},
    )
    return created


async def create_on_umbrella(
    session: AsyncSession, *, umbrella: Umbrella, author: User, text: str
) -> Solution:
    return await _insert(
        session,
        umbrella_id=umbrella.id,
        author_id=author.id,
        text=validate_text(text),
        post_id=None,
        post_solution=None,
    )


async def _insert(
    session: AsyncSession,
    *,
    umbrella_id: int,
    author_id: int,
    text: str,
    post_id: int | None,
    post_solution: PostSolution | None,
) -> Solution:
    now = datetime.now(timezone.utc)
    solution = await solutions_repo.add(
        session,
        umbrella_id=umbrella_id,
        post_id=post_id,
        post_solution_id=post_solution.id if post_solution else None,
        author_id=author_id,
        current_version=1,
        net_score=0,
        is_dominant=False,
        created_at=now,
    )
    await solutions_repo.add_version(
        session,
        solution_id=solution.id,
        version=1,
        text_body=text,
        created_by=author_id,
        amendment_id=None,
        ai_contribution_percentage=0,
        content_hash=hashing.solution_version_content_hash(
            solution_id=solution.id,
            version=1,
            text=text,
            created_by=author_id,
            created_at=now,
        ),
        created_at=now,
    )
    return solution


async def add_version(
    session: AsyncSession,
    *,
    solution: Solution,
    text: str,
    created_by: int,
    amendment_id: int | None,
) -> int:
    """Create version n+1. Every version is kept, with its own hash (Law 6)."""
    now = datetime.now(timezone.utc)
    version = solution.current_version + 1
    await solutions_repo.add_version(
        session,
        solution_id=solution.id,
        version=version,
        text_body=text,
        created_by=created_by,
        amendment_id=amendment_id,
        ai_contribution_percentage=0,
        content_hash=hashing.solution_version_content_hash(
            solution_id=solution.id,
            version=version,
            text=text,
            created_by=created_by,
            created_at=now,
        ),
        created_at=now,
    )
    solution.current_version = version
    await session.flush()
    return version


async def edit_text(
    session: AsyncSession, *, solution: Solution, editor: User, text: str
) -> None:
    """DEMOCRACY.md §4.3 — the author may edit only while the solution has zero
    votes and zero amendments. After that, changes happen only through
    amendments."""
    if solution.author_id != editor.id:
        raise Forbidden(
            "Solutions belong to the community once posted. Propose an amendment "
            "instead.",
            code="not_the_author",
        )
    votes = await votes_repo.count_votes_on(session, "solution", solution.id)
    amendments = await solutions_repo.count_amendments(session, solution.id)
    if votes or amendments:
        raise Conflict(
            "People have already voted on or amended this solution, so it belongs "
            "to the community now. Propose an amendment to change it.",
            code="solution_locked",
        )
    clean = validate_text(text)
    version = await solutions_repo.current_version(session, solution.id)
    if version is None:
        raise NotFound("That solution has no text.", code="solution_version_missing")
    now = datetime.now(timezone.utc)
    version.text_body = clean
    version.content_hash = hashing.solution_version_content_hash(
        solution_id=solution.id,
        version=version.version,
        text=clean,
        created_by=version.created_by,
        created_at=now,
    )
    version.created_at = now
    await session.flush()


async def move_if_untouched(
    session: AsyncSession, *, post_id: int, from_umbrella_id: int, to_umbrella: Umbrella
) -> tuple[bool, list[Solution]]:
    """A label correction moves the solutions already created only while every
    one of them has zero votes and zero amendments (DEMOCRACY.md §4.1)."""
    existing = await solutions_repo.for_post_community(session, post_id, from_umbrella_id)
    if not existing:
        return True, []
    for solution in existing:
        if await votes_repo.count_votes_on(session, "solution", solution.id):
            return False, existing
        if await solutions_repo.count_amendments(session, solution.id):
            return False, existing
    for solution in existing:
        solution.umbrella_id = to_umbrella.id
    await session.flush()
    return True, existing


async def require_umbrella(session: AsyncSession, umbrella_id: int) -> Umbrella:
    umbrella = await umbrellas_repo.get(session, umbrella_id)
    if umbrella is None:
        raise NotFound("That umbrella does not exist.", code="umbrella_not_found")
    return umbrella


async def require_solution(session: AsyncSession, solution_id: int) -> Solution:
    solution = await solutions_repo.get(session, solution_id)
    if solution is None or solution.deleted_at is not None:
        raise NotFound("That solution does not exist.", code="solution_not_found")
    return solution
