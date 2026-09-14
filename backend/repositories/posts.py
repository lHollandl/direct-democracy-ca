"""Posts, their solution texts, their communities, and their labels."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Label, Post, PostCommunity, PostSolution


async def get(session: AsyncSession, post_id: int) -> Post | None:
    return await session.get(Post, post_id)


async def add(session: AsyncSession, **fields) -> Post:
    row = Post(**fields)
    session.add(row)
    await session.flush()
    return row


async def add_solution_text(session: AsyncSession, **fields) -> PostSolution:
    row = PostSolution(**fields)
    session.add(row)
    await session.flush()
    return row


async def solution_texts(session: AsyncSession, post_id: int) -> list[PostSolution]:
    return list(
        (
            await session.execute(
                select(PostSolution)
                .where(PostSolution.post_id == post_id)
                .order_by(PostSolution.position)
            )
        )
        .scalars()
        .all()
    )


async def add_community(session: AsyncSession, **fields) -> PostCommunity:
    row = PostCommunity(**fields)
    session.add(row)
    await session.flush()
    return row


async def communities(session: AsyncSession, post_id: int) -> list[PostCommunity]:
    return list(
        (
            await session.execute(
                select(PostCommunity).where(PostCommunity.post_id == post_id)
            )
        )
        .scalars()
        .all()
    )


async def community(
    session: AsyncSession, post_id: int, level: str, entity_id: int
) -> PostCommunity | None:
    return await session.get(PostCommunity, (post_id, level, entity_id))


async def set_label_status(session: AsyncSession, post_id: int, status: str) -> None:
    await session.execute(update(Post).where(Post.id == post_id).values(label_status=status))


async def unlabeled_posts(session: AsyncSession, limit: int = 50) -> list[Post]:
    return list(
        (
            await session.execute(
                select(Post)
                .where(Post.label_status == "unlabeled", Post.deleted_at.is_(None))
                .order_by(Post.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def add_label(session: AsyncSession, **fields) -> Label:
    row = Label(**fields)
    session.add(row)
    await session.flush()
    return row


async def labels_for_post(session: AsyncSession, post_id: int) -> list[Label]:
    return list(
        (
            await session.execute(
                select(Label).where(Label.post_id == post_id).order_by(Label.id)
            )
        )
        .scalars()
        .all()
    )


async def latest_label(
    session: AsyncSession, post_id: int, level: str, entity_id: int
) -> Label | None:
    return (
        await session.execute(
            select(Label)
            .where(
                Label.post_id == post_id,
                Label.community_level == level,
                Label.community_entity_id == entity_id,
            )
            .order_by(Label.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def feed_page(
    session: AsyncSession,
    *,
    cursor: int | None,
    limit: int,
    community: tuple[str, int] | None = None,
    main_category_id: int | None = None,
    community_keys: list[tuple[str, int]] | None = None,
) -> list[Post]:
    """feed-v0: newest first, filtered by community and main category. That is
    the entire ordering rule (DEMOCRACY.md §12)."""
    stmt = select(Post).where(Post.deleted_at.is_(None))
    if community or main_category_id is not None or community_keys:
        stmt = stmt.join(PostCommunity, PostCommunity.post_id == Post.id)
    if community:
        stmt = stmt.where(
            PostCommunity.community_level == community[0],
            PostCommunity.community_entity_id == community[1],
        )
    elif community_keys:
        stmt = stmt.where(
            _community_tuple_filter(community_keys)
        )
    if main_category_id is not None:
        stmt = stmt.where(PostCommunity.main_category_id == main_category_id)
    if cursor is not None:
        stmt = stmt.where(Post.id < cursor)
    stmt = stmt.order_by(Post.id.desc()).limit(limit).distinct()
    return list((await session.execute(stmt)).scalars().all())


def _community_tuple_filter(keys: list[tuple[str, int]]):
    from sqlalchemy import or_

    return or_(
        *[
            (PostCommunity.community_level == level)
            & (PostCommunity.community_entity_id == entity_id)
            for level, entity_id in keys
        ]
    )
