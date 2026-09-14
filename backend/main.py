"""Application initialization and route registration. Nothing else lives here.

ARCHITECTURE.md §2: `main.py` registers routers and lifespan hooks.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.clients import redis as redis_client
from backend.config.settings_env import get_env_settings
from backend.db import dispose_engine
from backend.errors import install_error_handlers
from backend.jobs import scheduler
from backend.logging_config import configure_logging
from backend.middleware import install_middleware
from backend.routers import (
    admin,
    amendments,
    auth,
    ballots,
    comments,
    feed,
    geo,
    juries,
    legal,
    me,
    posts,
    references,
    solutions,
    summaries,
    transparency,
    umbrellas,
    votes,
)
from backend.services import export as export_service
from backend.services import export_iteration
from backend.services import startup_sync

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = get_env_settings()
    configure_logging(env.LOG_LEVEL)
    log.info("starting", extra={"build_label": env.BUILD_LABEL})

    # Iteration registers its export contributor with Foundation's registry, so
    # Foundation never names an Iteration table (ARCHITECTURE.md §2).
    export_service.register_contributor("iteration", export_iteration.contribute)

    await startup_sync.sync_main_categories()
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await redis_client.close_redis()
        await dispose_engine()
        log.info("stopped")


def create_app() -> FastAPI:
    env = get_env_settings()
    app = FastAPI(
        title="Direct Democracy Cali",
        version=env.BUILD_LABEL,
        description=(
            "The people's tool. Every rule this API applies is published at "
            "/settings; every AI action it takes is published at /ai/actions; "
            "every administrator action is published at /admin/log."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=env.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    install_middleware(app)
    install_error_handlers(app)

    # Foundation
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(geo.router)
    app.include_router(legal.router)
    app.include_router(transparency.router)
    # Iteration
    app.include_router(posts.router)
    app.include_router(feed.router)
    app.include_router(umbrellas.router)
    app.include_router(solutions.router)
    app.include_router(amendments.router)
    app.include_router(comments.router)
    app.include_router(votes.router)
    app.include_router(references.router)
    app.include_router(ballots.router)
    app.include_router(juries.router)
    app.include_router(summaries.router)
    # Admin: settings are Foundation, cycle controls are Iteration; one router.
    app.include_router(admin.router)

    @app.get("/health", tags=["platform"])
    async def health() -> dict:
        return {"status": "ok", "build": env.BUILD_LABEL}

    return app


app = create_app()
