"""Workshop votes (DEMOCRACY.md §4.4)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import SessionDep, VerifiedUser
from backend.services import votes as votes_service

router = APIRouter(prefix="/votes", tags=["votes"])


class VoteIn(BaseModel):
    target_type: str = Field(pattern="^(solution|amendment|comment)$")
    target_id: int
    direction: int = Field(description="1 for up, -1 for down")


@router.put("")
async def cast_vote(body: VoteIn, user: VerifiedUser, session: SessionDep) -> dict:
    return await votes_service.cast(
        session,
        user=user,
        target_type=body.target_type,
        target_id=body.target_id,
        direction=body.direction,
    )


class VoteRemoveIn(BaseModel):
    target_type: str = Field(pattern="^(solution|amendment|comment)$")
    target_id: int


@router.delete("")
async def remove_vote(
    body: VoteRemoveIn, user: VerifiedUser, session: SessionDep
) -> dict:
    return await votes_service.withdraw(
        session, user=user, target_type=body.target_type, target_id=body.target_id
    )
