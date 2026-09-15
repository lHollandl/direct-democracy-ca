"""Reference-recommendation job (ARCHITECTURE.md §7, DEMOCRACY.md §9.4).

Runs after the admin's request commits, so the Ollama and search calls never
hold a request open — the same rationale `export.py::build_export`'s job
already follows. A failure never crashes the app and is never swallowed
(CLAUDE.md Law 12); it is only ever visible as the admin action never
gaining a matching `ai_actions` row.
"""

from __future__ import annotations

import logging
import uuid

from backend.db import session_scope
from backend.repositories import umbrellas as umbrellas_repo
from backend.services import references as references_service

log = logging.getLogger(__name__)


async def recommend_references_task(umbrella_id: int) -> None:
    job_id = uuid.uuid4().hex[:8]
    log.info(
        "job_start",
        extra={"job": "recommend_references", "job_id": job_id, "umbrella_id": umbrella_id},
    )
    try:
        async with session_scope() as session:
            umbrella = await umbrellas_repo.get(session, umbrella_id)
            if umbrella is None:
                log.warning(
                    "recommend_references_missing_umbrella",
                    extra={"job_id": job_id, "umbrella_id": umbrella_id},
                )
                return
            result = await references_service.recommend(session, umbrella=umbrella)
        log.info(
            "job_end",
            extra={"job": "recommend_references", "job_id": job_id, "added": len(result["added"])},
        )
    except Exception:
        log.exception(
            "job_failed",
            extra={"job": "recommend_references", "job_id": job_id, "umbrella_id": umbrella_id},
        )
