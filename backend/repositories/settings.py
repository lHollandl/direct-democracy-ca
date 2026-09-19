"""The `settings` table: append-only, current value = latest effective_from."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Setting


async def current_rows(session: AsyncSession) -> list[Setting]:
    """The row in force for every key: the latest `effective_from` per key."""
    rows = (
        await session.execute(
            select(Setting).order_by(Setting.key, Setting.effective_from.desc(), Setting.id.desc())
        )
    ).scalars().all()
    seen: dict[str, Setting] = {}
    for row in rows:
        seen.setdefault(row.key, row)
    return list(seen.values())


async def history_page(
    session: AsyncSession, key: str | None, *, cursor: int | None, limit: int
) -> list[Setting]:
    """`GET /settings/history` (ARCHITECTURE.md §6). Rows are inserted in
    `effective_from` order, so `id` and `effective_from` are monotonic
    together — filtering on `id` alone keeps the same order as `history()`
    without a compound cursor."""
    stmt = select(Setting).order_by(Setting.effective_from.desc(), Setting.id.desc())
    if key:
        stmt = stmt.where(Setting.key == key)
    if cursor is not None:
        stmt = stmt.where(Setting.id < cursor)
    stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def value_in_force_at(session: AsyncSession, key: str, moment: datetime) -> Setting | None:
    return (
        await session.execute(
            select(Setting)
            .where(Setting.key == key, Setting.effective_from <= moment)
            .order_by(Setting.effective_from.desc(), Setting.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def append(
    session: AsyncSession,
    *,
    key: str,
    value: str,
    changed_by: int | None,
    reason: str | None,
) -> Setting:
    row = Setting(key=key, value=value, changed_by=changed_by, reason=reason)
    session.add(row)
    await session.flush()
    return row
