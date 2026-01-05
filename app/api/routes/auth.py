from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.tables import User
from app.schemas.auth import (
    FacebookLinkRequest,
    FacebookLinkResponse,
    FacebookStatusResponse,
    GoogleLoginRequest,
    GoogleLoginResponse,
    GoogleRefreshResponse,
    GoogleTokenStatusResponse,
    GoogleUserOut,
)
from app.services import auth_service, facebook_service

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
    user = auth_service.store_app_tokens(db, user, tokens)
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
        access_token_saved=bool(user.access_token),
        refresh_token_saved=bool(user.refresh_token),
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


@router.post("/facebook/link", response_model=FacebookLinkResponse)
def link_facebook_page(
    payload: FacebookLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FacebookLinkResponse:
    """
    Liên kết Facebook Page với User account (chỉ cần làm 1 lần).
    
    Flow:
    1. Exchange Short-lived → Long-lived User Token (60 ngày)
    2. Lấy Page Token từ Long-lived User Token
    3. Lưu cả 2 vào DB
    
    Sau đó hệ thống tự động refresh Page Token khi cần.
    """
    try:
        # 1. Exchange thành Long-lived User Token
        long_lived = facebook_service.exchange_long_lived_token(payload.user_access_token)
        
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=long_lived["expires_in"]
        )
        
        # 2. Lấy Page Token
        page_info = facebook_service.get_page_token_from_user_token(
            long_lived["access_token"]
        )
        
        # 3. Lưu vào DB
        now = datetime.now(timezone.utc)
        current_user.facebook_user_access_token = long_lived["access_token"]
        current_user.facebook_user_token_expires_at = expires_at
        current_user.facebook_page_id = page_info["page_id"]
        current_user.facebook_access_token = page_info["access_token"]
        current_user.facebook_token_expires_at = page_info.get("expires_at")
        current_user.facebook_page_name = page_info.get("name")
        current_user.updated_at = now
        
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        
        return FacebookLinkResponse(
            linked=True,
            page_id=page_info["page_id"],
            page_name=page_info.get("name"),
            user_token_expires_at=expires_at,
            message="Đã liên kết thành công! Token sẽ tự động refresh khi cần.",
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "facebook_link_failed", "message": str(e)},
        )


@router.get("/facebook/status", response_model=FacebookStatusResponse)
def facebook_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FacebookStatusResponse:
    """
    Kiểm tra trạng thái liên kết Facebook Page.
    """
    now = datetime.now(timezone.utc)
    
    is_linked = bool(current_user.facebook_page_id and current_user.facebook_access_token)
    is_valid = False
    message = None
    
    if is_linked:
        # Check Page Token
        if current_user.facebook_token_expires_at is None:
            is_valid = True  # Long-lived Page Token
        elif current_user.facebook_token_expires_at > now:
            is_valid = True  # Page Token còn hạn
        else:
            # Page Token hết hạn, check User Token
            if current_user.facebook_user_token_expires_at:
                if current_user.facebook_user_token_expires_at > now:
                    # User Token còn hạn → có thể auto refresh
                    is_valid = True
                    message = "Page token hết hạn nhưng có thể tự động refresh."
                else:
                    # User Token cũng hết hạn
                    is_valid = False
                    message = "Token đã hết hạn (60 ngày). Vui lòng liên kết lại Facebook."
            else:
                is_valid = False
                message = "Chưa có Long-lived User Token. Vui lòng liên kết lại Facebook."
    else:
        message = "Chưa liên kết Facebook Page."
    
    return FacebookStatusResponse(
        linked=is_linked,
        valid=is_valid,
        page_id=current_user.facebook_page_id,
        page_name=current_user.facebook_page_name,
        expires_at=current_user.facebook_user_token_expires_at,
        message=message,
    )
