"""Writing and reading the public admin action log (DEMOCRACY.md §13).

Every director control writes a row: who, what, subject, old and new values,
and a reason when one was given. The log is public at `/admin/log` and needs
no login to read (CLAUDE.md §2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories import admin as admin_repo
from backend.services.display import author_displays


async def record(
    session: AsyncSession,
    *,
    admin_user_id: int,
    action: str,
    subject_type: str,
    subject_id: int | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
) -> None:
    await admin_repo.add(
        session,
        admin_user_id=admin_user_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )


async def public_page(
    session: AsyncSession, *, cursor: int | None, limit: int
) -> dict[str, Any]:
    rows = await admin_repo.page(session, cursor=cursor, limit=limit)
    displays = await author_displays(session, [r.admin_user_id for r in rows])
    return {
        "items": [
            {
                "id": r.id,
                "administrator": displays.get(r.admin_user_id, "Former Community Member"),
                "action": r.action,
                "subject_type": r.subject_type,
                "subject_id": r.subject_id,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "reason": r.reason,
                "at": r.created_at,
            }
            for r in rows
        ],
        "next_cursor": rows[-1].id if len(rows) == limit else None,
    }
