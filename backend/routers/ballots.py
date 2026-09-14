"""Cycles and the ballot (DEMOCRACY.md §10)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import OptionalUser, SessionDep, VerifiedUser
from backend.repositories import cycles as cycles_repo
from backend.services import ballots as ballots_service
from backend.services import community as community_service
from backend.services import cycles as cycles_service

router = APIRouter(tags=["ballot"])


@router.get("/communities/{level}/{entity_id}/cycles")
async def community_cycles(level: str, entity_id: int, session: SessionDep) -> dict:
    community = await community_service.resolve(session, level, entity_id)
    rows = await cycles_repo.for_community(session, level, entity_id)
    return {
        "community": community.as_dict(),
        "cycles": [
            {
                "id": c.id,
                "number": c.number,
                "state": c.state,
                "prepared_at": c.prepared_at,
                "opened_at": c.opened_at,
                "closed_at": c.closed_at,
                "published_at": c.published_at,
            }
            for c in rows
        ],
    }


@router.get("/cycles/{cycle_id}")
async def get_cycle(cycle_id: int, session: SessionDep) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    return await cycles_service.view(session, cycle)


@router.get("/cycles/{cycle_id}/ballot")
async def get_ballot(cycle_id: int, session: SessionDep, viewer: OptionalUser) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    return await ballots_service.ballot_view(session, cycle=cycle, viewer=viewer)


class BallotVoteIn(BaseModel):
    choice: str = Field(pattern="^(yes|no)$")


@router.put("/cycles/{cycle_id}/ballot/{item_id}/vote")
async def cast_ballot_vote(
    cycle_id: int,
    item_id: int,
    body: BallotVoteIn,
    user: VerifiedUser,
    session: SessionDep,
) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    return await ballots_service.cast(
        session, cycle=cycle, item_id=item_id, voter=user, choice=body.choice
    )
