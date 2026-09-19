"""Auth and account endpoints (ARCHITECTURE.md §6, Foundation)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from backend.config.settings_env import get_env_settings
from backend.deps import CurrentUser, SessionDep
from backend.errors import Unauthorized
from backend.routers.common import Message
from backend.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """The refresh token travels only in an httpOnly, SameSite=Strict cookie
    (ARCHITECTURE.md §4). It is never in a response body."""
    env = get_env_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=env.REFRESH_TOKEN_DAYS * 24 * 3600,
        httponly=True,
        samesite="strict",
        secure=False,  # Demo 1 runs on http://localhost; HTTPS is a parked task.
        path="/",
    )


class SignupIn(BaseModel):
    email: EmailStr
    #: The length and content rules live in services/security.py so the
    #: person is told in plain words what is wrong (CLAUDE.md §8); only
    #: bcrypt's hard 72-byte limit is enforced here.
    password: str = Field(max_length=72)
    real_name: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=2, max_length=40)
    date_of_birth: date
    gender: str
    political_party: str
    county_id: int
    city_id: int
    terms_version: str
    agreed_to_terms: bool


class SignupOut(BaseModel):
    id: int
    message: str


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SignupOut)
async def signup(body: SignupIn, request: Request, session: SessionDep) -> SignupOut:
    if not body.agreed_to_terms:
        raise Unauthorized(
            "You have to agree to the terms and the privacy policy to join.",
            code="terms_not_accepted",
        )
    user, _token = await auth_service.signup(
        session,
        email=str(body.email),
        password=body.password,
        real_name=body.real_name,
        display_name=body.display_name,
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        political_party=body.political_party,
        county_id=body.county_id,
        city_id=body.city_id,
        terms_version=body.terms_version,
        ip_address=request.client.host if request.client else "unknown",
    )
    return SignupOut(
        id=user.id,
        message=(
            "Account created. Check your email and use the confirmation link "
            "before posting, voting or commenting."
        ),
    )


class TokenIn(BaseModel):
    token: str


@router.post("/verify-email", response_model=Message)
async def verify_email(body: TokenIn, session: SessionDep) -> Message:
    await auth_service.verify_email(session, body.token)
    return Message(message="Email confirmed. You can now post, vote and comment.")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email_verified: bool


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, response: Response, session: SessionDep) -> TokenOut:
    user, access, refresh_token, _expiry = await auth_service.login(
        session, email=str(body.email), password=body.password
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenOut(
        access_token=access,
        user_id=user.id,
        email_verified=user.email_verified_at is not None,
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, session: SessionDep) -> TokenOut:
    cookie = request.cookies.get(REFRESH_COOKIE)
    if not cookie:
        raise Unauthorized("Please sign in again.", code="no_refresh_cookie")
    user, access, new_refresh, _expiry = await auth_service.refresh(session, cookie)
    _set_refresh_cookie(response, new_refresh)
    return TokenOut(
        access_token=access,
        user_id=user.id,
        email_verified=user.email_verified_at is not None,
    )


@router.post("/logout", response_model=Message)
async def logout(request: Request, response: Response, session: SessionDep) -> Message:
    await auth_service.logout(
        session,
        raw_refresh_token=request.cookies.get(REFRESH_COOKIE),
        authorization_header=request.headers.get("Authorization", ""),
    )
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return Message(message="Signed out.")


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password", response_model=Message)
async def forgot_password(body: ForgotIn, session: SessionDep) -> Message:
    await auth_service.forgot_password(session, str(body.email))
    # The same answer whether or not the address has an account, so this
    # endpoint cannot be used to find out who is a member.
    return Message(
        message="If that address has an account, a reset link is on its way."
    )


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(max_length=72)


@router.post("/reset-password", response_model=Message)
async def reset_password(body: ResetIn, session: SessionDep) -> Message:
    await auth_service.reset_password(
        session, token=body.token, new_password=body.new_password
    )
    return Message(message="Password changed. You have been signed out everywhere.")


class MeOut(BaseModel):
    id: int
    email: EmailStr
    real_name: str
    display_name: str
    public_name_mode: str
    verification_level: str
    verification_explanation: str
    email_verified: bool
    is_admin: bool
    home_communities: list[dict]


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: SessionDep) -> MeOut:
    return MeOut(**await auth_service.me_view(session, user))
