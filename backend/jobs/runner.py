"""Starting a background job from a request, safely.

FastAPI's `BackgroundTasks` attaches work to the response, and that work is
cancelled when the client disconnects. Labeling a post must not depend on the
poster keeping their browser open, so jobs are started as independent asyncio
tasks instead, with a strong reference held here until they finish — a task
nobody holds can be garbage-collected mid-flight.

Every failure is logged with the job name; none of them can crash the app
(CLAUDE.md Law 12).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_running: set[asyncio.Task] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _running.add(task)
    task.add_done_callback(_finished)
    return task


def _finished(task: asyncio.Task) -> None:
    _running.discard(task)
    if task.cancelled():
        log.warning("background_job_cancelled", extra={"job": task.get_name()})
        return
    error = task.exception()
    if error is not None:
        log.error(
            "background_job_failed",
            extra={"job": task.get_name()},
            exc_info=error,
        )


def spawn_after_commit(
    session: AsyncSession, factory: Callable[[], Coroutine[Any, Any, Any]], *, name: str
) -> None:
    """Start a job only once the request's transaction has actually committed.

    ARCHITECTURE.md §7 says labeling runs "after `POST /posts` commits". Started
    any earlier, the job opens its own session and finds nothing there. If the
    transaction rolls back instead, the job never starts at all, which is the
    behaviour a failed write should have.
    """
    loop = asyncio.get_running_loop()
    started = False

    @event.listens_for(session.sync_session, "after_commit")
    def _on_commit(_sync_session) -> None:  # pragma: no branch - one call
        nonlocal started
        if started:
            return
        started = True
        loop.call_soon(lambda: spawn(factory(), name=name))


def running() -> int:
    return len(_running)


async def drain(timeout: float = 30.0) -> None:
    """Wait for in-flight jobs at shutdown, so nothing is lost silently."""
    if not _running:
        return
    log.info("waiting_for_background_jobs", extra={"count": len(_running)})
    await asyncio.wait(set(_running), timeout=timeout)
