import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class GovernanceLevel(enum.Enum):
    city = "city"
    county = "county"
    state = "state"
    federal = "federal"


class VoteType(enum.Enum):
    upvote = "upvote"
    downvote = "downvote"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    influence_score = Column(Integer, default=0)
    political_party = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    posts = relationship("Post", back_populates="author")
    votes = relationship("Vote", back_populates="user")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(String(5000), nullable=False)
    governance_level = Column(Enum(GovernanceLevel), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Constitution law: every post records how much AI contributed to its content
    ai_contribution_percentage = Column(Integer, default=0)
    ai_model_used = Column(String, nullable=True)
    # Constitution law: content_hash is permanent public record — never modified after creation
    content_hash = Column(String, nullable=True)

    author = relationship("User", back_populates="posts")
    labels = relationship("Label", back_populates="post")
    votes = relationship("Vote", back_populates="post")


class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    # Free text, not an enum — AI can generate any category (Housing, Traffic, etc.)
    # without requiring a database migration as the platform grows
    category = Column(String, nullable=False)
    subcategory = Column(String, nullable=True)
    # How confident the AI was (0-100) — low scores prompt users to confirm the label
    confidence_score = Column(Integer, default=0)
    created_by_ai = Column(Boolean, default=True)
    confirmed_by_user = Column(Boolean, default=False)
    # Records what the user changed the label to — becomes AI training data over time
    user_correction = Column(String, nullable=True)

    post = relationship("Post", back_populates="labels")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    vote_type = Column(Enum(VoteType), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # One vote per user per post — enforced at the database level
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_vote_user_post"),)

    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes")


class UmbrellaIssue(Base):
    __tablename__ = "umbrella_issues"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    governance_level = Column(Enum(GovernanceLevel), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    upvote_count = Column(Integer, default=0)
