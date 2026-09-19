"""The feed (DEMOCRACY.md §12). Newest first. No ranking."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import OptionalUser, SessionDep
from backend.routers.common import CursorParam, DEFAULT_LIMIT, LimitParam
from backend.services import posts as posts_service
from backend.services import rules

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
    result = await posts_service.feed(
        session,
        viewer=viewer,
        community=community,
        category=category,
        cursor=cursor,
        limit=limit,
    )
    return FeedOut(
        ranking=rules.FEED_VERSION,
        explanation=rules.FEED_EXPLANATION,
        **result,
    )
