"""Similar amendments: AI suggests, humans decide (DEMOCRACY.md §5.4, §9.3).

When several people propose nearly the same change, they should count together.
Embeddings from Ollama produce a score; the score only raises a question on the
page. Nothing merges until people press **Same**.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import ollama as ollama_client
from backend.errors import Conflict, ExternalServiceDown, NotFound
from backend.models import Amendment, AmendmentSimilarity, User
from backend.repositories import solutions as solutions_repo
from backend.services import ai_log
from backend.services import settings as settings_service

log = logging.getLogger(__name__)

#: Similarity uses an embedding model, not a prompt file. The `ai_actions` row
#: still has to name a prompt file, so it names the model's own identity: there
#: is no prompt text to hash, and pretending otherwise would make the log lie.
PROMPT_FILE = "(embeddings: no prompt file)"


async def check_new_amendment(session: AsyncSession, amendment: Amendment) -> list[dict]:
    """Compare a new amendment with every other `proposed` amendment on the same
    solution. Any pair at or above `similarity_threshold` is flagged."""
    others = [
        other
        for other in await solutions_repo.amendments_for(
            session, amendment.solution_id, status="proposed"
        )
        if other.id != amendment.id
    ]
    if not others:
        return []

    threshold = float(await settings_service.get(session, "similarity_threshold"))
    client = ollama_client.get_ollama()
    try:
        mine = await client.embed(amendment.proposed_text)
    except ExternalServiceDown:
        log.warning("similarity_skipped", extra={"amendment_id": amendment.id})
        return []

    flagged = []
    for other in others:
        try:
            theirs = await client.embed(other.proposed_text)
            score = ollama_client.cosine_similarity(mine, theirs)
        except (ExternalServiceDown, ValueError):
            log.warning(
                "similarity_pair_skipped",
                extra={"amendment_id": amendment.id, "other_id": other.id},
            )
            continue

        low, high = sorted((amendment.id, other.id))
        model_input = {
            "a": {"id": low},
            "b": {"id": high},
            "text_a_hash": _text_hash(amendment if amendment.id == low else other),
            "text_b_hash": _text_hash(other if amendment.id == low else amendment),
        }
        action = await ai_log.record(
            session,
            action_type="similarity",
            subject_type="amendment",
            subject_id=high,
            model=client.embed_model_label,
            prompt_file=PROMPT_FILE,
            prompt_hash="0" * 64,
            model_input=model_input,
            output={
                "score": round(score, 3),
                "threshold": threshold,
                "flagged": score >= threshold,
                "amendment_a_id": low,
                "amendment_b_id": high,
            },
            confidence=abs(score),
        )
        if score < threshold:
            continue
        existing = [
            pair
            for pair in await solutions_repo.similarities_for_solution(
                session, amendment.solution_id
            )
            if (pair.amendment_a_id, pair.amendment_b_id) == (low, high)
        ]
        if existing:
            continue
        pair = await solutions_repo.add_similarity(
            session,
            amendment_a_id=low,
            amendment_b_id=high,
            score=Decimal(str(round(score, 3))),
            ai_action_id=action.id,
            decision="pending",
        )
        flagged.append({"similarity_id": pair.id, "score": round(score, 3), "with": other.id})
        log.info(
            "similarity_flagged",
            extra={"similarity_id": pair.id, "score": round(score, 3)},
        )
    return flagged


def _text_hash(amendment: Amendment) -> str:
    from backend.services.hashing import sha256_hex

    return sha256_hex(amendment.proposed_text)


async def decide(
    session: AsyncSession, *, similarity: AmendmentSimilarity, user: User, choice: str
) -> dict:
    """A person presses Same or Different. The AI suggested; this decides."""
    from backend.deps import require_member
    from backend.services import amendments as amendments_service

    amendment = await amendments_service.require_amendment(session, similarity.amendment_a_id)
    level, entity_id = await amendments_service.community_of(session, amendment)
    await require_member(session, user, level, entity_id)

    if similarity.decision != "pending":
        raise Conflict(
            f"That pair has already been settled as {similarity.decision}.",
            code="similarity_already_decided",
        )
    newer = await solutions_repo.get_amendment(session, similarity.amendment_b_id)
    older = await solutions_repo.get_amendment(session, similarity.amendment_a_id)
    if newer is None or older is None:
        raise NotFound("One of those amendments no longer exists.", code="amendment_not_found")

    await solutions_repo.add_similarity_vote(
        session, similarity_id=similarity.id, user_id=user.id, choice=choice
    )
    votes = await solutions_repo.similarity_votes(session, similarity.id)
    same_votes = [v for v in votes if v.choice == "same"]
    different_votes = [v for v in votes if v.choice == "different"]
    needed = int(await settings_service.get(session, "similarity_confirm_min"))

    authors = {newer.author_id, older.author_id}
    author_pressed_same = any(v.user_id in authors for v in same_votes)
    author_pressed_different = any(v.user_id in authors for v in different_votes)

    decided = None
    if len(same_votes) >= needed or author_pressed_same:
        decided = "same"
    elif len(different_votes) >= needed or author_pressed_different:
        decided = "different"

    result = {
        "similarity_id": similarity.id,
        "same_presses": len(same_votes),
        "different_presses": len(different_votes),
        "presses_needed": needed,
        "decision": similarity.decision,
        "merged_amendment_id": None,
    }
    if decided is None:
        return result

    similarity.decision = decided
    similarity.decided_at = datetime.now(timezone.utc)
    if decided == "same":
        newer.status = "merged_into"
        newer.merged_into_id = older.id
        result["merged_amendment_id"] = newer.id
    await ai_log.record_outcome(
        session,
        action_id=similarity.ai_action_id,
        outcome="accepted" if decided == "same" else "rejected",
        user_id=user.id,
    )
    await session.flush()
    result["decision"] = decided
    log.info(
        "similarity_decided",
        extra={"similarity_id": similarity.id, "decision": decided},
    )

    if decided == "same":
        # The merged amendment's upvoters now count towards the older one.
        from backend.services import amendments as amendments_service

        result["absorption"] = await amendments_service.evaluate_absorption(session, older)
    return result


async def require_similarity(session: AsyncSession, similarity_id: int) -> AmendmentSimilarity:
    similarity = await solutions_repo.get_similarity(session, similarity_id)
    if similarity is None:
        raise NotFound("That flagged pair does not exist.", code="similarity_not_found")
    return similarity


async def pairs_for_solution(session: AsyncSession, solution_id: int) -> list[dict]:
    pairs = await solutions_repo.similarities_for_solution(session, solution_id)
    out = []
    for pair in pairs:
        votes = await solutions_repo.similarity_votes(session, pair.id)
        out.append(
            {
                "id": pair.id,
                "amendment_a_id": pair.amendment_a_id,
                "amendment_b_id": pair.amendment_b_id,
                "score": float(pair.score),
                "decision": pair.decision,
                "same_presses": sum(1 for v in votes if v.choice == "same"),
                "different_presses": sum(1 for v in votes if v.choice == "different"),
                "question": (
                    f"Similar to amendment #{pair.amendment_a_id} — are these the "
                    "same change?"
                ),
                "labelled": "Flagged as similar by AI. People decide.",
            }
        )
    return out
