"""Amendments and the similarity decision (DEMOCRACY.md §5)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, Field

from backend.deps import SessionDep, VerifiedUser, require_member
from backend.errors import NotFound
from backend.jobs import similarity as similarity_job
from backend.repositories import solutions as solutions_repo
from backend.routers.common import Message
from backend.services import amendments as amendments_service
from backend.services import similarity as similarity_service
from backend.services import solutions as solutions_service
from backend.services.display import author_displays

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
    background: BackgroundTasks,
) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    level, entity_id = await _community_of_solution(session, solution)
    await require_member(session, user, level, entity_id)
    amendment = await amendments_service.propose(
        session,
        solution=solution,
        author=user,
        text=body.proposed_text,
        rationale=body.rationale,
    )
    amendment_id = amendment.id
    background.add_task(similarity_job.similarity_check_task, amendment_id)
    return {
        "id": amendment_id,
        "message": (
            "Proposed. It becomes the solution's text once enough of the people "
            "who support that solution back your change."
        ),
        "absorption_threshold": await amendments_service.absorption_threshold_for(
            session, solution.id
        ),
    }


@router.get("/solutions/{solution_id}/amendments")
async def list_amendments(solution_id: int, session: SessionDep) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    rows = await solutions_repo.amendments_for(session, solution.id)
    displays = await author_displays(session, [a.author_id for a in rows])
    current = await solutions_repo.current_version(session, solution.id)
    text = current.text_body if current else ""
    return {
        "solution_id": solution.id,
        "current_version": solution.current_version,
        "absorption_threshold": await amendments_service.absorption_threshold_for(
            session, solution.id
        ),
        "supporters": await solutions_repo.supporters(session, solution.id),
        "amendments": [
            {
                "id": a.id,
                "author": displays.get(a.author_id, "Former Community Member"),
                "proposed_text": a.proposed_text,
                "rationale": a.rationale,
                "status": a.status,
                "base_version": a.base_version,
                "absorbed_as_version": a.absorbed_as_version,
                "merged_into_id": a.merged_into_id,
                "net_score": a.net_score,
                "diff": amendments_service.diff(text, a.proposed_text),
                "created_at": a.created_at,
            }
            for a in rows
        ],
        "similar_pairs": await similarity_service.pairs_for_solution(session, solution.id),
    }


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
    similarity = await solutions_repo.get_similarity(session, similarity_id)
    if similarity is None:
        raise NotFound("That flagged pair does not exist.", code="similarity_not_found")
    amendment = await solutions_repo.get_amendment(session, similarity.amendment_a_id)
    if amendment is None:
        raise NotFound("That amendment no longer exists.", code="amendment_not_found")
    level, entity_id = await amendments_service.community_of(session, amendment)
    await require_member(session, user, level, entity_id)
    return await similarity_service.decide(
        session, similarity=similarity, user=user, choice=body.choice
    )


async def _community_of_solution(session, solution) -> tuple[str, int]:
    from backend.repositories import umbrellas as umbrellas_repo

    umbrella = await umbrellas_repo.get(session, solution.umbrella_id)
    if umbrella is None:
        raise NotFound("That solution's umbrella is missing.", code="umbrella_not_found")
    return umbrella.community_level, umbrella.community_entity_id
