from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContentStatus
from app.schemas.asset import AssetOut, PublicAssetOut


# ============================================================================
# Album Item schemas
# ============================================================================

class AlbumItemOut(BaseModel):
    """Schema cho item trong album (ảnh)."""

    position: int = Field(..., description="Thứ tự trong album.")
    caption: Optional[str] = Field(default=None, description="Chú thích ảnh.")
    asset: AssetOut = Field(..., description="Thông tin asset.")


class PublicAlbumItemOut(BaseModel):
    """Schema cho item trong album (public API)."""

    position: int = Field(..., description="Thứ tự trong album.")
    caption: Optional[str] = Field(default=None, description="Chú thích ảnh.")
    asset: PublicAssetOut = Field(..., description="Thông tin asset.")


class AlbumVideoOut(BaseModel):
    """Schema cho video trong album."""

    position: int = Field(..., description="Thứ tự trong album.")
    video: dict = Field(..., description="Thông tin video embed.")


class PublicAlbumVideoOut(BaseModel):
    """Schema cho video trong album (public API)."""

    position: int = Field(..., description="Thứ tự trong album.")
    video: dict = Field(..., description="Thông tin video embed.")


# ============================================================================
# Admin API schemas
# ============================================================================

class AlbumItemCreate(BaseModel):
    """Schema để thêm item vào album."""

    asset_public_id: UUID = Field(..., description="Public ID của asset (ảnh).")
    position: int = Field(..., description="Thứ tự trong album.")
    caption: Optional[str] = Field(default=None, description="Chú thích ảnh.")


class AlbumVideoCreate(BaseModel):
    """Schema để thêm video vào album."""

    video_public_id: UUID = Field(..., description="Public ID của video embed.")
    position: int = Field(..., description="Thứ tự trong album.")


class AlbumBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(
        default=None,
        description="Nếu bỏ trống, backend sẽ tự sinh từ title.",
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    status: ContentStatus = Field(
        default=ContentStatus.PUBLISHED,
        description="Workflow nội dung: draft / published / archived.",
    )
    cover_asset_public_id: Optional[UUID] = Field(
        default=None,
        description="Public ID của ảnh cover. Nếu None, tự động lấy ảnh đầu tiên.",
    )


class AlbumCreate(AlbumBase):
    """Schema để tạo album mới."""

    items: Optional[list[AlbumItemCreate]] = Field(
        default=None,
        description="Danh sách ảnh trong album (theo thứ tự).",
    )
    videos: Optional[list[AlbumVideoCreate]] = Field(
        default=None,
        description="Danh sách video trong album (theo thứ tự).",
    )


class AlbumUpdate(BaseModel):
    """Schema để cập nhật album."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(
        default=None,
        description="Nếu set null thì giữ nguyên slug cũ.",
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[ContentStatus] = None
    cover_asset_public_id: Optional[UUID] = Field(
        default=None,
        description="Public ID của ảnh cover. Set null để giữ nguyên.",
    )


class AlbumOut(BaseModel):
    """Schema cho admin API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID nội bộ của album (BigInteger).")
    public_id: UUID = Field(..., description="UUID công khai của album.")
    title: str
    slug: str
    description: Optional[str]
    status: ContentStatus
    cover: Optional[AssetOut] = Field(
        default=None,
        description="Ảnh cover của album.",
    )
    items: Optional[list[AlbumItemOut]] = Field(
        default=None,
        description="Danh sách ảnh trong album (theo thứ tự).",
    )
    videos: Optional[list[AlbumVideoOut]] = Field(
        default=None,
        description="Danh sách video trong album (theo thứ tự).",
    )
    item_count: int = Field(..., description="Tổng số items (ảnh + video).")
    image_count: int = Field(..., description="Số lượng ảnh.")
    video_count: int = Field(..., description="Số lượng video.")
    created_by: Optional[int] = Field(default=None, description="ID người tạo.")
    created_at: datetime
    updated_at: datetime


class AlbumListMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AlbumListOut(BaseModel):
    items: list[AlbumOut]
    meta: AlbumListMeta


class SlugCheckOut(BaseModel):
    is_unique: bool
    normalized_slug: str


# ============================================================================
# Public API schemas (chỉ trả về public_id, không có id nội bộ)
# ============================================================================

class PublicAlbumOut(BaseModel):
    """Schema cho public API - chỉ trả về public_id, không có id nội bộ và status."""

    model_config = ConfigDict(from_attributes=True)

    public_id: UUID = Field(..., description="UUID công khai của album.")
    title: str
    slug: str
    description: Optional[str]
    cover: Optional[PublicAssetOut] = Field(
        default=None,
        description="Ảnh cover của album.",
    )
    items: Optional[list[PublicAlbumItemOut]] = Field(
        default=None,
        description="Danh sách ảnh trong album (theo thứ tự).",
    )
    videos: Optional[list[PublicAlbumVideoOut]] = Field(
        default=None,
        description="Danh sách video trong album (theo thứ tự).",
    )
    item_count: int = Field(..., description="Tổng số items (ảnh + video).")
    image_count: int = Field(..., description="Số lượng ảnh.")
    video_count: int = Field(..., description="Số lượng video.")
    created_at: datetime
    updated_at: datetime


class PublicAlbumListOut(BaseModel):
    items: list[PublicAlbumOut]
    meta: AlbumListMeta

