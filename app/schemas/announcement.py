from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import PublicPostAssetOut


class PublicAnnouncementOut(BaseModel):
    """Schema cho public API - chỉ trả về public_id, không có id nội bộ và status."""

    model_config = ConfigDict(from_attributes=True)

    public_id: UUID = Field(..., description="UUID công khai của thông báo.")
    title: str
    slug: str
    excerpt: Optional[str]
    content_html: str
    meta_title: Optional[str]
    meta_description: Optional[str]
    content_assets: Optional[list[PublicPostAssetOut]] = Field(
        default=None,
        description="Danh sách ảnh trong nội dung thông báo (theo thứ tự).",
    )
    block_code: str = Field(..., description="Mã khối (bee/mouse/bear/dolphin).")
    block_name: str = Field(..., description="Tên khối.")
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AnnouncementListMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PublicAnnouncementListOut(BaseModel):
    items: list[PublicAnnouncementOut]
    meta: AnnouncementListMeta

