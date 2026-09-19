"""The one place that counts every table generically, for the nightly
reconciliation's before/after snapshot (DATABASE.md §7). Not one aggregate's
repository — a schema-wide count belongs here rather than in any of them."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Base


async def table_counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for name, table in sorted(Base.metadata.tables.items()):
        counts[name] = int(
            (await session.execute(select(func.count()).select_from(table))).scalar_one()
        )
    return counts
