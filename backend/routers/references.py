"""Useful / Not useful on a reference (DEMOCRACY.md §9.4).

The URL keeps the word "references"; the table is `umbrella_references`,
because `references` is a PostgreSQL reserved word (DATABASE.md §1).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import SessionDep, VerifiedUser, require_member
from backend.services import references as references_service

router = APIRouter(prefix="/references", tags=["references"])


class FeedbackIn(BaseModel):
    useful: bool


@router.put("/{reference_id}/feedback")
async def reference_feedback(
    reference_id: int, body: FeedbackIn, user: VerifiedUser, session: SessionDep
) -> dict:
    reference = await references_service.require_reference(session, reference_id)
    community = await references_service.community_of_reference(session, reference)
    if community is not None:
        await require_member(session, user, *community)
    return await references_service.feedback(
        session, reference=reference, user=user, useful=body.useful
    )
