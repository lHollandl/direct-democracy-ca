"""Export jobs: build a requested export, and expire old files (ARCHITECTURE.md §7)."""

from __future__ import annotations

import logging

from backend.db import session_scope
from backend.services import export as export_service

log = logging.getLogger(__name__)


async def build_export_task(export_id: int) -> None:
    """A failure here never crashes the app and is never swallowed (Law 12)."""
    try:
        async with session_scope() as session:
            await export_service.build_export(session, export_id)
    except Exception:
        log.exception("export_build_failed", extra={"export_id": export_id})


async def expire_exports_task() -> int:
    try:
        async with session_scope() as session:
            removed = await export_service.expire_exports(session)
        log.info("exports_expired", extra={"files_removed": removed})
        return removed
    except Exception:
        log.exception("export_expiry_failed")
        return 0
