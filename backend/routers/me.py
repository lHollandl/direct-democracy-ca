"""The signed-in person's own account: display settings, export, deletion."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.deps import CurrentUser, SessionDep
from backend.errors import NotFound
from backend.routers.common import Message
from backend.services import account as account_service
from backend.services import export as export_service

router = APIRouter(prefix="/me", tags=["me"])


class DisplayIn(BaseModel):
    public_name_mode: str = Field(pattern="^(real_name|display_name|anonymous)$")


class DisplayOut(BaseModel):
    public_name_mode: str
    shown_as: str


@router.patch("/display", response_model=DisplayOut)
async def set_display(body: DisplayIn, user: CurrentUser, session: SessionDep) -> DisplayOut:
    result = await account_service.set_display(session, user, body.public_name_mode)
    return DisplayOut(**result)


class ProfileIn(BaseModel):
    real_name: str | None = Field(default=None, min_length=2, max_length=120)
    display_name: str | None = Field(default=None, min_length=2, max_length=40)
    gender: str | None = None
    political_party: str | None = None


class ProfileOut(BaseModel):
    real_name: str
    display_name: str
    gender: str
    political_party: str


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(body: ProfileIn, user: CurrentUser, session: SessionDep) -> ProfileOut:
    updated = await account_service.update_profile(
        session,
        user,
        real_name=body.real_name,
        display_name=body.display_name,
        gender=body.gender,
        political_party=body.political_party,
    )
    return ProfileOut(
        real_name=updated.real_name,
        display_name=updated.display_name,
        gender=updated.gender,
        political_party=updated.political_party,
    )


class EmailChangeIn(BaseModel):
    new_email: str
    password: str


@router.post("/email", response_model=Message)
async def request_email_change(
    body: EmailChangeIn, user: CurrentUser, session: SessionDep
) -> Message:
    await account_service.request_email_change(
        session, user, new_email=body.new_email, password=body.password
    )
    return Message(
        message=(
            "Check the new address for a confirmation link. We also sent a "
            "notice to your current address."
        )
    )


class ExportOut(BaseModel):
    id: int
    status: str
    message: str


@router.post("/export", status_code=status.HTTP_202_ACCEPTED, response_model=ExportOut)
async def request_export(user: CurrentUser, session: SessionDep) -> ExportOut:
    row = await export_service.request_export(session, user)
    return ExportOut(
        id=row.id,
        status="requested",
        message=(
            "We are putting your data together. Come back to this link in a "
            "moment to download it."
        ),
    )


@router.get("/export/{export_id}")
async def download_export(export_id: int, user: CurrentUser, session: SessionDep):
    row = await export_service.get_export(session, user, export_id)
    if row.file_path is None:
        raise NotFound(
            "Your export is not ready yet, or it has expired. Ask for a new one.",
            code="export_not_ready",
        )
    return FileResponse(
        row.file_path,
        media_type="application/json",
        filename=f"direct-democracy-ca-export-{user.id}.json",
    )


class DeleteIn(BaseModel):
    password: str
    understand_this_cannot_be_undone: bool


@router.delete("", response_model=Message)
async def delete_me(body: DeleteIn, user: CurrentUser, session: SessionDep) -> Message:
    if not body.understand_this_cannot_be_undone:
        return Message(
            message=(
                "Nothing was deleted. Tick the box to confirm you understand this "
                "cannot be undone."
            )
        )
    await account_service.delete_account(session, user, body.password)
    return Message(
        message=(
            "Your account is deleted. Your name, email, password, date of birth, "
            "gender and political party are erased. What you wrote stays in the "
            "civic record as Former Community Member."
        )
    )
