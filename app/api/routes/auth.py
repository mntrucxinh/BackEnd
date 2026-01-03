from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    GoogleLoginRequest,
    GoogleLoginResponse,
    GoogleRefreshResponse,
    GoogleTokenStatusResponse,
    GoogleUserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/google/login", response_model=GoogleLoginResponse)
def google_login(
    payload: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> GoogleLoginResponse:
    user, exp_dt, is_valid = auth_service.login_with_google(
        db,
        id_token=payload.id_token,
        access_token=payload.access_token,
        access_token_expires_in=payload.access_token_expires_in,
        refresh_token=payload.refresh_token,
        scope=payload.scope,
    )
    message = None
    if not is_valid:
        message = "Token đã hết hạn; hãy đăng nhập lại Google để lấy token mới."

    tokens = auth_service.issue_app_tokens(user)
    auth_service.set_refresh_cookie(
        response, tokens["refresh_token"], tokens["refresh_expires_at"]
    )

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
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        access_token_expires_at_app=tokens["access_expires_at"],
        refresh_token_expires_at_app=tokens["refresh_expires_at"],
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


@router.post("/refresh", response_model=GoogleRefreshResponse)
def refresh_tokens(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None, alias=auth_service.REFRESH_COOKIE_NAME
    ),
) -> GoogleRefreshResponse:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_refresh_token", "message": "Không tìm thấy refresh token."},
        )

    user, tokens = auth_service.refresh_app_tokens(db, refresh_token)
    auth_service.set_refresh_cookie(
        response, tokens["refresh_token"], tokens["refresh_expires_at"]
    )

    return GoogleRefreshResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        access_token_expires_at=tokens["access_expires_at"],
        refresh_token_expires_at=tokens["refresh_expires_at"],
        user=GoogleUserOut(
            id=user.id,
            public_id=str(user.public_id),
            email=user.email,
            google_sub=user.google_sub,
        ),
    )


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None, alias=auth_service.REFRESH_COOKIE_NAME
    ),
) -> dict:
    user_email = None
    if refresh_token:
        try:
            user = auth_service.get_user_from_refresh(db, refresh_token)
            user_email = user.email
        except HTTPException:
            # Ignore invalid token on logout
            pass

    response.delete_cookie(auth_service.REFRESH_COOKIE_NAME, path="/")
    return {"message": "Logged out", "email": user_email}
