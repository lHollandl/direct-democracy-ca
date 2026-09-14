"""Umbrellas and main categories (DATABASE.md §4.1, §4.2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import MainCategory, Umbrella


async def get(session: AsyncSession, umbrella_id: int) -> Umbrella | None:
    return await session.get(Umbrella, umbrella_id)


async def for_community(
    session: AsyncSession, level: str, entity_id: int, *, active_only: bool = True
) -> list[Umbrella]:
    stmt = select(Umbrella).where(
        Umbrella.community_level == level, Umbrella.community_entity_id == entity_id
    )
    if active_only:
        stmt = stmt.where(Umbrella.status == "active")
    return list((await session.execute(stmt.order_by(Umbrella.name))).scalars().all())


async def by_ids(session: AsyncSession, ids: list[int]) -> dict[int, Umbrella]:
    if not ids:
        return {}
    rows = (
        await session.execute(select(Umbrella).where(Umbrella.id.in_(set(ids))))
    ).scalars().all()
    return {row.id: row for row in rows}


async def categories(session: AsyncSession, *, active_only: bool = True) -> list[MainCategory]:
    stmt = select(MainCategory)
    if active_only:
        stmt = stmt.where(MainCategory.active.is_(True))
    return list((await session.execute(stmt.order_by(MainCategory.name))).scalars().all())


async def category_by_name(session: AsyncSession, name: str) -> MainCategory | None:
    return (
        await session.execute(select(MainCategory).where(MainCategory.name == name))
    ).scalar_one_or_none()


async def category_by_slug(session: AsyncSession, slug: str) -> MainCategory | None:
    return (
        await session.execute(select(MainCategory).where(MainCategory.slug == slug))
    ).scalar_one_or_none()


async def categories_by_ids(session: AsyncSession, ids: list[int]) -> dict[int, MainCategory]:
    if not ids:
        return {}
    rows = (
        await session.execute(select(MainCategory).where(MainCategory.id.in_(set(ids))))
    ).scalars().all()
    return {row.id: row for row in rows}
