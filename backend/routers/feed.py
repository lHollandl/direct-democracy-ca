"""The feed (DEMOCRACY.md §12.1) — feed-v1: search plus four plain sorts."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import OptionalUser, SessionDep
from backend.routers.common import DEFAULT_LIMIT, LimitParam
from backend.services import posts as posts_service
from backend.services import rules

router = APIRouter(tags=["feed"])

FeedCursorParam = Annotated[
    str | None, Query(description="Opaque token from a previous page's next_cursor")
]
SortParam = Literal["newest", "oldest", "most_votes", "most_comments"]


class FeedOut(BaseModel):
    ranking: str
    sort: str
    explanation: str
    items: list[dict]
    next_cursor: str | None
    filters: dict


@router.get("/feed", response_model=FeedOut)
async def feed(
    session: SessionDep,
    viewer: OptionalUser,
    scope: Literal["home", "all"] | None = Query(
        default=None, description="'all' widens a signed-in viewer to every community"
    ),
    community: str | None = Query(
        default=None, description="level:entity_id, e.g. city:42"
    ),
    category: str | None = Query(default=None, description="main category slug"),
    q: str | None = Query(
        default=None, min_length=2, max_length=100, description="Full-text search"
    ),
    sort: SortParam = rules.DEFAULT_FEED_SORT,
    cursor: FeedCursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> FeedOut:
    result = await posts_service.feed(
        session,
        viewer=viewer,
        scope=scope,
        community=community,
        category=category,
        q=q,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    return FeedOut(
        ranking=rules.FEED_VERSION,
        sort=sort,
        explanation=rules.FEED_SORTS[sort],
        **result,
    )
