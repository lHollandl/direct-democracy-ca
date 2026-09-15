"""Amendments: how a dominant solution changes (DEMOCRACY.md §5).

An amendment is a complete replacement text plus a one-line rationale. It can
be proposed only on a **dominant** solution, by anyone in the community except
the author of the solution's current version — the person who wrote the text
does not get to rewrite it through the amendment machinery.

When enough of the solution's supporters back an amendment it is **absorbed**:
a new version of the solution is created with the amendment's text, and every
other proposed amendment on that solution becomes `superseded`, because they
were all written against a text that no longer exists.

Nothing is ever deleted.
"""

from __future__ import annotations

import difflib
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Conflict, Forbidden, NotFound, ValidationFailed
from backend.models import Amendment, Solution, User
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import hashing
from backend.services import rules
from backend.services import settings as settings_service
from backend.services import similarity as similarity_service
from backend.services import solutions as solutions_service
from backend.services.display import author_displays

log = logging.getLogger(__name__)

MIN_RATIONALE = 10
MAX_RATIONALE = 300


async def propose(
    session: AsyncSession, *, solution: Solution, author: User, text: str, rationale: str
) -> Amendment:
    if not solution.is_dominant:
        raise Conflict(
            "Amendments can only be proposed on dominant solutions. Upvote this one "
            "to help it get there, or propose a better solution of your own.",
            code="solution_not_dominant",
        )
    current = await solutions_repo.current_version(session, solution.id)
    if current is None:
        raise NotFound("That solution has no text.", code="solution_version_missing")
    if current.created_by == author.id:
        raise Forbidden(
            "You wrote the text that is in place now, so you cannot amend it. "
            "Someone else in the community can.",
            code="author_of_current_version",
        )
    clean_text = solutions_service.validate_text(text, "An amendment")
    clean_rationale = rationale.strip()
    if not MIN_RATIONALE <= len(clean_rationale) <= MAX_RATIONALE:
        raise ValidationFailed(
            f"The reason for your change needs to be between {MIN_RATIONALE} and "
            f"{MAX_RATIONALE} characters.",
            code="bad_rationale",
        )
    if clean_text == current.text_body:
        raise ValidationFailed(
            "That is the text the solution already has.", code="amendment_no_change"
        )

    now = datetime.now(timezone.utc)
    amendment = await solutions_repo.add_amendment(
        session,
        solution_id=solution.id,
        base_version=current.version,
        author_id=author.id,
        proposed_text=clean_text,
        rationale=clean_rationale,
        status="proposed",
        net_score=0,
        ai_contribution_percentage=0,
        content_hash=hashing.amendment_content_hash(
            solution_id=solution.id,
            base_version=current.version,
            author_id=author.id,
            proposed_text=clean_text,
            rationale=clean_rationale,
            created_at=now,
        ),
        created_at=now,
    )
    log.info(
        "amendment_proposed",
        extra={"amendment_id": amendment.id, "solution_id": solution.id},
    )
    _schedule_similarity_check(session, amendment.id)
    return amendment


def _schedule_similarity_check(session: AsyncSession, amendment_id: int) -> None:
    """The service that owns the transaction schedules the job (ARCHITECTURE.md
    §7; resolves audit demo-01 run 1's ambiguity 1)."""
    from backend.jobs import runner
    from backend.jobs import similarity as similarity_job

    runner.spawn_after_commit(
        session,
        lambda: similarity_job.similarity_check_task(amendment_id),
        name=f"similarity_check:{amendment_id}",
    )


async def withdraw(session: AsyncSession, *, amendment: Amendment, user: User) -> None:
    """DEMOCRACY.md §5.2 — by its author, only while its net score is below the
    absorption threshold."""
    if amendment.author_id != user.id:
        raise Forbidden("Only the person who proposed it can withdraw it.", code="not_the_author")
    if amendment.status != "proposed":
        raise Conflict(
            f"That amendment is already {amendment.status.replace('_', ' ')}.",
            code="amendment_not_proposed",
        )
    needed = await absorption_threshold_for(session, amendment.solution_id)
    if amendment.net_score >= needed:
        raise Conflict(
            "Enough people have backed this amendment that it is no longer yours "
            "to withdraw.",
            code="amendment_has_support",
        )
    amendment.status = "withdrawn"
    await session.flush()


async def absorption_threshold_for(session: AsyncSession, solution_id: int) -> int:
    values = await settings_service.all_values(session)
    supporters = await solutions_repo.supporters(session, solution_id)
    return rules.absorption_threshold(
        amendment_pct=values["amendment_pct"],
        amendment_min=values["amendment_min"],
        supporters=supporters,
    )


async def effective_supporters(session: AsyncSession, amendment: Amendment) -> set[int]:
    """The amendment's own upvoters, plus the upvoters of every amendment merged
    into it. A person who upvoted both counts once (DEMOCRACY.md §5.4)."""
    ids: set[int] = set()
    for amendment_id in [amendment.id] + [
        merged.id for merged in await solutions_repo.merged_into(session, amendment.id)
    ]:
        upvoters, _down = await _upvoters(session, amendment_id)
        ids |= upvoters
    return ids


async def _upvoters(session: AsyncSession, amendment_id: int) -> tuple[set[int], set[int]]:
    return await votes_repo.direction_sets(session, "amendment", amendment_id)


async def evaluate_absorption(session: AsyncSession, amendment: Amendment) -> dict:
    """DEMOCRACY.md §5.3, evaluated on every vote event on the amendment."""
    solution = await solutions_repo.get(session, amendment.solution_id)
    if solution is None:
        raise NotFound("That amendment's solution is missing.", code="solution_not_found")
    needed = await absorption_threshold_for(session, solution.id)
    supporters = await solutions_repo.supporters(session, solution.id)

    if amendment.status != "proposed":
        return {
            "absorbed": amendment.status == "absorbed",
            "absorption_threshold": needed,
            "solution_supporters": supporters,
            "status": amendment.status,
        }

    # Amendments merged into this one bring their upvoters with them.
    combined = len(await effective_supporters(session, amendment))
    _up, down = await _upvoters(session, amendment.id)
    effective_score = combined - len(down)

    if effective_score < needed:
        return {
            "absorbed": False,
            "absorption_threshold": needed,
            "solution_supporters": supporters,
            "effective_net_score": effective_score,
            "status": amendment.status,
        }

    version = await absorb(session, solution=solution, amendment=amendment)
    return {
        "absorbed": True,
        "absorption_threshold": needed,
        "solution_supporters": supporters,
        "effective_net_score": effective_score,
        "new_version": version,
        "status": amendment.status,
    }


async def absorb(session: AsyncSession, *, solution: Solution, amendment: Amendment) -> int:
    """One transaction: new version, amendment marked absorbed, every other
    proposed amendment on this solution superseded (DEMOCRACY.md §5.3).

    No AI action is logged. This is a human action.
    """
    version = await solutions_service.add_version(
        session,
        solution=solution,
        text=amendment.proposed_text,
        created_by=amendment.author_id,
        amendment_id=amendment.id,
    )
    amendment.status = "absorbed"
    amendment.absorbed_as_version = version
    for other in await solutions_repo.amendments_for(session, solution.id, status="proposed"):
        if other.id != amendment.id:
            other.status = "superseded"
    await session.flush()
    log.info(
        "amendment_absorbed",
        extra={
            "amendment_id": amendment.id,
            "solution_id": solution.id,
            "new_version": version,
        },
    )
    return version


def diff(before: str, after: str) -> list[dict[str, str]]:
    """The platform renders the diff against the current version (§5.1).

    Word-level, so the reader sees what actually changed rather than two
    paragraphs side by side.
    """
    matcher = difflib.SequenceMatcher(None, before.split(), after.split())
    out: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append({"kind": "same", "text": " ".join(before.split()[i1:i2])})
        elif tag == "delete":
            out.append({"kind": "removed", "text": " ".join(before.split()[i1:i2])})
        elif tag == "insert":
            out.append({"kind": "added", "text": " ".join(after.split()[j1:j2])})
        else:
            out.append({"kind": "removed", "text": " ".join(before.split()[i1:i2])})
            out.append({"kind": "added", "text": " ".join(after.split()[j1:j2])})
    return [part for part in out if part["text"]]


async def require_amendment(session: AsyncSession, amendment_id: int) -> Amendment:
    amendment = await solutions_repo.get_amendment(session, amendment_id)
    if amendment is None:
        raise NotFound("That amendment does not exist.", code="amendment_not_found")
    return amendment


async def community_of(session: AsyncSession, amendment: Amendment) -> tuple[str, int]:
    solution = await solutions_repo.get(session, amendment.solution_id)
    if solution is None:
        raise NotFound("That amendment's solution is missing.", code="solution_not_found")
    return await community_of_solution(session, solution)


async def community_of_solution(session: AsyncSession, solution: Solution) -> tuple[str, int]:
    umbrella = await umbrellas_repo.get(session, solution.umbrella_id)
    if umbrella is None:
        raise NotFound("That solution's umbrella is missing.", code="umbrella_not_found")
    return umbrella.community_level, umbrella.community_entity_id


async def list_for_solution(session: AsyncSession, solution: Solution) -> dict:
    """`GET /solutions/{id}/amendments` — the whole response (ARCHITECTURE.md
    §2/§10: one service call per router endpoint beyond a `require_*`
    resolver)."""
    rows = await solutions_repo.amendments_for(session, solution.id)
    current = await solutions_repo.current_version(session, solution.id)
    text = current.text_body if current else ""
    displays = await author_displays(session, [a.author_id for a in rows])
    return {
        "solution_id": solution.id,
        "current_version": solution.current_version,
        "absorption_threshold": await absorption_threshold_for(session, solution.id),
        "supporters": await solutions_repo.supporters(session, solution.id),
        "amendments": [
            {
                "id": a.id,
                "author": displays.get(a.author_id, "Former Community Member"),
                "proposed_text": a.proposed_text,
                "rationale": a.rationale,
                "status": a.status,
                "base_version": a.base_version,
                "absorbed_as_version": a.absorbed_as_version,
                "merged_into_id": a.merged_into_id,
                "net_score": a.net_score,
                "diff": diff(text, a.proposed_text),
                "created_at": a.created_at,
            }
            for a in rows
        ],
        "similar_pairs": await similarity_service.pairs_for_solution(session, solution.id),
    }
