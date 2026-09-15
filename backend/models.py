"""Every table in the platform, grouped by half (DATABASE.md §2).

Foundation tables are permanent from the adoption of CLAUDE.md. Iteration
tables are regenerated fresh for each demo until the director declares a
keeper build.

Conventions (DATABASE.md §1): integer identity primary keys; `created_at`
everywhere; `updated_at` only where rows are mutable; soft delete where
deletion is possible; PostgreSQL enums named `<table>_<column>_enum` except
the two shared enums; every foreign key indexed; SHA-256 hashes as CHAR(64).

Columns are deprecated, never deleted (CLAUDE.md Law 3).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _ts(**kw) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), **kw)


# --------------------------------------------------------------------------
# Shared enums (DATABASE.md §1 — the only two enums used by more than one
# table, named for what they are rather than where they live).
# --------------------------------------------------------------------------

COMMUNITY_LEVELS = ("city", "county", "state", "federal")
VERIFICATION_LEVELS = ("unverified", "phone", "address", "voter")

community_level_enum = SAEnum(
    *COMMUNITY_LEVELS, name="community_level_enum", create_type=False
)
verification_level_enum = SAEnum(
    *VERIFICATION_LEVELS, name="verification_level_enum", create_type=False
)


def _enum(*values: str, name: str) -> SAEnum:
    return SAEnum(*values, name=name, create_type=False)


# ==========================================================================
# FOUNDATION
# ==========================================================================


class User(Base):
    """DATABASE.md §3.1. Personal columns are erased by the anonymization
    procedure; home city and county are kept so the civic record stays in the
    right community (CLAUDE.md §6)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    real_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(
        _enum(
            "woman",
            "man",
            "nonbinary",
            "other",
            "prefer_not_to_say",
            name="users_gender_enum",
        ),
        nullable=False,
    )
    political_party: Mapped[str] = mapped_column(
        _enum(
            "democratic",
            "republican",
            "green",
            "libertarian",
            "american_independent",
            "peace_and_freedom",
            "no_party_preference",
            "other",
            "prefer_not_to_say",
            name="users_political_party_enum",
        ),
        nullable=False,
    )
    county_id: Mapped[int] = mapped_column(
        ForeignKey("counties.id", ondelete="RESTRICT"), nullable=False
    )
    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False
    )
    verification_level: Mapped[str] = mapped_column(
        verification_level_enum, nullable=False, server_default=text("'unverified'")
    )
    email_verified_at: Mapped[datetime | None] = _ts(nullable=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    last_active_at: Mapped[datetime | None] = _ts(nullable=True)
    #: Deprecated until reputation is designed (PROJECT.md parking lot).
    #: No code writes to this column.
    influence_score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = _ts(nullable=True)

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_county_id", "county_id"),
        Index("ix_users_city_id", "city_id"),
        Index("ix_users_last_active_at", "last_active_at"),
        Index("ix_users_county_last_active", "county_id", "last_active_at"),
        Index("ix_users_city_last_active", "city_id", "last_active_at"),
        Index(
            "uq_users_display_name",
            "display_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class UserDisplaySettings(Base):
    """DATABASE.md §3.2. How this user's name appears on everything they write."""

    __tablename__ = "user_display_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    public_name_mode: Mapped[str] = mapped_column(
        _enum(
            "real_name",
            "display_name",
            "anonymous",
            name="user_display_settings_public_name_mode_enum",
        ),
        nullable=False,
        server_default=text("'display_name'"),
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RefreshToken(Base):
    """DATABASE.md §3.3. The raw token never touches the database."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = _ts(nullable=False)
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
        Index("ix_refresh_tokens_replaced_by_id", "replaced_by_id"),
    )


class EmailVerification(Base):
    """DATABASE.md §3.4. Single use; lives `EMAIL_VERIFY_HOURS`."""

    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = _ts(nullable=False)
    used_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_email_verifications_user_id", "user_id"),)


class PasswordReset(Base):
    """DATABASE.md §3.4. Single use; lives `PASSWORD_RESET_MINUTES`."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = _ts(nullable=False)
    used_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_password_resets_user_id", "user_id"),)


class TermsVersion(Base):
    """DATABASE.md §3.5."""

    __tablename__ = "terms_versions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    privacy_policy_md: Mapped[str] = mapped_column(Text, nullable=False)
    terms_of_service_md: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())


class TermsAcceptance(Base):
    """DATABASE.md §3.5. A legal record; never deleted."""

    __tablename__ = "terms_acceptances"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    terms_version_id: Mapped[int] = mapped_column(
        ForeignKey("terms_versions.id"), nullable=False
    )
    accepted_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_terms_acceptances_user_id", "user_id"),
        Index("ix_terms_acceptances_terms_version_id", "terms_version_id"),
    )


class State(Base):
    """DATABASE.md §3.6."""

    __tablename__ = "states"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())


class County(Base):
    """DATABASE.md §3.6."""

    __tablename__ = "counties"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    fips: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_counties_state_id", "state_id"),
        UniqueConstraint("state_id", "name", name="uq_counties_state_id_name"),
    )


class City(Base):
    """DATABASE.md §3.6."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    county_id: Mapped[int] = mapped_column(ForeignKey("counties.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    incorporated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    fips: Mapped[str | None] = mapped_column(String(7), nullable=True, unique=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_cities_county_id", "county_id"),
        UniqueConstraint("county_id", "name", name="uq_cities_county_id_name"),
    )


class Official(Base):
    """DATABASE.md §3.7. Demo 1: every email is `OFFICIALS_TEST_EMAIL`."""

    __tablename__ = "officials"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    community_level: Mapped[str] = mapped_column(community_level_enum, nullable=False)
    community_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    office: Mapped[str] = mapped_column(Text, nullable=False)
    holder_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        _enum("seed", "user_correction", name="officials_source_enum"), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_officials_community", "community_level", "community_entity_id"),
        UniqueConstraint(
            "community_level",
            "community_entity_id",
            "office",
            name="uq_officials_community_office",
        ),
    )


class Setting(Base):
    """DATABASE.md §3.8. Append-only: the value in force at any past moment can
    be read back, which is what CLAUDE.md Law 8 requires."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_settings_key_effective_from", "key", text("effective_from DESC")),
        Index("ix_settings_changed_by", "changed_by"),
    )


class AdminAction(Base):
    """DATABASE.md §3.9. Append-only, public read."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_admin_actions_admin_user_id", "admin_user_id"),
        Index("ix_admin_actions_created_at", "created_at"),
        Index("ix_admin_actions_subject", "subject_type", "subject_id"),
    )


class AiAction(Base):
    """DATABASE.md §3.10 / DEMOCRACY.md §9.2. One row per AI action, written
    before its result is shown (CLAUDE.md Law 7). Only the `human_outcome_*`
    columns are ever updated, once."""

    __tablename__ = "ai_actions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    action_type: Mapped[str] = mapped_column(
        _enum(
            "label", "similarity", "reference_recommend", name="ai_actions_action_type_enum"
        ),
        nullable=False,
    )
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    demo_build: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_file: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    human_outcome: Mapped[str] = mapped_column(
        _enum(
            "unreviewed",
            "confirmed",
            "corrected",
            "accepted",
            "rejected",
            name="ai_actions_human_outcome_enum",
        ),
        nullable=False,
        server_default=text("'unreviewed'"),
    )
    human_outcome_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    human_outcome_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_ai_actions_subject", "subject_type", "subject_id"),
        Index("ix_ai_actions_created_at", "created_at"),
        Index("ix_ai_actions_human_outcome_by", "human_outcome_by"),
    )


class DataExport(Base):
    """DATABASE.md §3.11."""

    __tablename__ = "data_exports"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = _ts(nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = _ts(nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_data_exports_user_id", "user_id"),
        Index("ix_data_exports_expires_at", "expires_at"),
    )


# ==========================================================================
# ITERATION
# ==========================================================================


class MainCategory(Base):
    """DATABASE.md §4.1. Mirror of `backend/config/categories.py` so foreign
    keys exist. Synced at startup: insert missing, never delete, mark inactive."""

    __tablename__ = "main_categories"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())


class Umbrella(Base):
    """DATABASE.md §4.2. A named problem inside a main category, scoped to one
    community. AI never creates one (CLAUDE.md §5)."""

    __tablename__ = "umbrellas"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    main_category_id: Mapped[int] = mapped_column(
        ForeignKey("main_categories.id"), nullable=False
    )
    community_level: Mapped[str] = mapped_column(community_level_enum, nullable=False)
    community_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        _enum("active", "retired", name="umbrellas_status_enum"),
        nullable=False,
        server_default=text("'active'"),
    )
    source: Mapped[str] = mapped_column(
        _enum("seed", "proposal", name="umbrellas_source_enum"), nullable=False
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "community_level",
            "community_entity_id",
            "main_category_id",
            "name",
            name="uq_umbrellas_community_category_name",
        ),
        Index("ix_umbrellas_community", "community_level", "community_entity_id"),
        Index("ix_umbrellas_main_category_id", "main_category_id"),
    )


class Post(Base):
    """DATABASE.md §4.3. Immutable in Demo 1 except `label_status`."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    problem_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_choice: Mapped[str] = mapped_column(
        _enum("ai", "author_selected", name="posts_category_choice_enum"), nullable=False
    )
    label_status: Mapped[str] = mapped_column(
        _enum(
            "pending", "labeled", "needs_review", "unlabeled", name="posts_label_status_enum"
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    ai_contribution_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = _ts(nullable=True)

    __table_args__ = (
        Index("ix_posts_author_id", "author_id"),
        Index("ix_posts_created_at", "created_at"),
        Index("ix_posts_label_status", "label_status"),
    )


class PostSolution(Base):
    """DATABASE.md §4.4. The author's solution texts exactly as submitted; the
    staging record workshop solutions are created from."""

    __tablename__ = "post_solutions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    text_body: Mapped[str] = mapped_column("text", Text, nullable=False)
    ai_contribution_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("post_id", "position", name="uq_post_solutions_post_position"),
        Index("ix_post_solutions_post_id", "post_id"),
    )


class PostCommunity(Base):
    """DATABASE.md §4.5. One row per community the author selected."""

    __tablename__ = "post_communities"

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    community_level: Mapped[str] = mapped_column(community_level_enum, primary_key=True)
    community_entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    umbrella_id: Mapped[int | None] = mapped_column(
        ForeignKey("umbrellas.id"), nullable=True
    )
    main_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("main_categories.id"), nullable=True
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_post_communities_umbrella_id", "umbrella_id"),
        Index("ix_post_communities_main_category_id", "main_category_id"),
        Index("ix_post_communities_community", "community_level", "community_entity_id"),
    )


class Label(Base):
    """DATABASE.md §4.6. One row per labeling attempt per post-community."""

    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    community_level: Mapped[str] = mapped_column(community_level_enum, nullable=False)
    community_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_action_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_actions.id"), nullable=True
    )
    main_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("main_categories.id"), nullable=True
    )
    umbrella_id: Mapped[int | None] = mapped_column(
        ForeignKey("umbrellas.id"), nullable=True
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    outcome: Mapped[str] = mapped_column(
        _enum(
            "unreviewed",
            "confirmed_by_author",
            "corrected_by_author",
            "author_selected",
            name="labels_outcome_enum",
        ),
        nullable=False,
        server_default=text("'unreviewed'"),
    )
    corrected_umbrella_id: Mapped[int | None] = mapped_column(
        ForeignKey("umbrellas.id"), nullable=True
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_labels_post_id", "post_id"),
        Index("ix_labels_ai_action_id", "ai_action_id"),
        Index("ix_labels_umbrella_id", "umbrella_id"),
        Index("ix_labels_main_category_id", "main_category_id"),
        Index("ix_labels_corrected_umbrella_id", "corrected_umbrella_id"),
    )


class Solution(Base):
    """DATABASE.md §4.7. Lives inside exactly one umbrella. Community-owned
    once posted (CLAUDE.md §6)."""

    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    umbrella_id: Mapped[int] = mapped_column(ForeignKey("umbrellas.id"), nullable=False)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    post_solution_id: Mapped[int | None] = mapped_column(
        ForeignKey("post_solutions.id"), nullable=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    #: Cache of the vote rows; the rows are authoritative (DATABASE.md §1).
    net_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: Cache of DEMOCRACY.md §7.1, recomputed on every vote and nightly.
    is_dominant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    dominant_since: Mapped[datetime | None] = _ts(nullable=True)
    last_ballot_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("cycles.id"), nullable=True
    )
    last_ballot_result: Mapped[str | None] = mapped_column(
        _enum("passed", "failed", "held_back", name="solutions_last_ballot_result_enum"),
        nullable=True,
    )
    last_ballot_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = _ts(nullable=True)

    __table_args__ = (
        Index("ix_solutions_umbrella_id", "umbrella_id"),
        Index("ix_solutions_author_id", "author_id"),
        Index("ix_solutions_post_id", "post_id"),
        Index("ix_solutions_post_solution_id", "post_solution_id"),
        Index("ix_solutions_last_ballot_cycle_id", "last_ballot_cycle_id"),
        Index(
            "ix_solutions_umbrella_rank",
            "umbrella_id",
            text("net_score DESC"),
            "created_at",
        ),
        Index(
            "uq_solutions_post_solution_umbrella",
            "post_solution_id",
            "umbrella_id",
            unique=True,
            postgresql_where=text("post_solution_id IS NOT NULL"),
        ),
    )


class SolutionVersion(Base):
    """DATABASE.md §4.8. Every version is kept, with its own hash (Law 6)."""

    __tablename__ = "solution_versions"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    solution_id: Mapped[int] = mapped_column(
        ForeignKey("solutions.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text_body: Mapped[str] = mapped_column("text", Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amendment_id: Mapped[int | None] = mapped_column(
        ForeignKey("amendments.id"), nullable=True
    )
    ai_contribution_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("solution_id", "version", name="uq_solution_versions_solution_version"),
        Index("ix_solution_versions_solution_id", "solution_id"),
        Index("ix_solution_versions_created_by", "created_by"),
        Index("ix_solution_versions_amendment_id", "amendment_id"),
    )


class Amendment(Base):
    """DATABASE.md §4.9. A complete replacement text plus a rationale."""

    __tablename__ = "amendments"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    solution_id: Mapped[int] = mapped_column(
        ForeignKey("solutions.id", ondelete="CASCADE"), nullable=False
    )
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    proposed_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        _enum(
            "proposed",
            "absorbed",
            "superseded",
            "merged_into",
            "withdrawn",
            name="amendments_status_enum",
        ),
        nullable=False,
        server_default=text("'proposed'"),
    )
    absorbed_as_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("amendments.id"), nullable=True
    )
    net_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ai_contribution_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_amendments_solution_id", "solution_id"),
        Index("ix_amendments_solution_status", "solution_id", "status"),
        Index("ix_amendments_author_id", "author_id"),
        Index("ix_amendments_merged_into_id", "merged_into_id"),
    )


class AmendmentSimilarity(Base):
    """DATABASE.md §4.10. AI suggests the pair; humans decide (CLAUDE.md §5)."""

    __tablename__ = "amendment_similarity"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    amendment_a_id: Mapped[int] = mapped_column(
        ForeignKey("amendments.id", ondelete="CASCADE"), nullable=False
    )
    amendment_b_id: Mapped[int] = mapped_column(
        ForeignKey("amendments.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    ai_action_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_actions.id"), nullable=True
    )
    decision: Mapped[str] = mapped_column(
        _enum("pending", "same", "different", name="amendment_similarity_decision_enum"),
        nullable=False,
        server_default=text("'pending'"),
    )
    decided_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "amendment_a_id", "amendment_b_id", name="uq_amendment_similarity_pair"
        ),
        CheckConstraint(
            "amendment_a_id < amendment_b_id", name="ck_amendment_similarity_ordered"
        ),
        Index("ix_amendment_similarity_a", "amendment_a_id"),
        Index("ix_amendment_similarity_b", "amendment_b_id"),
        Index("ix_amendment_similarity_ai_action_id", "ai_action_id"),
    )


class AmendmentSimilarityVote(Base):
    """DATABASE.md §4.10. Same / Different presses by community members."""

    __tablename__ = "amendment_similarity_votes"

    similarity_id: Mapped[int] = mapped_column(
        ForeignKey("amendment_similarity.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    choice: Mapped[str] = mapped_column(
        _enum("same", "different", name="amendment_similarity_votes_choice_enum"),
        nullable=False,
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_amendment_similarity_votes_user_id", "user_id"),)


class Comment(Base):
    """DATABASE.md §4.11. On an umbrella's problem or a dominant solution only."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    target_type: Mapped[str] = mapped_column(
        _enum("umbrella", "solution", name="comments_target_type_enum"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True
    )
    reply_to_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True
    )
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text_body: Mapped[str] = mapped_column("text", Text, nullable=False)
    edited_at: Mapped[datetime | None] = _ts(nullable=True)
    removed_at: Mapped[datetime | None] = _ts(nullable=True)
    net_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ai_contribution_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_comments_target", "target_type", "target_id", "parent_id"),
        Index("ix_comments_author_id", "author_id"),
        Index("ix_comments_parent_id", "parent_id"),
        Index("ix_comments_reply_to_comment_id", "reply_to_comment_id"),
    )


class Vote(Base):
    """DATABASE.md §4.12. Workshop votes on solutions, amendments and comments.
    Removing a vote deletes the row — the only hard delete in Iteration."""

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(
        _enum("solution", "amendment", "comment", name="votes_target_type_enum"),
        nullable=False,
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("direction IN (1, -1)", name="ck_votes_direction"),
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_votes_user_target"),
        Index("ix_votes_target", "target_type", "target_id"),
        Index("ix_votes_user_id", "user_id"),
    )


class UmbrellaReference(Base):
    """DATABASE.md §4.13. Named `umbrella_references` because `references` is a
    PostgreSQL reserved word (DATABASE.md §1)."""

    __tablename__ = "umbrella_references"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    umbrella_id: Mapped[int] = mapped_column(ForeignKey("umbrellas.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        _enum("user", "ai", name="umbrella_references_source_enum"), nullable=False
    )
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ai_action_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_actions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        _enum("active", "rejected", name="umbrella_references_status_enum"),
        nullable=False,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_umbrella_references_umbrella_id", "umbrella_id"),
        Index("ix_umbrella_references_added_by", "added_by"),
        Index("ix_umbrella_references_ai_action_id", "ai_action_id"),
    )


class ReferenceFeedback(Base):
    """DATABASE.md §4.13. Useful / Not useful, one press per member."""

    __tablename__ = "reference_feedback"

    reference_id: Mapped[int] = mapped_column(
        ForeignKey("umbrella_references.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    useful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_reference_feedback_user_id", "user_id"),)


class Cycle(Base):
    """DATABASE.md §4.14. One ballot cycle for one community."""

    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    community_level: Mapped[str] = mapped_column(community_level_enum, nullable=False)
    community_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        _enum(
            "workshop",
            "prepared",
            "jury_review",
            "open",
            "closed",
            "published",
            name="cycles_state_enum",
        ),
        nullable=False,
    )
    settings_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active_users_at_prepare: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prepared_at: Mapped[datetime | None] = _ts(nullable=True)
    jury_review_started_at: Mapped[datetime | None] = _ts(nullable=True)
    opened_at: Mapped[datetime | None] = _ts(nullable=True)
    closed_at: Mapped[datetime | None] = _ts(nullable=True)
    published_at: Mapped[datetime | None] = _ts(nullable=True)
    transitioned_by: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "community_level",
            "community_entity_id",
            "number",
            name="uq_cycles_community_number",
        ),
        Index(
            "uq_cycles_one_open_per_community",
            "community_level",
            "community_entity_id",
            unique=True,
            postgresql_where=text("state <> 'published'"),
        ),
        Index("ix_cycles_community", "community_level", "community_entity_id"),
    )


class BallotItem(Base):
    """DATABASE.md §4.15. A frozen solution version on one ballot."""

    __tablename__ = "ballot_items"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("cycles.id", ondelete="CASCADE"), nullable=False
    )
    solution_id: Mapped[int] = mapped_column(ForeignKey("solutions.id"), nullable=False)
    solution_version: Mapped[int] = mapped_column(Integer, nullable=False)
    umbrella_id: Mapped[int] = mapped_column(ForeignKey("umbrellas.id"), nullable=False)
    net_score_at_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    held_back: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    yes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str | None] = mapped_column(
        _enum("passed", "failed", "held_back", name="ballot_items_result_enum"),
        nullable=True,
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("cycle_id", "solution_id", name="uq_ballot_items_cycle_solution"),
        UniqueConstraint("cycle_id", "position", name="uq_ballot_items_cycle_position"),
        Index("ix_ballot_items_cycle_id", "cycle_id"),
        Index("ix_ballot_items_solution_id", "solution_id"),
        Index("ix_ballot_items_umbrella_id", "umbrella_id"),
    )


class BallotVote(Base):
    """DATABASE.md §4.16. Never deleted. A row is exposed to exactly one
    person: the voter who cast it. No other endpoint, admin included, returns
    a vote with a voter id — everything else is counts."""

    __tablename__ = "ballot_votes"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    ballot_item_id: Mapped[int] = mapped_column(
        ForeignKey("ballot_items.id"), nullable=False
    )
    voter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    choice: Mapped[str] = mapped_column(
        _enum("yes", "no", name="ballot_votes_choice_enum"), nullable=False
    )
    voter_verification_level: Mapped[str] = mapped_column(
        verification_level_enum, nullable=False
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("ballot_item_id", "voter_id", name="uq_ballot_votes_item_voter"),
        Index("ix_ballot_votes_ballot_item_id", "ballot_item_id"),
        Index("ix_ballot_votes_voter_id", "voter_id"),
    )


class Jury(Base):
    """DATABASE.md §4.17. One row per draw — never deleted; a redraw sets
    `superseded_at` on the old row and inserts a new one, so every draw stays
    inspectable (DEMOCRACY.md §8.1; audit demo-01 run 2)."""

    __tablename__ = "juries"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("cycles.id", ondelete="CASCADE"), nullable=False
    )
    size_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_pool: Mapped[list] = mapped_column(JSONB, nullable=False)
    random_bytes: Mapped[str] = mapped_column(String(64), nullable=False)
    drawn_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    superseded_at: Mapped[datetime | None] = _ts(nullable=True)
    redrawn_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    seated_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "uq_juries_current_per_cycle",
            "cycle_id",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
        Index("ix_juries_cycle_id", "cycle_id"),
    )


class Juror(Base):
    """DATABASE.md §4.17. A seated juror is one with `status = accepted`."""

    __tablename__ = "jurors"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    jury_id: Mapped[int] = mapped_column(
        ForeignKey("juries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    seat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        _enum(
            "drawn", "accepted", "declined", "replaced", "no_response", name="jurors_status_enum"
        ),
        nullable=False,
        server_default=text("'drawn'"),
    )
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("jurors.id"), nullable=True
    )
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("jury_id", "user_id", name="uq_jurors_jury_user"),
        Index("ix_jurors_jury_id", "jury_id"),
        Index("ix_jurors_user_id", "user_id"),
        Index("ix_jurors_replaced_by_id", "replaced_by_id"),
    )


class JuryHoldback(Base):
    """DATABASE.md §4.17. One juror's hold-back of one ballot item."""

    __tablename__ = "jury_holdbacks"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    jury_id: Mapped[int] = mapped_column(
        ForeignKey("juries.id", ondelete="CASCADE"), nullable=False
    )
    juror_id: Mapped[int] = mapped_column(ForeignKey("jurors.id"), nullable=False)
    ballot_item_id: Mapped[int] = mapped_column(
        ForeignKey("ballot_items.id"), nullable=False
    )
    reason_category: Mapped[str] = mapped_column(
        _enum(
            "duplicate",
            "not_actionable",
            "incomplete",
            "outside_governance_level",
            "other",
            name="jury_holdbacks_reason_category_enum",
        ),
        nullable=False,
    )
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("juror_id", "ballot_item_id", name="uq_jury_holdbacks_juror_item"),
        Index("ix_jury_holdbacks_jury_id", "jury_id"),
        Index("ix_jury_holdbacks_juror_id", "juror_id"),
        Index("ix_jury_holdbacks_ballot_item_id", "ballot_item_id"),
    )


class Summary(Base):
    """DATABASE.md §4.18. Immutable after publish; the page renders from `data`."""

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("cycles.id"), nullable=False, unique=True
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_summaries_published_at", "published_at"),)


#: Tables owned by each half (DATABASE.md §2). The schema verifier and the
#: migration chains use these lists, so the split is data, not a comment.
FOUNDATION_TABLES = (
    "users",
    "user_display_settings",
    "refresh_tokens",
    "email_verifications",
    "password_resets",
    "terms_versions",
    "terms_acceptances",
    "states",
    "counties",
    "cities",
    "officials",
    "settings",
    "admin_actions",
    "ai_actions",
    "data_exports",
)

ITERATION_TABLES = (
    "main_categories",
    "umbrellas",
    "posts",
    "post_solutions",
    "post_communities",
    "labels",
    "solutions",
    "solution_versions",
    "amendments",
    "amendment_similarity",
    "amendment_similarity_votes",
    "comments",
    "votes",
    "umbrella_references",
    "reference_feedback",
    "cycles",
    "ballot_items",
    "ballot_votes",
    "juries",
    "jurors",
    "jury_holdbacks",
    "summaries",
)
