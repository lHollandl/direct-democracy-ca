"""Data export (CLAUDE.md §6: users can export all their personal data).

Foundation gathers the Foundation data and then calls every registered
**export contributor**. Iteration registers one at startup, so Foundation code
never names an Iteration table (ARCHITECTURE.md §2, DATABASE.md §3.11). When no
contributor is registered, the export says so rather than pretending to be
complete.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings_env import repo_root
from backend.errors import Forbidden, NotFound
from backend.models import City, County, DataExport, State, User, UserDisplaySettings
from backend.repositories import users as users_repo

log = logging.getLogger(__name__)

Contributor = Callable[[AsyncSession, int], Awaitable[dict]]

_contributors: dict[str, Contributor] = {}

EXPORT_DIR = repo_root() / "var" / "exports"
EXPORT_LIFETIME_HOURS = 48


def register_contributor(name: str, contribute: Contributor) -> None:
    """Iteration calls this at startup with `export_iteration.py::contribute`."""
    _contributors[name] = contribute
    log.info("export_contributor_registered", extra={"contributor": name})


def registered_contributors() -> list[str]:
    return sorted(_contributors)


def clear_contributors() -> None:
    """Used by the test suite between cases."""
    _contributors.clear()


async def request_export(session: AsyncSession, user: User) -> DataExport:
    row = DataExport(
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=EXPORT_LIFETIME_HOURS),
    )
    session.add(row)
    await session.flush()
    return row


async def build_export(session: AsyncSession, export_id: int) -> Path:
    """Assemble the file. Runs in a background job so a large export does not
    hold a request open."""
    row = await session.get(DataExport, export_id)
    if row is None:
        raise NotFound("That export request no longer exists.", code="export_not_found")
    payload = await gather(session, row.user_id)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"export-{row.user_id}-{row.id}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    row.file_path = str(path)
    row.completed_at = datetime.now(timezone.utc)
    await session.flush()
    log.info("export_built", extra={"export_id": row.id, "user_id": row.user_id})
    return path


async def gather(session: AsyncSession, user_id: int) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("That account no longer exists.", code="user_not_found")
    display = await session.get(UserDisplaySettings, user_id)
    city = await session.get(City, user.city_id)
    county = await session.get(County, user.county_id)
    state = await session.get(State, county.state_id) if county else None

    payload: dict = {
        "export_generated_at": datetime.now(timezone.utc),
        "what_this_is": (
            "Everything this platform holds that is about you. Your ballot votes "
            "are included here and are shown to nobody else, not even an "
            "administrator."
        ),
        "account": {
            "id": user.id,
            "email": user.email,
            "real_name": user.real_name,
            "display_name": user.display_name,
            "date_of_birth": user.date_of_birth,
            "gender": user.gender,
            "political_party": user.political_party,
            "home_city": city.name if city else None,
            "home_county": county.name if county else None,
            "home_state": state.name if state else None,
            "verification_level": user.verification_level,
            "email_verified_at": user.email_verified_at,
            "is_admin": user.is_admin,
            "created_at": user.created_at,
            "deleted_at": user.deleted_at,
        },
        "display_settings": {
            "public_name_mode": display.public_name_mode if display else None
        },
        "terms_acceptances": [
            {
                "terms_version_id": a.terms_version_id,
                "accepted_at": a.accepted_at,
            }
            for a in await users_repo.terms_acceptances(session, user_id)
        ],
        "note_on_hashes": (
            "Content fingerprints (hashes) are public cryptographic proofs, not "
            "personal data. They are never deleted, including when you delete "
            "your account."
        ),
    }

    if not _contributors:
        payload["civic_record"] = {
            "note": (
                "No civic-data contributor is registered in this build, so this "
                "export contains your account data only."
            )
        }
    else:
        civic: dict = {}
        for name, contribute in sorted(_contributors.items()):
            civic[name] = await contribute(session, user_id)
        payload["civic_record"] = civic
    return payload


async def get_export(session: AsyncSession, user: User, export_id: int) -> DataExport:
    row = await session.get(DataExport, export_id)
    if row is None:
        raise NotFound("That export does not exist.", code="export_not_found")
    if row.user_id != user.id:
        raise Forbidden("That export belongs to someone else.", code="export_not_yours")
    return row


async def expire_exports(session: AsyncSession) -> int:
    """Delete export files past `expires_at`. Files only; rows stay
    (ARCHITECTURE.md §7)."""
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(DataExport).where(
                DataExport.expires_at < now, DataExport.file_path.is_not(None)
            )
        )
    ).scalars().all()
    removed = 0
    for row in rows:
        path = Path(row.file_path)
        if path.exists():
            path.unlink()
            removed += 1
        row.file_path = None
    await session.flush()
    return removed
