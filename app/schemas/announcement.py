from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContentStatus
from app.schemas.asset import PostAssetOut, PublicPostAssetOut


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


# ============================================================================
# Admin schemas
# ============================================================================


class AnnouncementBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(
        default=None,
        description="Nếu bỏ trống, backend sẽ tự sinh từ title.",
        min_length=1,
        max_length=255,
    )
    excerpt: Optional[str] = Field(default=None, max_length=500)
    content_html: str = Field(..., min_length=1)
    status: ContentStatus = Field(
        default=ContentStatus.DRAFT,
        description="Trạng thái: draft/published/archived.",
    )
    publish_to_facebook: bool = Field(
        default=True,
        description=(
            "Có đăng lên Facebook hay không. "
            "Chỉ áp dụng khi status = published; draft/archived sẽ không đăng."
        ),
    )
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    block_code: str = Field(
        ...,
        description="Mã khối (bee/mouse/bear/dolphin).",
        min_length=1,
        max_length=50,
    )
    content_asset_public_ids: Optional[list[UUID]] = Field(
        default=None,
        description=(
            "Danh sách public_id của các asset dùng làm ảnh/video trong nội dung"
            " (theo thứ tự)."
        ),
    )


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(
        default=None,
        description="Không dùng từ client. Backend tự sinh từ title nếu title thay đổi.",
        min_length=1,
        max_length=255,
    )
    excerpt: Optional[str] = Field(default=None, max_length=500)
    content_html: Optional[str] = Field(default=None, min_length=1)
    status: Optional[ContentStatus] = None
    publish_to_facebook: Optional[bool] = Field(
        default=None,
        description=(
            "Có đăng lên Facebook hay không. "
            "None = giữ nguyên; False = chỉ web; True = đăng/đăng lại Facebook."
        ),
    )
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    block_code: Optional[str] = Field(
        default=None,
        description="Mã khối mới (bee/mouse/bear/dolphin).",
        min_length=1,
        max_length=50,
    )
    content_asset_public_ids: Optional[list[UUID]] = Field(
        default=None,
        description=(
            "Danh sách public_id mới của các asset trong nội dung (theo thứ tự). "
            "None = giữ nguyên, [] = xoá hết, [ids] = thay thế."
        ),
    )


class AdminAnnouncementOut(BaseModel):
    """Schema cho admin CMS - bao gồm id nội bộ, status, block info, assets."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID nội bộ của thông báo (BigInteger).")
    public_id: UUID = Field(..., description="UUID công khai của thông báo.")
    title: str
    slug: str
    excerpt: Optional[str]
    content_html: str
    status: ContentStatus
    meta_title: Optional[str]
    meta_description: Optional[str]
    content_assets: Optional[list[PostAssetOut]] = Field(
        default=None,
        description="Danh sách ảnh/video trong nội dung (theo thứ tự).",
    )
    block_code: str = Field(..., description="Mã khối (bee/mouse/bear/dolphin).")
    block_name: str = Field(..., description="Tên khối.")
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AdminAnnouncementListMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AdminAnnouncementListOut(BaseModel):
    items: list[AdminAnnouncementOut]
    meta: AdminAnnouncementListMeta

