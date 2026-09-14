"""FastAPI dependencies: who is calling, and what they are allowed to do.

ARCHITECTURE.md §4 defines four: `current_user` (a valid, non-deleted account),
`verified_user` (email confirmed), `admin_user`, and `community_member`.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import redis as redis_client
from backend.db import get_session
from backend.errors import Forbidden, Unauthorized
from backend.models import User
from backend.repositories import users as users_repo
from backend.services import auth as auth_service
from backend.services import community as community_service
from backend.services import security

log = logging.getLogger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

#: `last_active_at` is the source for the active-user count (DEMOCRACY.md
#: §2.4). Writing it on every request would be a write per read, so Redis
#: debounces it to at most once per minute per user (ARCHITECTURE.md §4).
LAST_ACTIVE_DEBOUNCE_SECONDS = 60


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


async def current_user(request: Request, session: SessionDep) -> User:
    token = _bearer_token(request)
    if not token:
        raise Unauthorized("Please sign in to do that.", code="not_signed_in")
    payload = security.decode_access_token(token)
    jti = payload.get("jti")
    if jti and await redis_client.is_jti_blacklisted(jti):
        raise Unauthorized("That session has been signed out.", code="token_revoked")
    user = await users_repo.get_live(session, int(payload["sub"]))
    if user is None:
        raise Unauthorized("That account no longer exists.", code="user_not_found")
    await _debounced_touch(session, user.id)
    return user


async def _debounced_touch(session: AsyncSession, user_id: int) -> None:
    try:
        fresh = await redis_client.set_if_absent(
            f"lastactive:{user_id}", "1", LAST_ACTIVE_DEBOUNCE_SECONDS
        )
    except Exception:
        log.warning("last_active_debounce_unavailable", extra={"user_id": user_id})
        fresh = True
    if fresh:
        await users_repo.touch_last_active(session, user_id)


async def optional_user(request: Request, session: SessionDep) -> User | None:
    """For public pages that show a little more to a signed-in reader."""
    if not _bearer_token(request):
        return None
    try:
        return await current_user(request, session)
    except Unauthorized:
        return None


CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]


async def verified_user(user: CurrentUser) -> User:
    await auth_service.require_verified(user)
    return user


VerifiedUser = Annotated[User, Depends(verified_user)]


async def admin_user(user: VerifiedUser) -> User:
    if not user.is_admin:
        raise Forbidden("That is an administrator action.", code="not_admin")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


async def require_member(
    session: AsyncSession, user: User, level: str, entity_id: int
) -> None:
    """DEMOCRACY.md §2.3 — users may read any community but act only in their
    own three."""
    if not await community_service.is_member(session, user, level, entity_id):
        community = await community_service.resolve(session, level, entity_id)
        raise Forbidden(
            f"You can read everything in {community.label}, but you can only post, "
            "comment and vote in your own city, your county and California.",
            code="not_a_member",
        )
