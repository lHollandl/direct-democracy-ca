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
from backend.repositories import cycles as cycles_repo
from backend.repositories import email_changes as email_changes_repo
from backend.repositories import geography as geo_repo
from backend.repositories import home_changes as home_changes_repo
from backend.repositories import users as users_repo
from backend.services import security
from backend.services import settings as settings_service
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


async def _active_jury_duties(session: AsyncSession, user_id: int) -> list:
    """A jury the user is drawn or seated on whose cycle is not yet
    published — a redrawn (superseded) jury does not count."""
    duties = await cycles_repo.jury_duties_for_user(session, user_id)
    return [
        (juror, jury, cycle)
        for juror, jury, cycle in duties
        if jury.superseded_at is None
        and juror.status in ("drawn", "accepted")
        and cycle.state != "published"
    ]


async def _home_change_refusal(session: AsyncSession, user: User) -> tuple[str | None, datetime | None]:
    """The one-sentence reason a home change is refused right now, and the
    date the cooldown lifts (DEMOCRACY.md §2.3 rules 1-2). Both `None` when
    a change is allowed."""
    cooldown_days = int(await settings_service.get(session, "home_change_cooldown_days"))
    last_change = await home_changes_repo.latest_for_user(session, user.id)
    next_allowed_at = (
        last_change.changed_at + timedelta(days=cooldown_days) if last_change else None
    )
    if next_allowed_at is not None and datetime.now(timezone.utc) < next_allowed_at:
        return (
            f"You can change your home community again on "
            f"{next_allowed_at.date().isoformat()}. The first change after signup is "
            f"always free; after that it is once every {cooldown_days} days.",
            next_allowed_at,
        )
    if await _active_jury_duties(session, user.id):
        return (
            "You are serving on a jury that has not finished yet. You can change "
            "your home community once that cycle is published.",
            next_allowed_at,
        )
    return None, next_allowed_at


async def home_status(session: AsyncSession, user: User) -> dict:
    """`GET /me/home` (ARCHITECTURE.md §6) — current home, the date the next
    change is allowed, and any reason a change is refused now."""
    refusal, next_allowed_at = await _home_change_refusal(session, user)
    county = await geo_repo.get_county(session, user.county_id)
    city = await geo_repo.get_city(session, user.city_id) if user.city_id is not None else None
    return {
        "county": {"id": county.id, "name": county.name} if county else None,
        "city": {"id": city.id, "name": city.name} if city else None,
        "next_change_allowed_at": next_allowed_at,
        "refused_now_reason": refusal,
    }


async def change_home(
    session: AsyncSession, user: User, *, county_id: int, city_id: int | None
) -> dict:
    """`POST /me/home` (DEMOCRACY.md §2.3 "Changing home", rules 1-3).

    Rule 3 — never letting the move carry a vote into a ballot already under
    way — is not enforced here: it falls out of `user_home_changes` being the
    source ballot eligibility reads (DEMOCRACY.md §10.3,
    `services/ballots.py::_eligible`), so nothing here needs to know about
    cycles.
    """
    county = await geo_repo.get_county(session, county_id)
    if county is None:
        raise NotFound("That county is not in the list.", code="county_not_found")
    if city_id is not None:
        city = await geo_repo.get_city(session, city_id)
        if city is None:
            raise NotFound("That city is not in the list.", code="city_not_found")
        if city.county_id != county_id:
            raise ValidationFailed(
                "That city is not in the county you chose.", code="city_county_mismatch"
            )

    if county_id == user.county_id and city_id == user.city_id:
        raise ValidationFailed("That is already your home community.", code="home_unchanged")

    refusal, _next_allowed_at = await _home_change_refusal(session, user)
    if refusal is not None:
        raise Conflict(refusal, code="home_change_refused")

    await home_changes_repo.add(
        session,
        user_id=user.id,
        from_county_id=user.county_id,
        from_city_id=user.city_id,
        to_county_id=county_id,
        to_city_id=city_id,
    )
    await users_repo.update_profile(session, user.id, county_id=county_id, city_id=city_id)
    log.info("home_changed", extra={"user_id": user.id})
    return {
        "county_id": county_id,
        "city_id": city_id,
        "message": (
            "Your home community is updated. Posting, commenting and voting in "
            "the workshop follow your new home right away. A vote already under "
            "way in your old or new community sits this one out. Everything you "
            "already posted, said or voted stays where it was made."
        ),
    }


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
