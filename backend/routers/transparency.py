"""The public transparency pages: settings, the AI action log, the admin log.

CLAUDE.md §2 — every threshold, rule and setting that shapes a democratic
outcome is a public value, and every AI action is disclosed and logged. None of
these endpoints needs a login.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import SessionDep
from backend.routers.common import CursorParam, DEFAULT_LIMIT, LimitParam
from backend.services import admin_log
from backend.services import ai_log
from backend.services import rules
from backend.services import settings as settings_service

router = APIRouter(tags=["transparency"])


class SettingOut(BaseModel):
    key: str
    value: object | None
    raw_value: str | None
    meaning: str
    defined_in: str
    effective_from: datetime | None
    changed_by_user_id: int | None
    reason: str | None
    set_by: str


class SettingsOut(BaseModel):
    explanation: str
    rules_version: str
    settings: list[SettingOut]


@router.get("/settings", response_model=SettingsOut)
async def public_settings(session: SessionDep) -> SettingsOut:
    return SettingsOut(
        explanation=(
            "Every number on this page decides something about how the platform "
            "works. They are all public, they are all changeable by the "
            "community's administrators, and every change is recorded in the "
            "admin log with a reason. Nothing here is hidden in the code."
        ),
        rules_version=rules.RULES_VERSION,
        settings=[SettingOut(**row) for row in await settings_service.public_view(session)],
    )


class SettingHistoryOut(BaseModel):
    key: str
    value: str
    effective_from: datetime
    changed_by: str
    reason: str | None


@router.get("/settings/history", response_model=list[SettingHistoryOut])
async def settings_history(
    session: SessionDep, key: str | None = Query(default=None)
) -> list[SettingHistoryOut]:
    return [SettingHistoryOut(**row) for row in await settings_service.history(session, key)]


class AiActionOut(BaseModel):
    id: int
    action_type: str
    subject_type: str
    subject_id: int
    demo_build: str
    model: str
    prompt_file: str
    prompt_hash: str
    input_hash: str
    output: dict
    confidence: float | None
    human_outcome: str
    human_outcome_at: datetime | None
    created_at: datetime


class AiActionsOut(BaseModel):
    explanation: str
    items: list[AiActionOut]
    next_cursor: int | None


@router.get("/ai/actions", response_model=AiActionsOut)
async def ai_actions(
    session: SessionDep,
    subject_type: str | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    action_type: str | None = Query(default=None),
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> AiActionsOut:
    rows = await ai_log.page(
        session,
        cursor=cursor,
        limit=limit,
        subject_type=subject_type,
        subject_id=subject_id,
        action_type=action_type,
    )
    return AiActionsOut(
        explanation=(
            "Every action any AI takes on this platform is written down here "
            "before its result is shown to anyone: what it was, what it acted on, "
            "which model and which prompt file, a fingerprint of exactly what it "
            "was given, what it answered, and whether a person later confirmed or "
            "corrected it. AI never decides anything here."
        ),
        items=[
            AiActionOut(
                id=r.id,
                action_type=r.action_type,
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                demo_build=r.demo_build,
                model=r.model,
                prompt_file=r.prompt_file,
                prompt_hash=r.prompt_hash,
                input_hash=r.input_hash,
                output=r.output,
                confidence=float(r.confidence) if r.confidence is not None else None,
                human_outcome=r.human_outcome,
                human_outcome_at=r.human_outcome_at,
                created_at=r.created_at,
            )
            for r in rows
        ],
        next_cursor=rows[-1].id if len(rows) == limit else None,
    )


class AdminLogOut(BaseModel):
    explanation: str
    items: list[dict]
    next_cursor: int | None


@router.get("/admin/log", response_model=AdminLogOut)
async def admin_action_log(
    session: SessionDep, cursor: CursorParam = None, limit: LimitParam = DEFAULT_LIMIT
) -> AdminLogOut:
    page = await admin_log.public_page(session, cursor=cursor, limit=limit)
    return AdminLogOut(
        explanation=(
            "Everything an administrator does on this platform is recorded here, "
            "with what changed and why. You do not need an account to read it."
        ),
        **page,
    )
