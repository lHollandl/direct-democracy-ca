import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from database import get_db
from limiter import limiter
from models import Label, Post, User, Vote

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    date_of_birth: date
    agreed_to_terms: bool
    agreed_to_terms_version: str
    political_party: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    influence_score: int
    political_party: str | None
    is_active: bool
    date_of_birth: date
    agreed_to_terms_at: datetime
    agreed_to_terms_version: str

    model_config = {"from_attributes": True}


@router.post("/users", response_model=UserResponse)
@limiter.limit("5/minute")
async def create_user(
    request: Request, user_data: UserCreate, db: Session = Depends(get_db)
):
    if not user_data.agreed_to_terms:
        raise HTTPException(
            status_code=400,
            detail="You must agree to the terms of service to register",
        )

    # COPPA compliance: reject users under 13
    today = date.today()
    age = today.year - user_data.date_of_birth.year - (
        (today.month, today.day) < (user_data.date_of_birth.month, user_data.date_of_birth.day)
    )
    if age < 13:
        raise HTTPException(
            status_code=400,
            detail="You must be at least 13 years old to register (COPPA compliance)",
        )

    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=pwd_context.hash(user_data.password),
        date_of_birth=user_data.date_of_birth,
        agreed_to_terms_at=datetime.now(timezone.utc),
        agreed_to_terms_version=user_data.agreed_to_terms_version,
        political_party=user_data.political_party,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{user_id}/export")
async def export_user_data(user_id: int, db: Session = Depends(get_db)):
    """
    CCPA data export — returns everything the platform holds about this user.
    Also records the timestamp of the export request for compliance tracking.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    posts = db.query(Post).filter(Post.user_id == user_id).all()
    votes = db.query(Vote).filter(Vote.user_id == user_id).all()

    post_ids = [p.id for p in posts]
    # Include labels on the user's posts so they can see AI labels and their own corrections
    labels = db.query(Label).filter(Label.post_id.in_(post_ids)).all() if post_ids else []

    # Record that export was requested — satisfies legal compliance tracking
    user.data_export_requested_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "date_of_birth": user.date_of_birth.isoformat(),
            "created_at": user.created_at.isoformat(),
            "influence_score": user.influence_score,
            "political_party": user.political_party,
            "agreed_to_terms_at": user.agreed_to_terms_at.isoformat(),
            "agreed_to_terms_version": user.agreed_to_terms_version,
            "data_export_requested_at": user.data_export_requested_at.isoformat(),
        },
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "content": p.content,
                "governance_level": p.governance_level.value,
                "created_at": p.created_at.isoformat(),
                "ai_contribution_percentage": p.ai_contribution_percentage,
                "content_hash": p.content_hash,
            }
            for p in posts
        ],
        "votes": [
            {
                "post_id": v.post_id,
                "vote_type": v.vote_type.value,
                "created_at": v.created_at.isoformat(),
            }
            for v in votes
        ],
        "label_corrections": [
            {
                "label_id": label.id,
                "post_id": label.post_id,
                "original_category": label.category,
                "user_correction": label.user_correction,
            }
            for label in labels
            if label.confirmed_by_user and label.user_correction
        ],
    }
