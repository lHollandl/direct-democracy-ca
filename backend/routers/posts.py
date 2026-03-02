import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from limiter import limiter
from models import GovernanceLevel, Label, Post, Vote

router = APIRouter()


def strip_html(text: str) -> str:
    """Remove HTML tags from user input to prevent stored XSS in civic posts."""
    return re.sub(r"<[^>]+>", "", text)


class PostCreate(BaseModel):
    user_id: int
    title: str
    content: str
    governance_level: GovernanceLevel
    # Constitution law: ai_contribution_percentage is required on every post
    ai_contribution_percentage: int
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
    governance_level: GovernanceLevel
    created_at: datetime
    ai_contribution_percentage: int
    ai_model_used: str | None
    content_hash: str | None
    label_count: int = 0
    vote_count: int = 0

    model_config = {"from_attributes": True}


@router.post("/posts", response_model=PostResponse)
@limiter.limit("10/minute")
async def create_post(
    request: Request, post_data: PostCreate, db: Session = Depends(get_db)
):
    post = Post(
        user_id=post_data.user_id,
        title=post_data.title,
        content=post_data.content,
        governance_level=post_data.governance_level,
        ai_contribution_percentage=post_data.ai_contribution_percentage,
        ai_model_used=post_data.ai_model_used,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    # Fresh post starts at zero for both counts
    post.label_count = 0
    post.vote_count = 0
    return post


@router.get("/posts", response_model=list[PostResponse])
async def get_posts(db: Session = Depends(get_db)):
    results = (
        db.query(
            Post,
            func.count(Label.id.distinct()).label("label_count"),
            func.count(Vote.id.distinct()).label("vote_count"),
        )
        .outerjoin(Label, Label.post_id == Post.id)
        .outerjoin(Vote, Vote.post_id == Post.id)
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
    return post
