"""Iteration's contribution to a user's data export (DATABASE.md §3.11).

Registered with Foundation's registry at startup, so Foundation's export code
never names an Iteration table (ARCHITECTURE.md §2).

This includes the person's **own ballot votes**, which are shown to nobody else
— not to other voters, and not to administrators.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories import comments as comments_repo
from backend.repositories import cycles as cycles_repo
from backend.repositories import posts as posts_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import votes as votes_repo


async def contribute(session: AsyncSession, user_id: int) -> dict:
    posts = await posts_repo.by_author(session, user_id)
    solutions = await solutions_repo.by_author(session, user_id)

    ballot_votes = []
    for vote in await cycles_repo.ballot_votes_of_user(session, user_id):
        item = await cycles_repo.get_item(session, vote.ballot_item_id)
        ballot_votes.append(
            {
                "cycle_id": item.cycle_id if item else None,
                "ballot_item_id": vote.ballot_item_id,
                "solution_id": item.solution_id if item else None,
                "your_choice": vote.choice,
                "your_verification_level_at_the_time": vote.voter_verification_level,
                "cast_at": vote.created_at,
                "last_changed_at": vote.updated_at,
            }
        )

    jury_service = []
    for juror, jury, _cycle in await cycles_repo.jury_duties_for_user(session, user_id):
        holdbacks = await cycles_repo.holdbacks_for_juror(session, juror.id)
        jury_service.append(
            {
                "cycle_id": jury.cycle_id,
                "seat": juror.seat,
                "status": juror.status,
                "hold_backs": [
                    {
                        "ballot_item_id": h.ballot_item_id,
                        "category": h.reason_category,
                        "reason": h.reason_text,
                    }
                    for h in holdbacks
                ],
            }
        )

    return {
        "posts": [
            {
                "id": post.id,
                "problem_text": post.problem_text,
                "created_at": post.created_at,
                "content_hash": post.content_hash,
                "label_status": post.label_status,
                "solution_texts": [
                    {"position": row.position, "text": row.text_body, "content_hash": row.content_hash}
                    for row in await posts_repo.solution_texts(session, post.id)
                ],
            }
            for post in posts
        ],
        "solutions_you_started": [
            {
                "id": solution.id,
                "umbrella_id": solution.umbrella_id,
                "current_version": solution.current_version,
                "net_score": solution.net_score,
                "versions": [
                    {"version": v.version, "text": v.text_body, "content_hash": v.content_hash}
                    for v in await solutions_repo.versions(session, solution.id)
                ],
            }
            for solution in solutions
        ],
        "amendments_you_proposed": [
            {
                "id": a.id,
                "solution_id": a.solution_id,
                "proposed_text": a.proposed_text,
                "rationale": a.rationale,
                "status": a.status,
                "content_hash": a.content_hash,
            }
            for a in await solutions_repo.amendments_by_author(session, user_id)
        ],
        "comments_you_wrote": [
            {
                "id": c.id,
                "target_type": c.target_type,
                "target_id": c.target_id,
                "text": c.text_body,
                "created_at": c.created_at,
                "removed": c.removed_at is not None,
            }
            for c in await comments_repo.by_author(session, user_id)
        ],
        "workshop_votes": [
            {
                "target_type": v.target_type,
                "target_id": v.target_id,
                "direction": "up" if v.direction == 1 else "down",
                "cast_at": v.created_at,
            }
            for v in await votes_repo.user_votes(session, user_id)
        ],
        "your_ballot_votes": ballot_votes,
        "your_ballot_votes_note": (
            "These are yours alone. No other endpoint on this platform returns a "
            "ballot vote with a voter attached to it, including to administrators."
        ),
        "jury_service": jury_service,
    }
