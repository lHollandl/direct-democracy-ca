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
from backend.services import ai_log
from backend.services import comments as comments_service
from backend.services import community as community_service
from backend.services import hashing
from backend.services import juries as juries_service
from backend.services import rules
from backend.services import settings as settings_service
from backend.services import similarity as similarity_service
from backend.services.display import author_displays

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
        extra={
            "post_id": post.id,
            "umbrella_id": umbrella.id,
            "solutions_created": len(created),
        },
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
    amendments.

    The edit creates version n+1 with `created_by` the author and no
    amendment — the same mechanism as absorption (`add_version`), so
    version 1 and its hash are kept (CLAUDE.md Law 6; DATABASE.md §4.8:
    no column of an existing version row is ever updated)."""
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
    existing = await solutions_repo.current_version(session, solution.id)
    if existing is None:
        raise NotFound("That solution has no text.", code="solution_version_missing")
    await add_version(
        session, solution=solution, text=clean, created_by=editor.id, amendment_id=None
    )


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


async def detail_view(session: AsyncSession, solution: Solution, viewer: User | None) -> dict:
    """`GET /solutions/{id}` — the whole page (ARCHITECTURE.md §2: one service
    call per router endpoint beyond a `require_*` resolver; audit demo-01
    run 2 found this assembled across ten service calls in the router)."""
    from backend.services import amendments as amendments_service

    umbrella = await require_umbrella(session, solution.umbrella_id)
    versions = await solutions_repo.versions(session, solution.id)
    values = await settings_service.all_values(session)
    active_users = await community_service.active_user_count(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    my_vote = (
        (await votes_repo.user_votes_on(session, viewer.id, "solution", [solution.id])).get(
            solution.id
        )
        if viewer
        else None
    )
    amendments = await solutions_repo.amendments_for(session, solution.id)
    community = await community_service.resolve(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    displays = await author_displays(
        session, [solution.author_id] + [v.created_by for v in versions]
    )
    amendment_displays = await author_displays(session, [a.author_id for a in amendments])
    current = versions[-1].text_body if versions else ""

    return {
        "id": solution.id,
        "umbrella": {"id": umbrella.id, "name": umbrella.name},
        "community": community.as_dict(),
        "text": current,
        "current_version": solution.current_version,
        "author": displays.get(solution.author_id, "Former Community Member"),
        "net_score": solution.net_score,
        "my_vote": my_vote,
        "supporters": await solutions_repo.supporters(session, solution.id),
        "is_dominant": solution.is_dominant,
        "dominant_since": solution.dominant_since,
        "dominant_threshold": rules.dominant_threshold(
            dominant_pct=values["dominant_pct"],
            dominant_min=values["dominant_min"],
            active_users=active_users,
        ),
        "ballot_threshold": rules.ballot_threshold(
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
        "absorption_threshold": await amendments_service.absorption_threshold_for(
            session, solution.id
        ),
        "on_track_for_ballot": rules.on_track_for_ballot(
            is_dominant_now=solution.is_dominant,
            net_score_value=solution.net_score,
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
        "last_ballot_result": solution.last_ballot_result,
        "last_ballot_version": solution.last_ballot_version,
        "return_rule_note": (
            "A solution that has been on a ballot — passed, failed or held back — "
            "returns only once it has a newer version. The way back is an amendment."
        ),
        "ownership_note": (
            "Solutions belong to the community once posted. The author is recorded "
            "and shown; changes happen through amendments."
        ),
        "versions": [
            {
                "version": v.version,
                "text": v.text_body,
                "written_by": displays.get(v.created_by, "Former Community Member"),
                "from_amendment_id": v.amendment_id,
                "content_hash": v.content_hash,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "amendments": [
            {
                "id": a.id,
                "author": amendment_displays.get(a.author_id, "Former Community Member"),
                "proposed_text": a.proposed_text,
                "rationale": a.rationale,
                "status": a.status,
                "base_version": a.base_version,
                "absorbed_as_version": a.absorbed_as_version,
                "merged_into_id": a.merged_into_id,
                "net_score": a.net_score,
                "diff": amendments_service.diff(current, a.proposed_text),
                "content_hash": a.content_hash,
                "created_at": a.created_at,
                "ai_influence": ai_log.influence(a.ai_contribution_percentage),
            }
            for a in amendments
        ],
        "similar_pairs": await similarity_service.pairs_for_solution(session, solution.id),
        "discussion": (
            await comments_service.thread(
                session,
                target_type="solution",
                target_id=solution.id,
                viewer_id=viewer.id if viewer else None,
            )
            if solution.is_dominant
            else []
        ),
        "discussion_note": (
            None
            if solution.is_dominant
            else "Discussion opens when a solution becomes dominant."
        ),
        "ai_influence": ai_log.influence(
            versions[-1].ai_contribution_percentage if versions else 0
        ),
        "jury_notes": await juries_service.jury_notes_for_solution(session, solution.id),
    }
