"""
AI labeling pipeline for Direct Democracy Cali.

Called as a FastAPI background task after every post is saved. Runs AFTER
the HTTP response has already been sent — the user never waits for AI.
Posts always save regardless of whether this function succeeds or fails.

Architecture (see TODO.md — "Core Architecture — Category and Umbrella System"):
  - Labeling a post and assigning it to an umbrella problem are THE SAME action.
  - Subcategory = umbrella problem. When AI picks a subcategory, that IS the umbrella.
  - AI always assigns to the CLOSEST existing umbrella — no minimum threshold.
  - If no umbrellas exist for the post's governance level, the post is flagged
    "Pending Human Review". The AI never creates new umbrella problems.
  - Only humans create new umbrella problems through the democratic proposal system.
"""

import json
import logging
import os
import sys

import httpx
from sqlalchemy.orm import Session

# The backend/ directory is on sys.path because uvicorn runs from there.
# These imports work correctly when label_and_assign_post is called from
# within the backend FastAPI process.
#
# If running this file standalone (e.g. for testing), set PYTHONPATH to
# include the backend/ directory:  PYTHONPATH=../backend python labeler.py
from config.categories import MAIN_CATEGORIES
from database import SessionLocal
from models import Label, PostUmbrellaIssue, Solution, UmbrellaIssue

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT_SECONDS = 30


async def label_and_assign_post(
    post_id: int,
    title: str,
    content: str,
    locations: list[dict],
) -> None:
    """
    Entry point called by FastAPI BackgroundTasks after a post is saved.

    locations is a list of dicts: [{"location_type": "city", "location_id": 1}, ...]

    Opens its own database session — the request-scoped session passed by the
    route handler is closed by FastAPI before background tasks run.

    Six steps:
    1. Query existing umbrella problems for this post's governance levels.
    2. Build the Ollama prompt and call llama3.2.
    3. Parse and validate the AI response.
    4. Save a Label row (category = main category, subcategory = umbrella title).
    5. Create PostUmbrellaIssue link and update Solution.umbrella_issue_id.
    6. Log the result.
    """
    db = SessionLocal()
    try:
        await _run_labeling(post_id, title, content, locations, db)
    except Exception as exc:
        # Last-resort catch — something unexpected bypassed our internal error handlers.
        # Save a fallback label so every post always has a label row (constitution law).
        logger.exception(
            "Unexpected error in label_and_assign_post for post_id=%s: %s", post_id, exc
        )
        _save_fallback_label(post_id, db)
    finally:
        db.close()


async def _run_labeling(
    post_id: int,
    title: str,
    content: str,
    locations: list[dict],
    db: Session,
) -> None:
    """Core labeling logic. Separated so the outer function can catch all exceptions cleanly."""

    # -------------------------------------------------------------------------
    # Step 1 — Collect existing umbrella problems for this post's governance levels.
    # Query all umbrella issues matching any location this post was submitted under.
    # -------------------------------------------------------------------------
    umbrella_issues: list[UmbrellaIssue] = []
    for loc in locations:
        loc_type = loc["location_type"]
        loc_id = loc.get("location_id")

        query = db.query(UmbrellaIssue).filter(UmbrellaIssue.location_type == loc_type)
        if loc_id is not None:
            query = query.filter(UmbrellaIssue.location_id == loc_id)
        else:
            # Federal umbrella issues have location_id NULL
            query = query.filter(UmbrellaIssue.location_id.is_(None))

        umbrella_issues.extend(query.all())

    # Deduplicate — same umbrella might match multiple location filters
    seen_ids: set[int] = set()
    unique_umbrellas: list[UmbrellaIssue] = []
    for ui in umbrella_issues:
        if ui.id not in seen_ids:
            seen_ids.add(ui.id)
            unique_umbrellas.append(ui)

    # -------------------------------------------------------------------------
    # Step 2 — Build the Ollama prompt and call llama3.2.
    # -------------------------------------------------------------------------
    if unique_umbrellas:
        # Format: "42: \"Road Damage and Pothole Repair\", 17: \"Broken Streetlights\""
        umbrella_list_text = ", ".join(
            f'{ui.id}: "{ui.title}"' for ui in unique_umbrellas
        )
    else:
        umbrella_list_text = "EMPTY"

    prompt = f"""You are a civic issue classifier for California government.

Title: {title}
Content: {content}

Step 1 - Choose the single best main category from this exact list:
{", ".join(MAIN_CATEGORIES)}

Step 2 - You will be given a list of existing umbrella problems. Choose the single most similar one to this post, no matter how similar or dissimilar it seems. You must always pick the closest match. Never leave this blank.
Existing umbrella problems: {umbrella_list_text}
If the list is EMPTY respond with: NONE

Respond with ONLY a valid JSON object, no other text:
{{
  "main_category": "exact name from main category list",
  "umbrella_id": the integer id of the closest matching umbrella problem or null if list was EMPTY,
  "umbrella_match_reasoning": "one sentence explaining why this is the closest match",
  "confidence": a number from 0 to 100
}}"""

    # -------------------------------------------------------------------------
    # Call Ollama. If it is down or slow, fall back gracefully — never fail the post.
    # -------------------------------------------------------------------------
    ai_response: dict | None = None
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            raw_text = response.json().get("response", "")
            ai_response = _parse_json_response(raw_text)

    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.error("Ollama unreachable or timed out for post_id=%s: %s", post_id, exc)
        _save_fallback_label(post_id, db)
        return

    except Exception as exc:
        logger.error("Unexpected error calling Ollama for post_id=%s: %s", post_id, exc)
        _save_fallback_label(post_id, db)
        return

    if ai_response is None:
        logger.error("Ollama returned unparseable JSON for post_id=%s", post_id)
        _save_fallback_label(post_id, db)
        return

    # -------------------------------------------------------------------------
    # Step 3 — Validate the AI response fields.
    # -------------------------------------------------------------------------
    main_category = ai_response.get("main_category", "")
    if main_category not in MAIN_CATEGORIES:
        # AI returned something not in the approved list — find the closest match.
        # This guards against minor formatting errors (e.g. "Roads & Infrastructure").
        main_category = _closest_category(main_category)

    raw_umbrella_id = ai_response.get("umbrella_id")
    confidence = max(0, min(100, int(ai_response.get("confidence", 0))))

    # Convert to int if AI returned it as a string
    umbrella_id: int | None = None
    if raw_umbrella_id is not None:
        try:
            umbrella_id = int(raw_umbrella_id)
        except (ValueError, TypeError):
            umbrella_id = None

    # Verify the returned umbrella_id actually exists — AI can hallucinate IDs
    matched_umbrella: UmbrellaIssue | None = None
    if umbrella_id is not None:
        matched_umbrella = db.query(UmbrellaIssue).filter(
            UmbrellaIssue.id == umbrella_id
        ).first()
        if matched_umbrella is None:
            logger.warning(
                "AI returned non-existent umbrella_id=%s for post_id=%s — treating as no match",
                umbrella_id,
                post_id,
            )
            umbrella_id = None

    # Determine the subcategory string to store in the Label row.
    # Subcategory = umbrella problem title, or the pending-review sentinel.
    if matched_umbrella is not None:
        subcategory = matched_umbrella.title
    else:
        # Either no umbrellas exist yet for this governance level, or the AI
        # returned an invalid ID. Flag for human review either way.
        subcategory = "Pending Human Review"

    # -------------------------------------------------------------------------
    # Step 4 — Save the Label row (labeling and umbrella assignment are one action).
    # -------------------------------------------------------------------------
    label = Label(
        post_id=post_id,
        category=main_category,
        subcategory=subcategory,
        confidence_score=confidence,
        created_by_ai=True,
        confirmed_by_user=False,
    )
    db.add(label)
    # Flush to get label.id before committing, in case we need it for debugging
    db.flush()

    # -------------------------------------------------------------------------
    # Step 5 — Create PostUmbrellaIssue and update Solution.umbrella_issue_id.
    # Both happen in the same transaction — the post is either fully assigned or not.
    # -------------------------------------------------------------------------
    if matched_umbrella is not None:
        db.add(PostUmbrellaIssue(
            post_id=post_id,
            umbrella_issue_id=matched_umbrella.id,
        ))
        # Update the solution so it appears in the umbrella's solution rankings
        solution = db.query(Solution).filter(Solution.post_id == post_id).first()
        if solution is not None:
            solution.umbrella_issue_id = matched_umbrella.id

    db.commit()

    # -------------------------------------------------------------------------
    # Step 6 — Log the outcome for observability.
    # -------------------------------------------------------------------------
    logger.info(
        "Labeled post_id=%s: category=%r subcategory=%r umbrella_id=%s confidence=%s",
        post_id,
        main_category,
        subcategory,
        matched_umbrella.id if matched_umbrella else None,
        confidence,
    )


def _parse_json_response(text: str) -> dict | None:
    """
    Extract the first JSON object from the AI's response text.
    llama3.2 sometimes wraps output in markdown backticks or adds explanation text
    before or after the JSON object. We strip everything outside { ... }.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _closest_category(ai_category: str) -> str:
    """
    If the AI returns a main_category string not in MAIN_CATEGORIES, find the
    closest official category by substring matching. Falls back to the first
    category if nothing matches. This rarely triggers — it guards against minor
    AI formatting errors like 'Roads & Infrastructure' vs 'Roads and Infrastructure'.
    """
    ai_lower = ai_category.lower()
    for cat in MAIN_CATEGORIES:
        if cat.lower() in ai_lower or ai_lower in cat.lower():
            return cat
    logger.warning(
        "AI returned unknown category %r — falling back to %r", ai_category, MAIN_CATEGORIES[0]
    )
    return MAIN_CATEGORIES[0]


def _save_fallback_label(post_id: int, db: Session) -> None:
    """
    Save a minimal label row when Ollama is unavailable or returns invalid data.
    Constitution law: posts must always have a label row for transparency.
    This satisfies that requirement while flagging the post for human review.
    Never raises — it is called from error handlers where raising would swallow the
    original error.
    """
    try:
        existing = db.query(Label).filter(Label.post_id == post_id).first()
        if existing is None:
            db.add(Label(
                post_id=post_id,
                category="Unlabeled",
                subcategory="Pending Review",
                confidence_score=0,
                created_by_ai=True,
                confirmed_by_user=False,
            ))
            db.commit()
    except Exception as exc:
        # Roll back so the session is left in a usable state — the outer finally
        # block closes it, but an explicit rollback here prevents PendingRollbackError
        # if anything attempts to use the session again before close.
        db.rollback()
        logger.exception(
            "Failed to save fallback label for post_id=%s: %s", post_id, exc
        )
