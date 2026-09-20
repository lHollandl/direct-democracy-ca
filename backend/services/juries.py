"""The citizen jury (DEMOCRACY.md §8).

Three residents, drawn at random from the community's active users, look at
every solution that qualified for the ballot. They cannot change anything and
cannot add anything. The only thing a juror can do is **hold a solution back**,
with a written public reason. A hold-back takes effect when more than half of
the seated jurors held the same solution back, counted once when the ballot
opens.

The draw is logged in full — the eligible pool, the drawn ids, the timestamp and
the random bytes used — so anyone can inspect it afterwards. Provably
reproducible draws are parked (PROJECT.md).
"""

from __future__ import annotations

import logging
import random
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound, ValidationFailed
from backend.models import Cycle, Jury, Juror, User
from backend.repositories import cycles as cycles_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import users as users_repo
from backend.services import community as community_service
from backend.services import rules
from backend.services import settings as settings_service

log = logging.getLogger(__name__)

MIN_REASON = 20
MAX_REASON = 1000
REASON_CATEGORIES = (
    "duplicate",
    "not_actionable",
    "incomplete",
    "outside_governance_level",
    "other",
)


async def eligible_pool(
    session: AsyncSession, *, cycle: Cycle, solution_ids: list[int]
) -> list[int]:
    """DEMOCRACY.md §8.1 — active users of the community, minus everyone with a
    stake in what is on this ballot, minus admins."""
    window_days = int(await settings_service.get(session, "active_user_window_days"))
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    candidates = await users_repo.active_member_ids(
        session,
        cycle.community_level,
        cycle.community_entity_id,
        cutoff,
        exclude_admins=True,
    )

    excluded: set[int] = set()
    if solution_ids:
        # Anyone who authored any version of a qualified solution.
        excluded |= await solutions_repo.version_authors_for_solutions(session, solution_ids)
        solutions_by_id = await solutions_repo.by_ids(session, solution_ids)
        excluded |= {s.author_id for s in solutions_by_id.values()}
        excluded |= await solutions_repo.proposed_amendment_authors_for_solutions(
            session, solution_ids
        )

    no_repeat = int(await settings_service.get(session, "jury_no_repeat_cycles"))
    excluded |= await cycles_repo.previous_jury_user_ids(
        session, cycle.community_level, cycle.community_entity_id, no_repeat
    )

    return sorted(uid for uid in candidates if uid not in excluded)


async def draw(
    session: AsyncSession, *, cycle: Cycle, solution_ids: list[int], reason: str | None = None
) -> Jury:
    """Draw `jury_size` jurors, replayably (DEMOCRACY.md §8.1; TODO D2-00,
    audit-6 MEDIUM). 32 bytes from the platform's cryptographic random source
    are logged and **seed** the sampler — `random.Random` seeded from the
    bytes, sampling the pool sorted by id — so anyone with the logged pool
    and the logged bytes can reproduce the exact drawn ids. Demo 1 logged the
    bytes without using them to drive the draw; `secrets.SystemRandom()` drew
    from true randomness the log could never replay."""
    size = int(await settings_service.get(session, "jury_size"))
    pool = await eligible_pool(session, cycle=cycle, solution_ids=solution_ids)
    random_bytes = secrets.token_hex(32)
    rng = random.Random(int(random_bytes, 16))
    drawn = rng.sample(pool, min(size, len(pool)))

    jury = await cycles_repo.add_jury(
        session,
        cycle_id=cycle.id,
        size_requested=size,
        eligible_pool=pool,
        random_bytes=random_bytes,
        drawn_at=datetime.now(timezone.utc),
        redrawn_reason=reason,
    )
    for seat, user_id in enumerate(drawn, start=1):
        await cycles_repo.add_juror(
            session, jury_id=jury.id, user_id=user_id, seat=seat, status="drawn"
        )
    await session.flush()
    log.info(
        "jury_drawn",
        extra={
            "cycle_id": cycle.id,
            "jury_id": jury.id,
            "pool_size": len(pool),
            "drawn": len(drawn),
            "requested": size,
        },
    )
    return jury


async def redraw(session: AsyncSession, *, cycle: Cycle, reason: str) -> Jury:
    """Director control, only while the cycle is in jury review, logged with a
    reason (DEMOCRACY.md §13)."""
    if cycle.state != "jury_review":
        raise Conflict(
            "A jury can only be redrawn while the cycle is in jury review.",
            code="cycle_not_in_jury_review",
        )
    existing = await cycles_repo.jury_for_cycle(session, cycle.id)
    if existing is not None:
        for juror in await cycles_repo.jurors(session, existing.id):
            if juror.status in ("drawn", "accepted"):
                juror.status = "replaced"
        await session.flush()
        # The superseded draw is kept, not deleted — its pool, drawn ids,
        # random bytes and jurors' statuses stay inspectable (DEMOCRACY.md
        # §8.1, §13; audit demo-01 run 2).
        await cycles_repo.supersede_jury(session, existing, reason=reason)
    items = await cycles_repo.items(session, cycle.id)
    return await draw(
        session, cycle=cycle, solution_ids=[i.solution_id for i in items], reason=reason
    )


async def accept(session: AsyncSession, *, juror: Juror, user: User) -> Juror:
    if juror.user_id != user.id:
        raise Forbidden("That jury seat is not yours.", code="not_your_seat")
    if juror.status not in ("drawn",):
        raise Conflict(
            f"You have already answered: {juror.status.replace('_', ' ')}.",
            code="juror_already_answered",
        )
    juror.status = "accepted"
    await session.flush()
    return juror


async def decline(session: AsyncSession, *, juror: Juror, user: User) -> dict:
    """A decline draws a replacement from the remaining pool immediately
    (DEMOCRACY.md §8.2)."""
    if juror.user_id != user.id:
        raise Forbidden("That jury seat is not yours.", code="not_your_seat")
    if juror.status not in ("drawn",):
        raise Conflict(
            f"You have already answered: {juror.status.replace('_', ' ')}.",
            code="juror_already_answered",
        )
    juror.status = "declined"
    jury = await cycles_repo.get_jury(session, juror.jury_id)
    if jury is None:
        raise NotFound("That jury no longer exists.", code="jury_not_found")

    taken = {j.user_id for j in await cycles_repo.jurors(session, jury.id)}
    remaining = [uid for uid in jury.eligible_pool if uid not in taken]
    replacement = None
    if remaining:
        rng = secrets.SystemRandom()
        chosen = rng.choice(remaining)
        replacement = await cycles_repo.add_juror(
            session, jury_id=jury.id, user_id=chosen, seat=juror.seat, status="drawn"
        )
        juror.replaced_by_id = replacement.id
    await session.flush()
    log.info(
        "juror_declined",
        extra={"juror_id": juror.id, "replacement_id": replacement.id if replacement else None},
    )
    return {
        "declined": juror.id,
        "replacement_drawn": replacement is not None,
        "note": (
            "Thank you for answering quickly — someone else has been drawn."
            if replacement
            else "Nobody else in the community was eligible, so the jury is smaller. "
            "The published summary will say so."
        ),
    }


async def hold_back(
    session: AsyncSession,
    *,
    juror: Juror,
    user: User,
    ballot_item_id: int,
    category: str,
    reason_text: str,
) -> dict:
    if juror.user_id != user.id:
        raise Forbidden("That jury seat is not yours.", code="not_your_seat")
    if juror.status != "accepted":
        raise Forbidden(
            "Accept your jury duty before reviewing the ballot.", code="juror_not_seated"
        )
    if category not in REASON_CATEGORIES:
        raise ValidationFailed(
            "Choose one of the listed reasons for holding a solution back.",
            code="bad_reason_category",
        )
    clean = reason_text.strip()
    if not MIN_REASON <= len(clean) <= MAX_REASON:
        raise ValidationFailed(
            f"Your reason must be between {MIN_REASON} and {MAX_REASON:,} characters. "
            "It is published with the results, so the community can judge it.",
            code="bad_reason_text",
        )
    item = await cycles_repo.get_item(session, ballot_item_id)
    if item is None:
        raise NotFound("That ballot item does not exist.", code="ballot_item_not_found")
    jury = await cycles_repo.get_jury(session, juror.jury_id)
    if jury is None or item.cycle_id != jury.cycle_id:
        raise Forbidden("That item is not on the ballot you are reviewing.", code="wrong_ballot")
    cycle = await cycles_repo.get(session, item.cycle_id)
    if cycle is None or cycle.state != "jury_review":
        raise Conflict(
            "Jury review for this ballot has closed.", code="jury_review_closed"
        )
    if await cycles_repo.holdback_for(session, juror.id, ballot_item_id) is not None:
        raise Conflict("You have already held that item back.", code="already_held_back")

    await cycles_repo.add_holdback(
        session,
        jury_id=jury.id,
        juror_id=juror.id,
        ballot_item_id=ballot_item_id,
        reason_category=category,
        reason_text=clean,
    )
    log.info(
        "juror_held_back", extra={"juror_id": juror.id, "ballot_item_id": ballot_item_id}
    )
    return {
        "ballot_item_id": ballot_item_id,
        "note": (
            "Recorded. Jurors do not see each other's hold-backs until the ballot "
            "opens. Your reason will be published with the results."
        ),
    }


async def apply_holdbacks(session: AsyncSession, *, cycle: Cycle) -> dict:
    """Counted once, when the ballot is opened (DEMOCRACY.md §8.3).

    Jurors who never answered are marked `no_response`, are not seated, and are
    not replaced; the jury is the seated jurors.
    """
    jury = await cycles_repo.jury_for_cycle(session, cycle.id)
    if jury is None:
        return {"seated": 0, "held_back": []}
    jurors = await cycles_repo.jurors(session, jury.id)
    for juror in jurors:
        if juror.status == "drawn":
            juror.status = "no_response"
    seated = [j for j in jurors if j.status == "accepted"]
    jury.seated_count = len(seated)
    seated_ids = {j.id for j in seated}

    counts: dict[int, int] = {}
    for holdback in await cycles_repo.holdbacks(session, jury.id):
        if holdback.juror_id in seated_ids:
            counts[holdback.ballot_item_id] = counts.get(holdback.ballot_item_id, 0) + 1

    held = []
    for item in await cycles_repo.items(session, cycle.id):
        if rules.holdback_takes_effect(
            holdbacks_from_seated=counts.get(item.id, 0), seated_jurors=len(seated)
        ):
            item.held_back = True
            item.result = "held_back"
            held.append(item.id)
    await session.flush()
    log.info(
        "holdbacks_applied",
        extra={"cycle_id": cycle.id, "seated": len(seated), "held_back": len(held)},
    )
    return {"seated": len(seated), "held_back": held, "drawn": len(jurors)}


async def duties_for(session: AsyncSession, user: User) -> list[dict]:
    """`GET /juries/mine` — what this person has been asked to do."""
    out = []
    for juror, jury, cycle in await cycles_repo.jury_duties_for_user(session, user.id):
        community = await community_service.resolve(
            session, cycle.community_level, cycle.community_entity_id
        )
        items = []
        if juror.status == "accepted" and cycle.state == "jury_review":
            items = await review_items(session, cycle=cycle, juror=juror)
        out.append(
            {
                "juror_id": juror.id,
                "seat": juror.seat,
                "status": juror.status,
                "cycle_id": cycle.id,
                "cycle_number": cycle.number,
                "cycle_state": cycle.state,
                "community": community.as_dict(),
                "what_you_can_do": (
                    "You can look at every solution that qualified and, for any of "
                    "them, hold it back with a written reason that will be "
                    "published. You cannot change anything, and you cannot add "
                    "anything. Doing nothing is a valid answer."
                ),
                # The timer exists as a setting and is displayed as "would close
                # on ..." but does not fire in Demo 1 (DEMOCRACY.md §10.1).
                "would_close_on": jury_review_would_close_on(cycle),
                "items": items,
            }
        )
    return out


def jury_review_would_close_on(cycle: Cycle) -> datetime | None:
    """`jury_review_started_at + jury_review_days`, from the settings snapshot
    recorded on the cycle at prepare (DEMOCRACY.md §10.1, §8.2)."""
    if cycle.jury_review_started_at is None:
        return None
    return cycle.jury_review_started_at + timedelta(
        days=int(cycle.settings_snapshot["jury_review_days"])
    )


async def review_items(session: AsyncSession, *, cycle: Cycle, juror: Juror) -> list[dict]:
    """What a seated juror sees: every qualified solution with its frozen text,
    its umbrella, its net score and its amendment history (DEMOCRACY.md §8.3)."""
    items = await cycles_repo.items(session, cycle.id)
    solutions = await solutions_repo.by_ids(session, [i.solution_id for i in items])
    umbrellas = await umbrellas_repo.by_ids(session, [i.umbrella_id for i in items])
    out = []
    for item in items:
        version = await solutions_repo.version_at(
            session, item.solution_id, item.solution_version
        )
        solution = solutions.get(item.solution_id)
        amendments = await solutions_repo.amendments_for(session, item.solution_id)
        mine = await cycles_repo.holdback_for(session, juror.id, item.id)
        out.append(
            {
                "ballot_item_id": item.id,
                "position": item.position,
                "umbrella": umbrellas[item.umbrella_id].name
                if item.umbrella_id in umbrellas
                else None,
                "frozen_text": version.text_body if version else "",
                "frozen_version": item.solution_version,
                "frozen_hash": version.content_hash if version else None,
                "net_score_at_snapshot": item.net_score_at_snapshot,
                "current_net_score": solution.net_score if solution else None,
                "amendment_history": [
                    {
                        "id": a.id,
                        "rationale": a.rationale,
                        "status": a.status,
                        "absorbed_as_version": a.absorbed_as_version,
                    }
                    for a in amendments
                ],
                "previous_holdback_reasons": await previous_holdback_reasons(
                    session, item.solution_id, cycle.id
                ),
                "my_holdback": (
                    {"category": mine.reason_category, "reason": mine.reason_text}
                    if mine
                    else None
                ),
                "reason_categories": list(REASON_CATEGORIES),
            }
        )
    return out


async def jury_notes_for_solution(session: AsyncSession, solution_id: int) -> dict | None:
    """"Jury notes" on the solution page, from the moment the ballot opens
    (DEMOCRACY.md §8.3): every seated juror's category and reason for this
    solution's current ballot item, whether or not the hold-back reached a
    majority. `None` before the ballot has opened, or once it has and no
    juror held the item back."""
    found = await cycles_repo.current_ballot_item_for_solution(session, solution_id)
    if found is None:
        return None
    item, cycle = found
    jury = await cycles_repo.jury_for_cycle(session, cycle.id)
    if jury is None:
        return None
    jurors = await cycles_repo.jurors(session, jury.id)
    seated = [j for j in jurors if j.status == "accepted"]
    seat_numbers = {j.id: n for n, j in enumerate(seated, start=1)}
    notes = [
        {
            "juror": f"Juror {seat_numbers[h.juror_id]} of {len(seated)}",
            "category": h.reason_category,
            "reason": h.reason_text,
        }
        for h in await cycles_repo.holdbacks(session, jury.id)
        if h.ballot_item_id == item.id and h.juror_id in seat_numbers
    ]
    if not notes:
        return None
    return {"cycle_number": cycle.number, "seated": len(seated), "notes": notes}


async def previous_holdback_reasons(
    session: AsyncSession, solution_id: int, current_cycle_id: int
) -> list[dict]:
    """A hold-back is feedback; the next jury sees it (DEMOCRACY.md §8.4)."""
    rows = await cycles_repo.holdback_history_for_solution(
        session, solution_id, current_cycle_id
    )
    return [
        {
            "cycle_id": item.cycle_id,
            "category": holdback.reason_category,
            "reason": holdback.reason_text,
            "solution_version": item.solution_version,
        }
        for holdback, item in rows
    ]


async def admin_user_view(session: AsyncSession, user_id: int) -> dict:
    """`GET /admin/users/{id}` — verification level and jury history. **Never
    ballot votes** — a ballot vote is visible only to the voter who cast it
    (DEMOCRACY.md §13)."""
    user = await users_repo.get(session, user_id)
    if user is None:
        raise NotFound("No such account.", code="user_not_found")
    duties = []
    for juror, jury, cycle in await cycles_repo.jury_duties_for_user(session, user_id):
        community = await community_service.resolve(
            session, cycle.community_level, cycle.community_entity_id
        )
        duties.append(
            {
                "cycle_id": cycle.id,
                "cycle_number": cycle.number,
                "community": community.as_dict(),
                "seat": juror.seat,
                "status": juror.status,
            }
        )
    return {
        "id": user.id,
        "display_name": user.display_name,
        "verification_level": user.verification_level,
        "email_verified": user.email_verified_at is not None,
        "deleted": user.deleted_at is not None,
        "is_admin": user.is_admin,
        "last_active_at": user.last_active_at,
        "jury_history": duties,
        "ballot_votes": (
            "Not available to anyone but the voter. This endpoint never returns "
            "them, by design (DEMOCRACY.md §13)."
        ),
    }


async def redraw_for_admin(
    session: AsyncSession, *, cycle: Cycle, reason: str, admin: User
) -> dict:
    """`POST /admin/cycles/{id}/redraw-jury` — redraws and writes the admin
    log row in one service call (ARCHITECTURE.md §2/§10)."""
    old_jury = await cycles_repo.jury_for_cycle(session, cycle.id)
    jury = await redraw(session, cycle=cycle, reason=reason)
    jurors = await cycles_repo.jurors(session, jury.id)

    from backend.services import admin_log

    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="redraw_jury",
        subject_type="cycle",
        subject_id=cycle.id,
        old_value={"jury_id": old_jury.id if old_jury else None},
        new_value={"jury_id": jury.id, "drawn": len(jurors)},
        reason=reason,
    )
    return {
        "jury_id": jury.id,
        "drawn": len(jurors),
        "reason": reason,
    }


async def require_juror(session: AsyncSession, juror_id: int) -> Juror:
    juror = await cycles_repo.get_juror(session, juror_id)
    if juror is None:
        raise NotFound("That jury seat does not exist.", code="juror_not_found")
    return juror
