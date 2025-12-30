from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    GoogleLoginRequest,
    GoogleLoginResponse,
    GoogleTokenStatusResponse,
    GoogleUserOut,
    GoogleAccountVerifyResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/google/login", response_model=GoogleLoginResponse)
def google_login(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> GoogleLoginResponse:
    user, exp_dt, is_valid = auth_service.login_with_google(
        db,
        payload.id_token,
        access_token=payload.access_token,
        access_token_expires_in=payload.access_token_expires_in,
        refresh_token=payload.refresh_token,
        scope=payload.scope,
    )
    message = None
    if not is_valid:
        message = "Token đã hết hạn; hãy đăng nhập lại Google để lấy token mới."

    return GoogleLoginResponse(
        user=GoogleUserOut(
            id=user.id,
            public_id=str(user.public_id),
            email=user.email,
            google_sub=user.google_sub,
        ),
        token_expires_at=exp_dt,
        token_is_valid=is_valid,
        access_token_expires_at=user.google_access_token_expires_at,
        access_token_saved=bool(user.google_access_token),
        refresh_token_saved=bool(user.google_refresh_token),
        message=message,
    )


@router.get("/google/token-status", response_model=GoogleTokenStatusResponse)
def google_token_status(
    email: str,
    db: Session = Depends(get_db),
) -> GoogleTokenStatusResponse:
    exp_dt, is_valid = auth_service.token_status(db, email)
    message = None
    if not is_valid:
        message = "Token đã hết hạn; vui lòng đăng nhập lại Google để refresh."

    return GoogleTokenStatusResponse(
        token_expires_at=exp_dt,
        token_is_valid=is_valid,
        message=message,
    )


@router.get("/google/verify", response_model=GoogleAccountVerifyResponse)
def google_account_verify(email: str) -> GoogleAccountVerifyResponse:
    allowed = auth_service.is_allowed_google_account(email)
    return GoogleAccountVerifyResponse(
        allowed=allowed,
        message="OK" if allowed else "Email không được phép đăng nhập.",
    )
