"""Account deletion and anonymization (DATABASE.md §3.1, CLAUDE.md §6).

"The civic record is preserved; the identity is removed." Every personal
column is erased. Home city and county are kept, because the posts, solutions
and votes have to stay in the right community and neither is identifying on its
own. Everything the person wrote stays, attributed to "Former Community Member".

One transaction, no exceptions.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import Unauthorized
from backend.models import User
from backend.repositories import users as users_repo
from backend.services import security
from backend.services.display import FORMER_MEMBER

log = logging.getLogger(__name__)

ERASED_DATE_OF_BIRTH = date(1900, 1, 1)
ERASED_PASSWORD_HASH = "!"


async def anonymize(session: AsyncSession, user: User) -> None:
    """The anonymization procedure, exactly as DATABASE.md §3.1 states it."""
    now = datetime.now(timezone.utc)
    await users_repo.anonymize(
        session,
        user.id,
        email=f"deleted+{user.id}@invalid",
        password_hash=ERASED_PASSWORD_HASH,
        display_name=FORMER_MEMBER,
        date_of_birth=ERASED_DATE_OF_BIRTH,
        gender="prefer_not_to_say",
        political_party="prefer_not_to_say",
        # county_id and city_id are deliberately kept (CLAUDE.md §6).
        deleted_at=now,
    )
    await users_repo.revoke_all_refresh_tokens(session, user.id)
    await users_repo.reset_display_mode(session, user.id, "display_name")
    await session.flush()
    log.info("account_anonymized", extra={"user_id": user.id})


async def set_display(session: AsyncSession, user: User, mode: str) -> dict:
    row = await users_repo.set_display_mode(session, user.id, mode)
    shown = {
        "real_name": user.real_name,
        "display_name": user.display_name,
        "anonymous": "Anonymous Community Member",
    }[row.public_name_mode]
    return {"public_name_mode": row.public_name_mode, "shown_as": shown}


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    """Deleting an account asks for the password first, because it cannot be
    undone."""
    if not security.verify_password(password, user.password_hash):
        raise Unauthorized(
            "That password is not right. Your account has not been changed.",
            code="bad_credentials",
        )
    await anonymize(session, user)
