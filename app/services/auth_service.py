from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import User

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ALLOWED_GOOGLE_ACCOUNT = os.getenv("GOOGLE_ACCOUNT")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def verify_google_id_token(id_token: str) -> Tuple[dict, datetime]:
    """
    Verify Google ID token via tokeninfo endpoint.
    Returns payload dict and expiry datetime (UTC).
    """
    try:
        resp = requests.get(
            GOOGLE_TOKENINFO_URL, params={"id_token": id_token}, timeout=5
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "google_verify_failed",
                "message": f"Không gọi được Google tokeninfo: {e}",
            },
        )

    if resp.status_code != 200:
        detail = resp.text
        try:
            detail = resp.json()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_google_token",
                "message": "ID token không hợp lệ hoặc đã hết hạn.",
                "detail": detail,
            },
        )

    payload = resp.json()

    # Audience check (nếu set GOOGLE_CLIENT_ID)
    aud = payload.get("aud")
    if GOOGLE_CLIENT_ID and aud != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_google_audience",
                "message": "ID token không khớp client_id đã cấu hình.",
            },
        )

    exp_ts = payload.get("exp")
    exp_dt = (
        datetime.fromtimestamp(int(exp_ts), tz=timezone.utc) if exp_ts is not None else None
    )

    sub = payload.get("sub")
    email = payload.get("email")

    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "google_payload_missing",
                "message": "Thiếu sub/email trong ID token.",
            },
        )

    return payload, exp_dt


def _is_token_valid(exp_dt: Optional[datetime]) -> bool:
    return bool(exp_dt and exp_dt > _now())


def login_with_google(
    db: Session,
    id_token: str,
    access_token: Optional[str] = None,
    access_token_expires_in: Optional[int] = None,
    refresh_token: Optional[str] = None,
    scope: Optional[str] = None,
) -> Tuple[User, Optional[datetime], bool]:
    payload, exp_dt = verify_google_id_token(id_token)
    sub = payload["sub"]
    email = payload["email"]

    user = db.scalar(select(User).where(User.google_sub == sub))
    if not user:
        user = db.scalar(select(User).where(User.email == email))

    if not user:
        user = User(email=email, google_sub=sub)
        db.add(user)
    else:
        # Ensure sub is stored
        if not user.google_sub:
            user.google_sub = sub

    now = _now()
    user.google_id_token = id_token
    user.google_id_token_expires_at = exp_dt
    if scope:
        user.google_token_scope = scope

    # Access token (optional)
    if access_token:
        user.google_access_token = access_token
        if access_token_expires_in is not None:
            user.google_access_token_expires_at = now + timedelta(
                seconds=access_token_expires_in
            )
        elif user.google_access_token_expires_at is None:
            user.google_access_token_expires_at = None

    # Refresh token (optional)
    if refresh_token:
        user.google_refresh_token = refresh_token
    user.updated_at = now

    db.add(user)
    db.commit()
    db.refresh(user)

    return user, exp_dt, _is_token_valid(exp_dt)


def token_status(db: Session, email: str) -> Tuple[Optional[datetime], bool]:
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User không tồn tại."},
        )

    exp_dt = user.google_id_token_expires_at
    return exp_dt, _is_token_valid(exp_dt)


def is_allowed_google_account(email: str) -> bool:
    """
    Check email against allowed list from env (GOOGLE_ACCOUNT).
    Supports comma-separated list; case-insensitive.
    If env not set, allow all.
    """
    if not ALLOWED_GOOGLE_ACCOUNT:
        return True
    allowed = [e.strip().lower() for e in ALLOWED_GOOGLE_ACCOUNT.split(",") if e.strip()]
    if not allowed:
        return True
    return email.lower() in allowed


def _ensure_client_secret():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "google_oauth_config_missing",
                "message": "Thiếu GOOGLE_CLIENT_ID hoặc GOOGLE_CLIENT_SECRET để refresh token.",
            },
        )


def refresh_google_access_token(db: Session, user: User) -> str:
    if not user.google_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_refresh_token",
                "message": "Chưa lưu refresh token; cần đăng nhập lại Google với quyền offline.",
            },
        )

    _ensure_client_secret()

    data = {
        "grant_type": "refresh_token",
        "refresh_token": user.google_refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
    }
    try:
        resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=5)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "google_refresh_failed",
                "message": f"Không gọi được Google để refresh: {e}",
            },
        )

    if resp.status_code != 200:
        detail = resp.text
        try:
            detail = resp.json()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "google_refresh_invalid",
                "message": "Refresh token không hợp lệ hoặc đã thu hồi; đăng nhập lại Google.",
                "detail": detail,
            },
        )

    data = resp.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "google_refresh_missing_token",
                "message": "Google không trả access_token khi refresh.",
            },
        )

    now = _now()
    user.google_access_token = access_token
    if expires_in:
        user.google_access_token_expires_at = now + timedelta(seconds=int(expires_in))
    else:
        user.google_access_token_expires_at = None
    user.updated_at = now
    db.add(user)
    db.commit()
    db.refresh(user)
    return access_token


def get_valid_access_token(db: Session, user: User) -> str:
    now = _now()
    if user.google_access_token and user.google_access_token_expires_at:
        if user.google_access_token_expires_at > now:
            return user.google_access_token
    elif user.google_access_token:
        # No expiry stored → assume valid until proven otherwise
        return user.google_access_token

    # Need refresh
    return refresh_google_access_token(db, user)


def get_user_for_google(db: Session, email: Optional[str] = None) -> User:
    user = None
    if email:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "user_not_found", "message": "User không tồn tại."},
            )
    else:
        user = db.scalar(select(User).order_by(User.id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Chưa có user để dùng Google token."},
        )
    return user
