"""The summary document: the platform's output (DEMOCRACY.md §11). Public."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from backend.config.settings_env import get_env_settings
from backend.deps import SessionDep, VerifiedUser
from backend.routers.common import CursorParam, DEFAULT_LIMIT, LimitParam
from backend.services import summaries as summaries_service

router = APIRouter(tags=["summaries"])


@router.get("/summaries/hashes")
async def hash_list(
    session: SessionDep, cursor: CursorParam = None, limit: LimitParam = DEFAULT_LIMIT
) -> dict:
    page = await summaries_service.hash_list(session, cursor=cursor, limit=limit)
    return {
        "explanation": (
            "Every document this platform has published, with its fingerprint. "
            "Download any document's JSON, run SHA-256 over it, and compare."
        ),
        "summaries": page["items"],
        "next_cursor": page["next_cursor"],
    }


@router.get("/results")
async def my_results(user: VerifiedUser, session: SessionDep) -> dict:
    return await summaries_service.for_user(session, user=user)


@router.get("/summaries/{level}/{entity_id}/{number}")
async def summary_page(
    level: str, entity_id: int, number: int, session: SessionDep
) -> dict:
    return await summaries_service.by_community_and_number(
        session, level=level, entity_id=entity_id, number=number
    )


@router.get("/summaries/{level}/{entity_id}/{number}/json", response_class=PlainTextResponse)
async def summary_json(
    level: str, entity_id: int, number: int, session: SessionDep
) -> PlainTextResponse:
    """Exactly the bytes the fingerprint was computed over."""
    cycle = await summaries_service.require_cycle_by_number(
        session, level=level, entity_id=entity_id, number=number
    )
    text = await summaries_service.canonical_json(session, cycle=cycle)
    return PlainTextResponse(
        text,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="summary-{level}-{entity_id}-{number}.json"'
            )
        },
    )


@router.get("/summaries/{level}/{entity_id}/{number}/verify")
async def summary_verify(
    level: str, entity_id: int, number: int, session: SessionDep
) -> dict:
    cycle = await summaries_service.require_cycle_by_number(
        session, level=level, entity_id=entity_id, number=number
    )
    return await summaries_service.verify(session, cycle=cycle)


@router.get("/summaries/{level}/{entity_id}/{number}/pdf")
async def summary_pdf(
    level: str, entity_id: int, number: int, session: SessionDep
) -> Response:
    cycle = await summaries_service.require_cycle_by_number(
        session, level=level, entity_id=entity_id, number=number
    )
    url = get_env_settings().absolute_url(f"/summaries/{level}/{entity_id}/{number}")
    payload = await summaries_service.pdf_bytes(session, cycle=cycle, url=url)
    return Response(
        payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="ballot-results-{level}-{entity_id}-{number}.pdf"'
            )
        },
    )
