from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., description="ID token từ Google Sign-In")
    access_token: Optional[str] = Field(
        default=None, description="Access token của Google (nếu FE có)"
    )
    access_token_expires_in: Optional[int] = Field(
        default=None,
        description="Số giây còn hạn của access token (nếu FE có). Sẽ được tính thành expires_at.",
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token của Google (nếu có quyền offline). Nên gửi để BE có thể refresh.",
    )
    scope: Optional[str] = Field(
        default=None, description="Chuỗi scope từ Google (tùy chọn lưu lại)."
    )


class GoogleUserOut(BaseModel):
    id: int
    public_id: str
    email: str
    google_sub: Optional[str] = None


class GoogleLoginResponse(BaseModel):
    user: GoogleUserOut
    token_expires_at: Optional[datetime] = Field(
        None, description="Thời điểm hết hạn của ID token lưu trong DB (UTC)"
    )
    token_is_valid: bool = Field(
        ..., description="Token trong DB còn hạn (theo exp từ Google)"
    )
    access_token_expires_at: Optional[datetime] = Field(
        None, description="Thời điểm hết hạn access token (nếu lưu)"
    )
    access_token_saved: bool = Field(
        ..., description="Có lưu access token vào DB không"
    )
    refresh_token_saved: bool = Field(
        ..., description="Có lưu refresh token vào DB không"
    )
    message: Optional[str] = None


class GoogleTokenStatusResponse(BaseModel):
    token_expires_at: Optional[datetime] = None
    token_is_valid: bool = False
    message: Optional[str] = None


class GoogleAccountVerifyResponse(BaseModel):
    allowed: bool = Field(..., description="Email có được phép đăng nhập không")
    message: Optional[str] = None
