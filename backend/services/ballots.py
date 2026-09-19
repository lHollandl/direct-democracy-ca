"""Voting on a ballot (DEMOCRACY.md §10.3).

Yes or no, one vote per member per item, changeable until the ballot closes.
Every vote row records the voter's verification level at the time of voting —
recorded and reported in totals, never used to weight the vote (CLAUDE.md §3).

**A ballot vote row is exposed to exactly one person: the voter who cast it.**
Everything else anyone can ask for is counts.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound
from backend.models import Cycle, User
from backend.repositories import cycles as cycles_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import community as community_service
from backend.services import rules

log = logging.getLogger(__name__)


async def ballot_view(session: AsyncSession, *, cycle: Cycle, viewer: User | None) -> dict:
    """Items in `position` order with their frozen text. The caller's own votes
    are included, and nobody else's ever are."""
    items = await cycles_repo.items(session, cycle.id)
    umbrellas = await umbrellas_repo.by_ids(session, [i.umbrella_id for i in items])
    community = await community_service.resolve(
        session, cycle.community_level, cycle.community_entity_id
    )
    my_votes = (
        await cycles_repo.my_ballot_votes(session, viewer.id, [i.id for i in items])
        if viewer
        else {}
    )
    can_vote = bool(
        viewer
        and cycle.state == "open"
        and await community_service.is_member(
            session, viewer, cycle.community_level, cycle.community_entity_id
        )
    )

    shaped = []
    for item in items:
        version = await solutions_repo.version_at(
            session, item.solution_id, item.solution_version
        )
        shaped.append(
            {
                "ballot_item_id": item.id,
                "position": item.position,
                "umbrella": umbrellas[item.umbrella_id].name
                if item.umbrella_id in umbrellas
                else None,
                "solution_id": item.solution_id,
                "frozen_version": item.solution_version,
                "frozen_text": version.text_body if version else "",
                "frozen_hash": version.content_hash if version else None,
                "net_score_at_snapshot": item.net_score_at_snapshot,
                "held_back": item.held_back,
                "votable": (not item.held_back) and cycle.state == "open",
                "my_vote": my_votes.get(item.id),
                "yes_count": item.yes_count,
                "no_count": item.no_count,
                "result": item.result,
            }
        )
    return {
        "cycle_id": cycle.id,
        "cycle_number": cycle.number,
        "state": cycle.state,
        "community": community.as_dict(),
        "you_can_vote": can_vote,
        "ordering": {
            "version": rules.BALLOT_ORDER_VERSION,
            "explanation": rules.BALLOT_ORDER_EXPLANATION,
        },
        "privacy_note": (
            "Your ballot votes are shown to you and to nobody else. Not to other "
            "voters, and not to administrators — they see totals only."
        ),
        "items": shaped,
    }


async def cast(
    session: AsyncSession, *, cycle: Cycle, item_id: int, voter: User, choice: str
) -> dict:
    if cycle.state != "open":
        raise Conflict(
            "That ballot is not open for voting.", code="ballot_not_open"
        )
    if choice not in ("yes", "no"):
        raise Conflict("A ballot vote is yes or no.", code="bad_choice")
    if not await community_service.is_member(
        session, voter, cycle.community_level, cycle.community_entity_id
    ):
        community = await community_service.resolve(
            session, cycle.community_level, cycle.community_entity_id
        )
        raise Forbidden(
            f"You can read this ballot, but only residents of {community.label} vote on it.",
            code="not_a_member",
        )
    item = await cycles_repo.get_item(session, item_id)
    if item is None or item.cycle_id != cycle.id:
        raise NotFound("That item is not on this ballot.", code="ballot_item_not_found")
    if item.held_back:
        raise Conflict(
            "The jury held this one back, so it is not being voted on this cycle.",
            code="item_held_back",
        )

    await cycles_repo.put_ballot_vote(
        session,
        ballot_item_id=item.id,
        voter_id=voter.id,
        choice=choice,
        verification_level=voter.verification_level,
    )
    log.info("ballot_vote_cast", extra={"cycle_id": cycle.id, "ballot_item_id": item.id})
    return {
        "ballot_item_id": item.id,
        "your_vote": choice,
        "note": (
            "You can change this until the ballot closes. Only you can see it."
        ),
    }
