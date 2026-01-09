"""
API endpoints để upload assets (ảnh và video).

- Ảnh: lưu vào /uploads/images/YYYY/MM/
- Video: lưu vào /uploads/videos/YYYY/MM/
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.tables import User
from app.schemas.asset import AssetListOut, AssetOut
from app.services import asset_service

router = APIRouter(prefix="/admin/assets", tags=["Admin - Assets"])


@router.get("", response_model=AssetListOut)
def list_assets(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    mime_type: Optional[str] = Query(
        None,
        description="Lọc theo mime_type (ví dụ: 'image/' hoặc 'video/'). Bỏ trống để lấy tất cả.",
    ),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm (search trong url và object_key).",
    ),
    current_user: User = Depends(get_current_user),
) -> AssetListOut:
    """
    Lấy danh sách assets trong thư viện.
    
    Dùng để hiển thị thư viện assets cho admin chọn khi tạo album hoặc bài viết.
    Hỗ trợ filter theo mime_type (ảnh/video) và search.
    """
    return asset_service.list_assets(
        db,
        page=page,
        page_size=page_size,
        mime_type_filter=mime_type,
        q=q,
    )


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(..., description="File ảnh hoặc video để upload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetOut:
    """
    Upload asset (ảnh hoặc video).
    
    - Ảnh: lưu vào /uploads/images/YYYY/MM/
    - Video: lưu vào /uploads/videos/YYYY/MM/
    
    Returns:
        AssetOut với public_id để dùng khi tạo post hoặc album
    """
    user_id = current_user.id
    
    asset = await asset_service.upload_asset(db, file, user_id)

    return AssetOut(
        id=asset.id,
        public_id=asset.public_id,
        url=asset.url or "",
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        width=asset.width,
        height=asset.height,
    )

