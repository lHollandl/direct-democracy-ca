"""Data export (CLAUDE.md §6: users can export all their personal data).

Foundation gathers the Foundation data and then calls every registered
**export contributor**. Iteration registers one at startup, so Foundation code
never names an Iteration table (ARCHITECTURE.md §2, DATABASE.md §3.11). When no
contributor is registered, the export says so rather than pretending to be
complete.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings_env import get_env_settings, repo_root
from backend.errors import Forbidden, Gone, NotFound
from backend.models import DataExport, User
from backend.repositories import data_exports as data_exports_repo
from backend.repositories import email_changes as email_changes_repo
from backend.repositories import geography as geo_repo
from backend.repositories import home_changes as home_changes_repo
from backend.repositories import users as users_repo

log = logging.getLogger(__name__)

Contributor = Callable[[AsyncSession, int], Awaitable[dict]]

_contributors: dict[str, Contributor] = {}

EXPORT_DIR = repo_root() / "var" / "exports"


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
    row = await data_exports_repo.add(
        session,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=get_env_settings().EXPORT_FILE_HOURS),
    )
    export_id = row.id
    _schedule_build(session, export_id)
    return row


def _schedule_build(session: AsyncSession, export_id: int) -> None:
    """The service that owns the transaction schedules the job (ARCHITECTURE.md
    §7)."""
    from backend.jobs import exports as export_job
    from backend.jobs import runner

    runner.spawn_after_commit(
        session, lambda: export_job.build_export_task(export_id), name=f"export:{export_id}"
    )


async def build_export(session: AsyncSession, export_id: int) -> Path:
    """Assemble the file. Runs in a background job so a large export does not
    hold a request open."""
    row = await data_exports_repo.get(session, export_id)
    if row is None:
        raise NotFound("That export request no longer exists.", code="export_not_found")
    payload = await gather(session, row.user_id)
    path = EXPORT_DIR / f"export-{row.user_id}-{row.id}.json"
    # No blocking calls inside async def (Law 11; audit demo-01 run 4, MEDIUM
    # — the same class of finding fix run 2 fixed in seed.py only).
    await asyncio.to_thread(_write_export_file, path, payload)
    row.file_path = str(path)
    row.completed_at = datetime.now(timezone.utc)
    await session.flush()
    log.info("export_built", extra={"export_id": row.id, "user_id": row.user_id})
    return path


def _write_export_file(path: Path, payload: dict) -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def gather(session: AsyncSession, user_id: int) -> dict:
    user = await users_repo.get(session, user_id)
    if user is None:
        raise NotFound("That account no longer exists.", code="user_not_found")
    display = await users_repo.display_settings(session, user_id)
    city = await geo_repo.get_city(session, user.city_id) if user.city_id is not None else None
    county = await geo_repo.get_county(session, user.county_id)
    state = await geo_repo.get_state(session, county.state_id) if county else None

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
        "home_changes": [
            {
                "from_county_id": c.from_county_id,
                "from_city_id": c.from_city_id,
                "to_county_id": c.to_county_id,
                "to_city_id": c.to_city_id,
                "changed_at": c.changed_at,
            }
            for c in await home_changes_repo.for_user(session, user_id)
        ],
        "pending_email_changes": [
            {"new_email": c.new_email, "expires_at": c.expires_at}
            for c in await email_changes_repo.pending_for_user(session, user_id)
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
    row = await data_exports_repo.get(session, export_id)
    if row is None:
        raise NotFound("That export does not exist.", code="export_not_found")
    if row.user_id != user.id:
        raise Forbidden("That export belongs to someone else.", code="export_not_yours")
    # Refused the moment expires_at has passed, independently of whether the
    # hourly sweep (expire_exports) has run yet — the window a person has to
    # collect their own export is EXPORT_FILE_HOURS, not that plus up to an
    # hour (audit demo-01 run 5, LOW).
    if row.expires_at < datetime.now(timezone.utc):
        raise Gone(
            "That export's window to download it has closed. Ask for a new one.",
            code="export_expired",
        )
    return row


def _remove_if_exists(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


async def expire_exports(session: AsyncSession) -> int:
    """Delete export files past `expires_at`. Files only; rows stay
    (ARCHITECTURE.md §7)."""
    now = datetime.now(timezone.utc)
    rows = await data_exports_repo.expired_with_file(session, now)
    removed = 0
    for row in rows:
        path = Path(row.file_path)
        # No blocking calls inside async def (Law 11).
        if await asyncio.to_thread(_remove_if_exists, path):
            removed += 1
        row.file_path = None
    await session.flush()
    return removed
