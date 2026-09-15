"""The summary document: the platform's output (DEMOCRACY.md §11). Public."""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from backend.deps import SessionDep, VerifiedUser
from backend.services import summaries as summaries_service

router = APIRouter(tags=["summaries"])


@router.get("/summaries/hashes")
async def hash_list(session: SessionDep) -> dict:
    return {
        "explanation": (
            "Every document this platform has published, with its fingerprint. "
            "Download any document's JSON, run SHA-256 over it, and compare."
        ),
        "summaries": await summaries_service.hash_list(session),
    }


@router.get("/results")
async def my_results(user: VerifiedUser, session: SessionDep) -> dict:
    return await summaries_service.for_user(session, user=user)


@router.get("/summaries/{level}/{entity_id}/{number}")
async def summary_page(
    level: str, entity_id: int, number: int, session: SessionDep
) -> dict:
    document = await summaries_service.by_community_and_number(
        session, level=level, entity_id=entity_id, number=number
    )
    send = document["document"]["send_to_representatives"]
    document["mailto"] = _mailto(send, level, entity_id, number, document["summary_hash"])
    return document


@router.get("/summaries/{level}/{entity_id}/{number}/json", response_class=PlainTextResponse)
async def summary_json(
    level: str, entity_id: int, number: int, session: SessionDep
) -> PlainTextResponse:
    """Exactly the bytes the fingerprint was computed over."""
    cycle = await summaries_service.cycle_for(
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
    cycle = await summaries_service.cycle_for(
        session, level=level, entity_id=entity_id, number=number
    )
    return await summaries_service.verify(session, cycle=cycle)


@router.get("/summaries/{level}/{entity_id}/{number}/pdf")
async def summary_pdf(
    level: str, entity_id: int, number: int, session: SessionDep
) -> Response:
    cycle = await summaries_service.cycle_for(
        session, level=level, entity_id=entity_id, number=number
    )
    url = f"/summaries/{level}/{entity_id}/{number}"
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


def _mailto(send: dict, level: str, entity_id: int, number: int, digest: str) -> str:
    """DEMOCRACY.md §11.5 — the user's own mail client, from their own address.
    The platform sends nothing and records nothing about the send."""
    recipients = ",".join(r["email"] for r in send["recipients"])
    url = f"/summaries/{level}/{entity_id}/{number}"
    body = (
        "I am a resident of this community. These are the results of our ballot "
        "this cycle, voted on by residents and published in full:\n\n"
        f"{url}\n\n"
        f"Document fingerprint (SHA-256): {digest}\n\n"
        "The page explains every rule that produced these results and how to "
        "check that the document has not been altered.\n"
    )
    query = urllib.parse.urlencode(
        {"subject": send["subject"], "body": body}, quote_via=urllib.parse.quote
    )
    return f"mailto:{recipients}?{query}"
