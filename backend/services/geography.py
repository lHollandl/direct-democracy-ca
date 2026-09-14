"""States, counties and cities (DATABASE.md §3.6, Foundation)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import City, County
from backend.repositories import geography as geo_repo


async def all_counties(session: AsyncSession) -> list[County]:
    return await geo_repo.all_counties(session)


async def cities_in_county(session: AsyncSession, county_id: int) -> list[City]:
    return await geo_repo.cities_in_county(session, county_id)
