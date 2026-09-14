"""Solutions: the full view, the author's edit window, the version history."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import OptionalUser, SessionDep, VerifiedUser
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import ai_log
from backend.services import amendments as amendments_service
from backend.services import comments as comments_service
from backend.services import community as community_service
from backend.services import rules
from backend.services import settings as settings_service
from backend.services import similarity as similarity_service
from backend.services import solutions as solutions_service
from backend.services.display import author_displays

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.get("/{solution_id}")
async def get_solution(solution_id: int, session: SessionDep, viewer: OptionalUser) -> dict:
    solution = await solutions_service.require_solution(session, solution_id)
    umbrella = await umbrellas_repo.get(session, solution.umbrella_id)
    versions = await solutions_repo.versions(session, solution.id)
    displays = await author_displays(
        session, [solution.author_id] + [v.created_by for v in versions]
    )
    values = await settings_service.all_values(session)
    active_users = await community_service.active_user_count(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    my_vote = (
        (await votes_repo.user_votes_on(session, viewer.id, "solution", [solution.id])).get(
            solution.id
        )
        if viewer
        else None
    )
    amendments = await solutions_repo.amendments_for(session, solution.id)
    amendment_displays = await author_displays(session, [a.author_id for a in amendments])
    current = versions[-1].text_body if versions else ""
    community = await community_service.resolve(
        session, umbrella.community_level, umbrella.community_entity_id
    )

    return {
        "id": solution.id,
        "umbrella": {"id": umbrella.id, "name": umbrella.name},
        "community": community.as_dict(),
        "text": current,
        "current_version": solution.current_version,
        "author": displays.get(solution.author_id, "Former Community Member"),
        "net_score": solution.net_score,
        "my_vote": my_vote,
        "supporters": await solutions_repo.supporters(session, solution.id),
        "is_dominant": solution.is_dominant,
        "dominant_since": solution.dominant_since,
        "dominant_threshold": rules.dominant_threshold(
            dominant_pct=values["dominant_pct"],
            dominant_min=values["dominant_min"],
            active_users=active_users,
        ),
        "ballot_threshold": rules.ballot_threshold(
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
        "absorption_threshold": await amendments_service.absorption_threshold_for(
            session, solution.id
        ),
        "on_track_for_ballot": rules.on_track_for_ballot(
            is_dominant_now=solution.is_dominant,
            net_score_value=solution.net_score,
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            active_users=active_users,
        ),
        "last_ballot_result": solution.last_ballot_result,
        "last_ballot_version": solution.last_ballot_version,
        "return_rule_note": (
            "A solution that has been on a ballot — passed, failed or held back — "
            "returns only once it has a newer version. The way back is an amendment."
        ),
        "ownership_note": (
            "Solutions belong to the community once posted. The author is recorded "
            "and shown; changes happen through amendments."
        ),
        "versions": [
            {
                "version": v.version,
                "text": v.text_body,
                "written_by": displays.get(v.created_by, "Former Community Member"),
                "from_amendment_id": v.amendment_id,
                "content_hash": v.content_hash,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "amendments": [
            {
                "id": a.id,
                "author": amendment_displays.get(a.author_id, "Former Community Member"),
                "proposed_text": a.proposed_text,
                "rationale": a.rationale,
                "status": a.status,
                "base_version": a.base_version,
                "absorbed_as_version": a.absorbed_as_version,
                "merged_into_id": a.merged_into_id,
                "net_score": a.net_score,
                "diff": amendments_service.diff(current, a.proposed_text),
                "content_hash": a.content_hash,
                "created_at": a.created_at,
            }
            for a in amendments
        ],
        "similar_pairs": await similarity_service.pairs_for_solution(session, solution.id),
        "discussion": (
            await comments_service.thread(
                session,
                target_type="solution",
                target_id=solution.id,
                viewer_id=viewer.id if viewer else None,
            )
            if solution.is_dominant
            else []
        ),
        "discussion_note": (
            None
            if solution.is_dominant
            else "Discussion opens when a solution becomes dominant."
        ),
        "ai_influence": ai_log.influence(
            versions[-1].ai_contribution_percentage if versions else 0
        ),
    }


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
