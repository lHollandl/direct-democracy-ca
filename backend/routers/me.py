"""The signed-in person's own account: display settings, export, deletion."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.deps import CurrentUser, SessionDep
from backend.errors import NotFound
from backend.routers.common import Message
from backend.services import account as account_service
from backend.services import auth as auth_service
from backend.services import export as export_service

router = APIRouter(prefix="/me", tags=["me"])


class ResendVerificationOut(BaseModel):
    message: str
    #: ARCHITECTURE.md §4 "Demo mail" — present only when `EMAIL_BACKEND=console`
    #: and `ALLOW_TEST_DATA=true`.
    demo_link: str | None = None


@router.post("/resend-verification", response_model=ResendVerificationOut)
async def resend_verification(user: CurrentUser, session: SessionDep) -> ResendVerificationOut:
    demo_link = await auth_service.resend_verification(session, user)
    return ResendVerificationOut(
        message="A new confirmation link is on its way to your email address.",
        demo_link=demo_link,
    )


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


class PlaceOut(BaseModel):
    id: int
    name: str


class HomeStatusOut(BaseModel):
    county: PlaceOut | None
    city: PlaceOut | None
    next_change_allowed_at: datetime | None = None
    refused_now_reason: str | None = None


@router.get("/home", response_model=HomeStatusOut)
async def home_status(user: CurrentUser, session: SessionDep) -> HomeStatusOut:
    return HomeStatusOut(**await account_service.home_status(session, user))


class HomeChangeIn(BaseModel):
    county_id: int
    #: NULL = "Unincorporated — no city" (DEMOCRACY.md §2.3).
    city_id: int | None = None


class HomeChangeOut(BaseModel):
    county_id: int
    city_id: int | None
    message: str


@router.post("/home", response_model=HomeChangeOut)
async def change_home(body: HomeChangeIn, user: CurrentUser, session: SessionDep) -> HomeChangeOut:
    result = await account_service.change_home(
        session, user, county_id=body.county_id, city_id=body.city_id
    )
    return HomeChangeOut(**result)


class EmailChangeIn(BaseModel):
    new_email: str
    password: str


class EmailChangeOut(BaseModel):
    message: str
    #: ARCHITECTURE.md §4 "Demo mail" — present only when `EMAIL_BACKEND=console`
    #: and `ALLOW_TEST_DATA=true`.
    demo_link: str | None = None


@router.post("/email", response_model=EmailChangeOut)
async def request_email_change(
    body: EmailChangeIn, user: CurrentUser, session: SessionDep
) -> EmailChangeOut:
    demo_link = await account_service.request_email_change(
        session, user, new_email=body.new_email, password=body.password
    )
    return EmailChangeOut(
        message=(
            "Check the new address for a confirmation link. We also sent a "
            "notice to your current address."
        ),
        demo_link=demo_link,
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
