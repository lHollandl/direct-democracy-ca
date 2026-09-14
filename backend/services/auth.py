"""Signup, sign-in, tokens, verification and password reset (ARCHITECTURE.md §4).

Every function here owns its transaction. Nothing in this module knows what an
HTTP request is; the routers shape the responses.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import email as email_client
from backend.clients import redis as redis_client
from backend.config.settings_env import get_env_settings
from backend.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from backend.models import User
from backend.repositories import geography as geo_repo
from backend.repositories import users as users_repo
from backend.services import security
from backend.services import settings as settings_service

log = logging.getLogger(__name__)

#: Where the verification and reset links point. The frontend owns those pages;
#: the backend only needs to know the origin, which is configuration.
def _frontend_origin() -> str:
    origins = get_env_settings().cors_origin_list
    return origins[0] if origins else "http://localhost:3000"


def age_on(born: date, day: date) -> int:
    return day.year - born.year - ((day.month, day.day) < (born.month, born.day))


async def signup(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    real_name: str,
    display_name: str,
    date_of_birth: date,
    gender: str,
    political_party: str,
    county_id: int,
    city_id: int,
    terms_version: str,
    ip_address: str,
) -> tuple[User, str]:
    """Create an account and issue an email-verification token.

    Returns the user and the raw verification token, which only the email
    client ever sees. Under-age applicants are refused before anything is
    written (DEMOCRACY.md §2.3).
    """
    today = datetime.now(timezone.utc).date()
    min_age = int(await settings_service.get(session, "min_signup_age"))
    if age_on(date_of_birth, today) < min_age:
        raise ValidationFailed(
            f"You need to be at least {min_age} to join. Nothing you entered has been saved.",
            code="too_young",
        )

    security.validate_password(password)

    if await users_repo.by_email(session, email) is not None:
        raise Conflict(
            "An account already exists with that email address.", code="email_taken"
        )
    if await users_repo.display_name_taken(session, display_name):
        raise Conflict(
            "That display name is already in use. Please choose another.",
            code="display_name_taken",
        )

    city = await geo_repo.get_city(session, city_id)
    if city is None:
        raise NotFound("That city is not in the list.", code="city_not_found")
    if city.county_id != county_id:
        raise ValidationFailed(
            "That city is not in the county you chose.", code="city_county_mismatch"
        )
    county = await geo_repo.get_county(session, county_id)
    if county is None:
        raise NotFound("That county is not in the list.", code="county_not_found")

    terms = await users_repo.terms_by_version(session, terms_version)
    if terms is None:
        raise ValidationFailed(
            "The terms you agreed to are not the current ones. Please reload the page.",
            code="terms_version_unknown",
        )

    user = await users_repo.create(
        session,
        email=email.strip(),
        password_hash=security.hash_password(password),
        real_name=real_name.strip(),
        display_name=display_name.strip(),
        date_of_birth=date_of_birth,
        gender=gender,
        political_party=political_party,
        county_id=county_id,
        city_id=city_id,
        verification_level="unverified",
    )
    await users_repo.create_display_settings(session, user.id)
    await users_repo.add_terms_acceptance(
        session,
        user_id=user.id,
        terms_version_id=terms.id,
        ip_hash=security.hash_ip(ip_address),
    )

    token = security.new_opaque_token()
    env = get_env_settings()
    await users_repo.add_email_verification(
        session,
        user_id=user.id,
        token_hash=security.token_fingerprint(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=env.EMAIL_VERIFY_HOURS),
    )
    await email_client.send(
        to=user.email,
        subject="Confirm your email address — Direct Democracy Cali",
        text_body=(
            f"Welcome, {user.display_name}.\n\n"
            "Confirm your email address to start posting, voting and commenting:\n\n"
            f"{_frontend_origin()}/verify-email?token={token}\n\n"
            f"The link works for {env.EMAIL_VERIFY_HOURS} hours. "
            "If you did not create this account, ignore this message.\n"
        ),
    )
    log.info("signup", extra={"user_id": user.id})
    return user, token


async def verify_email(session: AsyncSession, token: str) -> User:
    row = await users_repo.email_verification_by_hash(
        session, security.token_fingerprint(token)
    )
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise ValidationFailed(
            "That confirmation link is no longer valid. Ask for a new one from the sign-in page.",
            code="verification_invalid",
        )
    row.used_at = now
    await users_repo.mark_email_verified(session, row.user_id)
    user = await users_repo.get_live(session, row.user_id)
    if user is None:
        raise NotFound("That account no longer exists.", code="user_not_found")
    log.info("email_verified", extra={"user_id": user.id})
    return user


async def login(
    session: AsyncSession, *, email: str, password: str
) -> tuple[User, str, str, datetime]:
    """Returns (user, access token, raw refresh token, refresh expiry)."""
    user = await users_repo.by_email(session, email)
    if user is None or user.deleted_at is not None:
        # The same message either way, so the endpoint cannot be used to learn
        # which email addresses have accounts.
        raise Unauthorized("Email or password is incorrect.", code="bad_credentials")
    if not security.verify_password(password, user.password_hash):
        raise Unauthorized("Email or password is incorrect.", code="bad_credentials")
    access, _jti, _exp = security.create_access_token(user.id)
    refresh, refresh_expiry = await _issue_refresh_token(session, user.id)
    await users_repo.touch_last_active(session, user.id)
    log.info("login", extra={"user_id": user.id})
    return user, access, refresh, refresh_expiry


async def _issue_refresh_token(
    session: AsyncSession, user_id: int, replaces: int | None = None
) -> tuple[str, datetime]:
    env = get_env_settings()
    raw = security.new_opaque_token()
    expires = datetime.now(timezone.utc) + timedelta(days=env.REFRESH_TOKEN_DAYS)
    row = await users_repo.add_refresh_token(
        session,
        user_id=user_id,
        token_hash=security.token_fingerprint(raw),
        expires_at=expires,
    )
    if replaces is not None:
        old = await session.get(type(row), replaces)
        if old is not None:
            old.replaced_by_id = row.id
            old.revoked_at = datetime.now(timezone.utc)
    await session.flush()
    return raw, expires


async def refresh(session: AsyncSession, raw_refresh_token: str) -> tuple[User, str, str, datetime]:
    """Rotate a refresh token. Presenting a token that was already replaced
    revokes its whole chain (ARCHITECTURE.md §4)."""
    row = await users_repo.refresh_token_by_hash(
        session, security.token_fingerprint(raw_refresh_token)
    )
    now = datetime.now(timezone.utc)
    if row is None:
        raise Unauthorized("Please sign in again.", code="refresh_invalid")
    if row.replaced_by_id is not None or row.revoked_at is not None:
        # The revocation has to outlive this request. Raising `Unauthorized`
        # rolls the request's transaction back, so the chain is revoked in its
        # own committed transaction first — otherwise a stolen token would
        # survive the very check that detected it.
        revoked = await _revoke_chain_in_own_transaction(row.id)
        log.warning(
            "refresh_token_reuse_detected",
            extra={"user_id": row.user_id, "revoked_tokens": revoked},
        )
        raise Unauthorized(
            "For your safety we signed you out of every device. Please sign in again.",
            code="refresh_reused",
        )
    if row.expires_at < now:
        raise Unauthorized("Please sign in again.", code="refresh_expired")

    user = await users_repo.get_live(session, row.user_id)
    if user is None:
        raise Unauthorized("Please sign in again.", code="refresh_invalid")

    new_raw, expires = await _issue_refresh_token(session, user.id, replaces=row.id)
    access, _jti, _exp = security.create_access_token(user.id)
    return user, access, new_raw, expires


async def _revoke_chain_in_own_transaction(refresh_token_id: int) -> int:
    from backend.db import session_scope
    from backend.models import RefreshToken

    async with session_scope() as fresh:
        row = await fresh.get(RefreshToken, refresh_token_id)
        if row is None:
            return 0
        return await users_repo.revoke_refresh_chain(fresh, row)


async def logout(
    session: AsyncSession, *, raw_refresh_token: str | None, access_jti: str | None, access_exp: int | None
) -> None:
    """Revoke the refresh token and blacklist the access token's jti for the
    remainder of its life (ARCHITECTURE.md §4)."""
    if raw_refresh_token:
        row = await users_repo.refresh_token_by_hash(
            session, security.token_fingerprint(raw_refresh_token)
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            await session.flush()
    if access_jti and access_exp:
        remaining = access_exp - int(datetime.now(timezone.utc).timestamp())
        await redis_client.blacklist_jti(access_jti, remaining)


async def forgot_password(session: AsyncSession, email: str) -> str | None:
    """Always succeeds from the caller's point of view, so the endpoint cannot
    be used to find out which addresses have accounts. Returns the raw token
    for the test suite; the router never returns it."""
    user = await users_repo.by_email(session, email)
    if user is None or user.deleted_at is not None:
        log.info("password_reset_requested_for_unknown_address")
        return None
    env = get_env_settings()
    token = security.new_opaque_token()
    await users_repo.add_password_reset(
        session,
        user_id=user.id,
        token_hash=security.token_fingerprint(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=env.PASSWORD_RESET_MINUTES),
    )
    await email_client.send(
        to=user.email,
        subject="Reset your password — Direct Democracy Cali",
        text_body=(
            f"Someone asked to reset the password for this account.\n\n"
            f"{_frontend_origin()}/reset-password?token={token}\n\n"
            f"The link works for {env.PASSWORD_RESET_MINUTES} minutes. "
            "If it was not you, ignore this message — nothing has changed.\n"
        ),
    )
    return token


async def reset_password(session: AsyncSession, *, token: str, new_password: str) -> User:
    row = await users_repo.password_reset_by_hash(session, security.token_fingerprint(token))
    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        raise ValidationFailed(
            "That reset link is no longer valid. Ask for a new one.", code="reset_invalid"
        )
    security.validate_password(new_password)
    user = await users_repo.get_live(session, row.user_id)
    if user is None:
        raise NotFound("That account no longer exists.", code="user_not_found")
    user.password_hash = security.hash_password(new_password)
    row.used_at = now
    # A password reset signs out every existing session.
    await users_repo.revoke_all_refresh_tokens(session, user.id)
    await session.flush()
    log.info("password_reset", extra={"user_id": user.id})
    return user


async def require_verified(user: User) -> None:
    if user.email_verified_at is None:
        raise Forbidden(
            "Confirm your email address before posting, voting or commenting. "
            "Check your inbox for the link we sent when you signed up.",
            code="email_not_verified",
        )
