"""The `admin_actions` table: append-only, public read (DATABASE.md §3.9)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AdminAction


async def add(
    session: AsyncSession,
    *,
    admin_user_id: int,
    action: str,
    subject_type: str,
    subject_id: int | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
) -> AdminAction:
    row = AdminAction(
        admin_user_id=admin_user_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )
    session.add(row)
    await session.flush()
    return row


async def page(
    session: AsyncSession, *, cursor: int | None, limit: int
) -> list[AdminAction]:
    stmt = select(AdminAction).order_by(AdminAction.id.desc()).limit(limit)
    if cursor is not None:
        stmt = stmt.where(AdminAction.id < cursor)
    return list((await session.execute(stmt)).scalars().all())
