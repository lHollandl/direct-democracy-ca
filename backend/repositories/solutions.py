"""Solutions, their versions and their amendments (DATABASE.md §4.7-§4.10)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Amendment,
    AmendmentSimilarity,
    AmendmentSimilarityVote,
    Solution,
    SolutionVersion,
    Vote,
)


async def get(session: AsyncSession, solution_id: int) -> Solution | None:
    return await session.get(Solution, solution_id)


async def add(session: AsyncSession, **fields) -> Solution:
    row = Solution(**fields)
    session.add(row)
    await session.flush()
    return row


async def add_version(session: AsyncSession, **fields) -> SolutionVersion:
    row = SolutionVersion(**fields)
    session.add(row)
    await session.flush()
    return row


async def versions(session: AsyncSession, solution_id: int) -> list[SolutionVersion]:
    return list(
        (
            await session.execute(
                select(SolutionVersion)
                .where(SolutionVersion.solution_id == solution_id)
                .order_by(SolutionVersion.version)
            )
        )
        .scalars()
        .all()
    )


async def version_at(
    session: AsyncSession, solution_id: int, version: int
) -> SolutionVersion | None:
    return (
        await session.execute(
            select(SolutionVersion).where(
                SolutionVersion.solution_id == solution_id,
                SolutionVersion.version == version,
            )
        )
    ).scalar_one_or_none()


async def current_version(session: AsyncSession, solution_id: int) -> SolutionVersion | None:
    return (
        await session.execute(
            select(SolutionVersion)
            .where(SolutionVersion.solution_id == solution_id)
            .order_by(SolutionVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def current_versions(
    session: AsyncSession, solution_ids: list[int]
) -> dict[int, SolutionVersion]:
    if not solution_ids:
        return {}
    latest = (
        select(
            SolutionVersion.solution_id,
            func.max(SolutionVersion.version).label("version"),
        )
        .where(SolutionVersion.solution_id.in_(set(solution_ids)))
        .group_by(SolutionVersion.solution_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(SolutionVersion).join(
                latest,
                (SolutionVersion.solution_id == latest.c.solution_id)
                & (SolutionVersion.version == latest.c.version),
            )
        )
    ).scalars().all()
    return {row.solution_id: row for row in rows}


async def in_umbrella(session: AsyncSession, umbrella_id: int) -> list[Solution]:
    """DEMOCRACY.md §3.3 item 4 — net score descending, ties oldest first.
    Nothing is ever hidden."""
    return list(
        (
            await session.execute(
                select(Solution)
                .where(Solution.umbrella_id == umbrella_id, Solution.deleted_at.is_(None))
                .order_by(Solution.net_score.desc(), Solution.created_at, Solution.id)
            )
        )
        .scalars()
        .all()
    )


async def dominant_in_umbrella(session: AsyncSession, umbrella_id: int) -> list[Solution]:
    return list(
        (
            await session.execute(
                select(Solution)
                .where(
                    Solution.umbrella_id == umbrella_id,
                    Solution.is_dominant.is_(True),
                    Solution.deleted_at.is_(None),
                )
                .order_by(Solution.net_score.desc(), Solution.created_at)
            )
        )
        .scalars()
        .all()
    )


async def for_post(session: AsyncSession, post_id: int) -> list[Solution]:
    return list(
        (
            await session.execute(
                select(Solution).where(Solution.post_id == post_id).order_by(Solution.id)
            )
        )
        .scalars()
        .all()
    )


async def for_post_community(
    session: AsyncSession, post_id: int, umbrella_id: int
) -> list[Solution]:
    return list(
        (
            await session.execute(
                select(Solution).where(
                    Solution.post_id == post_id, Solution.umbrella_id == umbrella_id
                )
            )
        )
        .scalars()
        .all()
    )


async def all_in_community_umbrellas(
    session: AsyncSession, umbrella_ids: list[int]
) -> list[Solution]:
    if not umbrella_ids:
        return []
    return list(
        (
            await session.execute(
                select(Solution).where(
                    Solution.umbrella_id.in_(set(umbrella_ids)),
                    Solution.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )


async def all_solutions(session: AsyncSession) -> list[Solution]:
    return list(
        (await session.execute(select(Solution).where(Solution.deleted_at.is_(None))))
        .scalars()
        .all()
    )


async def by_ids(session: AsyncSession, ids: list[int]) -> dict[int, Solution]:
    if not ids:
        return {}
    rows = (
        await session.execute(select(Solution).where(Solution.id.in_(set(ids))))
    ).scalars().all()
    return {row.id: row for row in rows}


async def supporters(session: AsyncSession, solution_id: int) -> int:
    """DEMOCRACY.md §4.5 — distinct users with a current upvote."""
    return int(
        (
            await session.execute(
                select(func.count(func.distinct(Vote.user_id))).where(
                    Vote.target_type == "solution",
                    Vote.target_id == solution_id,
                    Vote.direction == 1,
                )
            )
        ).scalar_one()
    )


async def supporter_ids(session: AsyncSession, solution_id: int) -> set[int]:
    rows = (
        await session.execute(
            select(Vote.user_id).where(
                Vote.target_type == "solution",
                Vote.target_id == solution_id,
                Vote.direction == 1,
            )
        )
    ).scalars().all()
    return set(rows)


# --- amendments -----------------------------------------------------------


async def add_amendment(session: AsyncSession, **fields) -> Amendment:
    row = Amendment(**fields)
    session.add(row)
    await session.flush()
    return row


async def get_amendment(session: AsyncSession, amendment_id: int) -> Amendment | None:
    return await session.get(Amendment, amendment_id)


async def amendments_for(
    session: AsyncSession, solution_id: int, status: str | None = None
) -> list[Amendment]:
    stmt = select(Amendment).where(Amendment.solution_id == solution_id)
    if status:
        stmt = stmt.where(Amendment.status == status)
    return list((await session.execute(stmt.order_by(Amendment.id))).scalars().all())


async def amendments_for_page(
    session: AsyncSession, solution_id: int, *, cursor: int | None, limit: int
) -> list[Amendment]:
    """`GET /solutions/{id}/amendments` (ARCHITECTURE.md §6, audit demo-01
    run 3 HIGH). The solution's own detail page keeps embedding the whole,
    unpaginated set via `amendments_for()` — this is only the dedicated,
    ever-growing list."""
    stmt = select(Amendment).where(Amendment.solution_id == solution_id)
    if cursor is not None:
        stmt = stmt.where(Amendment.id > cursor)
    stmt = stmt.order_by(Amendment.id).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def amendments_by_author(session: AsyncSession, author_id: int) -> list[Amendment]:
    return list(
        (
            await session.execute(
                select(Amendment).where(Amendment.author_id == author_id).order_by(Amendment.id)
            )
        )
        .scalars()
        .all()
    )


async def count_amendments(session: AsyncSession, solution_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(Amendment).where(
                    Amendment.solution_id == solution_id
                )
            )
        ).scalar_one()
    )


async def proposed_amendment_authors_for_solutions(
    session: AsyncSession, solution_ids: list[int]
) -> set[int]:
    if not solution_ids:
        return set()
    rows = (
        await session.execute(
            select(Amendment.author_id).where(
                Amendment.solution_id.in_(set(solution_ids)),
                Amendment.status == "proposed",
            )
        )
    ).scalars().all()
    return set(rows)


# --- similarity -----------------------------------------------------------


async def add_similarity(session: AsyncSession, **fields) -> AmendmentSimilarity:
    row = AmendmentSimilarity(**fields)
    session.add(row)
    await session.flush()
    return row


async def get_similarity(session: AsyncSession, similarity_id: int) -> AmendmentSimilarity | None:
    return await session.get(AmendmentSimilarity, similarity_id)


async def similarities_for_solution(
    session: AsyncSession, solution_id: int
) -> list[AmendmentSimilarity]:
    amendment_ids = select(Amendment.id).where(Amendment.solution_id == solution_id)
    return list(
        (
            await session.execute(
                select(AmendmentSimilarity).where(
                    AmendmentSimilarity.amendment_a_id.in_(amendment_ids)
                )
            )
        )
        .scalars()
        .all()
    )


async def add_similarity_vote(
    session: AsyncSession, *, similarity_id: int, user_id: int, choice: str
) -> AmendmentSimilarityVote:
    existing = await session.get(AmendmentSimilarityVote, (similarity_id, user_id))
    if existing is not None:
        existing.choice = choice
        await session.flush()
        return existing
    row = AmendmentSimilarityVote(
        similarity_id=similarity_id, user_id=user_id, choice=choice
    )
    session.add(row)
    await session.flush()
    return row


async def similarity_votes(
    session: AsyncSession, similarity_id: int
) -> list[AmendmentSimilarityVote]:
    return list(
        (
            await session.execute(
                select(AmendmentSimilarityVote).where(
                    AmendmentSimilarityVote.similarity_id == similarity_id
                )
            )
        )
        .scalars()
        .all()
    )


async def merged_into(session: AsyncSession, amendment_id: int) -> list[Amendment]:
    return list(
        (
            await session.execute(
                select(Amendment).where(Amendment.merged_into_id == amendment_id)
            )
        )
        .scalars()
        .all()
    )


async def by_author(session: AsyncSession, author_id: int) -> list[Solution]:
    return list(
        (
            await session.execute(
                select(Solution).where(Solution.author_id == author_id).order_by(Solution.id)
            )
        )
        .scalars()
        .all()
    )


async def version_authors_for_solutions(session: AsyncSession, solution_ids: list[int]) -> set[int]:
    if not solution_ids:
        return set()
    rows = (
        await session.execute(
            select(SolutionVersion.created_by).where(
                SolutionVersion.solution_id.in_(set(solution_ids))
            )
        )
    ).scalars().all()
    return set(rows)


async def ids_in_umbrella(session: AsyncSession, umbrella_id: int) -> list[int]:
    return list(
        (
            await session.execute(
                select(Solution.id).where(Solution.umbrella_id == umbrella_id)
            )
        )
        .scalars()
        .all()
    )


async def amendment_ids_for_solutions(session: AsyncSession, solution_ids: list[int]) -> list[int]:
    if not solution_ids:
        return []
    return list(
        (
            await session.execute(
                select(Amendment.id).where(Amendment.solution_id.in_(set(solution_ids)))
            )
        )
        .scalars()
        .all()
    )


async def similarities_for_amendment_ids(
    session: AsyncSession, amendment_ids: list[int]
) -> list[AmendmentSimilarity]:
    if not amendment_ids:
        return []
    return list(
        (
            await session.execute(
                select(AmendmentSimilarity).where(
                    AmendmentSimilarity.amendment_a_id.in_(set(amendment_ids))
                )
            )
        )
        .scalars()
        .all()
    )
