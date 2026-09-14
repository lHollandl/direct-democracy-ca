"""Posts and labels (ARCHITECTURE.md §6, Iteration)."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import CurrentUser, SessionDep, VerifiedUser
from backend.jobs import labeling as labeling_job
from backend.jobs import runner
from backend.routers.common import Message
from backend.services import posts as posts_service

router = APIRouter(prefix="/posts", tags=["posts"])


class CommunityIn(BaseModel):
    level: str
    entity_id: int
    umbrella_id: int | None = None


class PostIn(BaseModel):
    problem_text: str = Field(min_length=20, max_length=5000)
    solutions: list[str] = Field(min_length=1)
    communities: list[CommunityIn] = Field(min_length=1)
    category_choice: str = Field(pattern="^(ai|author_selected)$")

    @field_validator("solutions")
    @classmethod
    def _not_blank(cls, value: list[str]) -> list[str]:
        if not any(v.strip() for v in value):
            raise ValueError("every post needs at least one proposed solution")
        return value


class PostCreatedOut(BaseModel):
    id: int
    label_status: str
    message: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostCreatedOut)
async def create_post(
    body: PostIn, user: VerifiedUser, session: SessionDep
) -> PostCreatedOut:
    post = await posts_service.create(
        session,
        author=user,
        problem_text=body.problem_text,
        solution_texts=body.solutions,
        communities=[(c.level, c.entity_id) for c in body.communities],
        category_choice=body.category_choice,
        chosen_umbrellas={
            (c.level, c.entity_id): c.umbrella_id
            for c in body.communities
            if c.umbrella_id is not None
        },
    )
    post_id = post.id
    label_status = post.label_status
    if body.category_choice == "ai":
        # Labeling runs after the post commits (ARCHITECTURE.md §7). The job is
        # its own task, not tied to this response, so closing the tab does not
        # cancel the filing.
        runner.spawn_after_commit(
            session,
            lambda: labeling_job.label_post_task(post_id),
            name=f"label_post:{post_id}",
        )
    return PostCreatedOut(
        id=post_id,
        label_status=label_status,
        message=(
            "Posted. It is being filed into an umbrella now — that usually takes a "
            "moment. You can confirm or correct where it lands."
            if label_status == "pending"
            else "Posted and filed."
        ),
    )


@router.get("/{post_id}")
async def get_post(post_id: int, session: SessionDep) -> dict:
    post = await posts_service.require_post(session, post_id)
    return await posts_service.view(session, post)


class CorrectIn(BaseModel):
    level: str
    entity_id: int
    umbrella_id: int


@router.post("/{post_id}/label/confirm", response_model=Message)
async def confirm_label(post_id: int, user: CurrentUser, session: SessionDep) -> Message:
    post = await posts_service.require_post(session, post_id)
    result = await posts_service.confirm_label(session, post=post, user=user)
    return Message(
        message=(
            f"Thank you — {result['confirmed']} filing"
            f"{'s' if result['confirmed'] != 1 else ''} confirmed. "
            "That is recorded in the public AI log."
        )
    )


@router.post("/{post_id}/label/correct")
async def correct_label(
    post_id: int, body: CorrectIn, user: CurrentUser, session: SessionDep
) -> dict:
    post = await posts_service.require_post(session, post_id)
    return await posts_service.correct_label(
        session,
        post=post,
        user=user,
        level=body.level,
        entity_id=body.entity_id,
        umbrella_id=body.umbrella_id,
    )
