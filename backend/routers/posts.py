import os
import re
import sys
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from limiter import limiter
from models import Label, LocationType, Post, PostLocation, Solution, User, Vote

# The ai/ directory lives at the repo root, one level above backend/.
# Add the repo root to sys.path so the labeler can be imported from there.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from ai.labeler import label_and_assign_post

router = APIRouter()


def strip_html(text: str) -> str:
    """Remove HTML tags from user input to prevent stored XSS in civic posts."""
    return re.sub(r"<[^>]+>", "", text)


class LocationInput(BaseModel):
    location_type: LocationType
    # None is valid for federal — federal posts have no specific geographic entity
    location_id: int | None = None


class LocationResponse(BaseModel):
    id: int
    location_type: LocationType
    location_id: int | None

    model_config = {"from_attributes": True}


class SolutionSummary(BaseModel):
    id: int
    title: str
    content: str
    upvote_count: int
    ai_contribution_percentage: int
    content_hash: str | None

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    # user_id is NOT accepted from the client — it is set from the authenticated user's token.
    # This prevents users from posting as someone else.
    title: str
    content: str
    # Citizens must propose a solution alongside every problem they report
    solution_title: str
    solution_content: str
    locations: list[LocationInput]
    ai_contribution_percentage: int = 0
    ai_model_used: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = strip_html(v.strip())
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 200:
            raise ValueError("Title must be 200 characters or fewer")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = strip_html(v.strip())
        if not v:
            raise ValueError("Content cannot be empty")
        if len(v) > 5000:
            raise ValueError("Content must be 5000 characters or fewer")
        return v

    @field_validator("solution_title")
    @classmethod
    def validate_solution_title(cls, v: str) -> str:
        v = strip_html(v.strip())
        if not v:
            raise ValueError("Please propose a solution to the problem you are reporting")
        if len(v) > 200:
            raise ValueError("Solution title must be 200 characters or fewer")
        return v

    @field_validator("solution_content")
    @classmethod
    def validate_solution_content(cls, v: str) -> str:
        v = strip_html(v.strip())
        if not v:
            raise ValueError("Please propose a solution to the problem you are reporting")
        if len(v) > 5000:
            raise ValueError("Solution content must be 5000 characters or fewer")
        return v

    @field_validator("locations")
    @classmethod
    def validate_locations(cls, v: list[LocationInput]) -> list[LocationInput]:
        if not v:
            raise ValueError("Please select at least one governance level for your post")
        return v

    @field_validator("ai_contribution_percentage")
    @classmethod
    def validate_ai_percentage(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("ai_contribution_percentage must be between 0 and 100")
        return v


class PostResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    created_at: datetime
    ai_contribution_percentage: int
    ai_model_used: str | None
    content_hash: str | None
    label_count: int = 0
    vote_count: int = 0
    locations: list[LocationResponse] = []
    solution: SolutionSummary | None = None

    model_config = {"from_attributes": True}


@router.post("/posts", response_model=PostResponse, status_code=201)
@limiter.limit("10/minute")
async def create_post(
    request: Request,
    post_data: PostCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = Post(
        user_id=current_user.id,
        title=post_data.title,
        content=post_data.content,
        ai_contribution_percentage=post_data.ai_contribution_percentage,
        ai_model_used=post_data.ai_model_used,
    )
    db.add(post)
    # flush to get post.id before creating dependent rows
    db.flush()

    for loc in post_data.locations:
        db.add(PostLocation(
            post_id=post.id,
            location_type=loc.location_type,
            location_id=loc.location_id,
        ))

    # Every post must have a solution — citizens propose what they want done
    db.add(Solution(
        post_id=post.id,
        user_id=current_user.id,
        title=post_data.solution_title,
        content=post_data.solution_content,
        ai_contribution_percentage=post_data.ai_contribution_percentage,
    ))

    db.commit()
    db.refresh(post)
    post.label_count = 0
    post.vote_count = 0

    # Convert locations to plain dicts — the labeler runs as a background task
    # after this request's db session is closed, so it manages its own session.
    # Constitution law: users never wait for AI. The response goes out immediately.
    location_dicts = [
        {"location_type": loc.location_type.value, "location_id": loc.location_id}
        for loc in post_data.locations
    ]
    background_tasks.add_task(
        label_and_assign_post,
        post.id,
        post.title,
        post.content,
        location_dicts,
    )

    return post


@router.get("/posts", response_model=list[PostResponse])
async def get_posts(
    location_type: LocationType | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            Post,
            func.count(Label.id.distinct()).label("label_count"),
            func.count(Vote.id.distinct()).label("vote_count"),
        )
        .outerjoin(Label, Label.post_id == Post.id)
        .outerjoin(Vote, Vote.post_id == Post.id)
    )

    if location_type is not None or location_id is not None:
        # Inner join so we only return posts that have a matching location row
        query = query.join(PostLocation, PostLocation.post_id == Post.id)
        if location_type is not None:
            query = query.filter(PostLocation.location_type == location_type)
        if location_id is not None:
            query = query.filter(PostLocation.location_id == location_id)

    results = (
        query
        .group_by(Post.id)
        .order_by(Post.created_at.desc())
        .all()
    )

    posts = []
    for post, label_count, vote_count in results:
        post.label_count = label_count
        post.vote_count = vote_count
        posts.append(post)
    return posts


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Session = Depends(get_db)):
    result = (
        db.query(
            Post,
            func.count(Label.id.distinct()).label("label_count"),
            func.count(Vote.id.distinct()).label("vote_count"),
        )
        .outerjoin(Label, Label.post_id == Post.id)
        .outerjoin(Vote, Vote.post_id == Post.id)
        .filter(Post.id == post_id)
        .group_by(Post.id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Post not found")

    post, label_count, vote_count = result
    post.label_count = label_count
    post.vote_count = vote_count
    # post.locations and post.solution are lazy-loaded from relationships
    return post
