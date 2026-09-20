"""`email_change_requests` (DATABASE.md §3.13). Single use; a newer request
voids older unused ones; deleted whole on anonymization."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import EmailChangeRequest


async def add(
    session: AsyncSession, *, user_id: int, new_email: str, token_hash: str, expires_at: datetime
) -> EmailChangeRequest:
    row = EmailChangeRequest(
        user_id=user_id, new_email=new_email, token_hash=token_hash, expires_at=expires_at
    )
    session.add(row)
    await session.flush()
    return row


async def void_unused_for_user(session: AsyncSession, user_id: int) -> None:
    """A newer request voids older unused ones (DATABASE.md §3.13)."""
    await session.execute(
        update(EmailChangeRequest)
        .where(EmailChangeRequest.user_id == user_id, EmailChangeRequest.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )


async def by_token_hash(session: AsyncSession, token_hash: str) -> EmailChangeRequest | None:
    return (
        await session.execute(
            select(EmailChangeRequest).where(EmailChangeRequest.token_hash == token_hash)
        )
    ).scalar_one_or_none()


async def pending_for_user(session: AsyncSession, user_id: int) -> list[EmailChangeRequest]:
    """Unused, unexpired requests — the user's data export (DATABASE.md §3.11)."""
    now = datetime.now(timezone.utc)
    return list(
        (
            await session.execute(
                select(EmailChangeRequest).where(
                    EmailChangeRequest.user_id == user_id,
                    EmailChangeRequest.used_at.is_(None),
                    EmailChangeRequest.expires_at > now,
                )
            )
        )
        .scalars()
        .all()
    )


async def delete_for_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(EmailChangeRequest).where(EmailChangeRequest.user_id == user_id))
