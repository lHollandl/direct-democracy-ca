"""Labeling jobs (ARCHITECTURE.md §7).

`label_post` runs after `POST /posts` commits. `label_retry` re-queues posts
whose labeling failed, every `label_retry_minutes`. A failure never crashes the
app and is never swallowed (CLAUDE.md Law 12).
"""

from __future__ import annotations

import logging
import uuid

from backend.db import session_scope
from backend.repositories import posts as posts_repo
from backend.services import labeling
from backend.services import settings as settings_service

log = logging.getLogger(__name__)


async def label_post_task(post_id: int) -> None:
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "label_post", "job_id": job_id, "post_id": post_id})
    try:
        async with session_scope() as session:
            post = await posts_repo.get(session, post_id)
            if post is None:
                log.warning("label_post_missing", extra={"job_id": job_id, "post_id": post_id})
                return
            result = await labeling.label_post(session, post)
        log.info("job_end", extra={"job": "label_post", "job_id": job_id, **result})
    except Exception:
        log.exception("job_failed", extra={"job": "label_post", "job_id": job_id, "post_id": post_id})
        try:
            async with session_scope() as session:
                await posts_repo.set_label_status(session, post_id, "unlabeled")
        except Exception:
            log.exception("label_status_rollback_failed", extra={"post_id": post_id})


async def label_retry_task() -> dict:
    """Re-queue every post still marked `unlabeled` (DEMOCRACY.md §4.1)."""
    job_id = uuid.uuid4().hex[:8]
    log.info("job_start", extra={"job": "label_retry", "job_id": job_id})
    retried = 0
    succeeded = 0
    try:
        async with session_scope() as session:
            pending = await posts_repo.unlabeled_posts(session)
            post_ids = [p.id for p in pending]
        for post_id in post_ids:
            retried += 1
            async with session_scope() as session:
                post = await posts_repo.get(session, post_id)
                if post is None:
                    continue
                result = await labeling.label_post(session, post)
            if result.get("status") in ("labeled", "needs_review"):
                succeeded += 1
    except Exception:
        log.exception("job_failed", extra={"job": "label_retry", "job_id": job_id})
    counts = {"retried": retried, "succeeded": succeeded}
    log.info("job_end", extra={"job": "label_retry", "job_id": job_id, **counts})
    return counts


async def retry_interval_seconds() -> int:
    async with session_scope() as session:
        minutes = int(await settings_service.get(session, "label_retry_minutes"))
    return max(minutes, 1) * 60
