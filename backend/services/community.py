"""Communities: one governance level plus one entity (DEMOCRACY.md §2.2).

A community is `(city, Vallejo)`, `(county, Solano)` or `(state, California)`.
Rows all over the platform carry the pair `(community_level,
community_entity_id)`. PostgreSQL cannot express that polymorphic foreign key,
so `resolve` is the guard on every write path and the nightly reconciliation
job checks for orphans (DATABASE.md §3.7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import NotFound, ValidationFailed
from backend.models import City, County, State, User
from backend.services import settings as settings_service

#: `federal` exists in the enum with no entity behind it (PROJECT.md parking
#: lot). Demo 1 refuses it rather than pretending it works.
SUPPORTED_LEVELS = ("city", "county", "state")


@dataclass(frozen=True)
class Community:
    level: str
    entity_id: int
    name: str

    @property
    def key(self) -> tuple[str, int]:
        return (self.level, self.entity_id)

    @property
    def label(self) -> str:
        if self.level == "city":
            return f"{self.name} (city)"
        if self.level == "county":
            return f"{self.name} County"
        return self.name

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "entity_id": self.entity_id,
            "name": self.name,
            "label": self.label,
        }


async def resolve(session: AsyncSession, level: str, entity_id: int) -> Community:
    """Check that this level/entity pair names a real place, and return it."""
    if level == "federal":
        raise ValidationFailed(
            "There is no federal community yet. Posts and ballots run at city, "
            "county and state level.",
            code="federal_not_available",
        )
    if level not in SUPPORTED_LEVELS:
        raise ValidationFailed(
            f"{level!r} is not a governance level. Use city, county or state.",
            code="unknown_community_level",
        )
    model = {"city": City, "county": County, "state": State}[level]
    row = await session.get(model, entity_id)
    if row is None:
        raise NotFound(f"No {level} with id {entity_id} exists.", code="community_not_found")
    return Community(level=level, entity_id=entity_id, name=row.name)


async def home_communities(session: AsyncSession, user: User) -> list[Community]:
    """Every user belongs to exactly three: their city, their county, and
    California (DEMOCRACY.md §2.3)."""
    city = await session.get(City, user.city_id)
    county = await session.get(County, user.county_id)
    if city is None or county is None:
        raise NotFound("This account's home city or county is missing.", code="home_missing")
    state = await session.get(State, county.state_id)
    if state is None:
        raise NotFound("This account's home state is missing.", code="home_missing")
    return [
        Community("city", city.id, city.name),
        Community("county", county.id, county.name),
        Community("state", state.id, state.name),
    ]


async def is_member(session: AsyncSession, user: User, level: str, entity_id: int) -> bool:
    return any(c.key == (level, entity_id) for c in await home_communities(session, user))


ACTIVE_USER_DEFINITION = (
    "An active user of a community is a member of that community whose email "
    "is verified, whose account has not been deleted, and who has made at "
    "least one signed-in request in the last {days} days."
)


async def active_user_count(session: AsyncSession, level: str, entity_id: int) -> int:
    """DEMOCRACY.md §2.4 — the denominator for every percentage threshold.

    Computed on demand. The count is displayed on each community's page with
    this definition beside it.
    """
    window_days = int(await settings_service.get(session, "active_user_window_days"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = select(func.count()).select_from(User).where(
        User.deleted_at.is_(None),
        User.email_verified_at.is_not(None),
        User.last_active_at.is_not(None),
        User.last_active_at >= cutoff,
    )
    if level == "city":
        stmt = stmt.where(User.city_id == entity_id)
    elif level == "county":
        stmt = stmt.where(User.county_id == entity_id)
    elif level == "state":
        stmt = stmt.join(County, County.id == User.county_id).where(County.state_id == entity_id)
    else:
        raise ValidationFailed(
            f"{level!r} is not a governance level.", code="unknown_community_level"
        )
    return int((await session.execute(stmt)).scalar_one())


async def active_user_definition(session: AsyncSession) -> str:
    days = int(await settings_service.get(session, "active_user_window_days"))
    return ACTIVE_USER_DEFINITION.format(days=days)


async def members_query_filter(level: str, entity_id: int):
    """The `users` filter for "member of this community", for reuse by the jury
    draw and the ballot eligibility check."""
    if level == "city":
        return User.city_id == entity_id
    if level == "county":
        return User.county_id == entity_id
    if level == "state":
        return User.county_id.in_(select(County.id).where(County.state_id == entity_id))
    raise ValidationFailed(f"{level!r} is not a governance level.", code="unknown_community_level")
