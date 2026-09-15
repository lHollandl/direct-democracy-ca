"""Background jobs, started in the app lifespan (ARCHITECTURE.md §7). No Celery.

Each loop logs start, end, counts and failures with a job id. A failure never
crashes the app and never swallows the exception (CLAUDE.md Law 12).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from backend.jobs import exports as export_job
from backend.jobs import labeling as labeling_job
from backend.jobs import reconcile as reconcile_job

log = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []
RECONCILE_AT = time(hour=3, minute=0)
EXPORT_EXPIRY_INTERVAL_SECONDS = 3600
#: Last resort only, when `label_retry_minutes` cannot be read at all (the
#: settings table or Redis is unavailable) — not a substitute for the
#: setting, which decides no democratic status either way (CLAUDE.md Law 8;
#: audit demo-01 run 2).
LABEL_RETRY_FALLBACK_SECONDS = 600


async def start() -> None:
    _tasks.append(asyncio.create_task(_label_retry_loop(), name="label_retry"))
    _tasks.append(asyncio.create_task(_nightly_reconcile_loop(), name="reconcile"))
    _tasks.append(asyncio.create_task(_export_expiry_loop(), name="expire_exports"))
    log.info("background_jobs_started", extra={"jobs": [t.get_name() for t in _tasks]})


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: B014 - never crash on shutdown, but log it (Law 12)
            log.warning(
                "background_job_failed_on_shutdown", exc_info=True, extra={"job": task.get_name()}
            )
    _tasks.clear()
    log.info("background_jobs_stopped")


async def _label_retry_loop() -> None:
    while True:
        try:
            interval = await labeling_job.retry_interval_seconds()
        except Exception:
            log.exception("label_retry_interval_unavailable")
            interval = LABEL_RETRY_FALLBACK_SECONDS
        await asyncio.sleep(interval)
        await labeling_job.label_retry_task()


async def _nightly_reconcile_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until(RECONCILE_AT))
        await reconcile_job.reconcile_task()


async def _export_expiry_loop() -> None:
    while True:
        await asyncio.sleep(EXPORT_EXPIRY_INTERVAL_SECONDS)
        await export_job.expire_exports_task()


def _seconds_until(target: time) -> float:
    now = datetime.now(timezone.utc)
    next_run = now.replace(
        hour=target.hour, minute=target.minute, second=0, microsecond=0
    )
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()
