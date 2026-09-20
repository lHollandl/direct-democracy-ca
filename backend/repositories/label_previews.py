"""`label_previews` (DATABASE.md §4.19). No draft text is stored — only its
hash. `ai_action_id`, `result`, and `consumed_post_id` are each set once."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import LabelPreview


async def add(
    session: AsyncSession, *, user_id: int, input_hash: str, communities: list[dict]
) -> LabelPreview:
    row = LabelPreview(user_id=user_id, input_hash=input_hash, communities=communities)
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, preview_id: int) -> LabelPreview | None:
    return await session.get(LabelPreview, preview_id)


async def set_ai_action(session: AsyncSession, preview_id: int, ai_action_id: int) -> None:
    row = await session.get(LabelPreview, preview_id)
    if row is not None:
        row.ai_action_id = ai_action_id
        await session.flush()


async def set_result(session: AsyncSession, preview_id: int, result: dict) -> None:
    row = await session.get(LabelPreview, preview_id)
    if row is not None:
        row.result = result
        await session.flush()


async def mark_consumed(session: AsyncSession, preview_id: int, post_id: int) -> None:
    row = await session.get(LabelPreview, preview_id)
    if row is not None:
        row.consumed_post_id = post_id
        await session.flush()


async def count_since(session: AsyncSession, user_id: int, since: datetime) -> int:
    """The rate limit's query (`label_preview_max_per_hour`, DEMOCRACY.md §9.1)."""
    stmt = (
        select(func.count())
        .select_from(LabelPreview)
        .where(LabelPreview.user_id == user_id, LabelPreview.created_at >= since)
    )
    return int((await session.execute(stmt)).scalar_one())
