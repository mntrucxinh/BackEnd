from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AssetOut(BaseModel):
    """Schema cho asset trong response."""

    id: int
    public_id: UUID
    url: str
    mime_type: str
    byte_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class PostAssetOut(BaseModel):
    """Schema cho ảnh trong nội dung bài viết."""

    position: int = Field(..., description="Thứ tự ảnh trong bài viết.")
    caption: Optional[str] = Field(default=None, description="Chú thích ảnh.")
    asset: AssetOut = Field(..., description="Thông tin asset.")


# ============================================================================
# Public API schemas (chỉ trả về public_id, không có id nội bộ)
# ============================================================================

class PublicAssetOut(BaseModel):
    """Schema cho asset trong public API - chỉ trả về public_id."""

    public_id: UUID
    url: str
    mime_type: str
    byte_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class PublicPostAssetOut(BaseModel):
    """Schema cho ảnh trong nội dung bài viết (public API)."""

    position: int = Field(..., description="Thứ tự ảnh trong bài viết.")
    caption: Optional[str] = Field(default=None, description="Chú thích ảnh.")
    asset: PublicAssetOut = Field(..., description="Thông tin asset.")
