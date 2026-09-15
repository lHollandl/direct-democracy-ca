"""Amendments and the similarity decision (DEMOCRACY.md §5)."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend.deps import SessionDep, VerifiedUser
from backend.routers.common import CursorParam, DEFAULT_LIMIT, LimitParam, Message
from backend.services import amendments as amendments_service
from backend.services import similarity as similarity_service
from backend.services import solutions as solutions_service

router = APIRouter(tags=["amendments"])


class AmendmentIn(BaseModel):
    proposed_text: str = Field(min_length=20, max_length=5000)
    rationale: str = Field(min_length=10, max_length=300)


@router.post("/solutions/{solution_id}/amendments", status_code=status.HTTP_201_CREATED)
async def propose_amendment(
    solution_id: int,
    body: AmendmentIn,
    user: VerifiedUser,
    session: SessionDep,
) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    return await amendments_service.propose_as_member(
        session, solution=solution, author=user, text=body.proposed_text, rationale=body.rationale
    )


@router.get("/solutions/{solution_id}/amendments")
async def list_amendments(
    solution_id: int,
    session: SessionDep,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    return await amendments_service.list_for_solution(session, solution, cursor=cursor, limit=limit)


@router.post("/amendments/{amendment_id}/withdraw", response_model=Message)
async def withdraw_amendment(
    amendment_id: int, user: VerifiedUser, session: SessionDep
) -> Message:
    amendment = await amendments_service.require_amendment(session, amendment_id)
    await amendments_service.withdraw(session, amendment=amendment, user=user)
    return Message(message="Withdrawn. It stays on the record, marked withdrawn.")


class DecisionIn(BaseModel):
    choice: str = Field(pattern="^(same|different)$")


@router.post("/similarity/{similarity_id}/decide")
async def decide_similarity(
    similarity_id: int, body: DecisionIn, user: VerifiedUser, session: SessionDep
) -> dict:
    similarity = await similarity_service.require_similarity(session, similarity_id)
    return await similarity_service.decide(
        session, similarity=similarity, user=user, choice=body.choice
    )
