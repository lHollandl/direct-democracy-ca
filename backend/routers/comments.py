"""Threaded discussion (DEMOCRACY.md §6)."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend.deps import SessionDep, VerifiedUser
from backend.services import comments as comments_service

router = APIRouter(prefix="/comments", tags=["comments"])


class CommentIn(BaseModel):
    target_type: str = Field(pattern="^(umbrella|solution)$")
    target_id: int
    parent_id: int | None = None
    text: str = Field(min_length=1, max_length=2000)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CommentIn, user: VerifiedUser, session: SessionDep
) -> dict:
    comment = await comments_service.create(
        session,
        author=user,
        target_type=body.target_type,
        target_id=body.target_id,
        parent_id=body.parent_id,
        text=body.text,
    )
    return {"id": comment.id, "depth": comment.depth, "message": "Posted."}


class CommentEditIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.patch("/{comment_id}")
async def edit_comment(
    comment_id: int, body: CommentEditIn, user: VerifiedUser, session: SessionDep
) -> dict:
    comment = await comments_service.require_comment(session, comment_id)
    await comments_service.edit(session, comment=comment, user=user, text=body.text)
    return {"id": comment.id, "message": "Edited.", "edited": True}


@router.delete("/{comment_id}")
async def remove_comment(
    comment_id: int, user: VerifiedUser, session: SessionDep
) -> dict:
    comment = await comments_service.require_comment(session, comment_id)
    await comments_service.remove(session, comment=comment, user=user)
    return {
        "id": comment.id,
        "message": (
            "Removed. The comment stays in place so the replies beneath it still "
            "make sense, with its text replaced."
        ),
    }
