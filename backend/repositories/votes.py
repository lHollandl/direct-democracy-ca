"""Workshop votes (DATABASE.md §4.12). The rows are authoritative; the
`net_score` columns are caches that the nightly job reconciles against them."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Amendment, Comment, Solution, Vote

TARGET_MODELS = {"solution": Solution, "amendment": Amendment, "comment": Comment}


async def get_vote(
    session: AsyncSession, *, user_id: int, target_type: str, target_id: int
) -> Vote | None:
    return (
        await session.execute(
            select(Vote).where(
                Vote.user_id == user_id,
                Vote.target_type == target_type,
                Vote.target_id == target_id,
            )
        )
    ).scalar_one_or_none()


async def put_vote(
    session: AsyncSession, *, user_id: int, target_type: str, target_id: int, direction: int
) -> Vote:
    row = await get_vote(
        session, user_id=user_id, target_type=target_type, target_id=target_id
    )
    if row is None:
        row = Vote(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            direction=direction,
        )
        session.add(row)
    else:
        row.direction = direction
    await session.flush()
    return row


async def remove_vote(
    session: AsyncSession, *, user_id: int, target_type: str, target_id: int
) -> bool:
    result = await session.execute(
        delete(Vote).where(
            Vote.user_id == user_id,
            Vote.target_type == target_type,
            Vote.target_id == target_id,
        )
    )
    await session.flush()
    return bool(result.rowcount)


async def tally(session: AsyncSession, target_type: str, target_id: int) -> tuple[int, int]:
    """(upvotes, downvotes) counted from the vote rows."""
    rows = (
        await session.execute(
            select(Vote.direction, func.count())
            .where(Vote.target_type == target_type, Vote.target_id == target_id)
            .group_by(Vote.direction)
        )
    ).all()
    counts = {int(direction): int(count) for direction, count in rows}
    return counts.get(1, 0), counts.get(-1, 0)


async def tallies(
    session: AsyncSession, target_type: str, target_ids: list[int]
) -> dict[int, tuple[int, int]]:
    if not target_ids:
        return {}
    rows = (
        await session.execute(
            select(Vote.target_id, Vote.direction, func.count())
            .where(Vote.target_type == target_type, Vote.target_id.in_(set(target_ids)))
            .group_by(Vote.target_id, Vote.direction)
        )
    ).all()
    out: dict[int, list[int]] = {}
    for target_id, direction, count in rows:
        slot = out.setdefault(target_id, [0, 0])
        slot[0 if int(direction) == 1 else 1] += int(count)
    return {k: (v[0], v[1]) for k, v in out.items()}


async def count_votes_on(session: AsyncSession, target_type: str, target_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(Vote).where(
                    Vote.target_type == target_type, Vote.target_id == target_id
                )
            )
        ).scalar_one()
    )


async def user_votes(session: AsyncSession, user_id: int) -> list[Vote]:
    return list(
        (await session.execute(select(Vote).where(Vote.user_id == user_id))).scalars().all()
    )


async def user_votes_on(
    session: AsyncSession, user_id: int, target_type: str, target_ids: list[int]
) -> dict[int, int]:
    if not target_ids:
        return {}
    rows = (
        await session.execute(
            select(Vote.target_id, Vote.direction).where(
                Vote.user_id == user_id,
                Vote.target_type == target_type,
                Vote.target_id.in_(set(target_ids)),
            )
        )
    ).all()
    return {int(tid): int(direction) for tid, direction in rows}
