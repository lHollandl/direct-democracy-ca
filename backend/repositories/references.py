"""External references attached to an umbrella (DATABASE.md §4.13)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ReferenceFeedback, UmbrellaReference


async def get(session: AsyncSession, reference_id: int) -> UmbrellaReference | None:
    return await session.get(UmbrellaReference, reference_id)


async def add(session: AsyncSession, **fields) -> UmbrellaReference:
    row = UmbrellaReference(**fields)
    session.add(row)
    await session.flush()
    return row


async def for_umbrella(session: AsyncSession, umbrella_id: int) -> list[UmbrellaReference]:
    return list(
        (
            await session.execute(
                select(UmbrellaReference)
                .where(UmbrellaReference.umbrella_id == umbrella_id)
                .order_by(UmbrellaReference.id)
            )
        )
        .scalars()
        .all()
    )


async def count_ai_active(session: AsyncSession, umbrella_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(UmbrellaReference)
                .where(
                    UmbrellaReference.umbrella_id == umbrella_id,
                    UmbrellaReference.source == "ai",
                    UmbrellaReference.status == "active",
                )
            )
        ).scalar_one()
    )


async def put_feedback(
    session: AsyncSession, *, reference_id: int, user_id: int, useful: bool
) -> ReferenceFeedback:
    row = await session.get(ReferenceFeedback, (reference_id, user_id))
    if row is None:
        row = ReferenceFeedback(reference_id=reference_id, user_id=user_id, useful=useful)
        session.add(row)
    else:
        row.useful = useful
    await session.flush()
    return row


async def feedback_counts(session: AsyncSession, reference_ids: list[int]) -> dict[int, tuple[int, int]]:
    """(useful, not useful) per reference."""
    if not reference_ids:
        return {}
    rows = (
        await session.execute(
            select(ReferenceFeedback.reference_id, ReferenceFeedback.useful, func.count())
            .where(ReferenceFeedback.reference_id.in_(set(reference_ids)))
            .group_by(ReferenceFeedback.reference_id, ReferenceFeedback.useful)
        )
    ).all()
    out: dict[int, list[int]] = {}
    for reference_id, useful, count in rows:
        slot = out.setdefault(reference_id, [0, 0])
        slot[0 if useful else 1] += int(count)
    return {k: (v[0], v[1]) for k, v in out.items()}
