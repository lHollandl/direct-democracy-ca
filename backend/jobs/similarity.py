"""The similarity check, run after an amendment is created (ARCHITECTURE.md §7)."""

from __future__ import annotations

import logging
import uuid

from backend.db import session_scope
from backend.services import similarity as similarity_service

log = logging.getLogger(__name__)


async def similarity_check_task(amendment_id: int) -> None:
    job_id = uuid.uuid4().hex[:8]
    log.info(
        "job_start",
        extra={"job": "similarity_check", "job_id": job_id, "amendment_id": amendment_id},
    )
    try:
        async with session_scope() as session:
            amendment = await similarity_service.load_amendment_for_job(session, amendment_id)
            if amendment is None:
                log.warning("similarity_amendment_missing", extra={"job_id": job_id})
                return
            flagged = await similarity_service.check_new_amendment(session, amendment)
        log.info(
            "job_end",
            extra={"job": "similarity_check", "job_id": job_id, "flagged": len(flagged)},
        )
    except Exception:
        log.exception(
            "job_failed",
            extra={"job": "similarity_check", "job_id": job_id, "amendment_id": amendment_id},
        )
