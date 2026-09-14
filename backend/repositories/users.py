"""The `users` table and everything keyed to one user's account."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    EmailVerification,
    PasswordReset,
    RefreshToken,
    TermsAcceptance,
    TermsVersion,
    User,
    UserDisplaySettings,
)


async def get(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_live(session: AsyncSession, user_id: int) -> User | None:
    return (
        await session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()


async def by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


async def display_name_taken(session: AsyncSession, display_name: str) -> bool:
    row = (
        await session.execute(
            select(User.id).where(
                func.lower(User.display_name) == display_name.lower(),
                User.deleted_at.is_(None),
            )
        )
    ).first()
    return row is not None


async def create(session: AsyncSession, **fields) -> User:
    user = User(**fields)
    session.add(user)
    await session.flush()
    return user


async def display_settings(session: AsyncSession, user_id: int) -> UserDisplaySettings | None:
    return await session.get(UserDisplaySettings, user_id)


async def create_display_settings(
    session: AsyncSession, user_id: int, mode: str = "display_name"
) -> UserDisplaySettings:
    row = UserDisplaySettings(user_id=user_id, public_name_mode=mode)
    session.add(row)
    await session.flush()
    return row


async def set_display_mode(session: AsyncSession, user_id: int, mode: str) -> UserDisplaySettings:
    row = await session.get(UserDisplaySettings, user_id)
    if row is None:
        return await create_display_settings(session, user_id, mode)
    row.public_name_mode = mode
    await session.flush()
    return row


async def touch_last_active(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(last_active_at=datetime.now(timezone.utc))
    )


async def mark_email_verified(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(email_verified_at=datetime.now(timezone.utc))
    )


# --- tokens ---------------------------------------------------------------


async def add_refresh_token(
    session: AsyncSession, *, user_id: int, token_hash: str, expires_at: datetime
) -> RefreshToken:
    row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row


async def refresh_token_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()


async def revoke_refresh_chain(session: AsyncSession, token: RefreshToken) -> int:
    """Reuse of a replaced token revokes the whole chain (ARCHITECTURE.md §4)."""
    revoked = 0
    now = datetime.now(timezone.utc)
    seen: set[int] = set()
    frontier = [token]
    while frontier:
        current = frontier.pop()
        if current.id in seen:
            continue
        seen.add(current.id)
        if current.revoked_at is None:
            current.revoked_at = now
            revoked += 1
        children = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.replaced_by_id == current.id)
            )
        ).scalars().all()
        frontier.extend(children)
        if current.replaced_by_id:
            nxt = await session.get(RefreshToken, current.replaced_by_id)
            if nxt is not None:
                frontier.append(nxt)
    await session.flush()
    return revoked


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def add_email_verification(
    session: AsyncSession, *, user_id: int, token_hash: str, expires_at: datetime
) -> EmailVerification:
    row = EmailVerification(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row


async def email_verification_by_hash(
    session: AsyncSession, token_hash: str
) -> EmailVerification | None:
    return (
        await session.execute(
            select(EmailVerification).where(EmailVerification.token_hash == token_hash)
        )
    ).scalar_one_or_none()


async def add_password_reset(
    session: AsyncSession, *, user_id: int, token_hash: str, expires_at: datetime
) -> PasswordReset:
    row = PasswordReset(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row


async def password_reset_by_hash(session: AsyncSession, token_hash: str) -> PasswordReset | None:
    return (
        await session.execute(select(PasswordReset).where(PasswordReset.token_hash == token_hash))
    ).scalar_one_or_none()


# --- terms ----------------------------------------------------------------


async def latest_terms(session: AsyncSession) -> TermsVersion | None:
    return (
        await session.execute(
            select(TermsVersion).order_by(TermsVersion.published_at.desc(), TermsVersion.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def terms_by_version(session: AsyncSession, version: str) -> TermsVersion | None:
    return (
        await session.execute(select(TermsVersion).where(TermsVersion.version == version))
    ).scalar_one_or_none()


async def add_terms_acceptance(
    session: AsyncSession, *, user_id: int, terms_version_id: int, ip_hash: str
) -> TermsAcceptance:
    row = TermsAcceptance(user_id=user_id, terms_version_id=terms_version_id, ip_hash=ip_hash)
    session.add(row)
    await session.flush()
    return row


async def terms_acceptances(session: AsyncSession, user_id: int) -> list[TermsAcceptance]:
    return list(
        (
            await session.execute(
                select(TermsAcceptance).where(TermsAcceptance.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )


async def refresh_token_by_id(session: AsyncSession, token_id: int) -> RefreshToken | None:
    return await session.get(RefreshToken, token_id)


# --- anonymization (DATABASE.md §3.1) --------------------------------------


async def anonymize(
    session: AsyncSession,
    user_id: int,
    *,
    email: str,
    password_hash: str,
    display_name: str,
    date_of_birth,
    gender: str,
    political_party: str,
    deleted_at,
) -> None:
    """county_id and city_id are deliberately left untouched (CLAUDE.md §6)."""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            email=email,
            password_hash=password_hash,
            real_name="",
            display_name=display_name,
            date_of_birth=date_of_birth,
            gender=gender,
            political_party=political_party,
            last_active_at=None,
            deleted_at=deleted_at,
        )
    )


async def reset_display_mode(session: AsyncSession, user_id: int, mode: str) -> None:
    await session.execute(
        update(UserDisplaySettings).where(UserDisplaySettings.user_id == user_id).values(
            public_name_mode=mode
        )
    )


# --- display and community-scoped counts -----------------------------------


async def display_rows(session: AsyncSession, user_ids: list[int]) -> list:
    """`(id, real_name, display_name, deleted_at, public_name_mode)` per user,
    one query for a page full of authors."""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return []
    return (
        await session.execute(
            select(
                User.id,
                User.real_name,
                User.display_name,
                User.deleted_at,
                UserDisplaySettings.public_name_mode,
            )
            .outerjoin(UserDisplaySettings, UserDisplaySettings.user_id == User.id)
            .where(User.id.in_(ids))
        )
    ).all()


def _community_clause(level: str, entity_id: int):
    from backend.models import County
    from backend.errors import ValidationFailed

    if level == "city":
        return User.city_id == entity_id
    if level == "county":
        return User.county_id == entity_id
    if level == "state":
        return User.county_id.in_(select(County.id).where(County.state_id == entity_id))
    raise ValidationFailed(f"{level!r} is not a governance level.", code="unknown_community_level")


async def count_active_members(
    session: AsyncSession, level: str, entity_id: int, cutoff: datetime
) -> int:
    """DEMOCRACY.md §2.4 — active members of one community."""
    stmt = (
        select(func.count())
        .select_from(User)
        .where(
            _community_clause(level, entity_id),
            User.deleted_at.is_(None),
            User.email_verified_at.is_not(None),
            User.last_active_at.is_not(None),
            User.last_active_at >= cutoff,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def active_member_ids(
    session: AsyncSession, level: str, entity_id: int, cutoff: datetime, *, exclude_admins: bool
) -> list[int]:
    """DEMOCRACY.md §8.1 — the jury-draw candidate pool before exclusions."""
    stmt = select(User.id).where(
        _community_clause(level, entity_id),
        User.deleted_at.is_(None),
        User.email_verified_at.is_not(None),
        User.last_active_at.is_not(None),
        User.last_active_at >= cutoff,
    )
    if exclude_admins:
        stmt = stmt.where(User.is_admin.is_(False))
    return list((await session.execute(stmt)).scalars().all())
