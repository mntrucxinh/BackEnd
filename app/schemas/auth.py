from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class GoogleLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_token: Optional[str] = Field(
        default=None,
        description="ID token từ Google Sign-In",
        validation_alias="idToken",
    )
    access_token: Optional[str] = Field(
        default=None,
        description="Access token của Google (nếu FE có)",
        validation_alias="accessToken",
    )
    access_token_expires_in: Optional[int] = Field(
        default=None,
        description="Số giây còn hạn của access token (nếu FE có). Sẽ được tính thành expires_at.",
        validation_alias="accessTokenExpiresIn",
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token của Google (nếu có quyền offline). Nên gửi để BE có thể refresh.",
        validation_alias="refreshToken",
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
    model_config = ConfigDict(populate_by_name=True)

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
    access_token: str = Field(
        ..., description="Access token của app", serialization_alias="accessToken"
    )
    refresh_token: str = Field(
        ..., description="Refresh token của app", serialization_alias="refreshToken"
    )
    access_token_expires_at_app: datetime = Field(
        ..., description="Hết hạn access token của app", serialization_alias="accessTokenExpiresAt"
    )
    refresh_token_expires_at_app: datetime = Field(
        ..., description="Hết hạn refresh token của app", serialization_alias="refreshTokenExpiresAt"
    )
    token_type: str = Field(
        "bearer", description="Kiểu token", serialization_alias="tokenType"
    )
    message: Optional[str] = None


class GoogleTokenStatusResponse(BaseModel):
    token_expires_at: Optional[datetime] = None
    token_is_valid: bool = False
    message: Optional[str] = None


class GoogleRefreshResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(
        ..., description="Access token của app", serialization_alias="accessToken"
    )
    refresh_token: str = Field(
        ..., description="Refresh token của app", serialization_alias="refreshToken"
    )
    access_token_expires_at: datetime = Field(
        ..., description="Hết hạn access token", serialization_alias="accessTokenExpiresAt"
    )
    refresh_token_expires_at: datetime = Field(
        ..., description="Hết hạn refresh token", serialization_alias="refreshTokenExpiresAt"
    )
    user: GoogleUserOut
