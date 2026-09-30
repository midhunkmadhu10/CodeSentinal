"""Auth endpoints: register, JWT token issuance, current user.

The legacy `/api/auth/login` (static demo token) stays in main.py so its
frozen request/response shape and fail-closed behavior are preserved.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import authenticate, create_access_token, get_current_user, register_user
from ..database import get_db
from ..db_models import User
from ..schemas import LoginAPIRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, req.email, req.password, req.name)
    return TokenResponse(
        access_token=create_access_token(user),
        user=UserOut(id=user.id, email=user.email, name=user.name, role=user.role),
    )


@router.post("/token", response_model=TokenResponse)
def token(req: LoginAPIRequest, db: Session = Depends(get_db)):
    user = authenticate(db, req.email, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user),
        user=UserOut(id=user.id, email=user.email, name=user.name, role=user.role),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)
