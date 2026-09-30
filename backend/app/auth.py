"""Authentication: JWT-based multi-user auth with password hashing.

Passwords use PBKDF2-HMAC-SHA256 (stdlib; no native deps). Access tokens are
HS256 JWTs signed with JWT_SECRET. Legacy deployments that only set
AUTH_USERNAME/AUTH_PASSWORD/AUTH_TOKEN keep working: a demo user is seeded
from those variables at startup and the legacy static bearer token remains
accepted so existing clients do not break during migration.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import JWT_EXPIRES_HOURS
from .database import get_db
from .db_models import User

load_dotenv()

logger = logging.getLogger("codesentinal.auth")

_PBKDF2_ITERATIONS = 390_000
_MIN_PASSWORD_LEN = 8

_AUTH_NOT_CONFIGURED = (
    "Authentication is not configured. Set AUTH_USERNAME, AUTH_PASSWORD, and "
    "AUTH_TOKEN in the backend environment and restart."
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=_AUTH_NOT_CONFIGURED)
    return value


def verify_credentials(username: str, password: str) -> bool:
    """Constant-time comparison of the supplied credentials against the env."""
    expected_username = _required_env("AUTH_USERNAME")
    expected_password = _required_env("AUTH_PASSWORD")
    return secrets.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8")
    ) and secrets.compare_digest(
        password.encode("utf-8"), expected_password.encode("utf-8")
    )


def get_auth_token() -> str:
    return _required_env("AUTH_TOKEN")


def verify_token(authorization: str = Header(default="")) -> None:
    """Legacy bearer-token dependency (static env token), fails closed."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    expected = get_auth_token()  # 503 when AUTH_TOKEN is not configured
    if not secrets.compare_digest(token.strip().encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    # Per-process fallback: valid until restart. Warn once.
    if not getattr(_jwt_secret, "_warned", False):
        logger.warning("JWT_SECRET is not set; using an ephemeral per-process secret")
        _jwt_secret._warned = True  # type: ignore[attr-defined]
    return secrets.token_hex(32)


# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ── Users ────────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def register_user(db: Session, email: str, password: str, name: str = "") -> User:
    email = email.strip().lower()
    if get_user_by_email(db, email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    if len(password) < _MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {_MIN_PASSWORD_LEN} characters long.",
        )
    user = User(email=email, name=name.strip(), password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered (email=%s, id=%s)", email, user.id)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def seed_demo_user(db: Session) -> None:
    """Create the legacy single-user account from AUTH_USERNAME/AUTH_PASSWORD."""
    username = os.getenv("AUTH_USERNAME", "").strip()
    password = os.getenv("AUTH_PASSWORD", "").strip()
    if not username or not password:
        return
    if get_user_by_email(db, username) is None:
        db.add(
            User(
                email=username.lower(),
                name="Demo User",
                password_hash=hash_password(password),
                role="admin",
            )
        )
        db.commit()
        logger.info("Seeded demo user from AUTH_USERNAME (email=%s)", username.lower())


# ── Tokens ───────────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return pyjwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _decode_access_token(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except pyjwt.PyJWTError:
        return None


def _legacy_token_valid(token: str) -> bool:
    expected = os.getenv("AUTH_TOKEN", "").strip()
    return bool(expected) and secrets.compare_digest(
        token.encode("utf-8"), expected.encode("utf-8")
    )


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    token = token.strip()
    user: User | None = None

    payload = _decode_access_token(token)
    if payload and payload.get("sub"):
        try:
            user = db.get(User, int(payload["sub"]))
        except (TypeError, ValueError):
            user = None

    if user is None:
        # Legacy static-token path (also covers JWT_SECRET rotation).
        if not os.getenv("AUTH_TOKEN", "").strip():
            raise HTTPException(status_code=503, detail=_AUTH_NOT_CONFIGURED)
        if _legacy_token_valid(token):
            username = os.getenv("AUTH_USERNAME", "").strip().lower()
            user = get_user_by_email(db, username) if username else None
            if user is None:
                user = db.query(User).order_by(User.id).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
