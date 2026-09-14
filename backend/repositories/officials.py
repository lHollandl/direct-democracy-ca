"""The officials directory (DATABASE.md §3.7)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Official


async def for_community(
    session: AsyncSession, level: str, entity_id: int
) -> list[Official]:
    return list(
        (
            await session.execute(
                select(Official)
                .where(
                    Official.community_level == level,
                    Official.community_entity_id == entity_id,
                    Official.active.is_(True),
                )
                .order_by(Official.office)
            )
        )
        .scalars()
        .all()
    )
