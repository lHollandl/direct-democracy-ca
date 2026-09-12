import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# Renamed from GovernanceLevel — now used to tag PostLocation and UmbrellaIssue
# with which tier of government the post or issue is directed at
class LocationType(enum.Enum):
    city = "city"
    county = "county"
    state = "state"
    federal = "federal"


class VoteType(enum.Enum):
    upvote = "upvote"
    downvote = "downvote"


# ---------------------------------------------------------------------------
# Geographic reference tables
# Seeded once with California data; users pick from these when creating posts
# ---------------------------------------------------------------------------

class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    abbreviation = Column(String, nullable=False)

    counties = relationship("County", back_populates="state")


class County(Base):
    __tablename__ = "counties"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)

    state = relationship("State", back_populates="counties")
    cities = relationship("City", back_populates="county")


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    county_id = Column(Integer, ForeignKey("counties.id"), nullable=False)

    county = relationship("County", back_populates="cities")


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

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
    # Required for COPPA compliance — users under 13 cannot register
    date_of_birth = Column(Date, nullable=False)
    # Tracks when user invoked their data export right (User Sovereignty, constitution §6)
    data_export_requested_at = Column(DateTime(timezone=True), nullable=True)
    # Retained after deletion to satisfy legal compliance records; PII is erased separately
    deletion_requested_at = Column(DateTime(timezone=True), nullable=True)
    # Legal consent record — timestamp and version stored so we know exactly what was agreed to
    agreed_to_terms_at = Column(DateTime(timezone=True), nullable=False)
    agreed_to_terms_version = Column(String, nullable=False)
    # Home location — set during signup or profile update.
    # NULL for users who skip location entry or were created before this field existed.
    county_id = Column(Integer, ForeignKey("counties.id"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)

    posts = relationship("Post", back_populates="author")
    votes = relationship("Vote", back_populates="user")
    solutions = relationship("Solution", back_populates="author")
    solution_votes = relationship("SolutionVote", back_populates="user")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(String(5000), nullable=False)
    # governance_level column removed — governance is now handled by PostLocation rows.
    # A post appears in multiple location feeds based on what the user selected at creation.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    # Constitution law: every post records how much AI contributed to its content
    ai_contribution_percentage = Column(Integer, default=0)
    ai_model_used = Column(String, nullable=True)
    # Constitution law: content_hash is permanent public record — never modified after creation
    content_hash = Column(String, nullable=True)

    author = relationship("User", back_populates="posts")
    labels = relationship("Label", back_populates="post")
    votes = relationship("Vote", back_populates="post")
    locations = relationship("PostLocation", back_populates="post")
    umbrella_issues = relationship("PostUmbrellaIssue", back_populates="post")
    # uselist=True — posts now support multiple solutions (one per governance level)
    solutions = relationship("Solution", back_populates="post")


class PostLocation(Base):
    """
    Joins a post to one or more geographic governance levels.
    A post must have at least one PostLocation row — enforced at the application layer
    when creating a post. One post can appear in city, county, and state feeds
    simultaneously if the user chose to direct it at multiple levels.
    location_id references cities.id, counties.id, or states.id depending on
    location_type. It is NULL for federal posts because federal has no specific
    geographic entity in our reference tables.
    """
    __tablename__ = "post_locations"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    location_type = Column(Enum(LocationType), nullable=False)
    # NULL only when location_type is 'federal' — federal has no geographic entity to reference
    location_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Composite index — the most common query is "posts for this city/county/state"
    __table_args__ = (Index("ix_post_locations_type_id", "location_type", "location_id"),)

    post = relationship("Post", back_populates="locations")


class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    vote_type = Column(Enum(VoteType), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # One vote per user per post — enforced at the database level.
    # Individual indexes on user_id and post_id support single-column lookups.
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_vote_user_post"),)

    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes")


class UmbrellaIssue(Base):
    """
    A named civic issue that groups related posts and their solutions under one banner.
    location_type and location_id mirror the same semantics as PostLocation —
    location_id is NULL for federal umbrella issues.
    """
    __tablename__ = "umbrella_issues"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    # Which tier of government this umbrella issue belongs to
    location_type = Column(Enum(LocationType), nullable=False)
    # References cities.id, counties.id, or states.id; NULL for federal
    location_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    upvote_count = Column(Integer, default=0)

    # Composite index — umbrella issues are always fetched by location
    __table_args__ = (Index("ix_umbrella_issues_type_id", "location_type", "location_id"),)

    posts = relationship("PostUmbrellaIssue", back_populates="umbrella_issue")
    solutions = relationship("Solution", back_populates="umbrella_issue")


class PostUmbrellaIssue(Base):
    """Junction table linking posts to umbrella issues."""
    __tablename__ = "post_umbrella_issues"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    umbrella_issue_id = Column(Integer, ForeignKey("umbrella_issues.id"), nullable=False)

    post = relationship("Post", back_populates="umbrella_issues")
    umbrella_issue = relationship("UmbrellaIssue", back_populates="posts")


class Solution(Base):
    """
    Every post must have exactly one Solution — citizens must propose what they want
    done, not just describe a problem. The unique constraint on post_id enforces this
    at the database level.

    umbrella_issue_id starts NULL and is set automatically when the AI labels the post
    and assigns it to an umbrella issue, so the solution appears in that umbrella's
    solution rankings.

    user_id must match the post's user_id — enforced at the application layer.
    """
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True)
    # unique=True removed — posts may now have multiple solutions (one per governance level)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    # Set by AI labeling pipeline after the post is assigned to an umbrella issue
    umbrella_issue_id = Column(Integer, ForeignKey("umbrella_issues.id"), nullable=True, index=True)
    # Must match the post author — enforced at the application layer
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # DEPRECATED — title was the original solution title field, superseded by the
    # post title field. Kept per database law (never delete columns). Do not write
    # to this column in new code; reads may return NULL for solutions created after
    # this deprecation.
    title = Column(String(200), nullable=True)
    content = Column(String(5000), nullable=False)
    # Which governance levels (city, county, state, federal) this solution targets.
    # Stored as a PostgreSQL text array. NULL for solutions created before this
    # field was added (pre-migration).
    governance_levels = Column(ARRAY(String), nullable=True)
    # Indexed — solutions are sorted by upvote_count descending in umbrella panels
    upvote_count = Column(Integer, default=0, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Constitution law: every solution records how much AI contributed to its content
    ai_contribution_percentage = Column(Integer, default=0)
    # Constitution law: content_hash is permanent public record — never modified after creation
    content_hash = Column(String, nullable=True)

    post = relationship("Post", back_populates="solutions")
    umbrella_issue = relationship("UmbrellaIssue", back_populates="solutions")
    author = relationship("User", back_populates="solutions")
    votes = relationship("SolutionVote", back_populates="solution")


class SolutionVote(Base):
    """
    One upvote per user per solution — enforced by the unique constraint.
    Casting a vote also increments solution.upvote_count (denormalized for
    ranking performance) — the application layer keeps these in sync.
    """
    __tablename__ = "solution_votes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # One vote per user per solution — enforced at the database level
    __table_args__ = (UniqueConstraint("user_id", "solution_id", name="uq_solution_vote_user_solution"),)

    user = relationship("User", back_populates="solution_votes")
    solution = relationship("Solution", back_populates="votes")
