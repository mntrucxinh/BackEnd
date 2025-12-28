"""
API endpoints để upload assets (ảnh và video).

- Ảnh: lưu vào /uploads/images/YYYY/MM/
- Video: lưu vào /uploads/videos/YYYY/MM/
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.asset import AssetOut
from app.services import asset_service

router = APIRouter(prefix="/admin/assets", tags=["Admin - Assets"])


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(..., description="File ảnh hoặc video để upload"),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # Uncomment khi có auth
) -> AssetOut:
    """
    Upload asset (ảnh hoặc video).
    
    - Ảnh: lưu vào /uploads/images/YYYY/MM/
    - Video: lưu vào /uploads/videos/YYYY/MM/
    
    Returns:
        AssetOut với public_id để dùng khi tạo post
    """
    # TODO: Uncomment khi có auth
    # user_id = current_user.id
    user_id = None  # Tạm thời
    
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

