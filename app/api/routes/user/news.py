from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.news import PublicNewsListOut, PublicNewsOut
from app.services.user import news_service

router = APIRouter(prefix="/public/news", tags=["Public - News"])


@router.get("", response_model=PublicNewsListOut)
def list_news(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm theo tiêu đề/slug/excerpt (ILIKE).",
    ),
) -> PublicNewsListOut:
    """
    Lấy danh sách tin tức công khai (chỉ published).
    Hỗ trợ search và pagination.
    """
    return news_service.list_news(
        db,
        page=page,
        page_size=page_size,
        q=q,
    )


@router.get("/{slug}", response_model=PublicNewsOut)
def get_news_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> PublicNewsOut:
    """
    Lấy chi tiết tin tức công khai theo slug (chỉ published).
    """
    return news_service.get_news_by_slug(db, slug)

