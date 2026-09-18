"""Nightly reconciliation job (ARCHITECTURE.md §7).

Calls only `backend.services.reconcile` — the reconciliation logic itself
(DATABASE.md §7) lives there, since a job may call services only and never a
repository or the session directly (ARCHITECTURE.md §2).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import session_scope
from backend.services import reconcile as reconcile_service

log = logging.getLogger(__name__)


async def reconcile_task(correct: bool = True) -> dict:
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "reconcile", "job_id": job_id})
    try:
        async with session_scope() as session:
            report = await run(session, correct=correct)
        log.info("job_end", extra={"job": "reconcile", "job_id": job_id, **_counts(report)})
        return report
    except Exception:
        log.exception("job_failed", extra={"job": "reconcile", "job_id": job_id})
        return {"error": "reconcile failed; see the log"}


def _counts(report: dict) -> dict:
    return {
        "net_score_drift": len(report["net_score_drift"]),
        "dominance_changes": len(report["dominance_changes"]),
        "orphan_communities": len(report["orphan_communities"]),
        "hash_mismatches": len(report["hash_mismatches"]),
    }


async def run(session: AsyncSession, *, correct: bool = True) -> dict:
    return await reconcile_service.run(session, correct=correct)


async def main() -> None:
    """`python -m backend.jobs.reconcile` runs it on demand."""
    import json

    from backend.db import dispose_engine
    from backend.logging_config import configure_logging

    configure_logging("INFO")
    async with session_scope() as session:
        report = await run(session, correct=True)
    await dispose_engine()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
