"""Solutions: the full view, the author's edit window, the version history."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import OptionalUser, SessionDep, VerifiedUser
from backend.services import solutions as solutions_service

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.get("/{solution_id}")
async def get_solution(solution_id: int, session: SessionDep, viewer: OptionalUser) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    return await solutions_service.detail_view(session, solution, viewer)


class SolutionEditIn(BaseModel):
    text: str = Field(min_length=20, max_length=5000)


@router.patch("/{solution_id}")
async def edit_solution(
    solution_id: int, body: SolutionEditIn, user: VerifiedUser, session: SessionDep
) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    await solutions_service.edit_text(
        session, solution=solution, editor=user, text=body.text
    )
    return {"id": solution.id, "message": "Updated."}
