"""Director controls (DEMOCRACY.md §13).

Every action here writes an `admin_actions` row: who, what, subject, old and
new values, and a reason when one is given. That log is public at `/admin/log`
and needs no login to read.

Administrators are not exempt from any threshold. They cannot vote twice, edit
anyone else's content, or alter votes — and they cannot see anyone's ballot
vote, ever.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.deps import AdminUser, SessionDep
from backend.routers.common import Message
from backend.services import admin_log
from backend.services import cycles as cycles_service
from backend.services import juries as juries_service
from backend.services import posts as posts_service
from backend.services import references as references_service
from backend.services import settings as settings_service
from backend.services import solutions as solutions_service

router = APIRouter(prefix="/admin", tags=["admin"])


class SettingIn(BaseModel):
    key: str
    value: str
    reason: str = Field(min_length=3, max_length=500)


@router.post("/settings")
async def change_setting(
    body: SettingIn, admin: AdminUser, session: SessionDep
) -> dict:
    old, new = await settings_service.change(
        session, key=body.key, value=body.value, changed_by=admin.id, reason=body.reason
    )
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="change_setting",
        subject_type="setting",
        old_value={"key": body.key, "value": old},
        new_value={"key": body.key, "value": new},
        reason=body.reason,
    )
    return {
        "key": body.key,
        "old_value": old,
        "new_value": new,
        "message": (
            "Changed. The new value is on the public settings page and the change "
            "is in the public admin log."
        ),
    }


class PrepareIn(BaseModel):
    level: str
    entity_id: int


@router.post("/cycles/prepare")
async def prepare_cycle(
    body: PrepareIn, admin: AdminUser, session: SessionDep
) -> dict:
    result = await cycles_service.prepare(
        session, level=body.level, entity_id=body.entity_id, admin=admin
    )
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="prepare_ballot",
        subject_type="cycle",
        subject_id=result["cycle_id"],
        new_value={
            "community": f"{body.level}:{body.entity_id}",
            "items": len(result["items"]),
            "active_users": result["active_users_at_prepare"],
        },
    )
    return result


class RedrawIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/cycles/{cycle_id}/redraw-jury")
async def redraw_jury(
    cycle_id: int, body: RedrawIn, admin: AdminUser, session: SessionDep
) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    result = await juries_service.redraw_for_admin(session, cycle=cycle, reason=body.reason)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="redraw_jury",
        subject_type="cycle",
        subject_id=cycle.id,
        old_value={"jury_id": result["old_jury_id"]},
        new_value={"jury_id": result["jury_id"], "drawn": result["drawn"]},
        reason=body.reason,
    )
    return {"jury_id": result["jury_id"], "drawn": result["drawn"], "reason": body.reason}


@router.post("/cycles/{cycle_id}/open")
async def open_ballot(cycle_id: int, admin: AdminUser, session: SessionDep) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    result = await cycles_service.open_ballot(session, cycle=cycle, admin=admin)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="open_ballot",
        subject_type="cycle",
        subject_id=cycle.id,
        new_value={
            "items_votable": result["items_votable"],
            "items_held_back": result["items_held_back"],
            "jurors_seated": result["jurors_seated"],
        },
    )
    return result


@router.post("/cycles/{cycle_id}/close")
async def close_ballot(cycle_id: int, admin: AdminUser, session: SessionDep) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    result = await cycles_service.close_ballot(session, cycle=cycle, admin=admin)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="close_ballot",
        subject_type="cycle",
        subject_id=cycle.id,
        new_value={"results": result["results"]},
    )
    return result


@router.post("/cycles/{cycle_id}/publish")
async def publish_summary(cycle_id: int, admin: AdminUser, session: SessionDep) -> dict:
    cycle = await cycles_service.require_cycle(session, cycle_id)
    result = await cycles_service.publish(session, cycle=cycle, admin=admin)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="publish_summary",
        subject_type="cycle",
        subject_id=cycle.id,
        new_value={"summary_hash": result["summary_hash"]},
    )
    return result


@router.post("/umbrellas/{umbrella_id}/recommend-references")
async def recommend_references(
    umbrella_id: int, admin: AdminUser, session: SessionDep
) -> dict:
    umbrella = await solutions_service.require_umbrella(session, umbrella_id)
    result = await references_service.recommend(session, umbrella=umbrella)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="recommend_references",
        subject_type="umbrella",
        subject_id=umbrella.id,
        new_value={"added": len(result["added"]), "queries": result["queries"]},
    )
    return result


@router.post("/posts/{post_id}/relabel", response_model=Message)
async def relabel_post(post_id: int, admin: AdminUser, session: SessionDep) -> Message:
    post = await posts_service.require_post(session, post_id)
    await admin_log.record(
        session,
        admin_user_id=admin.id,
        action="force_relabel",
        subject_type="post",
        subject_id=post.id,
        old_value={"label_status": post.label_status},
    )
    await posts_service.request_relabel(session, post)
    return Message(message="Queued for filing again.")


@router.get("/users/{user_id}")
async def admin_user_view(user_id: int, admin: AdminUser, session: SessionDep) -> dict:
    """Verification level and jury history. **Never ballot votes** — a ballot
    vote is visible only to the voter who cast it (DEMOCRACY.md §13)."""
    return await juries_service.admin_user_view(session, user_id)
