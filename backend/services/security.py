"""Passwords, tokens and hashing of secrets. CLAUDE.md §7 and Law 13.

Raw passwords are never stored. Raw refresh, verification and reset tokens are
never stored either — only their SHA-256, so a database copy cannot be replayed
against the platform.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from backend.config.settings_env import get_env_settings
from backend.errors import Unauthorized, ValidationFailed

BCRYPT_COST = 12
#: bcrypt hashes at most 72 bytes; a longer password would be silently
#: truncated, which is worse than telling the person.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_CHARS = 8


def validate_password(password: str) -> None:
    """Law 13: minimum 8 characters with an uppercase letter and a number."""
    problems = []
    if len(password) < MIN_PASSWORD_CHARS:
        problems.append("be at least 8 characters long")
    if not any(c.isupper() for c in password):
        problems.append("contain a capital letter")
    if not any(c.isdigit() for c in password):
        problems.append("contain a number")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        problems.append("be no longer than 72 bytes")
    if problems:
        raise ValidationFailed(
            "Your password needs to " + ", and ".join(problems) + ".",
            code="weak_password",
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_COST)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        # An anonymized account's hash is '!', which is not a bcrypt hash.
        return False


def new_opaque_token() -> str:
    """A refresh, verification or reset token: 32 random bytes, base64url."""
    return secrets.token_urlsafe(32)


def token_fingerprint(token: str) -> str:
    """What goes in the database in place of the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str) -> str:
    """Terms acceptances record a hashed IP, not an IP (DATABASE.md §3.5)."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def create_access_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expiry). 30 minutes by default (ARCHITECTURE.md §4)."""
    env = get_env_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=env.ACCESS_TOKEN_MINUTES)
    jti = uuid.uuid4().hex
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(expires.timestamp()), "jti": jti}
    return jwt.encode(payload, env.JWT_SECRET, algorithm="HS256"), jti, expires


def decode_access_token(token: str) -> dict[str, Any]:
    env = get_env_settings()
    try:
        return jwt.decode(token, env.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Your session has expired. Please sign in again.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("This sign-in could not be verified.", code="token_invalid") from exc
