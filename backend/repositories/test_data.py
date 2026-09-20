"""Everything `backend/services/test_data.py` needs to find and remove a
reserved-domain test account's rows (ARCHITECTURE.md §2, §3)."""

from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Amendment, Comment, Juror, Post, Solution, TermsAcceptance, User, Vote


async def account_ids_at_domain(session: AsyncSession, domain: str) -> list[int]:
    rows = (
        await session.execute(select(User.id).where(User.email.ilike(f"%@{domain}")))
    ).scalars().all()
    return list(rows)


async def posts_by_authors(session: AsyncSession, author_ids: list[int]) -> list[int]:
    if not author_ids:
        return []
    return list(
        (await session.execute(select(Post.id).where(Post.author_id.in_(author_ids))))
        .scalars()
        .all()
    )


async def solutions_by_authors(session: AsyncSession, author_ids: list[int]) -> list[int]:
    if not author_ids:
        return []
    return list(
        (await session.execute(select(Solution.id).where(Solution.author_id.in_(author_ids))))
        .scalars()
        .all()
    )


async def comments_by_authors(session: AsyncSession, author_ids: list[int]) -> list[int]:
    if not author_ids:
        return []
    return list(
        (await session.execute(select(Comment.id).where(Comment.author_id.in_(author_ids))))
        .scalars()
        .all()
    )


async def amendments_by_authors(session: AsyncSession, author_ids: list[int]) -> list[int]:
    if not author_ids:
        return []
    return list(
        (await session.execute(select(Amendment.id).where(Amendment.author_id.in_(author_ids))))
        .scalars()
        .all()
    )


async def comments_replying_to(
    session: AsyncSession, parent_ids: list[int], *, excluding_authors: list[int]
) -> list[tuple[int, int]]:
    if not parent_ids:
        return []
    rows = await session.execute(
        select(Comment.id, Comment.author_id).where(
            Comment.parent_id.in_(parent_ids), Comment.author_id.notin_(excluding_authors)
        )
    )
    return list(rows.all())


async def comment_ids_replying_to(session: AsyncSession, parent_ids: list[int]) -> list[int]:
    if not parent_ids:
        return []
    return list(
        (await session.execute(select(Comment.id).where(Comment.parent_id.in_(parent_ids))))
        .scalars()
        .all()
    )


async def comments_on_solutions(
    session: AsyncSession, solution_ids: list[int], *, excluding_authors: list[int] | None = None
) -> list[tuple[int, int]]:
    if not solution_ids:
        return []
    stmt = select(Comment.id, Comment.author_id).where(
        Comment.target_type == "solution", Comment.target_id.in_(solution_ids)
    )
    if excluding_authors is not None:
        stmt = stmt.where(Comment.author_id.notin_(excluding_authors))
    return list((await session.execute(stmt)).all())


async def amendments_on_solutions(
    session: AsyncSession, solution_ids: list[int], *, excluding_authors: list[int] | None = None
) -> list[tuple[int, int]]:
    if not solution_ids:
        return []
    stmt = select(Amendment.id, Amendment.author_id).where(
        Amendment.solution_id.in_(solution_ids)
    )
    if excluding_authors is not None:
        stmt = stmt.where(Amendment.author_id.notin_(excluding_authors))
    return list((await session.execute(stmt)).all())


async def votes_on_solutions_or_amendments(
    session: AsyncSession,
    *,
    solution_ids: list[int],
    amendment_ids: list[int],
    excluding_users: list[int],
) -> list[tuple[int, int, str]]:
    if not solution_ids and not amendment_ids:
        return []
    conditions = []
    if solution_ids:
        conditions.append((Vote.target_type == "solution") & Vote.target_id.in_(solution_ids))
    if amendment_ids:
        conditions.append((Vote.target_type == "amendment") & Vote.target_id.in_(amendment_ids))
    rows = await session.execute(
        select(Vote.id, Vote.user_id, Vote.target_type).where(
            or_(*conditions), Vote.user_id.notin_(excluding_users)
        )
    )
    return list(rows.all())


async def votes_on_comments(
    session: AsyncSession, comment_ids: list[int], *, excluding_users: list[int]
) -> list[tuple[int, int]]:
    if not comment_ids:
        return []
    rows = await session.execute(
        select(Vote.id, Vote.user_id).where(
            Vote.target_type == "comment",
            Vote.target_id.in_(comment_ids),
            Vote.user_id.notin_(excluding_users),
        )
    )
    return list(rows.all())


async def jurors_among(session: AsyncSession, user_ids: list[int]) -> list[tuple[int, int]]:
    if not user_ids:
        return []
    rows = await session.execute(
        select(Juror.id, Juror.user_id).where(Juror.user_id.in_(user_ids))
    )
    return list(rows.all())


async def delete_votes(
    session: AsyncSession,
    *,
    user_ids: list[int],
    solution_ids: list[int],
    amendment_ids: list[int],
    comment_ids: list[int],
) -> int:
    conditions = [Vote.user_id.in_(user_ids)] if user_ids else []
    if solution_ids:
        conditions.append((Vote.target_type == "solution") & Vote.target_id.in_(solution_ids))
    if amendment_ids:
        conditions.append((Vote.target_type == "amendment") & Vote.target_id.in_(amendment_ids))
    if comment_ids:
        conditions.append((Vote.target_type == "comment") & Vote.target_id.in_(comment_ids))
    if not conditions:
        return 0
    result = await session.execute(delete(Vote).where(or_(*conditions)))
    return result.rowcount or 0


async def delete_comments(session: AsyncSession, comment_ids: list[int]) -> int:
    if not comment_ids:
        return 0
    result = await session.execute(delete(Comment).where(Comment.id.in_(comment_ids)))
    return result.rowcount or 0


async def delete_amendments(session: AsyncSession, amendment_ids: list[int]) -> int:
    if not amendment_ids:
        return 0
    result = await session.execute(delete(Amendment).where(Amendment.id.in_(amendment_ids)))
    return result.rowcount or 0


async def delete_solutions(session: AsyncSession, solution_ids: list[int]) -> int:
    if not solution_ids:
        return 0
    result = await session.execute(delete(Solution).where(Solution.id.in_(solution_ids)))
    return result.rowcount or 0


async def delete_posts(session: AsyncSession, post_ids: list[int]) -> int:
    if not post_ids:
        return 0
    result = await session.execute(delete(Post).where(Post.id.in_(post_ids)))
    return result.rowcount or 0


async def delete_accounts(session: AsyncSession, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    await session.execute(delete(TermsAcceptance).where(TermsAcceptance.user_id.in_(user_ids)))
    result = await session.execute(delete(User).where(User.id.in_(user_ids)))
    return result.rowcount or 0
