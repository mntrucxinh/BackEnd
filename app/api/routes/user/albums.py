"""
API endpoints để xem albums (public).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.album import PublicAlbumListOut, PublicAlbumOut
from app.services.user import album_service

router = APIRouter(prefix="/public/albums", tags=["Public - Albums"])


@router.get("", response_model=PublicAlbumListOut)
def list_albums(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm theo tiêu đề/slug/description (ILIKE).",
    ),
) -> PublicAlbumListOut:
    """
    Lấy danh sách albums công khai (chỉ published).
    Hỗ trợ search và pagination.
    """
    return album_service.list_albums(
        db,
        page=page,
        page_size=page_size,
        q=q,
    )


@router.get("/{slug}", response_model=PublicAlbumOut)
def get_album_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> PublicAlbumOut:
    """
    Lấy chi tiết album công khai theo slug (chỉ published).
    """
    return album_service.get_album_by_slug(db, slug)

