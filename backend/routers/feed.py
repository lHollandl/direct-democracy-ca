"""The feed (DEMOCRACY.md §12). Newest first. No ranking."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import OptionalUser, SessionDep
from backend.repositories import posts as posts_repo
from backend.repositories import umbrellas as umbrellas_repo
from backend.routers.common import CursorParam, DEFAULT_LIMIT, LimitParam
from backend.services import ai_log
from backend.services import community as community_service
from backend.services import posts as posts_service
from backend.services import rules
from backend.services.display import author_displays

router = APIRouter(tags=["feed"])


class FeedOut(BaseModel):
    ranking: str
    explanation: str
    items: list[dict]
    next_cursor: int | None
    filters: dict


@router.get("/feed", response_model=FeedOut)
async def feed(
    session: SessionDep,
    viewer: OptionalUser,
    community: str | None = Query(
        default=None, description="level:entity_id, e.g. city:42"
    ),
    category: str | None = Query(default=None, description="main category slug"),
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> FeedOut:
    community_filter = None
    if community:
        level, _, raw_id = community.partition(":")
        resolved = await community_service.resolve(session, level, int(raw_id))
        community_filter = (resolved.level, resolved.entity_id)

    category_id = None
    if category:
        row = await umbrellas_repo.category_by_slug(session, category)
        category_id = row.id if row else -1

    home_keys = None
    if community_filter is None and viewer is not None:
        home_keys = [c.key for c in await community_service.home_communities(session, viewer)]

    rows = await posts_repo.feed_page(
        session,
        cursor=cursor,
        limit=limit,
        community=community_filter,
        main_category_id=category_id,
        community_keys=home_keys,
    )
    displays = await author_displays(session, [p.author_id for p in rows])
    items = []
    for post in rows:
        communities = await posts_repo.communities(session, post.id)
        items.append(
            {
                "id": post.id,
                "title": posts_service.derive_title(post.problem_text),
                "problem_text": post.problem_text,
                "author": displays.get(post.author_id, "Former Community Member"),
                "created_at": post.created_at,
                "label_status": post.label_status,
                "ai_influence": ai_log.influence(post.ai_contribution_percentage),
                "communities": [
                    {
                        "level": c.community_level,
                        "entity_id": c.community_entity_id,
                        "umbrella_id": c.umbrella_id,
                    }
                    for c in communities
                ],
            }
        )
    return FeedOut(
        ranking=rules.FEED_VERSION,
        explanation=rules.FEED_EXPLANATION,
        items=items,
        next_cursor=rows[-1].id if len(rows) == limit else None,
        filters={
            "community": community,
            "category": category,
            "default": (
                "your home communities"
                if home_keys
                else "everything, newest first"
            ),
        },
    )
