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

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import NotFound, ValidationFailed
from backend.models import Official, User
from backend.repositories import geography as geo_repo
from backend.repositories import officials as officials_repo
from backend.repositories import users as users_repo
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
    getter = {"city": geo_repo.get_city, "county": geo_repo.get_county, "state": geo_repo.get_state}[
        level
    ]
    row = await getter(session, entity_id)
    if row is None:
        raise NotFound(f"No {level} with id {entity_id} exists.", code="community_not_found")
    return Community(level=level, entity_id=entity_id, name=row.name)


async def home_communities(session: AsyncSession, user: User) -> list[Community]:
    """The one function that answers "which communities is this user a
    member of" (DEMOCRACY.md §2.3). A user with a home city belongs to
    three: their city, their county, and California. An unincorporated
    resident (`user.city_id` is NULL) belongs to two: their county and
    California. Nothing else derives membership."""
    county = await geo_repo.get_county(session, user.county_id)
    if county is None:
        raise NotFound("This account's home county is missing.", code="home_missing")
    state = await geo_repo.get_state(session, county.state_id)
    if state is None:
        raise NotFound("This account's home state is missing.", code="home_missing")
    communities = []
    if user.city_id is not None:
        city = await geo_repo.get_city(session, user.city_id)
        if city is None:
            raise NotFound("This account's home city is missing.", code="home_missing")
        communities.append(Community("city", city.id, city.name))
    communities.append(Community("county", county.id, county.name))
    communities.append(Community("state", state.id, state.name))
    return communities


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
    if level not in SUPPORTED_LEVELS:
        raise ValidationFailed(
            f"{level!r} is not a governance level.", code="unknown_community_level"
        )
    window_days = int(await settings_service.get(session, "active_user_window_days"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    return await users_repo.count_active_members(session, level, entity_id, cutoff)


async def active_user_definition(session: AsyncSession) -> str:
    days = int(await settings_service.get(session, "active_user_window_days"))
    return ACTIVE_USER_DEFINITION.format(days=days)


async def officials_for(session: AsyncSession, level: str, entity_id: int) -> list[Official]:
    return await officials_repo.for_community(session, level, entity_id)


def _official_dict(o: Official) -> dict:
    return {"id": o.id, "office": o.office, "holder_name": o.holder_name, "email": o.email, "source": o.source}


async def detail_view(session: AsyncSession, level: str, entity_id: int) -> dict:
    """`GET /communities/{level}/{id}` — the whole response (ARCHITECTURE.md
    §2/§10: one service call per router endpoint beyond a `require_*`
    resolver; audit demo-01 run 3, MEDIUM: this used to assemble four
    service calls in the router)."""
    community = await resolve(session, level, entity_id)
    officials = await officials_for(session, level, entity_id)
    return {
        **community.as_dict(),
        "active_users": await active_user_count(session, level, entity_id),
        "active_user_definition": await active_user_definition(session),
        "officials": [_official_dict(o) for o in officials],
    }


async def officials_list(session: AsyncSession, level: str, entity_id: int) -> list[dict]:
    """`GET /communities/{level}/{id}/officials` — one service call (audit
    demo-01 run 3, MEDIUM: this used to call `resolve` and `officials_for`
    separately from the router)."""
    await resolve(session, level, entity_id)
    return [_official_dict(o) for o in await officials_for(session, level, entity_id)]
