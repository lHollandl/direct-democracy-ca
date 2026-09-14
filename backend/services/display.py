"""How an author's name appears, everywhere, in one function (DATABASE.md §3.2).

Users own their identity (CLAUDE.md §6). The public display is a setting, not
an account type: real name, display name, or anonymous. A deleted account
always renders "Former Community Member" — the civic record is preserved, the
identity is removed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User, UserDisplaySettings

FORMER_MEMBER = "Former Community Member"
ANONYMOUS = "Anonymous Community Member"


async def author_display(session: AsyncSession, user_id: int | None) -> str:
    if user_id is None:
        return FORMER_MEMBER
    return (await author_displays(session, [user_id])).get(user_id, FORMER_MEMBER)


async def author_displays(session: AsyncSession, user_ids) -> dict[int, str]:
    """One query for a page full of authors."""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(
                User.id,
                User.real_name,
                User.display_name,
                User.deleted_at,
                UserDisplaySettings.public_name_mode,
            ).outerjoin(UserDisplaySettings, UserDisplaySettings.user_id == User.id)
            .where(User.id.in_(ids))
        )
    ).all()
    out: dict[int, str] = {}
    for user_id, real_name, display_name, deleted_at, mode in rows:
        if deleted_at is not None:
            out[user_id] = FORMER_MEMBER
        elif mode == "anonymous":
            out[user_id] = ANONYMOUS
        elif mode == "real_name":
            out[user_id] = real_name or display_name
        else:
            out[user_id] = display_name
    return out
