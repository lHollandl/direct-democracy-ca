"""
Authentication endpoints — login, logout, and current-user profile.
"""

from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user
from database import get_db
from limiter import limiter
from models import City, County, User

router = APIRouter(prefix="/auth")

# Generated once at module load — used as the bcrypt target when a username
# does not exist, so the response time is identical whether the user exists or
# not. Without this, an attacker could enumerate valid usernames by measuring
# how quickly we return (no bcrypt = fast = username not found).
_TIMING_DUMMY_HASH: str = bcrypt.hashpw(b"timing_dummy", bcrypt.gensalt()).decode()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    influence_score: int
    political_party: str | None
    # Home location IDs — set during signup, used to pre-fill the post form
    county_id: int | None
    city_id: int | None
    # Human-readable names — resolved from the DB by get_me and set as transient attrs
    county_name: str | None
    city_name: str | None

    model_config = {"from_attributes": True}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request, credentials: LoginRequest, db: Session = Depends(get_db)
):
    """
    Exchange username + password for a Bearer token.
    Returns 401 for any failure — deliberately vague so attackers cannot
    determine whether the username or the password was wrong.
    """
    user = db.query(User).filter(User.username == credentials.username).first()

    # Always run bcrypt — even when the user doesn't exist — so response time
    # is constant regardless of whether the username is valid.
    hash_to_check = user.hashed_password if user else _TIMING_DUMMY_HASH
    password_valid = bcrypt.checkpw(credentials.password.encode(), hash_to_check.encode())

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": create_access_token(user.id, user.username), "token_type": "bearer"}


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Acknowledges the logout request. JWTs are stateless — the server cannot
    invalidate a token; the client must discard it.
    Phase 3 will add a Redis token blacklist for true server-side invalidation.
    """
    return {"message": "Logged out"}


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the profile of the currently authenticated user.
    The frontend calls this on page load to confirm the stored token is still valid.
    Includes county_name and city_name so the post form can display the user's
    home location without an extra round-trip.
    Never returns hashed_password or any internal security fields.
    """
    county_name = None
    city_name = None

    if current_user.county_id:
        county = db.query(County).filter(County.id == current_user.county_id).first()
        county_name = county.name if county else None

    if current_user.city_id:
        city = db.query(City).filter(City.id == current_user.city_id).first()
        city_name = city.name if city else None

    # Set as transient attributes — Pydantic reads these via from_attributes
    current_user.county_name = county_name
    current_user.city_name = city_name

    return current_user
