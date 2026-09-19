"""Writing the AI action log, and turning it into the plain-English action list
an umbrella page shows (DEMOCRACY.md §9.2, §9.5).

CLAUDE.md Law 7: every AI action is a row, written before its result is shown.
This module is the only place rows are created, so no AI result can reach a
person without one.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings_env import get_env_settings
from backend.models import AiAction
from backend.repositories import ai_actions as ai_repo
from backend.repositories import posts as posts_repo
from backend.repositories import references as references_repo
from backend.repositories import solutions as solutions_repo
from backend.services import hashing


async def record(
    session: AsyncSession,
    *,
    action_type: str,
    subject_type: str,
    subject_id: int,
    model: str,
    prompt_file: str,
    prompt_hash: str,
    model_input: Any,
    output: dict[str, Any],
    confidence: float | None = None,
) -> AiAction:
    """One row, written before the result is shown to anyone."""
    return await ai_repo.add(
        session,
        action_type=action_type,
        subject_type=subject_type,
        subject_id=subject_id,
        demo_build=get_env_settings().BUILD_LABEL,
        model=model,
        prompt_file=prompt_file,
        prompt_hash=prompt_hash,
        input_hash=hashing.hash_payload(model_input),
        output=output,
        confidence=confidence,
    )


async def page(
    session: AsyncSession,
    *,
    cursor: int | None,
    limit: int,
    subject_type: str | None = None,
    subject_id: int | None = None,
    action_type: str | None = None,
):
    return await ai_repo.page(
        session,
        cursor=cursor,
        limit=limit,
        subject_type=subject_type,
        subject_id=subject_id,
        action_type=action_type,
    )


async def record_outcome(
    session: AsyncSession, *, action_id: int | None, outcome: str, user_id: int
) -> None:
    if action_id is None:
        return
    await ai_repo.record_outcome(
        session, action_id=action_id, outcome=outcome, user_id=user_id
    )


async def umbrella_action_list(session: AsyncSession, umbrella_id: int) -> dict[str, Any]:
    """DEMOCRACY.md §9.5 — an action list, not a percentage, generated from the
    AI action log at page render."""
    label_rows = await posts_repo.labels_for_umbrella(session, umbrella_id)
    post_ids = await posts_repo.post_ids_for_umbrella(session, umbrella_id)
    total_reports = len(set(post_ids))
    ai_labeled = [row for row in label_rows if row.ai_action_id is not None]
    confirmed = sum(1 for row in ai_labeled if row.outcome == "confirmed_by_author")
    corrected = sum(1 for row in ai_labeled if row.outcome == "corrected_by_author")
    unreviewed = sum(1 for row in ai_labeled if row.outcome == "unreviewed")

    solution_ids = await solutions_repo.ids_in_umbrella(session, umbrella_id)
    amendment_ids = await solutions_repo.amendment_ids_for_solutions(session, solution_ids)
    pairs = await solutions_repo.similarities_for_amendment_ids(session, amendment_ids)
    same = sum(1 for p in pairs if p.decision == "same")
    different = sum(1 for p in pairs if p.decision == "different")

    references = await references_repo.for_umbrella(session, umbrella_id)
    ai_refs = [r for r in references if r.source == "ai"]
    rejected_refs = sum(1 for r in ai_refs if r.status == "rejected")
    useful_refs = len(ai_refs) - rejected_refs

    sentence = (
        f"AI on this umbrella: {len(ai_labeled)} of {total_reports} problem "
        f"report{'s' if total_reports != 1 else ''} "
        f"{'were' if len(ai_labeled) != 1 else 'was'} AI-labeled "
        f"({confirmed} confirmed, {corrected} corrected, {unreviewed} unreviewed); "
        f"{len(pairs)} amendment pair{'s' if len(pairs) != 1 else ''} "
        f"{'were' if len(pairs) != 1 else 'was'} flagged similar "
        f"({same} confirmed same, {different} different); "
        f"{len(ai_refs)} of {len(references)} "
        f"reference{'s' if len(references) != 1 else ''} "
        f"{'were' if len(ai_refs) != 1 else 'was'} AI-recommended "
        f"({useful_refs} still listed, {rejected_refs} rejected)."
    )
    return {
        "sentence": sentence,
        "problem_reports_total": total_reports,
        "problem_reports_ai_labeled": len(ai_labeled),
        "labels_confirmed": confirmed,
        "labels_corrected": corrected,
        "labels_unreviewed": unreviewed,
        "amendment_pairs_flagged": len(pairs),
        "amendment_pairs_same": same,
        "amendment_pairs_different": different,
        "references_total": len(references),
        "references_ai": len(ai_refs),
        "references_ai_rejected": rejected_refs,
    }


AI_INFLUENCE_LABEL = "AI assistance on this platform: 0%"
AI_INFLUENCE_EXPLANATION = (
    "This is the share of the text that was written by AI the platform "
    "provided. This build offers no AI writing help, so it is 0% everywhere. "
    "Text somebody pasted in from an AI tool elsewhere cannot be detected, and "
    "this figure does not claim otherwise."
)


def influence(percentage: int) -> dict[str, Any]:
    """DEMOCRACY.md §9.5 — shown on every post, solution, comment and amendment."""
    return {
        "ai_contribution_percentage": percentage,
        "label": f"AI assistance on this platform: {percentage}%",
        "explanation": AI_INFLUENCE_EXPLANATION,
    }
