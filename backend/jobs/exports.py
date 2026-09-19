"""Export jobs: build a requested export, and expire old files (ARCHITECTURE.md §7)."""

from __future__ import annotations

import logging
import uuid

from backend.db import session_scope
from backend.services import export as export_service

log = logging.getLogger(__name__)


async def build_export_task(export_id: int) -> None:
    """A failure here never crashes the app and is never swallowed (Law 12)."""
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "build_export", "job_id": job_id, "export_id": export_id})
    try:
        async with session_scope() as session:
            await export_service.build_export(session, export_id)
        log.info("job_end", extra={"job": "build_export", "job_id": job_id, "export_id": export_id})
    except Exception:
        log.exception(
            "job_failed", extra={"job": "build_export", "job_id": job_id, "export_id": export_id}
        )


async def expire_exports_task() -> int:
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "expire_exports", "job_id": job_id})
    try:
        async with session_scope() as session:
            removed = await export_service.expire_exports(session)
        log.info(
            "job_end", extra={"job": "expire_exports", "job_id": job_id, "files_removed": removed}
        )
        return removed
    except Exception:
        log.exception("job_failed", extra={"job": "expire_exports", "job_id": job_id})
        return 0
