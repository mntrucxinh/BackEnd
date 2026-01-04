from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.announcement import (
    PublicAnnouncementListOut,
    PublicAnnouncementOut,
)
from app.services.user import announcement_service

router = APIRouter(prefix="/public/announcements", tags=["Public - Announcements"])


@router.get("", response_model=PublicAnnouncementListOut)
def list_announcements(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    grade: Optional[str] = Query(
        None,
        description="Lọc theo mã khối (bee/mouse/bear/dolphin). Bỏ trống để lấy tất cả.",
    ),
) -> PublicAnnouncementListOut:
    """
    Lấy danh sách thông báo công khai (chỉ published).
    Có thể filter theo grade (mã khối).
    """
    return announcement_service.list_announcements(
        db,
        page=page,
        page_size=page_size,
        grade=grade,
    )


@router.get("/{slug_or_id}", response_model=PublicAnnouncementOut)
def get_announcement_by_slug_or_id(
    slug_or_id: str,
    db: Session = Depends(get_db),
) -> PublicAnnouncementOut:
    """
    Lấy chi tiết thông báo công khai theo slug hoặc public_id (chỉ published).
    """
    return announcement_service.get_announcement_by_slug_or_id(db, slug_or_id)

