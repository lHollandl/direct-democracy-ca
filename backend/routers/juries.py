"""Jury duty (DEMOCRACY.md §8)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import SessionDep, VerifiedUser
from backend.services import juries as juries_service

router = APIRouter(tags=["jury"])


@router.get("/juries/mine")
async def my_duties(user: VerifiedUser, session: SessionDep) -> dict:
    duties = await juries_service.duties_for(session, user)
    return {
        "duties": duties,
        "note": (
            "Jurors are anonymous to the public — the published document says "
            "'Juror 1 of 3' — and the reasons you write are published in full."
        ),
    }


@router.post("/jurors/{juror_id}/accept")
async def accept(juror_id: int, user: VerifiedUser, session: SessionDep) -> dict:
    juror = await juries_service.require_juror(session, juror_id)
    await juries_service.accept(session, juror=juror, user=user)
    return {
        "juror_id": juror.id,
        "status": juror.status,
        "message": (
            "Thank you. You can now look at every solution that qualified and hold "
            "any of them back with a written reason."
        ),
    }


@router.post("/jurors/{juror_id}/decline")
async def decline(juror_id: int, user: VerifiedUser, session: SessionDep) -> dict:
    juror = await juries_service.require_juror(session, juror_id)
    return await juries_service.decline(session, juror=juror, user=user)


class HoldbackIn(BaseModel):
    juror_id: int
    reason_category: str = Field(
        pattern="^(duplicate|not_actionable|incomplete|outside_governance_level|other)$"
    )
    reason_text: str = Field(min_length=20, max_length=1000)


@router.post("/ballot-items/{item_id}/holdback")
async def hold_back(
    item_id: int, body: HoldbackIn, user: VerifiedUser, session: SessionDep
) -> dict:
    juror = await juries_service.require_juror(session, body.juror_id)
    return await juries_service.hold_back(
        session,
        juror=juror,
        user=user,
        ballot_item_id=item_id,
        category=body.reason_category,
        reason_text=body.reason_text,
    )
