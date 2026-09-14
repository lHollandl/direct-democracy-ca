"""Startup sync of `main_categories` with backend/config/categories.py.

DATABASE.md §4.1: insert missing, never delete, mark inactive if removed from
config. AI must choose from this list and cannot invent one (DEMOCRACY.md §3.1).
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select

from backend.config.categories import MAIN_CATEGORIES
from backend.db import session_scope
from backend.models import MainCategory

log = logging.getLogger(__name__)


def slug_for(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


async def sync_main_categories() -> dict[str, int]:
    counts = {"inserted": 0, "reactivated": 0, "deactivated": 0}
    async with session_scope() as session:
        existing = {
            row.slug: row
            for row in (await session.execute(select(MainCategory))).scalars().all()
        }
        config_slugs = set()
        for name in MAIN_CATEGORIES:
            slug = slug_for(name)
            config_slugs.add(slug)
            row = existing.get(slug)
            if row is None:
                session.add(MainCategory(slug=slug, name=name, active=True))
                counts["inserted"] += 1
            elif not row.active:
                row.active = True
                counts["reactivated"] += 1
        for slug, row in existing.items():
            if slug not in config_slugs and row.active:
                row.active = False
                counts["deactivated"] += 1
    log.info("main_categories_synced", extra=counts)
    return counts
