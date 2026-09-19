"""References: external information attached to an umbrella (DEMOCRACY.md §9.4).

Any member may add a URL with a one-line note. The director can also ask the AI
to recommend some: Ollama writes the search queries, the configured provider
runs them, Ollama picks from the results and says why each one is relevant, and
every pick arrives labelled "Recommended by AI" with a Useful / Not useful pair
beside it. Enough Not-useful presses mark a reference rejected — still visible,
never deleted.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import ollama as ollama_client
from backend.clients import search as search_client
from backend.errors import ExternalServiceDown, NotFound, ValidationFailed
from backend.models import Umbrella, UmbrellaReference, User
from backend.repositories import admin as admin_repo
from backend.repositories import ai_actions as ai_actions_repo
from backend.repositories import references as references_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import ai_log
from backend.services import settings as settings_service
from backend.services.display import author_displays

log = logging.getLogger(__name__)

QUERIES_PROMPT = "reference_queries.md"
SELECT_PROMPT = "reference_select.md"
MAX_NOTE = 300


async def load_umbrella_for_job(session: AsyncSession, umbrella_id: int) -> Umbrella | None:
    """`backend/jobs/references.py` may call services only (ARCHITECTURE.md
    §2); it never reaches `umbrellas_repo` itself."""
    return await umbrellas_repo.get(session, umbrella_id)


async def add_user_reference(
    session: AsyncSession, *, umbrella: Umbrella, user: User, url: str, title: str, note: str
) -> UmbrellaReference:
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        raise ValidationFailed(
            "A reference needs a web address starting with http:// or https://.",
            code="bad_url",
        )
    clean_note = note.strip()
    if not 1 <= len(clean_note) <= MAX_NOTE:
        raise ValidationFailed(
            f"Say in up to {MAX_NOTE} characters why this is worth reading.",
            code="bad_note",
        )
    return await references_repo.add(
        session,
        umbrella_id=umbrella.id,
        url=clean_url,
        title=(title.strip() or clean_url)[:300],
        note=clean_note,
        source="user",
        added_by=user.id,
        ai_action_id=None,
        status="active",
    )


async def feedback(
    session: AsyncSession, *, reference: UmbrellaReference, user: User, useful: bool
) -> dict:
    """`PUT /references/{id}/feedback` — one service call (ARCHITECTURE.md
    §2/§10: folds in the membership check the router used to run separately;
    audit demo-01 run 3, MEDIUM)."""
    from backend.deps import require_member

    community = await community_of_reference(session, reference)
    if community is not None:
        await require_member(session, user, *community)
    await references_repo.put_feedback(
        session, reference_id=reference.id, user_id=user.id, useful=useful
    )
    counts = await references_repo.feedback_counts(session, [reference.id])
    useful_count, not_useful_count = counts.get(reference.id, (0, 0))
    needed = int(await settings_service.get(session, "reference_reject_min"))
    if not_useful_count >= needed and reference.status == "active":
        reference.status = "rejected"
        await ai_log.record_outcome(
            session, action_id=reference.ai_action_id, outcome="rejected", user_id=user.id
        )
        await session.flush()
        log.info("reference_rejected", extra={"reference_id": reference.id})
    elif useful and reference.source == "ai" and reference.ai_action_id:
        await ai_log.record_outcome(
            session, action_id=reference.ai_action_id, outcome="accepted", user_id=user.id
        )
    return {
        "reference_id": reference.id,
        "useful": useful_count,
        "not_useful": not_useful_count,
        "rejections_needed": needed,
        "status": reference.status,
    }


async def _eligible_remaining(session: AsyncSession, umbrella_id: int) -> int:
    """The fast checks — is a provider configured, is there room under the
    per-umbrella cap — done both synchronously before the job is even
    scheduled (so an admin sees the refusal at once) and again inside the
    job itself (ARCHITECTURE.md §7)."""
    search_client.get_search().require_configured()
    limit = int(await settings_service.get(session, "references_ai_max_per_umbrella"))
    already = await references_repo.count_ai_active(session, umbrella_id)
    remaining = limit - already
    if remaining <= 0:
        raise ValidationFailed(
            f"This umbrella already has the most AI-recommended references it may "
            f"have ({limit}).",
            code="reference_limit_reached",
        )
    return remaining


async def recommend(session: AsyncSession, *, umbrella: Umbrella) -> dict:
    """DEMOCRACY.md §9.4, triggered by the director — never on a schedule."""
    search = search_client.get_search()
    remaining = await _eligible_remaining(session, umbrella.id)

    dominant = await solutions_repo.dominant_in_umbrella(session, umbrella.id)
    versions = await solutions_repo.current_versions(session, [s.id for s in dominant])
    solution_lines = (
        "\n".join(f"- {versions[s.id].text_body}" for s in dominant if s.id in versions)
        or "(no solution has become dominant yet)"
    )
    client = ollama_client.get_ollama()

    query_variables = {
        "umbrella_name": umbrella.name,
        "umbrella_statement": umbrella.statement,
        "community": f"{umbrella.community_level} {umbrella.community_entity_id}",
        "dominant_solutions": solution_lines,
    }
    raw, prompt = await client.generate(QUERIES_PROMPT, query_variables)
    try:
        queries = [str(q) for q in ollama_client.parse_json_output(raw).get("queries", [])][:3]
    except ValueError as exc:
        await ai_log.record(
            session,
            action_type="reference_recommend",
            subject_type="umbrella",
            subject_id=umbrella.id,
            model=client.model_label,
            prompt_file=QUERIES_PROMPT,
            prompt_hash=prompt.sha256,
            model_input=query_variables,
            output={"error": f"unparseable query output: {exc}", "raw": raw[:2000]},
        )
        raise ExternalServiceDown(
            "The recommendation step could not be read. Nothing was added.",
            code="ollama_bad_output",
        ) from exc
    if not queries:
        raise ExternalServiceDown(
            "No usable search queries came back. Nothing was added.", code="no_queries"
        )

    results: list[search_client.Result] = []
    raw_provider_results = []
    for query in queries:
        found, raw_response = await search.search(query)
        raw_provider_results.append({"query": query, "response": raw_response})
        results.extend(found)

    if not results:
        action = await ai_log.record(
            session,
            action_type="reference_recommend",
            subject_type="umbrella",
            subject_id=umbrella.id,
            model=client.model_label,
            prompt_file=QUERIES_PROMPT,
            prompt_hash=prompt.sha256,
            model_input=query_variables,
            output={
                "provider": search.provider,
                "queries": queries,
                "raw_results": raw_provider_results,
                "picks": [],
                "note": "the provider returned nothing",
            },
        )
        return {"added": [], "queries": queries, "ai_action_id": action.id}

    numbered = "\n".join(
        f"{i} | {r.title} | {r.url} | {r.snippet}" for i, r in enumerate(results, start=1)
    )
    select_variables = {
        "umbrella_name": umbrella.name,
        "umbrella_statement": umbrella.statement,
        "max_picks": remaining,
        "results": numbered,
    }
    select_raw, select_prompt = await client.generate(SELECT_PROMPT, select_variables)
    try:
        picks = ollama_client.parse_json_output(select_raw).get("picks", [])[:remaining]
    except ValueError as exc:
        await ai_log.record(
            session,
            action_type="reference_recommend",
            subject_type="umbrella",
            subject_id=umbrella.id,
            model=client.model_label,
            prompt_file=SELECT_PROMPT,
            prompt_hash=select_prompt.sha256,
            model_input=select_variables,
            output={"error": f"unparseable selection output: {exc}", "raw": select_raw[:2000]},
        )
        raise ExternalServiceDown(
            "The recommendation step could not be read. Nothing was added.",
            code="ollama_bad_output",
        ) from exc

    # The log row exists before any reference is visible (CLAUDE.md Law 7).
    action = await ai_log.record(
        session,
        action_type="reference_recommend",
        subject_type="umbrella",
        subject_id=umbrella.id,
        model=client.model_label,
        prompt_file=SELECT_PROMPT,
        prompt_hash=select_prompt.sha256,
        model_input={"queries": query_variables, "selection": select_variables},
        output={
            "provider": search.provider,
            "queries": queries,
            "raw_results": raw_provider_results,
            "picks": picks,
        },
    )

    added = []
    existing_urls = {r.url for r in await references_repo.for_umbrella(session, umbrella.id)}
    for pick in picks:
        try:
            index = int(pick["result_number"]) - 1
            why = str(pick["why"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < len(results) or not why:
            continue
        result = results[index]
        if result.url in existing_urls:
            continue
        existing_urls.add(result.url)
        row = await references_repo.add(
            session,
            umbrella_id=umbrella.id,
            url=result.url,
            title=result.title[:300],
            note=why[:MAX_NOTE],
            source="ai",
            added_by=None,
            ai_action_id=action.id,
            status="active",
        )
        added.append({"id": row.id, "url": row.url, "title": row.title, "why": row.note})
    log.info(
        "references_recommended",
        extra={"umbrella_id": umbrella.id, "added": len(added), "ai_action_id": action.id},
    )
    return {"added": added, "queries": queries, "ai_action_id": action.id}


async def recommend_as_admin(session: AsyncSession, *, umbrella: Umbrella, admin: User) -> dict:
    """`POST /admin/umbrellas/{id}/recommend-references` — logs the trigger
    and schedules the Ollama/search work as a background job, the same
    pattern every other row in ARCHITECTURE.md §7's job table uses (audit
    demo-01 run 3, MEDIUM: this used to run inline in the request)."""
    from backend.services import admin_log

    await _eligible_remaining(session, umbrella.id)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="recommend_references",
        subject_type="umbrella",
        subject_id=umbrella.id,
        new_value={"status": "pending"},
    )
    _schedule_recommend(session, umbrella.id)
    return {"status": "pending"}


def _schedule_recommend(session: AsyncSession, umbrella_id: int) -> None:
    from backend.jobs import references as references_job
    from backend.jobs import runner

    runner.spawn_after_commit(
        session,
        lambda: references_job.recommend_references_task(umbrella_id),
        name=f"recommend_references:{umbrella_id}",
    )


async def listing(session: AsyncSession, umbrella_id: int) -> dict:
    rows = await references_repo.for_umbrella(session, umbrella_id)
    shaped = await _shape_all(session, rows)
    return {
        "active": [r for r in shaped if r["status"] == "active"],
        "rejected": [r for r in shaped if r["status"] == "rejected"],
        "note": (
            "References the community marked not useful are moved to the rejected "
            "list. They are never deleted."
        ),
        "recommending": await _recommend_pending(session, umbrella_id),
    }


async def listing_page(
    session: AsyncSession, umbrella_id: int, *, cursor: int | None, limit: int
) -> dict:
    """`GET /umbrellas/{id}/references` (ARCHITECTURE.md §6, audit demo-01
    run 3 HIGH). Active and rejected are split within the page, not across
    the whole list — the same page of the underlying `id`-ordered rows both
    are drawn from."""
    rows = await references_repo.for_umbrella_page(session, umbrella_id, cursor=cursor, limit=limit)
    shaped = await _shape_all(session, rows)
    return {
        "active": [r for r in shaped if r["status"] == "active"],
        "rejected": [r for r in shaped if r["status"] == "rejected"],
        "note": (
            "References the community marked not useful are moved to the rejected "
            "list. They are never deleted."
        ),
        "recommending": await _recommend_pending(session, umbrella_id),
        "next_cursor": rows[-1].id if len(rows) == limit else None,
    }


async def _recommend_pending(session: AsyncSession, umbrella_id: int) -> bool:
    """True from the moment an admin triggers a recommendation until its
    `ai_actions` row exists (ARCHITECTURE.md §7; audit demo-01 run 3,
    MEDIUM) — the umbrella page shows "AI is looking for references…" for
    exactly that stretch."""
    triggered = await admin_repo.latest_for_subject(
        session, action="recommend_references", subject_type="umbrella", subject_id=umbrella_id
    )
    if triggered is None:
        return False
    latest_result = await ai_actions_repo.page(
        session,
        cursor=None,
        limit=1,
        subject_type="umbrella",
        subject_id=umbrella_id,
        action_type="reference_recommend",
    )
    return not latest_result or latest_result[0].created_at < triggered.created_at


async def _shape_all(session: AsyncSession, rows: list[UmbrellaReference]) -> list[dict]:
    counts = await references_repo.feedback_counts(session, [r.id for r in rows])
    displays = await author_displays(session, [r.added_by for r in rows if r.added_by])
    needed = int(await settings_service.get(session, "reference_reject_min"))

    def shape(row: UmbrellaReference) -> dict:
        useful, not_useful = counts.get(row.id, (0, 0))
        return {
            "id": row.id,
            "url": row.url,
            "title": row.title,
            "why": row.note,
            "source": row.source,
            "label": (
                "Recommended by AI"
                if row.source == "ai"
                else f"Added by {displays.get(row.added_by, 'Former Community Member')}"
            ),
            "status": row.status,
            "useful": useful,
            "not_useful": not_useful,
            "rejections_needed": needed,
            "added_at": row.created_at,
        }

    return [shape(r) for r in rows]


async def require_reference(session: AsyncSession, reference_id: int) -> UmbrellaReference:
    row = await references_repo.get(session, reference_id)
    if row is None:
        raise NotFound("That reference does not exist.", code="reference_not_found")
    return row


async def community_of_reference(
    session: AsyncSession, reference: UmbrellaReference
) -> tuple[str, int] | None:
    umbrella = await umbrellas_repo.get(session, reference.umbrella_id)
    if umbrella is None:
        return None
    return umbrella.community_level, umbrella.community_entity_id
