"""The legal pages, served from the current terms version (Foundation)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config.settings_env import repo_root
from backend.deps import SessionDep
from backend.errors import NotFound
from backend.repositories import users as users_repo

router = APIRouter(prefix="/legal", tags=["legal"])

LEGAL_DIR = repo_root() / "legal"


class LegalOut(BaseModel):
    version: str
    is_draft: bool
    draft_warning: str
    markdown: str


DRAFT_WARNING = (
    "This is placeholder text written for a demo build. It has not been "
    "reviewed by a lawyer. It describes what the platform actually does, so "
    "that nobody is misled while the real document is written."
)


async def _current(session) -> tuple[str, str, str]:
    terms = await users_repo.latest_terms(session)
    if terms is None:
        raise NotFound("No terms version has been published yet.", code="no_terms")
    return terms.version, terms.privacy_policy_md, terms.terms_of_service_md


@router.get("/current-version", response_model=dict)
async def current_version(session: SessionDep) -> dict:
    version, _p, _t = await _current(session)
    return {"version": version}


@router.get("/privacy", response_model=LegalOut)
async def privacy(session: SessionDep) -> LegalOut:
    version, privacy_md, _t = await _current(session)
    return LegalOut(
        version=version, is_draft=True, draft_warning=DRAFT_WARNING, markdown=privacy_md
    )


@router.get("/terms", response_model=LegalOut)
async def terms(session: SessionDep) -> LegalOut:
    version, _p, terms_md = await _current(session)
    return LegalOut(
        version=version, is_draft=True, draft_warning=DRAFT_WARNING, markdown=terms_md
    )


@router.get("/cookies", response_model=LegalOut)
async def cookies(session: SessionDep) -> LegalOut:
    version, _p, _t = await _current(session)
    path = LEGAL_DIR / "cookies.md"
    if not path.exists():
        raise NotFound("The cookie notice is missing.", code="no_cookie_notice")
    return LegalOut(
        version=version,
        is_draft=True,
        draft_warning=DRAFT_WARNING,
        markdown=path.read_text(encoding="utf-8"),
    )
