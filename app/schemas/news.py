from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContentStatus
from app.schemas.asset import PostAssetOut, PublicPostAssetOut


class NewsBase(BaseModel):
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
        description="Workflow nội dung: draft / published / archived.",
    )
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    content_asset_public_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Danh sách public_id của các asset dùng làm ảnh trong nội dung bài viết (theo thứ tự).",
    )


class NewsCreate(NewsBase):
    pass


class NewsUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(
        default=None,
        description="Nếu set null thì giữ nguyên slug cũ.",
        min_length=1,
        max_length=255,
    )
    excerpt: Optional[str] = Field(default=None, max_length=500)
    content_html: Optional[str] = Field(default=None, min_length=1)
    status: Optional[ContentStatus] = None
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    content_asset_public_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Danh sách public_id của các asset dùng làm ảnh trong nội dung bài viết (theo thứ tự). Set null để giữ nguyên.",
    )


class NewsOut(BaseModel):
    """Chuẩn response cho admin CMS."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID nội bộ của bài viết (BigInteger).")
    public_id: UUID = Field(..., description="UUID công khai của bài viết (dùng trong API).")
    title: str
    slug: str
    excerpt: Optional[str]
    content_html: str
    status: ContentStatus
    meta_title: Optional[str]
    meta_description: Optional[str]
    content_assets: Optional[list[PostAssetOut]] = Field(
        default=None,
        description="Danh sách ảnh trong nội dung bài viết (theo thứ tự).",
    )
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class NewsListMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class NewsListOut(BaseModel):
    items: list[NewsOut]
    meta: NewsListMeta


class SlugCheckOut(BaseModel):
    is_unique: bool
    normalized_slug: str


# ============================================================================
# Public API schemas (chỉ trả về public_id, không có id nội bộ)
# ============================================================================

class PublicNewsOut(BaseModel):
    """Schema cho public API - chỉ trả về public_id, không có id nội bộ và status."""

    model_config = ConfigDict(from_attributes=True)

    public_id: UUID = Field(..., description="UUID công khai của bài viết.")
    title: str
    slug: str
    excerpt: Optional[str]
    content_html: str
    meta_title: Optional[str]
    meta_description: Optional[str]
    content_assets: Optional[list[PublicPostAssetOut]] = Field(
        default=None,
        description="Danh sách ảnh trong nội dung bài viết (theo thứ tự).",
    )
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PublicNewsListOut(BaseModel):
    items: list[PublicNewsOut]
    meta: NewsListMeta

