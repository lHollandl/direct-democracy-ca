"""Cycles, ballot items, ballot votes, juries and summaries (§4.14-§4.18).

One repository per aggregate (ARCHITECTURE.md §2): the ballot cycle owns its
items, its votes, its jury and its summary, so they live together here.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    BallotItem,
    BallotVote,
    Cycle,
    Jury,
    Juror,
    JuryHoldback,
    Summary,
)


# --- cycles ---------------------------------------------------------------


async def get(session: AsyncSession, cycle_id: int) -> Cycle | None:
    return await session.get(Cycle, cycle_id)


async def add(session: AsyncSession, **fields) -> Cycle:
    row = Cycle(**fields)
    session.add(row)
    await session.flush()
    return row


async def open_cycle_for(session: AsyncSession, level: str, entity_id: int) -> Cycle | None:
    """The one cycle per community that is not yet published (DATABASE.md §4.14)."""
    return (
        await session.execute(
            select(Cycle).where(
                Cycle.community_level == level,
                Cycle.community_entity_id == entity_id,
                Cycle.state != "published",
            )
        )
    ).scalar_one_or_none()


async def for_community(session: AsyncSession, level: str, entity_id: int) -> list[Cycle]:
    return list(
        (
            await session.execute(
                select(Cycle)
                .where(Cycle.community_level == level, Cycle.community_entity_id == entity_id)
                .order_by(Cycle.number.desc())
            )
        )
        .scalars()
        .all()
    )


async def by_number(
    session: AsyncSession, level: str, entity_id: int, number: int
) -> Cycle | None:
    return (
        await session.execute(
            select(Cycle).where(
                Cycle.community_level == level,
                Cycle.community_entity_id == entity_id,
                Cycle.number == number,
            )
        )
    ).scalar_one_or_none()


async def next_number(session: AsyncSession, level: str, entity_id: int) -> int:
    highest = (
        await session.execute(
            select(func.max(Cycle.number)).where(
                Cycle.community_level == level, Cycle.community_entity_id == entity_id
            )
        )
    ).scalar_one()
    return int(highest or 0) + 1


async def cycles_user_can_see(session: AsyncSession, keys: list[tuple[str, int]]) -> list[Cycle]:
    if not keys:
        return []
    from sqlalchemy import or_

    return list(
        (
            await session.execute(
                select(Cycle)
                .where(
                    or_(
                        *[
                            (Cycle.community_level == level)
                            & (Cycle.community_entity_id == entity_id)
                            for level, entity_id in keys
                        ]
                    )
                )
                .order_by(Cycle.number.desc())
            )
        )
        .scalars()
        .all()
    )


# --- ballot items ---------------------------------------------------------


async def add_item(session: AsyncSession, **fields) -> BallotItem:
    row = BallotItem(**fields)
    session.add(row)
    await session.flush()
    return row


async def get_item(session: AsyncSession, item_id: int) -> BallotItem | None:
    return await session.get(BallotItem, item_id)


async def items(session: AsyncSession, cycle_id: int) -> list[BallotItem]:
    return list(
        (
            await session.execute(
                select(BallotItem)
                .where(BallotItem.cycle_id == cycle_id)
                .order_by(BallotItem.position)
            )
        )
        .scalars()
        .all()
    )


async def count_items(session: AsyncSession, cycle_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(BallotItem).where(BallotItem.cycle_id == cycle_id)
            )
        ).scalar_one()
    )


# --- ballot votes ---------------------------------------------------------


async def put_ballot_vote(
    session: AsyncSession,
    *,
    ballot_item_id: int,
    voter_id: int,
    choice: str,
    verification_level: str,
) -> BallotVote:
    row = (
        await session.execute(
            select(BallotVote).where(
                BallotVote.ballot_item_id == ballot_item_id, BallotVote.voter_id == voter_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = BallotVote(
            ballot_item_id=ballot_item_id,
            voter_id=voter_id,
            choice=choice,
            voter_verification_level=verification_level,
        )
        session.add(row)
    else:
        row.choice = choice
    await session.flush()
    return row


async def my_ballot_votes(
    session: AsyncSession, voter_id: int, item_ids: list[int]
) -> dict[int, str]:
    """The one place a ballot vote row is read with a voter id, and only ever
    for the voter themselves (DATABASE.md §4.16)."""
    if not item_ids:
        return {}
    rows = (
        await session.execute(
            select(BallotVote.ballot_item_id, BallotVote.choice).where(
                BallotVote.voter_id == voter_id,
                BallotVote.ballot_item_id.in_(set(item_ids)),
            )
        )
    ).all()
    return {int(item_id): choice for item_id, choice in rows}


async def ballot_votes_of_user(session: AsyncSession, voter_id: int) -> list[BallotVote]:
    """Only the data export calls this, for the voter's own rows."""
    return list(
        (
            await session.execute(select(BallotVote).where(BallotVote.voter_id == voter_id))
        )
        .scalars()
        .all()
    )


async def item_tallies(session: AsyncSession, cycle_id: int) -> dict[int, dict[str, int]]:
    """Counts only. No voter ids leave this function."""
    rows = (
        await session.execute(
            select(BallotVote.ballot_item_id, BallotVote.choice, func.count())
            .join(BallotItem, BallotItem.id == BallotVote.ballot_item_id)
            .where(BallotItem.cycle_id == cycle_id)
            .group_by(BallotVote.ballot_item_id, BallotVote.choice)
        )
    ).all()
    out: dict[int, dict[str, int]] = {}
    for item_id, choice, count in rows:
        out.setdefault(int(item_id), {"yes": 0, "no": 0})[choice] = int(count)
    return out


async def distinct_voters(session: AsyncSession, cycle_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count(func.distinct(BallotVote.voter_id)))
                .join(BallotItem, BallotItem.id == BallotVote.ballot_item_id)
                .where(BallotItem.cycle_id == cycle_id)
            )
        ).scalar_one()
    )


async def voter_verification_mix(session: AsyncSession, cycle_id: int) -> dict[str, int]:
    """Aggregate only — DEMOCRACY.md §11.2 item 1 prints the mix, never a name."""
    rows = (
        await session.execute(
            select(
                BallotVote.voter_verification_level,
                func.count(func.distinct(BallotVote.voter_id)),
            )
            .join(BallotItem, BallotItem.id == BallotVote.ballot_item_id)
            .where(BallotItem.cycle_id == cycle_id)
            .group_by(BallotVote.voter_verification_level)
        )
    ).all()
    return {level: int(count) for level, count in rows}


# --- juries ---------------------------------------------------------------


async def add_jury(session: AsyncSession, **fields) -> Jury:
    row = Jury(**fields)
    session.add(row)
    await session.flush()
    return row


async def jury_for_cycle(session: AsyncSession, cycle_id: int) -> Jury | None:
    """The **current** draw — the one with `superseded_at IS NULL`. A redraw
    never deletes the previous draw (DEMOCRACY.md §8.1; audit demo-01 run 2)."""
    return (
        await session.execute(
            select(Jury).where(Jury.cycle_id == cycle_id, Jury.superseded_at.is_(None))
        )
    ).scalar_one_or_none()


async def juries_for_cycle(session: AsyncSession, cycle_id: int) -> list[Jury]:
    """Every draw for this cycle, oldest first, so a reader can inspect any of
    them — not only the current one (DEMOCRACY.md §8.1)."""
    return list(
        (
            await session.execute(
                select(Jury).where(Jury.cycle_id == cycle_id).order_by(Jury.drawn_at, Jury.id)
            )
        )
        .scalars()
        .all()
    )


async def get_jury(session: AsyncSession, jury_id: int) -> Jury | None:
    return await session.get(Jury, jury_id)


async def supersede_jury(session: AsyncSession, jury: Jury, *, reason: str) -> None:
    """A redraw marks the old draw superseded; it is never deleted (DEMOCRACY.md
    §8.1, §13; audit demo-01 run 2 — the previous code deleted the row, which
    cascaded and destroyed the jurors' `replaced` status along with the pool,
    drawn ids and random bytes before anyone could inspect them)."""
    from datetime import datetime, timezone

    jury.superseded_at = datetime.now(timezone.utc)
    jury.redrawn_reason = reason
    await session.flush()


async def add_juror(session: AsyncSession, **fields) -> Juror:
    row = Juror(**fields)
    session.add(row)
    await session.flush()
    return row


async def get_juror(session: AsyncSession, juror_id: int) -> Juror | None:
    return await session.get(Juror, juror_id)


async def jurors(session: AsyncSession, jury_id: int) -> list[Juror]:
    return list(
        (
            await session.execute(
                select(Juror).where(Juror.jury_id == jury_id).order_by(Juror.seat, Juror.id)
            )
        )
        .scalars()
        .all()
    )


async def juror_for_user(session: AsyncSession, jury_id: int, user_id: int) -> Juror | None:
    return (
        await session.execute(
            select(Juror).where(Juror.jury_id == jury_id, Juror.user_id == user_id)
        )
    ).scalar_one_or_none()


async def jury_duties_for_user(session: AsyncSession, user_id: int) -> list[tuple[Juror, Jury, Cycle]]:
    rows = (
        await session.execute(
            select(Juror, Jury, Cycle)
            .join(Jury, Jury.id == Juror.jury_id)
            .join(Cycle, Cycle.id == Jury.cycle_id)
            .where(Juror.user_id == user_id)
            .order_by(Juror.id.desc())
        )
    ).all()
    return [(juror, jury, cycle) for juror, jury, cycle in rows]


async def add_holdback(session: AsyncSession, **fields) -> JuryHoldback:
    row = JuryHoldback(**fields)
    session.add(row)
    await session.flush()
    return row


async def holdback_for(
    session: AsyncSession, juror_id: int, ballot_item_id: int
) -> JuryHoldback | None:
    return (
        await session.execute(
            select(JuryHoldback).where(
                JuryHoldback.juror_id == juror_id,
                JuryHoldback.ballot_item_id == ballot_item_id,
            )
        )
    ).scalar_one_or_none()


async def holdbacks(session: AsyncSession, jury_id: int) -> list[JuryHoldback]:
    return list(
        (
            await session.execute(
                select(JuryHoldback).where(JuryHoldback.jury_id == jury_id).order_by(JuryHoldback.id)
            )
        )
        .scalars()
        .all()
    )


async def holdbacks_for_juror(session: AsyncSession, juror_id: int) -> list[JuryHoldback]:
    return list(
        (
            await session.execute(
                select(JuryHoldback).where(JuryHoldback.juror_id == juror_id)
            )
        )
        .scalars()
        .all()
    )


async def holdback_history_for_solution(
    session: AsyncSession, solution_id: int, exclude_cycle_id: int
) -> list[tuple[JuryHoldback, BallotItem]]:
    """DEMOCRACY.md §8.4 — a hold-back is feedback; the next jury sees it."""
    rows = (
        await session.execute(
            select(JuryHoldback, BallotItem)
            .join(BallotItem, BallotItem.id == JuryHoldback.ballot_item_id)
            .where(
                BallotItem.solution_id == solution_id,
                BallotItem.cycle_id != exclude_cycle_id,
            )
            .order_by(JuryHoldback.id)
        )
    ).all()
    return [(holdback, item) for holdback, item in rows]


async def current_ballot_item_for_solution(
    session: AsyncSession, solution_id: int
) -> tuple[BallotItem, Cycle] | None:
    """The most recent ballot item for this solution whose cycle has passed
    jury review — the point from which "Jury notes" is shown on the solution
    page (DEMOCRACY.md §8.3)."""
    row = (
        await session.execute(
            select(BallotItem, Cycle)
            .join(Cycle, Cycle.id == BallotItem.cycle_id)
            .where(
                BallotItem.solution_id == solution_id,
                Cycle.state.in_(("open", "closed", "published")),
            )
            .order_by(Cycle.number.desc())
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def previous_jury_user_ids(
    session: AsyncSession, level: str, entity_id: int, last_n_cycles: int
) -> set[int]:
    """Users who served on a jury for this community within the last N cycles
    (DEMOCRACY.md §8.1)."""
    if last_n_cycles <= 0:
        return set()
    recent = (
        select(Cycle.id)
        .where(Cycle.community_level == level, Cycle.community_entity_id == entity_id)
        .order_by(Cycle.number.desc())
        .limit(last_n_cycles)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Juror.user_id)
            .join(Jury, Jury.id == Juror.jury_id)
            .where(Jury.cycle_id.in_(select(recent.c.id)))
        )
    ).scalars().all()
    return set(rows)


# --- summaries ------------------------------------------------------------


async def add_summary(session: AsyncSession, **fields) -> Summary:
    row = Summary(**fields)
    session.add(row)
    await session.flush()
    return row


async def summary_for_cycle(session: AsyncSession, cycle_id: int) -> Summary | None:
    return (
        await session.execute(select(Summary).where(Summary.cycle_id == cycle_id))
    ).scalar_one_or_none()


async def published_summaries(session: AsyncSession) -> list[tuple[Summary, Cycle]]:
    rows = (
        await session.execute(
            select(Summary, Cycle)
            .join(Cycle, Cycle.id == Summary.cycle_id)
            .order_by(Summary.published_at.desc())
        )
    ).all()
    return [(s, c) for s, c in rows]


async def all_summaries(session: AsyncSession) -> list[Summary]:
    return list((await session.execute(select(Summary))).scalars().all())
