"""The ballot cycle: prepare, open, close, publish (DEMOCRACY.md §10).

    workshop -> prepared -> jury_review -> open -> closed -> published
                    +------------ (zero items only) -----------+

Exactly one cycle per community is in a non-published state at a time. Every
transition is timestamped and records who triggered it. In Demo 1 every
transition is a director control; the timers exist as settings and are
displayed as "would close on ..." but do not fire.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, NotFound
from backend.models import Cycle, User
from backend.repositories import cycles as cycles_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import community as community_service
from backend.services import juries as juries_service
from backend.services import rules
from backend.services import settings as settings_service

log = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "workshop": ("prepared",),
    "prepared": ("jury_review", "published"),  # `published` only with zero items
    "jury_review": ("open",),
    "open": ("closed",),
    "closed": ("published",),
    "published": (),
}


async def prepare(
    session: AsyncSession, *, level: str, entity_id: int, admin: User
) -> dict:
    """DEMOCRACY.md §10.2. A snapshot, not a live status."""
    community = await community_service.resolve(session, level, entity_id)
    existing = await cycles_repo.open_cycle_for(session, level, entity_id)
    if existing is not None:
        raise Conflict(
            f"Cycle {existing.number} for {community.label} is still "
            f"{existing.state.replace('_', ' ')}. Publish it before preparing the next one.",
            code="cycle_already_open",
        )

    values = await settings_service.snapshot_for_cycle(session)
    active_users = await community_service.active_user_count(session, level, entity_id)
    now = datetime.now(timezone.utc)

    cycle = await cycles_repo.add(
        session,
        community_level=level,
        community_entity_id=entity_id,
        number=await cycles_repo.next_number(session, level, entity_id),
        state="workshop",
        settings_snapshot=values,
        active_users_at_prepare=active_users,
        transitioned_by=[],
    )

    qualified = await _qualified_solutions(
        session, level=level, entity_id=entity_id, values=values, active_users=active_users, now=now
    )
    for position, entry in enumerate(qualified, start=1):
        solution = entry["solution"]
        await cycles_repo.add_item(
            session,
            cycle_id=cycle.id,
            solution_id=solution.id,
            solution_version=solution.current_version,
            umbrella_id=solution.umbrella_id,
            net_score_at_snapshot=solution.net_score,
            position=position,
            held_back=False,
        )
    await _transition(session, cycle, "prepared", admin.id, now)

    jury_summary = None
    if qualified:
        await _transition(session, cycle, "jury_review", admin.id, now)
        cycle.jury_review_started_at = now
        jury = await juries_service.draw(
            session, cycle=cycle, solution_ids=[e["solution"].id for e in qualified]
        )
        jurors = await cycles_repo.jurors(session, jury.id)
        jury_summary = {
            "jury_id": jury.id,
            "size_requested": jury.size_requested,
            "eligible_pool_size": len(jury.eligible_pool),
            "drawn": len(jurors),
            "note": (
                None
                if len(jurors) == jury.size_requested
                else "Fewer eligible residents than the jury size, so the jury is "
                "smaller. The published summary will say so."
            ),
        }
    await session.flush()

    log.info(
        "cycle_prepared",
        extra={
            "cycle_id": cycle.id,
            "community": f"{level}:{entity_id}",
            "items": len(qualified),
            "active_users": active_users,
        },
    )
    return {
        "cycle_id": cycle.id,
        "number": cycle.number,
        "state": cycle.state,
        "community": community.as_dict(),
        "active_users_at_prepare": active_users,
        "items": [
            {
                "solution_id": e["solution"].id,
                "version": e["solution"].current_version,
                "umbrella": e["umbrella_name"],
                "net_score": e["solution"].net_score,
            }
            for e in qualified
        ],
        "considered": [
            {
                "solution_id": e["solution"].id,
                "umbrella": e["umbrella_name"],
                "net_score": e["solution"].net_score,
                "conditions": e["conditions"],
            }
            for e in await _considered(
                session,
                level=level,
                entity_id=entity_id,
                values=values,
                active_users=active_users,
                now=now,
            )
        ],
        "jury": jury_summary,
        "zero_item_note": (
            None
            if qualified
            else "No solution qualified. Publish this cycle when ready and the next "
            "one can be prepared; no jury is drawn for an empty ballot."
        ),
    }


async def _considered(
    session: AsyncSession, *, level: str, entity_id: int, values: dict, active_users: int, now
) -> list[dict]:
    umbrellas = await umbrellas_repo.for_community(session, level, entity_id)
    names = {u.id: u.name for u in umbrellas}
    solutions = await solutions_repo.all_in_community_umbrellas(session, list(names))
    out = []
    for solution in solutions:
        _ok, conditions = rules.qualification_check(
            is_dominant_now=solution.is_dominant,
            dominant_since=solution.dominant_since,
            net_score_value=solution.net_score,
            current_version=solution.current_version,
            last_ballot_version=solution.last_ballot_version,
            now=now,
            ballot_pct=values["ballot_pct"],
            ballot_min=values["ballot_min"],
            ballot_min_dominant_days=values["ballot_min_dominant_days"],
            active_users=active_users,
        )
        out.append(
            {
                "solution": solution,
                "umbrella_name": names.get(solution.umbrella_id, ""),
                "conditions": conditions,
            }
        )
    return out


async def _qualified_solutions(
    session: AsyncSession, *, level: str, entity_id: int, values: dict, active_users: int, now
) -> list[dict]:
    """DEMOCRACY.md §7.2, evaluated at this instant, then frozen."""
    considered = await _considered(
        session, level=level, entity_id=entity_id, values=values, active_users=active_users, now=now
    )
    qualified = [entry for entry in considered if all(entry["conditions"].values())]
    qualified.sort(
        key=lambda e: rules.ballot_order_key(
            umbrella_name=e["umbrella_name"],
            net_score_at_snapshot=e["solution"].net_score,
            solution_id=e["solution"].id,
        )
    )
    return qualified


async def open_ballot(session: AsyncSession, *, cycle: Cycle, admin: User) -> dict:
    if cycle.state != "jury_review":
        raise Conflict(
            "A ballot opens from jury review.", code="cycle_wrong_state"
        )
    now = datetime.now(timezone.utc)
    # The review window closes when the ballot opens; there is no separate
    # "close review" action (DEMOCRACY.md §8.2).
    jury_result = await juries_service.apply_holdbacks(session, cycle=cycle)
    await _transition(session, cycle, "open", admin.id, now)
    cycle.opened_at = now
    await session.flush()
    items = await cycles_repo.items(session, cycle.id)
    votable = [i for i in items if not i.held_back]
    log.info(
        "ballot_opened",
        extra={"cycle_id": cycle.id, "votable": len(votable), "held_back": len(items) - len(votable)},
    )
    return {
        "cycle_id": cycle.id,
        "state": cycle.state,
        "opened_at": now,
        "would_close_on": now + timedelta(days=int(cycle.settings_snapshot["ballot_window_days"])),
        "jurors_drawn": jury_result.get("drawn", 0),
        "jurors_seated": jury_result["seated"],
        "items_votable": len(votable),
        "items_held_back": len(items) - len(votable),
        "note": (
            "In this build the ballot closes when the director closes it. The "
            "window shown is what the setting says it would be."
        ),
    }


async def close_ballot(session: AsyncSession, *, cycle: Cycle, admin: User) -> dict:
    if cycle.state != "open":
        raise Conflict("Only an open ballot can be closed.", code="cycle_wrong_state")
    now = datetime.now(timezone.utc)
    values = cycle.settings_snapshot
    tallies = await cycles_repo.item_tallies(session, cycle.id)

    results = []
    for item in await cycles_repo.items(session, cycle.id):
        if item.held_back:
            item.yes_count = None
            item.no_count = None
            item.result = "held_back"
            results.append({"ballot_item_id": item.id, "result": "held_back"})
            continue
        counts = tallies.get(item.id, {"yes": 0, "no": 0})
        item.yes_count = counts.get("yes", 0)
        item.no_count = counts.get("no", 0)
        item.result = rules.ballot_result(
            yes_count=item.yes_count,
            no_count=item.no_count,
            pass_rule=values["ballot_pass_rule"],
            quorum_min=int(values["ballot_quorum_min"]),
        )
        results.append(
            {
                "ballot_item_id": item.id,
                "yes": item.yes_count,
                "no": item.no_count,
                "result": item.result,
            }
        )

    await _record_on_solutions(session, cycle)
    await _transition(session, cycle, "closed", admin.id, now)
    cycle.closed_at = now
    await session.flush()
    log.info("ballot_closed", extra={"cycle_id": cycle.id, "items": len(results)})
    return {"cycle_id": cycle.id, "state": cycle.state, "closed_at": now, "results": results}


async def _record_on_solutions(session: AsyncSession, cycle: Cycle) -> None:
    """DEMOCRACY.md §10.5 — passed, failed and held-back alike are recorded on
    their solutions, and all three return only after a new version (§7.2
    condition 4)."""
    for item in await cycles_repo.items(session, cycle.id):
        solution = await solutions_repo.get(session, item.solution_id)
        if solution is None:
            continue
        solution.last_ballot_cycle_id = cycle.id
        solution.last_ballot_result = item.result
        solution.last_ballot_version = item.solution_version
    await session.flush()


async def publish(session: AsyncSession, *, cycle: Cycle, admin: User) -> dict:
    from backend.services import summaries as summaries_service

    item_count = await cycles_repo.count_items(session, cycle.id)
    if cycle.state == "prepared":
        if item_count:
            raise Conflict(
                "This ballot has items, so it goes through jury review and a vote "
                "before it can be published.",
                code="cycle_has_items",
            )
    elif cycle.state != "closed":
        raise Conflict(
            "A summary is published after the ballot closes, or straight from "
            "`prepared` when no solution qualified.",
            code="cycle_wrong_state",
        )

    now = datetime.now(timezone.utc)
    await _transition(session, cycle, "published", admin.id, now)
    cycle.published_at = now
    await session.flush()
    summary = await summaries_service.generate(session, cycle=cycle)
    log.info(
        "cycle_published",
        extra={"cycle_id": cycle.id, "summary_hash": summary["summary_hash"]},
    )
    return summary


async def _transition(
    session: AsyncSession, cycle: Cycle, to_state: str, by_user_id: int | None, at: datetime
) -> None:
    if to_state not in ALLOWED_TRANSITIONS[cycle.state]:
        raise Conflict(
            f"A cycle cannot go from {cycle.state} to {to_state}.",
            code="bad_cycle_transition",
        )
    cycle.state = to_state
    cycle.transitioned_by = list(cycle.transitioned_by or []) + [
        {"state": to_state, "at": at.isoformat(), "by": by_user_id or "system"}
    ]
    if to_state == "prepared":
        cycle.prepared_at = at
    await session.flush()


async def for_community(session: AsyncSession, level: str, entity_id: int) -> dict:
    community = await community_service.resolve(session, level, entity_id)
    rows = await cycles_repo.for_community(session, level, entity_id)
    return {
        "community": community.as_dict(),
        "cycles": [
            {
                "id": c.id,
                "number": c.number,
                "state": c.state,
                "prepared_at": c.prepared_at,
                "opened_at": c.opened_at,
                "closed_at": c.closed_at,
                "published_at": c.published_at,
            }
            for c in rows
        ],
    }


async def require_cycle(session: AsyncSession, cycle_id: int) -> Cycle:
    cycle = await cycles_repo.get(session, cycle_id)
    if cycle is None:
        raise NotFound("That ballot cycle does not exist.", code="cycle_not_found")
    return cycle


async def view(session: AsyncSession, cycle: Cycle) -> dict:
    community = await community_service.resolve(
        session, cycle.community_level, cycle.community_entity_id
    )
    jury = await cycles_repo.jury_for_cycle(session, cycle.id)
    jurors = await cycles_repo.jurors(session, jury.id) if jury else []
    return {
        "id": cycle.id,
        "number": cycle.number,
        "state": cycle.state,
        "community": community.as_dict(),
        "active_users_at_prepare": cycle.active_users_at_prepare,
        "settings_in_force": cycle.settings_snapshot,
        "prepared_at": cycle.prepared_at,
        "jury_review_started_at": cycle.jury_review_started_at,
        "opened_at": cycle.opened_at,
        "closed_at": cycle.closed_at,
        "published_at": cycle.published_at,
        "transitions": cycle.transitioned_by,
        "item_count": await cycles_repo.count_items(session, cycle.id),
        "jury": (
            {
                "drawn": len(jurors),
                "seated": jury.seated_count,
                "size_requested": jury.size_requested,
                "eligible_pool_size": len(jury.eligible_pool),
            }
            if jury
            else None
        ),
        "would_close_on": (
            cycle.opened_at + timedelta(days=int(cycle.settings_snapshot["ballot_window_days"]))
            if cycle.opened_at
            else None
        ),
    }
