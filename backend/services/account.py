"""Account deletion and anonymization (DATABASE.md §3.1, CLAUDE.md §6).

"The civic record is preserved; the identity is removed." Every personal
column is erased. Home city and county are kept, because the posts, solutions
and votes have to stay in the right community and neither is identifying on its
own. Everything the person wrote stays, attributed to "Former Community Member".

One transaction, no exceptions.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import email as email_client
from backend.config.settings_env import get_env_settings
from backend.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from backend.models import User
from backend.repositories import email_changes as email_changes_repo
from backend.repositories import home_changes as home_changes_repo
from backend.repositories import users as users_repo
from backend.services import security
from backend.services.display import FORMER_MEMBER

log = logging.getLogger(__name__)

ERASED_DATE_OF_BIRTH = date(1900, 1, 1)
ERASED_PASSWORD_HASH = "!"

PROFILE_FIELDS = ("real_name", "display_name", "gender", "political_party")


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
    # Past addresses and a pending email change are not part of the civic
    # record; the current community and the current email are what stays
    # (DATABASE.md §3.12, §3.13; CLAUDE.md §6).
    await home_changes_repo.delete_for_user(session, user.id)
    await email_changes_repo.delete_for_user(session, user.id)
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


async def update_profile(
    session: AsyncSession,
    user: User,
    *,
    real_name: str | None = None,
    display_name: str | None = None,
    gender: str | None = None,
    political_party: str | None = None,
) -> User:
    """`PATCH /me/profile` (ARCHITECTURE.md §6). Any of `real_name`,
    `display_name`, `gender`, `political_party` — date of birth is never
    editable. Display is resolved at read time everywhere (DATABASE.md
    §3.2), so a rename changes no hash on anything already posted."""
    fields: dict = {}
    if real_name is not None:
        fields["real_name"] = real_name.strip()
    if display_name is not None:
        display_name = display_name.strip()
        if (
            display_name.lower() != user.display_name.lower()
            and await users_repo.display_name_taken(session, display_name)
        ):
            raise Conflict(
                "That display name is already in use. Please choose another.",
                code="display_name_taken",
            )
        fields["display_name"] = display_name
    if gender is not None:
        fields["gender"] = gender
    if political_party is not None:
        fields["political_party"] = political_party
    if not fields:
        return user
    updated = await users_repo.update_profile(session, user.id, **fields)
    log.info("profile_updated", extra={"user_id": user.id, "fields": sorted(fields)})
    return updated


async def request_email_change(
    session: AsyncSession, user: User, *, new_email: str, password: str
) -> None:
    """`POST /me/email` (ARCHITECTURE.md §6). Nothing changes until the new
    address is confirmed; the old address is told, so an account takeover
    cannot go unnoticed."""
    if not security.verify_password(password, user.password_hash):
        raise Unauthorized(
            "That password is not right. Your email has not been changed.",
            code="bad_credentials",
        )
    new_email = new_email.strip().lower()
    if new_email == user.email.lower():
        raise ValidationFailed(
            "That is already your email address.", code="email_unchanged"
        )
    if await users_repo.by_email(session, new_email) is not None:
        raise Conflict(
            "An account already exists with that email address.", code="email_taken"
        )
    await email_changes_repo.void_unused_for_user(session, user.id)
    token = security.new_opaque_token()
    env = get_env_settings()
    await email_changes_repo.add(
        session,
        user_id=user.id,
        new_email=new_email,
        token_hash=security.token_fingerprint(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=env.EMAIL_VERIFY_HOURS),
    )
    await email_client.send(
        to=new_email,
        subject="Confirm your new email address — Direct Democracy CA",
        text_body=(
            "Confirm this address as the new sign-in email for your Direct "
            "Democracy CA account:\n\n"
            f"{env.absolute_url('/confirm-email-change')}?token={token}\n\n"
            f"The link works for {env.EMAIL_VERIFY_HOURS} hours. If you did "
            "not request this, ignore this message.\n"
        ),
    )
    await email_client.send(
        to=user.email,
        subject="Your email address is changing — Direct Democracy CA",
        text_body=(
            "Someone asked to change the sign-in email on your Direct "
            f"Democracy CA account to {new_email}. Nothing changes until "
            "that address is confirmed. If this was not you, sign in and "
            "change your password.\n"
        ),
    )
    log.info("email_change_requested", extra={"user_id": user.id})


async def confirm_email_change(session: AsyncSession, token: str) -> User:
    """`POST /auth/confirm-email-change` — also revokes every other refresh
    token (ARCHITECTURE.md §6)."""
    row = await email_changes_repo.by_token_hash(session, security.token_fingerprint(token))
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise ValidationFailed(
            "That confirmation link is no longer valid. Ask for a new one "
            "from your account page.",
            code="email_change_invalid",
        )
    if await users_repo.by_email(session, row.new_email) is not None:
        raise Conflict(
            "An account already exists with that email address.", code="email_taken"
        )
    row.used_at = now
    await users_repo.update_email(session, row.user_id, email=row.new_email)
    await users_repo.revoke_all_refresh_tokens(session, row.user_id)
    user = await users_repo.get_live(session, row.user_id)
    if user is None:
        raise NotFound("That account no longer exists.", code="user_not_found")
    log.info("email_changed", extra={"user_id": user.id})
    return user


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    """Deleting an account asks for the password first, because it cannot be
    undone."""
    if not security.verify_password(password, user.password_hash):
        raise Unauthorized(
            "That password is not right. Your account has not been changed.",
            code="bad_credentials",
        )
    await anonymize(session, user)
