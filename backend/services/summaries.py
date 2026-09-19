"""The summary document (DEMOCRACY.md §11).

One document per community per cycle. The same content for every reader.
Nothing personal in it. The canonical form is the JSON stored on the
`summaries` row; the web page and the PDF both render from that JSON, and the
hash is SHA-256 of its canonical form — keys sorted, UTF-8, no whitespace.

Anyone can download the JSON, run SHA-256 over it themselves, and compare. That
is the whole promise: if one letter changes, the fingerprint will not match.
"""

from __future__ import annotations

import logging
import urllib.parse

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings_env import get_env_settings
from backend.errors import Conflict, NotFound
from backend.models import Cycle
from backend.repositories import cycles as cycles_repo
from backend.repositories import officials as officials_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import community as community_service
from backend.services import hashing
from backend.services import pdf as pdf_service
from backend.services import rules

log = logging.getLogger(__name__)

VERIFY_EXPLANATION = (
    "This code is a fingerprint of everything above. It is made by running a "
    "standard calculation called SHA-256 over this document's data. If anyone "
    "changes one letter of it, the fingerprint will not match. You can check it "
    "yourself: download the JSON from this page, run SHA-256 over the file, and "
    "compare. Every published document's fingerprint is listed at /summaries/hashes."
)


async def generate(session: AsyncSession, *, cycle: Cycle) -> dict:
    """Build the document, hash it once, store both. Immutable after publish."""
    existing = await cycles_repo.summary_for_cycle(session, cycle.id)
    if existing is not None:
        return _shape(existing.data, existing.summary_hash, existing.published_at)

    data = await build_data(session, cycle=cycle)
    digest = hashing.summary_hash(data)
    row = await cycles_repo.add_summary(
        session, cycle_id=cycle.id, data=data, summary_hash=digest
    )
    log.info("summary_published", extra={"cycle_id": cycle.id, "summary_hash": digest})
    return _shape(data, digest, row.published_at)


def _shape(data: dict, digest: str, published_at) -> dict:
    return {
        "summary_hash": digest,
        "published_at": published_at,
        "document": data,
        "verify": {
            "hash": digest,
            "algorithm": "SHA-256 of the canonical JSON (keys sorted, UTF-8, no whitespace)",
            "explanation": VERIFY_EXPLANATION,
            "hash_list_url": get_env_settings().absolute_url("/summaries/hashes"),
        },
    }


async def build_data(session: AsyncSession, *, cycle: Cycle) -> dict:
    """DEMOCRACY.md §11.2 — the document's content, in order."""
    community = await community_service.resolve(
        session, cycle.community_level, cycle.community_entity_id
    )
    values = cycle.settings_snapshot
    items = await cycles_repo.items(session, cycle.id)
    umbrellas = await umbrellas_repo.by_ids(session, [i.umbrella_id for i in items])
    jury = await cycles_repo.jury_for_cycle(session, cycle.id)
    jurors = await cycles_repo.jurors(session, jury.id) if jury else []
    seated = [j for j in jurors if j.status == "accepted"]
    # A decline draws an immediate replacement for the same seat (DEMOCRACY.md
    # §8.2); the declining juror's own row stays "declined" on this, the
    # current, jury — "replaced" is reserved for a whole redraw superseding a
    # prior jury (DATABASE.md §4.17), which is a different row entirely.
    replaced = [j for j in jurors if j.status == "declined"]
    seat_numbers = {j.id: n for n, j in enumerate(seated, start=1)}
    holdbacks = await cycles_repo.holdbacks(session, jury.id) if jury else []
    voters = await cycles_repo.distinct_voters(session, cycle.id)
    mix = await cycles_repo.voter_verification_mix(session, cycle.id)

    # 1. Header
    header = {
        "community_name": community.name,
        "community_level": cycle.community_level,
        "community_label": community.label,
        "cycle_number": cycle.number,
        "ballot_opened_at": hashing.iso(cycle.opened_at) if cycle.opened_at else None,
        "ballot_closed_at": hashing.iso(cycle.closed_at) if cycle.closed_at else None,
        "active_users_at_snapshot": cycle.active_users_at_prepare,
        "members_who_voted": voters,
        "verification_mix": _mix_sentence(voters, mix),
        "verification_mix_counts": mix,
        "residency_note": (
            "Residency is self-declared and unverified at this verification level."
        ),
        "jury": (
            f"{len(jurors)} drawn, {len(replaced)} replaced, {len(seated)} seated"
            if jury
            else "No jury was drawn"
        ),
        "jurors_drawn": len(jurors),
        "jurors_replaced": len(replaced),
        "jurors_seated": len(seated),
        "build": get_env_settings().BUILD_LABEL,
    }

    # 2. Results — every item, in ballot order; failed items included.
    results = []
    held_back_section = []
    for item in items:
        version = await solutions_repo.version_at(
            session, item.solution_id, item.solution_version
        )
        entry = {
            "position": item.position,
            "umbrella": umbrellas[item.umbrella_id].name if item.umbrella_id in umbrellas else "",
            "solution_text": version.text_body if version else "",
            "solution_version": item.solution_version,
            "solution_version_hash": version.content_hash if version else None,
            # DEMOCRACY.md §11.1/§11.2 item 2 — no author, name, or user id of
            # any kind. Solutions are attributed to the community; authorship
            # lives on the solution page, resolved at read time so account
            # deletion reaches it without ever touching this hashed document
            # (CLAUDE.md §6; audit demo-01 run 4 CRITICAL).
            "workshop_note": f"Proposed and refined in the {community.name} workshop",
            "solution_url": get_env_settings().absolute_url(f"/solutions/{item.solution_id}"),
            "ai_influence_percentage": version.ai_contribution_percentage if version else 0,
            "ai_influence_label": ai_log.influence(
                version.ai_contribution_percentage if version else 0
            )["label"],
        }
        reasons = [
            {
                "juror": f"Juror {seat_numbers.get(h.juror_id, '?')} of {len(seated)}",
                "category": h.reason_category,
                "reason": h.reason_text,
            }
            for h in holdbacks
            if h.ballot_item_id == item.id and h.juror_id in seat_numbers
        ]
        if item.held_back:
            held_back_section.append({**entry, "jury_reasons": reasons})
        else:
            # DEMOCRACY.md §11.2 item 2 — a hold-back that did not reach a
            # majority still ran the item through the ballot, but every
            # juror's reason is still published (§8.3; audit demo-01 run 2).
            results.append(
                {
                    **entry,
                    "yes": item.yes_count or 0,
                    "no": item.no_count or 0,
                    "result": "Passed" if item.result == "passed" else "Failed",
                    "juror_concerns": (
                        {
                            "label": f"Juror concerns ({len(reasons)} of {len(seated)} seated)",
                            "reasons": reasons,
                        }
                        if reasons
                        else None
                    ),
                }
            )

    # 4. How this was produced — plain English, with the numbers that applied.
    how = _how_this_was_produced(values, cycle)

    return {
        "document_version": "summary-v1",
        "rules_version": rules.RULES_VERSION,
        "header": header,
        "results": results,
        "held_back": held_back_section,
        "how_this_was_produced": how,
        "settings_in_force": values,
        "empty_note": (
            "No solutions reached the ballot this cycle."
            if not items
            else None
        ),
        "send_to_representatives": await _send_block(session, cycle, community),
    }


def _mix_sentence(voters: int, mix: dict[str, int]) -> str:
    if voters == 0:
        return "No votes were cast."
    parts = ", ".join(f"{count} {level}" for level, count in sorted(mix.items()))
    return f"{voters} voter{'s' if voters != 1 else ''}: {parts}"


def _how_this_was_produced(values: dict, cycle: Cycle) -> list[dict[str, str]]:
    """DEMOCRACY.md §11.2 item 4 — one paragraph each, each ending with the
    setting values in force for this cycle and the rule's version."""
    return [
        {
            "heading": "Who counted as an active user",
            "text": (
                "An active user of this community is someone whose home city, "
                "county or state is this community, whose email is confirmed, "
                "whose account has not been deleted, and who signed in and did "
                "something within the window below. That number is the "
                "denominator for every percentage on this page."
            ),
            "settings_in_force": (
                f"active_user_window_days = {values['active_user_window_days']}; "
                f"active users at snapshot = {cycle.active_users_at_prepare}"
            ),
            "rule_version": rules.RULES_VERSION,
        },
        {
            "heading": "How a solution became dominant",
            "text": (
                "A solution becomes dominant when the number of people who "
                "upvoted it, minus the number who downvoted it, reaches a "
                "threshold: a percentage of the active users or a fixed number, "
                "whichever is lower, and never less than one. Dominant solutions "
                "are the only ones that can be amended and discussed."
            ),
            "settings_in_force": (
                f"dominant_pct = {values['dominant_pct']}; dominant_min = {values['dominant_min']}"
            ),
            "rule_version": rules.RULES_VERSION,
        },
        {
            "heading": "How a solution qualified for this ballot",
            "text": (
                "At the moment the ballot was prepared, a solution qualified if "
                "it was dominant, had been dominant for long enough, had a score "
                "at or above the ballot threshold, and — if it had ever been on a "
                "ballot before, whether it passed, failed or was held back — had "
                "been changed since. Nothing returns to the ballot unchanged; the "
                "way back is an amendment."
            ),
            "settings_in_force": (
                f"ballot_pct = {values['ballot_pct']}; ballot_min = {values['ballot_min']}; "
                f"ballot_min_dominant_days = {values['ballot_min_dominant_days']}"
            ),
            "rule_version": rules.RULES_VERSION,
        },
        {
            "heading": "How the jury was drawn and what it could do",
            "text": (
                "Jurors were drawn at random from this community's active users, "
                "leaving out anyone who wrote or proposed a change to a solution "
                "on this ballot, and leaving out administrators. The draw is "
                "recorded with the pool it drew from. A juror could do nothing, or "
                "hold a solution back with a written reason that is published "
                "below. A hold-back took effect when more than half of the seated "
                "jurors held the same solution back. Jurors could not change "
                "anything and could not add anything."
            ),
            "settings_in_force": (
                f"jury_size = {values['jury_size']}; "
                f"jury_no_repeat_cycles = {values['jury_no_repeat_cycles']}; "
                f"jury_review_days = {values['jury_review_days']}"
            ),
            "rule_version": rules.RULES_VERSION,
        },
        {
            "heading": "How a vote passed",
            "text": (
                "Every member of this community could vote yes or no on every "
                "item, once, and could change that vote until the ballot closed. "
                "Every vote counted the same, whatever the voter's verification "
                "level. An item passed when more people voted yes than no and at "
                "least the quorum voted. A tie failed."
            ),
            "settings_in_force": (
                f"ballot_pass_rule = {values['ballot_pass_rule']}; "
                f"ballot_quorum_min = {values['ballot_quorum_min']}; "
                f"ballot_window_days = {values['ballot_window_days']}"
            ),
            "rule_version": rules.RULES_VERSION,
        },
    ]


async def _send_block(session: AsyncSession, cycle: Cycle, community) -> dict:
    """DEMOCRACY.md §11.5 — the platform sends nothing and records nothing."""
    officials = await officials_repo.for_community(
        session, cycle.community_level, cycle.community_entity_id
    )
    return {
        "recipients": [{"office": o.office, "email": o.email} for o in officials],
        "subject": f"Ballot results — {community.label}, cycle {cycle.number}",
        "note": (
            "Pressing send opens your own email program with this message already "
            "written. You send it, from your own address. The platform sends "
            "nothing and cannot know whether you pressed send."
        ),
        "demo_note": (
            "In this build every address in the directory is a test address, not "
            "a real official."
        ),
    }


async def verify(session: AsyncSession, *, cycle: Cycle) -> dict:
    """Recompute the hash from the stored data and report match or mismatch."""
    summary = await cycles_repo.summary_for_cycle(session, cycle.id)
    if summary is None:
        raise NotFound("That cycle has no published summary.", code="summary_not_found")
    recomputed = hashing.summary_hash(summary.data)
    matches = recomputed == summary.summary_hash
    return {
        "cycle_id": cycle.id,
        "stored_hash": summary.summary_hash,
        "recomputed_hash": recomputed,
        "match": matches,
        "verdict": (
            "This document is unchanged since it was published."
            if matches
            else "This document does not match its fingerprint. Report this."
        ),
        "explanation": VERIFY_EXPLANATION,
    }


async def canonical_json(session: AsyncSession, *, cycle: Cycle) -> str:
    """Exactly the bytes the hash was computed over, so anyone can check it."""
    summary = await cycles_repo.summary_for_cycle(session, cycle.id)
    if summary is None:
        raise NotFound("That cycle has no published summary.", code="summary_not_found")
    return hashing.canonical_json(summary.data)


async def by_community_and_number(
    session: AsyncSession, *, level: str, entity_id: int, number: int
) -> dict:
    cycle = await cycles_repo.by_number(session, level, entity_id, number)
    if cycle is None:
        raise NotFound("There is no such cycle.", code="cycle_not_found")
    summary = await cycles_repo.summary_for_cycle(session, cycle.id)
    if summary is None:
        raise Conflict(
            "That cycle has not been published yet.", code="summary_not_published"
        )
    document = _shape(summary.data, summary.summary_hash, summary.published_at)
    document["mailto"] = _mailto(
        document["document"]["send_to_representatives"], level, entity_id, number, summary.summary_hash
    )
    return document


def _mailto(send: dict, level: str, entity_id: int, number: int, digest: str) -> str:
    """DEMOCRACY.md §11.5 — the user's own mail client, from their own
    address. The platform sends nothing and records nothing about the send.
    The body's URL is absolute (`PUBLIC_BASE_URL`) so it still resolves once
    forwarded outside a browser session with the platform open (audit
    demo-01 run 3, LOW). Composed here, not in the router (ARCHITECTURE.md
    §2: "no logic" in a router — audit demo-01 run 5, LOW)."""
    recipients = ",".join(r["email"] for r in send["recipients"])
    url = get_env_settings().absolute_url(f"/summaries/{level}/{entity_id}/{number}")
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


async def require_summary(session: AsyncSession, *, cycle: Cycle):
    summary = await cycles_repo.summary_for_cycle(session, cycle.id)
    if summary is None:
        raise NotFound("That cycle has no published summary.", code="summary_not_found")
    return summary


async def pdf_bytes(session: AsyncSession, *, cycle: Cycle, url: str) -> bytes:
    """`GET /summaries/{level}/{entity_id}/{number}/pdf` — DEMOCRACY.md §11.6."""
    summary = await require_summary(session, cycle=cycle)
    return pdf_service.render(summary.data, summary.summary_hash, url)


async def require_cycle_by_number(
    session: AsyncSession, *, level: str, entity_id: int, number: int
) -> Cycle:
    """A `require_*` resolver (ARCHITECTURE.md §2/§10) — audit demo-01 run 3,
    MEDIUM: named `cycle_for` before, so the layering test's `require_*`
    exemption didn't recognize it and every caller looked like two service
    calls."""
    cycle = await cycles_repo.by_number(session, level, entity_id, number)
    if cycle is None:
        raise NotFound("There is no such cycle.", code="cycle_not_found")
    return cycle


async def hash_list(session: AsyncSession, *, cursor: int | None, limit: int) -> dict:
    """`GET /summaries/hashes` (DEMOCRACY.md §11.3; ARCHITECTURE.md §6 —
    paginates like every other list endpoint, audit demo-01 run 3 HIGH)."""
    rows = await cycles_repo.published_summaries_page(session, cursor=cursor, limit=limit)
    out = []
    for summary, cycle in rows:
        community = await community_service.resolve(
            session, cycle.community_level, cycle.community_entity_id
        )
        out.append(
            {
                "community": community.as_dict(),
                "cycle_number": cycle.number,
                "published_at": summary.published_at,
                "summary_hash": summary.summary_hash,
                "url": (
                    f"/summaries/{cycle.community_level}/"
                    f"{cycle.community_entity_id}/{cycle.number}"
                ),
            }
        )
    return {
        "items": out,
        "next_cursor": rows[-1][0].id if len(rows) == limit else None,
    }


async def for_user(session: AsyncSession, *, user) -> dict:
    """DEMOCRACY.md §11.4 — the user's three communities' most recent summaries
    and their past cycles. The personalization is which three, not what is in
    them."""
    communities = await community_service.home_communities(session, user)
    out = []
    for community in communities:
        cycles = await cycles_repo.for_community(session, community.level, community.entity_id)
        published = []
        for cycle in cycles:
            summary = await cycles_repo.summary_for_cycle(session, cycle.id)
            if summary is None:
                continue
            published.append(
                {
                    "cycle_number": cycle.number,
                    "published_at": summary.published_at,
                    "summary_hash": summary.summary_hash,
                    "url": (
                        f"/summaries/{community.level}/{community.entity_id}/{cycle.number}"
                    ),
                    "item_count": len(summary.data.get("results", []))
                    + len(summary.data.get("held_back", [])),
                }
            )
        out.append(
            {
                "community": community.as_dict(),
                "most_recent": published[0] if published else None,
                "past_cycles": published[1:],
                "current_cycle_state": cycles[0].state if cycles else None,
            }
        )
    return {
        "communities": out,
        "note": (
            "These are your three communities. What each document says is the "
            "same for everyone who reads it."
        ),
    }
