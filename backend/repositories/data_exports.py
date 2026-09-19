"""The `data_exports` table (DATABASE.md §3.11)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import DataExport


async def add(session: AsyncSession, **fields) -> DataExport:
    row = DataExport(**fields)
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, export_id: int) -> DataExport | None:
    return await session.get(DataExport, export_id)


async def expired_with_file(session: AsyncSession, now: datetime) -> list[DataExport]:
    return list(
        (
            await session.execute(
                select(DataExport).where(
                    DataExport.expires_at < now, DataExport.file_path.is_not(None)
                )
            )
        )
        .scalars()
        .all()
    )
