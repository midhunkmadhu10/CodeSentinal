"""Authentication: environment-configured credentials and bearer token.

Fails closed — there are no default credentials. When AUTH_USERNAME,
AUTH_PASSWORD, or AUTH_TOKEN are missing or empty, login returns 503 and
protected routes reject every request until the operator configures them.
"""

import os
import secrets

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

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


def verify_token(authorization: str = Header(None)) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    expected = get_auth_token()
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
