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


_VALID_GOVERNANCE_LEVELS = {"city", "county", "state", "federal"}


class SolutionInput(BaseModel):
    """One solution proposed by the user, targeting specific governance levels."""
    content: str
    # Which tiers of government this solution is directed at
    governance_levels: list[str]

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = strip_html(v.strip())
        if not v:
            raise ValueError("Solution content cannot be empty")
        if len(v) > 5000:
            raise ValueError("Solution content must be 5000 characters or fewer")
        return v

    @field_validator("governance_levels")
    @classmethod
    def validate_governance_levels(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Each solution must target at least one governance level")
        invalid = set(v) - _VALID_GOVERNANCE_LEVELS
        if invalid:
            raise ValueError(
                f"Invalid governance levels: {invalid}. "
                "Valid values are: city, county, state, federal"
            )
        return v


class SolutionSummary(BaseModel):
    id: int
    # title is deprecated — nullable since migration 9ad861d88d23
    title: str | None
    content: str
    governance_levels: list[str] | None
    upvote_count: int
    ai_contribution_percentage: int
    content_hash: str | None

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    # user_id is NOT accepted from the client — it is set from the authenticated user's token.
    # This prevents users from posting as someone else.
    title: str
    content: str
    # Citizens must propose at least one solution alongside every problem they report.
    # Replaces the old single solution_title + solution_content fields.
    solutions: list[SolutionInput]
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

    @field_validator("solutions")
    @classmethod
    def validate_solutions(cls, v: list[SolutionInput]) -> list[SolutionInput]:
        if not v:
            raise ValueError("Please propose at least one solution to the problem you are reporting")
        return v

    @field_validator("locations")
    @classmethod
    def validate_locations(cls, v: list[LocationInput]) -> list[LocationInput]:
        if not v:
            raise ValueError("Please select at least one governance level for your post")
        return v

    # Set when the user manually picks a category instead of letting the AI decide.
    # The frontend restricts choices to MAIN_CATEGORIES, but we store any stripped
    # string here so the category list can evolve without requiring backend changes.
    manual_category: str | None = None

    @field_validator("manual_category")
    @classmethod
    def validate_manual_category(cls, v: str | None) -> str | None:
        if v is not None:
            v = strip_html(v.strip())
            if not v:
                return None
            if len(v) > 100:
                raise ValueError("Category name must be 100 characters or fewer")
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
    # username is not a column on Post — it is set as a transient attribute
    # on the ORM object by each route handler before serialisation.
    username: str
    title: str
    content: str
    created_at: datetime
    ai_contribution_percentage: int
    ai_model_used: str | None
    content_hash: str | None
    label_count: int = 0
    vote_count: int = 0
    locations: list[LocationResponse] = []
    solutions: list[SolutionSummary] = []

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

    # Create one Solution row per submitted solution.
    # title is set to "" (not None) for backward compatibility — the column is deprecated
    # but still nullable=True; existing reads that expect a string get an empty string.
    for sol in post_data.solutions:
        db.add(Solution(
            post_id=post.id,
            user_id=current_user.id,
            title="",
            content=sol.content,
            governance_levels=sol.governance_levels,
            ai_contribution_percentage=post_data.ai_contribution_percentage,
        ))

    # If the user manually selected a category, record it as a confirmed label.
    # Constitution §5: AI suggestions are advisory — a human's explicit choice
    # is treated as confirmed immediately with full confidence.
    if post_data.manual_category:
        db.add(Label(
            post_id=post.id,
            category=post_data.manual_category,
            confidence_score=100,
            created_by_ai=False,
            confirmed_by_user=True,
        ))

    db.commit()
    db.refresh(post)
    post.label_count = 0
    post.vote_count = 0
    post.username = current_user.username

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
        post.username = post.author.username
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
    post.username = post.author.username
    # post.locations and post.solution are lazy-loaded from relationships
    return post
