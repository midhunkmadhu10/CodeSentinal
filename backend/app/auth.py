import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "codesentinal")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "codesentinal-token-123")


def verify_credentials(username: str, password: str) -> bool:
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def verify_token(authorization: str = Header(None)) -> None:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or expired token")