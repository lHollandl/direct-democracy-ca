"""States, counties and cities (DATABASE.md §3.6)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import City, County, State


async def get_state(session: AsyncSession, state_id: int) -> State | None:
    return await session.get(State, state_id)


async def state_by_abbreviation(session: AsyncSession, abbreviation: str) -> State | None:
    return (
        await session.execute(select(State).where(State.abbreviation == abbreviation))
    ).scalar_one_or_none()


async def all_states(session: AsyncSession) -> list[State]:
    return list((await session.execute(select(State).order_by(State.name))).scalars().all())


async def get_county(session: AsyncSession, county_id: int) -> County | None:
    return await session.get(County, county_id)


async def county_by_name(session: AsyncSession, name: str) -> County | None:
    return (
        await session.execute(select(County).where(County.name == name))
    ).scalar_one_or_none()


async def all_counties(session: AsyncSession) -> list[County]:
    return list((await session.execute(select(County).order_by(County.name))).scalars().all())


async def get_city(session: AsyncSession, city_id: int) -> City | None:
    return await session.get(City, city_id)


async def city_by_name(session: AsyncSession, county_id: int, name: str) -> City | None:
    return (
        await session.execute(
            select(City).where(City.county_id == county_id, City.name == name)
        )
    ).scalar_one_or_none()


async def cities_in_county(session: AsyncSession, county_id: int) -> list[City]:
    return list(
        (
            await session.execute(
                select(City).where(City.county_id == county_id).order_by(City.name)
            )
        )
        .scalars()
        .all()
    )
