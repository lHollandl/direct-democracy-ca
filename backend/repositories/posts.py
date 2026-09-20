"""Posts, their solution texts, their communities, and their labels."""

from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import and_, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Comment, Label, Post, PostCommunity, PostSolution, Solution, Vote


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


_CURSOR_SEP = "|"


def _encode_feed_cursor(*parts: object) -> str:
    """The cursor is opaque to the client (ARCHITECTURE.md §6) — a base64
    token, never a bare id, so a count-sort cursor can't be mistaken for a
    date-sort one or hand-edited into a different page."""
    raw = _CURSOR_SEP.join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_feed_cursor(cursor: str) -> tuple[str, str]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    first, _, second = raw.partition(_CURSOR_SEP)
    return first, second


def _fts_match(column, q: str):
    return func.to_tsvector("english", column).op("@@")(func.websearch_to_tsquery("english", q))


async def feed_page(
    session: AsyncSession,
    *,
    sort: str,
    cursor: str | None,
    limit: int,
    community: tuple[str, int] | None = None,
    main_category_id: int | None = None,
    community_keys: list[tuple[str, int]] | None = None,
    query: str | None = None,
) -> tuple[list, str | None]:
    """feed-v1 (DEMOCRACY.md §12.1; the sort explanations live beside
    `FEED_SORTS` in `backend/services/rules.py`, Law 9).

    `vote_count` and `comment_count` are computed per post, not stored: the
    number of `votes` rows (up and down alike) whose target is a solution
    with that `post_id`, and the number of not-removed comments whose target
    is one of those solutions. `query` filters via PostgreSQL full-text
    search on the problem text or any solution text; it never orders
    (DEMOCRACY.md §12.1) — the GIN indexes it uses live in DATABASE.md §4.3,
    §4.4.
    """
    vote_count_col = (
        select(func.count(Vote.id))
        .select_from(Vote)
        .join(Solution, and_(Solution.id == Vote.target_id, Vote.target_type == "solution"))
        .where(Solution.post_id == Post.id)
        .correlate(Post)
        .scalar_subquery()
    )
    comment_count_col = (
        select(func.count(Comment.id))
        .select_from(Comment)
        .join(Solution, and_(Solution.id == Comment.target_id, Comment.target_type == "solution"))
        .where(Solution.post_id == Post.id, Comment.removed_at.is_(None))
        .correlate(Post)
        .scalar_subquery()
    )

    stmt = select(
        Post, vote_count_col.label("vote_count"), comment_count_col.label("comment_count")
    ).where(Post.deleted_at.is_(None))
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
    if query:
        solution_match = (
            select(PostSolution.id)
            .where(PostSolution.post_id == Post.id, _fts_match(PostSolution.text_body, query))
            .exists()
        )
        stmt = stmt.where(or_(_fts_match(Post.problem_text, query), solution_match))
    stmt = stmt.distinct()

    base = stmt.subquery("feed_base")
    outer = select(base)

    if sort in ("most_votes", "most_comments"):
        count_col = base.c.vote_count if sort == "most_votes" else base.c.comment_count
        if cursor is not None:
            cur_count, cur_id = _decode_feed_cursor(cursor)
            outer = outer.where(tuple_(count_col, base.c.id) < (int(cur_count), int(cur_id)))
        outer = outer.order_by(count_col.desc(), base.c.id.desc())
    elif sort == "oldest":
        if cursor is not None:
            cur_created_at, cur_id = _decode_feed_cursor(cursor)
            outer = outer.where(
                tuple_(base.c.created_at, base.c.id)
                > (datetime.fromisoformat(cur_created_at), int(cur_id))
            )
        outer = outer.order_by(base.c.created_at.asc(), base.c.id.asc())
    else:
        if cursor is not None:
            cur_created_at, cur_id = _decode_feed_cursor(cursor)
            outer = outer.where(
                tuple_(base.c.created_at, base.c.id)
                < (datetime.fromisoformat(cur_created_at), int(cur_id))
            )
        outer = outer.order_by(base.c.created_at.desc(), base.c.id.desc())

    outer = outer.limit(limit)
    rows = list((await session.execute(outer)).all())

    next_cursor = None
    if len(rows) == limit:
        last = rows[-1]
        if sort in ("most_votes", "most_comments"):
            value = last.vote_count if sort == "most_votes" else last.comment_count
            next_cursor = _encode_feed_cursor(value, last.id)
        else:
            next_cursor = _encode_feed_cursor(last.created_at.isoformat(), last.id)
    return rows, next_cursor


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
