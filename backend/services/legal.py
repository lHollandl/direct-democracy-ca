"""The legal pages, served from the current terms version (Foundation)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import NotFound
from backend.repositories import users as users_repo


async def current(session: AsyncSession) -> tuple[str, str, str]:
    terms = await users_repo.latest_terms(session)
    if terms is None:
        raise NotFound("No terms version has been published yet.", code="no_terms")
    return terms.version, terms.privacy_policy_md, terms.terms_of_service_md
