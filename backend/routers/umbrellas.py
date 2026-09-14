"""The umbrella page — the workshop (DEMOCRACY.md §3.3)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from backend.deps import OptionalUser, SessionDep, VerifiedUser, require_member
from backend.services import comments as comments_service
from backend.services import community as community_service
from backend.services import references as references_service
from backend.services import rules
from backend.services import settings as settings_service
from backend.services import solutions as solutions_service
from backend.services import umbrellas as umbrellas_service

router = APIRouter(prefix="/umbrellas", tags=["umbrellas"])


@router.get("")
async def list_umbrellas(
    session: SessionDep,
    community: str = Query(description="level:entity_id, e.g. city:42"),
) -> dict:
    level, _, raw_id = community.partition(":")
    return await umbrellas_service.listing(session, level, int(raw_id))


@router.get("/{umbrella_id}")
async def umbrella_page(
    umbrella_id: int, session: SessionDep, viewer: OptionalUser
) -> dict:
    return await umbrellas_service.page(
        session, umbrella_id, viewer.id if viewer else None
    )


@router.get("/{umbrella_id}/solutions")
async def umbrella_solutions(
    umbrella_id: int, session: SessionDep, viewer: OptionalUser
) -> dict:
    umbrella = await solutions_service.require_umbrella(session, umbrella_id)
    active_users = await community_service.active_user_count(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    values = await settings_service.all_values(session)
    return {
        "ordering": {
            "version": rules.SOLUTION_ORDER_VERSION,
            "explanation": rules.SOLUTION_ORDER_EXPLANATION,
        },
        "solutions": await umbrellas_service.solution_list(
            session, umbrella, viewer.id if viewer else None, active_users, values
        ),
    }


@router.get("/{umbrella_id}/comments")
async def umbrella_comments(
    umbrella_id: int, session: SessionDep, viewer: OptionalUser
) -> dict:
    await solutions_service.require_umbrella(session, umbrella_id)
    return {
        "ordering": {
            "version": rules.COMMENT_ORDER_VERSION,
            "explanation": rules.COMMENT_ORDER_EXPLANATION,
        },
        "comments": await comments_service.thread(
            session,
            target_type="umbrella",
            target_id=umbrella_id,
            viewer_id=viewer.id if viewer else None,
        ),
    }


@router.get("/{umbrella_id}/references")
async def umbrella_references(umbrella_id: int, session: SessionDep) -> dict:
    await solutions_service.require_umbrella(session, umbrella_id)
    return await references_service.listing(session, umbrella_id)


class SolutionIn(BaseModel):
    text: str = Field(min_length=20, max_length=5000)


@router.post(
    "/{umbrella_id}/solutions", status_code=status.HTTP_201_CREATED
)
async def add_solution(
    umbrella_id: int, body: SolutionIn, user: VerifiedUser, session: SessionDep
) -> dict:
    umbrella = await solutions_service.require_umbrella(session, umbrella_id)
    await require_member(
        session, user, umbrella.community_level, umbrella.community_entity_id
    )
    solution = await solutions_service.create_on_umbrella(
        session, umbrella=umbrella, author=user, text=body.text
    )
    return {
        "id": solution.id,
        "message": (
            "Posted. It belongs to the community now: anyone here can propose a "
            "change to it once it becomes dominant."
        ),
    }


class ReferenceIn(BaseModel):
    url: str
    title: str = ""
    note: str = Field(min_length=1, max_length=300)


@router.post("/{umbrella_id}/references", status_code=status.HTTP_201_CREATED)
async def add_reference(
    umbrella_id: int, body: ReferenceIn, user: VerifiedUser, session: SessionDep
) -> dict:
    umbrella = await solutions_service.require_umbrella(session, umbrella_id)
    await require_member(
        session, user, umbrella.community_level, umbrella.community_entity_id
    )
    row = await references_service.add_user_reference(
        session, umbrella=umbrella, user=user, url=body.url, title=body.title, note=body.note
    )
    return {"id": row.id, "message": "Added."}
