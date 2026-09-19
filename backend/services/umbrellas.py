"""The umbrella page — the workshop (DEMOCRACY.md §3.3).

Sections, in order: the problem; the problem reports filed here; the problem
discussion; every solution ordered by net score; the dominant solutions
expanded with their amendments and their own discussion; the references.

Nothing is ever hidden. A solution at −20 appears at the bottom of the list.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import NotFound
from backend.models import Umbrella
from backend.repositories import posts as posts_repo
from backend.repositories import solutions as solutions_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.repositories import votes as votes_repo
from backend.services import ai_log
from backend.services import comments as comments_service
from backend.services import community as community_service
from backend.services import posts as posts_service
from backend.services import references as references_service
from backend.services import rules
from backend.services import settings as settings_service
from backend.services import similarity as similarity_service
from backend.services.display import author_displays

#: ARCHITECTURE.md §6 — a whole-page endpoint embeds only the first page of
#: a list it shows, with a next_cursor; the rest comes from the list's own
#: dedicated endpoint (audit demo-01 run 5, NOTE — resolved by the director
#: into a rule rather than left as an observation).
_PAGE_SIZE = 25


async def listing(
    session: AsyncSession, level: str, entity_id: int, *, cursor: int | None, limit: int
) -> dict:
    community = await community_service.resolve(session, level, entity_id)
    umbrellas = await umbrellas_repo.for_community_page(
        session, level, entity_id, cursor=cursor, limit=limit
    )
    categories = await umbrellas_repo.categories_by_ids(
        session, [u.main_category_id for u in umbrellas]
    )
    return {
        "community": community.as_dict(),
        "active_users": await community_service.active_user_count(session, level, entity_id),
        "active_user_definition": await community_service.active_user_definition(session),
        "umbrellas": [
            {
                "id": u.id,
                "name": u.name,
                "statement": u.statement,
                "main_category": categories[u.main_category_id].name
                if u.main_category_id in categories
                else None,
                "status": u.status,
                "source": u.source,
            }
            for u in umbrellas
        ],
        "next_cursor": umbrellas[-1].id if len(umbrellas) == limit else None,
    }


async def page(session: AsyncSession, umbrella_id: int, viewer_id: int | None) -> dict:
    umbrella = await umbrellas_repo.get(session, umbrella_id)
    if umbrella is None:
        raise NotFound("That umbrella does not exist.", code="umbrella_not_found")

    community = await community_service.resolve(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    active_users = await community_service.active_user_count(
        session, umbrella.community_level, umbrella.community_entity_id
    )
    values = await settings_service.all_values(session)
    categories = await umbrellas_repo.categories_by_ids(session, [umbrella.main_category_id])

    # ARCHITECTURE.md §6 — a whole-page endpoint embeds only the first page
    # of a list it shows, with a next_cursor; the rest comes from the
    # list's own dedicated endpoint (audit demo-01 run 5, NOTE — resolved by
    # the director into a rule).
    discussion_page = await comments_service.thread_page(
        session,
        target_type="umbrella",
        target_id=umbrella.id,
        viewer_id=viewer_id,
        cursor=None,
        limit=_PAGE_SIZE,
    )
    solutions_page = await solutions_list_page(
        session, umbrella, viewer_id, cursor=None, limit=_PAGE_SIZE
    )
    references_page = await references_service.listing_page(
        session, umbrella.id, cursor=None, limit=_PAGE_SIZE
    )

    return {
        "problem": {
            "id": umbrella.id,
            "name": umbrella.name,
            "statement": umbrella.statement,
            "community": community.as_dict(),
            "main_category": categories[umbrella.main_category_id].name
            if umbrella.main_category_id in categories
            else None,
            "status": umbrella.status,
            "source": umbrella.source,
            "active_users": active_users,
            "active_user_definition": await community_service.active_user_definition(session),
            "ai_action_list": await ai_log.umbrella_action_list(session, umbrella.id),
            "dominant_threshold": rules.dominant_threshold(
                dominant_pct=values["dominant_pct"],
                dominant_min=values["dominant_min"],
                active_users=active_users,
            ),
            "ballot_threshold": rules.ballot_threshold(
                ballot_pct=values["ballot_pct"],
                ballot_min=values["ballot_min"],
                active_users=active_users,
            ),
        },
        "problem_reports": await _problem_reports(session, umbrella),
        "problem_discussion": discussion_page["comments"],
        "problem_discussion_next_cursor": discussion_page["next_cursor"],
        "solutions": solutions_page["solutions"],
        "solutions_next_cursor": solutions_page["next_cursor"],
        "dominant_solutions": await _dominant_detail(session, umbrella, viewer_id),
        "references": references_page,
        "ordering": {
            "version": rules.SOLUTION_ORDER_VERSION,
            "explanation": rules.SOLUTION_ORDER_EXPLANATION,
        },
    }


async def _problem_reports(session: AsyncSession, umbrella: Umbrella) -> list[dict]:
    """DEMOCRACY.md §3.3 item 2 — newest first, with author display and label
    status."""
    rows = await posts_repo.problem_reports_for_umbrella(session, umbrella.id)
    seen: dict[int, tuple] = {}
    for post, label in rows:
        if post.id not in seen or (label is not None and seen[post.id][1] is None):
            seen[post.id] = (post, label)
    posts = list(seen.values())
    displays = await author_displays(session, [p.author_id for p, _ in posts])
    return [
        {
            "post_id": post.id,
            "title": posts_service.derive_title(post.problem_text),
            "problem_text": post.problem_text,
            "author": displays.get(post.author_id, "Former Community Member"),
            "created_at": post.created_at,
            "content_hash": post.content_hash,
            "label_shown_as": posts_service._label_words(label),
            "ai_influence": ai_log.influence(post.ai_contribution_percentage),
        }
        for post, label in posts
    ]


async def solution_list(
    session: AsyncSession,
    umbrella: Umbrella,
    viewer_id: int | None,
    active_users: int | None = None,
    values: dict | None = None,
) -> list[dict]:
    """DEMOCRACY.md §3.3 item 4 — every solution, net score descending, ties
    oldest first. Nothing hidden.

    `active_users`/`values` are precomputed by `page()`, which already has
    them, to avoid a second lookup; `GET /umbrellas/{id}/solutions` calls this
    directly and leaves them to be resolved here (ARCHITECTURE.md §2/§10)."""
    if active_users is None:
        active_users = await community_service.active_user_count(
            session, umbrella.community_level, umbrella.community_entity_id
        )
    if values is None:
        values = await settings_service.all_values(session)
    rows = await solutions_repo.in_umbrella(session, umbrella.id)
    versions = await solutions_repo.current_versions(session, [s.id for s in rows])
    displays = await author_displays(session, [s.author_id for s in rows])
    my_votes = (
        await votes_repo.user_votes_on(session, viewer_id, "solution", [s.id for s in rows])
        if viewer_id
        else {}
    )
    out = []
    for solution in rows:
        version = versions.get(solution.id)
        out.append(
            {
                "id": solution.id,
                "text": version.text_body if version else "",
                "version": solution.current_version,
                "version_hash": version.content_hash if version else None,
                "author": displays.get(solution.author_id, "Former Community Member"),
                "net_score": solution.net_score,
                "my_vote": my_votes.get(solution.id),
                "status_badge": _badge(solution),
                "is_dominant": solution.is_dominant,
                "dominant_since": solution.dominant_since,
                "on_track_for_ballot": rules.on_track_for_ballot(
                    is_dominant_now=solution.is_dominant,
                    net_score_value=solution.net_score,
                    ballot_pct=values["ballot_pct"],
                    ballot_min=values["ballot_min"],
                    active_users=active_users,
                ),
                "last_ballot_result": solution.last_ballot_result,
                "last_ballot_version": solution.last_ballot_version,
                "post_id": solution.post_id,
                "ai_influence": ai_log.influence(
                    version.ai_contribution_percentage if version else 0
                ),
                "created_at": solution.created_at,
            }
        )
    return out


async def solutions_list_page(
    session: AsyncSession, umbrella: Umbrella, viewer_id: int | None, *, cursor: int | None, limit: int
) -> dict:
    """`GET /umbrellas/{id}/solutions` (ARCHITECTURE.md §6, audit demo-01 run
    3 HIGH). `page()` calls this too, for its own first page (audit demo-01
    run 5, NOTE — a whole-page endpoint embeds only the first page of a
    list, with a next_cursor)."""
    rows = await solution_list(session, umbrella, viewer_id)
    return _paginate_by_id(rows, cursor=cursor, limit=limit, key="solutions")


def _paginate_by_id(rows: list[dict], *, cursor: int | None, limit: int, key: str) -> dict:
    """Slices an already-ordered list of dicts by a cursor naming the last
    `id` seen. Works regardless of the ordering rule (net-score ranked lists
    included) because the cursor only has to locate a position in a sequence
    that is already in the right order, never express the sort key itself."""
    start = 0
    if cursor is not None:
        start = next((i + 1 for i, row in enumerate(rows) if row["id"] == cursor), len(rows))
    page = rows[start : start + limit]
    return {key: page, "next_cursor": page[-1]["id"] if len(page) == limit else None}


def _badge(solution) -> str | None:
    if solution.last_ballot_result == "held_back":
        return "held back"
    if solution.is_dominant:
        return "dominant"
    if solution.last_ballot_result == "passed":
        return "passed a ballot"
    if solution.last_ballot_result == "failed":
        return "failed a ballot"
    return None


async def _dominant_detail(
    session: AsyncSession, umbrella: Umbrella, viewer_id: int | None
) -> list[dict]:
    """DEMOCRACY.md §3.3 item 5 — dominant solutions expanded with their
    amendments and their discussion. Non-dominant solutions have neither."""
    dominant = await solutions_repo.dominant_in_umbrella(session, umbrella.id)
    versions = await solutions_repo.current_versions(session, [s.id for s in dominant])
    out = []
    for solution in dominant:
        # ARCHITECTURE.md §6 — first page + next_cursor; the rest comes from
        # GET /solutions/{id}/amendments.
        amendments = await solutions_repo.amendments_for_page(
            session, solution.id, cursor=None, limit=_PAGE_SIZE
        )
        displays = await author_displays(session, [a.author_id for a in amendments])
        my_votes = (
            await votes_repo.user_votes_on(
                session, viewer_id, "amendment", [a.id for a in amendments]
            )
            if viewer_id
            else {}
        )
        current_text = versions[solution.id].text_body if solution.id in versions else ""
        from backend.services import amendments as amendments_service

        out.append(
            {
                "solution_id": solution.id,
                "text": current_text,
                "version": solution.current_version,
                "net_score": solution.net_score,
                "supporters": await solutions_repo.supporters(session, solution.id),
                "absorption_threshold": await amendments_service.absorption_threshold_for(
                    session, solution.id
                ),
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
                        "my_vote": my_votes.get(a.id),
                        "diff": amendments_service.diff(current_text, a.proposed_text),
                        "ai_influence": ai_log.influence(a.ai_contribution_percentage),
                        "created_at": a.created_at,
                    }
                    for a in amendments
                ],
                "amendments_next_cursor": (
                    amendments[-1].id if len(amendments) == _PAGE_SIZE else None
                ),
                "similar_pairs": await similarity_service.pairs_for_solution(
                    session, solution.id
                ),
                "discussion": await comments_service.thread(
                    session,
                    target_type="solution",
                    target_id=solution.id,
                    viewer_id=viewer_id,
                ),
            }
        )
    return out
