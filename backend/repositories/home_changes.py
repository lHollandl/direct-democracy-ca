"""`user_home_changes` (DATABASE.md §3.12). Insert-only; deleted whole on
anonymization (CLAUDE.md §6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import UserHomeChange


async def add(
    session: AsyncSession,
    *,
    user_id: int,
    from_county_id: int,
    from_city_id: int | None,
    to_county_id: int,
    to_city_id: int | None,
) -> UserHomeChange:
    row = UserHomeChange(
        user_id=user_id,
        from_county_id=from_county_id,
        from_city_id=from_city_id,
        to_county_id=to_county_id,
        to_city_id=to_city_id,
    )
    session.add(row)
    await session.flush()
    return row


async def latest_for_user(session: AsyncSession, user_id: int) -> UserHomeChange | None:
    return (
        await session.execute(
            select(UserHomeChange)
            .where(UserHomeChange.user_id == user_id)
            .order_by(UserHomeChange.changed_at.desc(), UserHomeChange.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def for_user(session: AsyncSession, user_id: int) -> list[UserHomeChange]:
    return list(
        (
            await session.execute(
                select(UserHomeChange)
                .where(UserHomeChange.user_id == user_id)
                .order_by(UserHomeChange.changed_at)
            )
        )
        .scalars()
        .all()
    )


async def earliest_membership_start(
    session: AsyncSession, user_id: int, *, signup_at: datetime, level: str, entity_id: int
) -> datetime:
    """When this user's membership of this community began: signup, unless a
    later home change moved them into it (DEMOCRACY.md §2.3, §10.3)."""
    changes = await for_user(session, user_id)
    started = signup_at
    for change in changes:
        if level == "county":
            if change.to_county_id == entity_id and change.from_county_id != change.to_county_id:
                started = change.changed_at
        elif level == "city":
            if change.to_city_id == entity_id and change.from_city_id != change.to_city_id:
                started = change.changed_at
        # A move within California never changes state membership.
    return started


async def delete_for_user(session: AsyncSession, user_id: int) -> None:
    """Anonymization (DATABASE.md §3.12): past addresses are not part of the
    civic record."""
    await session.execute(delete(UserHomeChange).where(UserHomeChange.user_id == user_id))
