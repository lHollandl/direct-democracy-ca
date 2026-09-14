"""Threaded comments on an umbrella's problem or a dominant solution (§4.11)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Comment


async def get(session: AsyncSession, comment_id: int) -> Comment | None:
    return await session.get(Comment, comment_id)


async def add(session: AsyncSession, **fields) -> Comment:
    row = Comment(**fields)
    session.add(row)
    await session.flush()
    return row


async def for_target(session: AsyncSession, target_type: str, target_id: int) -> list[Comment]:
    """Every comment on one target, in one query. The service builds the tree
    and orders each thread by net score descending, ties oldest first."""
    return list(
        (
            await session.execute(
                select(Comment)
                .where(Comment.target_type == target_type, Comment.target_id == target_id)
                .order_by(Comment.net_score.desc(), Comment.created_at, Comment.id)
            )
        )
        .scalars()
        .all()
    )


async def by_author(session: AsyncSession, author_id: int) -> list[Comment]:
    return list(
        (
            await session.execute(
                select(Comment).where(Comment.author_id == author_id).order_by(Comment.id)
            )
        )
        .scalars()
        .all()
    )


async def all_comments(session: AsyncSession) -> list[Comment]:
    return list((await session.execute(select(Comment))).scalars().all())
