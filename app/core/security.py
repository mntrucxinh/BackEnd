from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

from fastapi import HTTPException, status
from jose import JWTError, jwt


def _now() -> datetime:
    return datetime.now(timezone.utc)


JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_token(
    payload: Dict[str, Any], expires_delta: timedelta, token_type: str
) -> Tuple[str, datetime]:
    exp = _now() + expires_delta
    to_encode = payload.copy()
    to_encode.update({"exp": exp, "type": token_type})
    encoded = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded, exp


def create_app_tokens(user_id: int, public_id: str, email: str) -> Dict[str, Any]:
    base_payload = {"sub": public_id, "uid": user_id, "email": email}
    access_token, access_exp = create_token(
        base_payload,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )
    refresh_token, refresh_exp = create_token(
        base_payload,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )
    return {
        "access_token": access_token,
        "access_expires_at": access_exp,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_exp,
    }


def decode_refresh_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_refresh_token",
                "message": f"Refresh token không hợp lệ: {e}",
            },
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_refresh_token_type",
                "message": "Token không phải refresh token.",
            },
        )
    return payload
