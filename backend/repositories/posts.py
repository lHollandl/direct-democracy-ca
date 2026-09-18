"""Posts, their solution texts, their communities, and their labels."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Label, Post, PostCommunity, PostSolution


async def get(session: AsyncSession, post_id: int) -> Post | None:
    return await session.get(Post, post_id)


async def all_posts(session: AsyncSession) -> list[Post]:
    return list((await session.execute(select(Post))).scalars().all())


async def all_post_solutions(session: AsyncSession) -> list[PostSolution]:
    return list((await session.execute(select(PostSolution))).scalars().all())


async def all_post_communities(session: AsyncSession) -> list[PostCommunity]:
    return list((await session.execute(select(PostCommunity))).scalars().all())


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


async def posts_awaiting_labels(
    session: AsyncSession, *, stale_before: datetime, limit: int = 50
) -> list[Post]:
    """Posts the labeler still owes an answer for.

    `unlabeled` means a labeling attempt failed. `pending` older than the retry
    window means the attempt never ran at all — the process was restarted
    between the post committing and its job starting. Both have to be picked
    up, or a post would sit saying "being filed" forever.
    """
    return list(
        (
            await session.execute(
                select(Post)
                .where(
                    Post.deleted_at.is_(None),
                    or_(
                        Post.label_status == "unlabeled",
                        and_(Post.label_status == "pending", Post.created_at < stale_before),
                    ),
                )
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


async def by_author(session: AsyncSession, author_id: int) -> list[Post]:
    return list(
        (
            await session.execute(
                select(Post).where(Post.author_id == author_id).order_by(Post.id)
            )
        )
        .scalars()
        .all()
    )


async def labels_for_umbrella(session: AsyncSession, umbrella_id: int) -> list[Label]:
    return list(
        (await session.execute(select(Label).where(Label.umbrella_id == umbrella_id)))
        .scalars()
        .all()
    )


async def post_ids_for_umbrella(session: AsyncSession, umbrella_id: int) -> list[int]:
    rows = (
        await session.execute(
            select(PostCommunity.post_id).where(PostCommunity.umbrella_id == umbrella_id)
        )
    ).scalars().all()
    return list(set(rows))


async def problem_reports_for_umbrella(
    session: AsyncSession, umbrella_id: int
) -> list[tuple[Post, Label | None]]:
    """DEMOCRACY.md §3.3 item 2 — newest first, one row per post with its label
    for this umbrella's community, if any."""
    rows = (
        await session.execute(
            select(Post, Label)
            .join(PostCommunity, PostCommunity.post_id == Post.id)
            .outerjoin(
                Label,
                (Label.post_id == Post.id)
                & (Label.community_level == PostCommunity.community_level)
                & (Label.community_entity_id == PostCommunity.community_entity_id),
            )
            .where(PostCommunity.umbrella_id == umbrella_id, Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc(), Post.id.desc())
        )
    ).all()
    return [(post, label) for post, label in rows]
