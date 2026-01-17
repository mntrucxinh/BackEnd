"""
API endpoints để xem assets (images và videos) công khai.
Chỉ lấy những ảnh và video được upload trong các album published.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.asset import PublicAssetListOut
from app.services.user import media_service

router = APIRouter(prefix="/public/assets", tags=["Public - Assets"])


@router.get("", response_model=PublicAssetListOut)
def list_assets(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    mime_type: Optional[str] = Query(
        None,
        description="Lọc theo mime_type: 'image/' hoặc 'video/'. Bỏ trống để lấy tất cả.",
    ),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm (search trong url và object_key).",
    ),
) -> PublicAssetListOut:
    """
    Lấy danh sách assets công khai từ các album published.
    
    Chỉ lấy những ảnh và video được upload trong album (không lấy tất cả assets).
    Hỗ trợ filter theo mime_type (ảnh/video) và search.
    """
    if mime_type == "image/":
        return media_service.list_images_from_albums(
            db,
            page=page,
            page_size=page_size,
            q=q,
        )
    elif mime_type == "video/":
        return media_service.list_videos_from_albums(
            db,
            page=page,
            page_size=page_size,
            q=q,
        )
    else:
        # Nếu không có mime_type, trả về cả images và videos
        # Hoặc có thể trả về lỗi yêu cầu chỉ định mime_type
        # Tạm thời trả về images
        return media_service.list_images_from_albums(
            db,
            page=page,
            page_size=page_size,
            q=q,
        )

