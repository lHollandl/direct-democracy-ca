"""The `ai_actions` table (DATABASE.md §3.10, DEMOCRACY.md §9.2).

Every AI action is a row, written before its result is shown (CLAUDE.md
Law 7). Rows are never deleted or edited except to set `human_outcome_*`, once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AiAction


async def add(
    session: AsyncSession,
    *,
    action_type: str,
    subject_type: str,
    subject_id: int,
    demo_build: str,
    model: str,
    prompt_file: str,
    prompt_hash: str,
    input_hash: str,
    output: dict[str, Any],
    confidence: float | None = None,
) -> AiAction:
    row = AiAction(
        action_type=action_type,
        subject_type=subject_type,
        subject_id=subject_id,
        demo_build=demo_build,
        model=model,
        prompt_file=prompt_file,
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        output=output,
        confidence=Decimal(str(round(confidence, 3))) if confidence is not None else None,
    )
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, action_id: int) -> AiAction | None:
    return await session.get(AiAction, action_id)


async def record_outcome(
    session: AsyncSession, *, action_id: int, outcome: str, user_id: int
) -> AiAction | None:
    row = await session.get(AiAction, action_id)
    if row is None or row.human_outcome != "unreviewed":
        return row
    row.human_outcome = outcome
    row.human_outcome_by = user_id
    row.human_outcome_at = datetime.now(timezone.utc)
    await session.flush()
    return row


async def page(
    session: AsyncSession,
    *,
    cursor: int | None,
    limit: int,
    subject_type: str | None = None,
    subject_id: int | None = None,
    action_type: str | None = None,
) -> list[AiAction]:
    stmt = select(AiAction).order_by(AiAction.id.desc()).limit(limit)
    if cursor is not None:
        stmt = stmt.where(AiAction.id < cursor)
    if subject_type:
        stmt = stmt.where(AiAction.subject_type == subject_type)
    if subject_id is not None:
        stmt = stmt.where(AiAction.subject_id == subject_id)
    if action_type:
        stmt = stmt.where(AiAction.action_type == action_type)
    return list((await session.execute(stmt)).scalars().all())


async def for_subjects(
    session: AsyncSession, subject_type: str, subject_ids: list[int]
) -> list[AiAction]:
    if not subject_ids:
        return []
    return list(
        (
            await session.execute(
                select(AiAction).where(
                    AiAction.subject_type == subject_type,
                    AiAction.subject_id.in_(subject_ids),
                )
            )
        )
        .scalars()
        .all()
    )


async def count_by_outcome(
    session: AsyncSession, subject_type: str, subject_ids: list[int], action_type: str
) -> dict[str, int]:
    if not subject_ids:
        return {}
    rows = (
        await session.execute(
            select(AiAction.human_outcome, func.count())
            .where(
                AiAction.subject_type == subject_type,
                AiAction.subject_id.in_(subject_ids),
                AiAction.action_type == action_type,
            )
            .group_by(AiAction.human_outcome)
        )
    ).all()
    return {outcome: int(count) for outcome, count in rows}
