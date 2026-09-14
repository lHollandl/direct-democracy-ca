"""Workshop votes and everything a vote sets off (DEMOCRACY.md §4.4, §5.3, §7.1).

One vote per person per item. A vote can be changed or removed at any time
until the item is frozen on a ballot. Every vote event recomputes the item's
net score from the vote rows — the denormalized column is never authoritative —
and then re-evaluates whatever status depends on it: dominance for a solution,
absorption for an amendment.

Downvotes lower a ranking. They never hide anything (CLAUDE.md §4).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, NotFound, ValidationFailed
from backend.models import Solution, User
from backend.repositories import comments as comments_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import community as community_service
from backend.services import rules
from backend.services import settings as settings_service

log = logging.getLogger(__name__)

TARGET_TYPES = ("solution", "amendment", "comment")


async def cast(
    session: AsyncSession,
    *,
    user: User,
    target_type: str,
    target_id: int,
    direction: int,
) -> dict:
    """Place or change a vote, then recompute everything it affects."""
    if target_type not in TARGET_TYPES:
        raise ValidationFailed(
            "You can vote on a solution, an amendment or a comment.",
            code="unknown_vote_target",
        )
    if direction not in (1, -1):
        raise ValidationFailed("A vote is either up (1) or down (-1).", code="bad_direction")

    target = await _load_target(session, target_type, target_id)
    await _require_member_of_target_community(session, user, target_type, target)
    await votes_repo.put_vote(
        session, user_id=user.id, target_type=target_type, target_id=target_id, direction=direction
    )
    return await recount(session, target_type=target_type, target_id=target_id, target=target)


async def withdraw(
    session: AsyncSession, *, user: User, target_type: str, target_id: int
) -> dict:
    if target_type not in TARGET_TYPES:
        raise ValidationFailed(
            "You can vote on a solution, an amendment or a comment.",
            code="unknown_vote_target",
        )
    target = await _load_target(session, target_type, target_id)
    removed = await votes_repo.remove_vote(
        session, user_id=user.id, target_type=target_type, target_id=target_id
    )
    if not removed:
        raise NotFound("You have no vote on that to remove.", code="no_vote")
    return await recount(session, target_type=target_type, target_id=target_id, target=target)


async def recount(
    session: AsyncSession, *, target_type: str, target_id: int, target=None
) -> dict:
    """Recompute the net score from the vote rows and re-evaluate any status."""
    if target is None:
        target = await _load_target(session, target_type, target_id)
    upvotes, downvotes = await votes_repo.tally(session, target_type, target_id)
    score = rules.net_score(upvotes, downvotes)
    target.net_score = score
    await session.flush()

    result: dict = {
        "target_type": target_type,
        "target_id": target_id,
        "net_score": score,
        "upvotes": upvotes,
        "downvotes": downvotes,
    }
    if target_type == "solution":
        result.update(await evaluate_dominance(session, target))
    elif target_type == "amendment":
        from backend.services import amendments as amendments_service

        result.update(await amendments_service.evaluate_absorption(session, target))
    return result


async def evaluate_dominance(session: AsyncSession, solution: Solution) -> dict:
    """DEMOCRACY.md §7.1, evaluated on every vote event and once nightly."""
    umbrella = await umbrellas_repo.get(session, solution.umbrella_id)
    if umbrella is None:
        raise NotFound("That solution's umbrella is missing.", code="umbrella_not_found")
    values = await settings_service.all_values(session)
    active_users = await community_service.active_user_count(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    needed = rules.dominant_threshold(
        dominant_pct=values["dominant_pct"],
        dominant_min=values["dominant_min"],
        active_users=active_users,
    )
    now_dominant = solution.net_score >= needed
    changed = now_dominant != solution.is_dominant
    if changed:
        solution.is_dominant = now_dominant
        solution.dominant_since = datetime.now(timezone.utc) if now_dominant else None
        await session.flush()
        log.info(
            "dominance_changed",
            extra={
                "solution_id": solution.id,
                "is_dominant": now_dominant,
                "net_score": solution.net_score,
                "threshold": needed,
                "active_users": active_users,
            },
        )
    return {
        "is_dominant": solution.is_dominant,
        "dominant_since": solution.dominant_since,
        "dominance_changed": changed,
        "dominant_threshold": needed,
        "active_users": active_users,
        "on_track_for_ballot": rules.on_track_for_ballot(
            is_dominant_now=solution.is_dominant,
            net_score_value=solution.net_score,
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
        "ballot_threshold": rules.ballot_threshold(
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
    }


async def _load_target(session: AsyncSession, target_type: str, target_id: int):
    getter = {
        "solution": solutions_repo.get,
        "amendment": solutions_repo.get_amendment,
        "comment": comments_repo.get,
    }[target_type]
    row = await getter(session, target_id)
    if row is None:
        raise NotFound("That is not something you can vote on.", code="vote_target_not_found")
    if target_type == "solution" and row.deleted_at is not None:
        raise NotFound("That solution does not exist.", code="solution_not_found")
    if target_type == "comment" and row.removed_at is not None:
        raise Conflict("That comment was removed by its author.", code="comment_removed")
    return row


async def _require_member_of_target_community(
    session: AsyncSession, user: User, target_type: str, target
) -> None:
    """Members vote in their own communities only (DEMOCRACY.md §2.3)."""
    umbrella_id = await _umbrella_of(session, target_type, target)
    umbrella = await umbrellas_repo.get(session, umbrella_id)
    if umbrella is None:
        raise NotFound("That item's umbrella is missing.", code="umbrella_not_found")
    from backend.deps import require_member

    await require_member(
        session, user, umbrella.community_level, umbrella.community_entity_id
    )


async def _umbrella_of(session: AsyncSession, target_type: str, target) -> int:
    if target_type == "solution":
        return target.umbrella_id
    if target_type == "amendment":
        solution = await solutions_repo.get(session, target.solution_id)
        if solution is None:
            raise NotFound("That amendment's solution is missing.", code="solution_not_found")
        return solution.umbrella_id
    if target.target_type == "umbrella":
        return target.target_id
    solution = await solutions_repo.get(session, target.target_id)
    if solution is None:
        raise NotFound("That comment's solution is missing.", code="solution_not_found")
    return solution.umbrella_id


async def umbrella_of_target(session: AsyncSession, target_type: str, target) -> int:
    return await _umbrella_of(session, target_type, target)
