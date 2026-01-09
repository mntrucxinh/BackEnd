"""
Service xử lý upload assets (ảnh và video).

- Ảnh: lưu vào /uploads/images/YYYY/MM/
- Video: lưu vào /uploads/videos/YYYY/MM/
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from PIL import Image

from app.models.tables import Asset
from app.schemas.asset import AssetListMeta, AssetListOut, AssetOut

# Cấu hình thư mục lưu trữ
# Nếu có UPLOAD_DIR env thì dùng, không thì dùng relative path (cho local dev)
upload_dir_env = os.getenv("UPLOAD_DIR")
if upload_dir_env:
    UPLOAD_DIR = Path(upload_dir_env)
else:
    # Relative path cho local development
    UPLOAD_DIR = Path("uploads")
IMAGES_DIR = UPLOAD_DIR / "images"
VIDEOS_DIR = UPLOAD_DIR / "videos"

# Tạo thư mục nếu chưa có
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


async def upload_asset(
    db: Session,
    file: UploadFile,
    uploaded_by: Optional[int],
) -> Asset:
    """
    Upload asset (ảnh hoặc video) và lưu vào thư mục phù hợp.
    
    - Ảnh: lưu vào /uploads/images/YYYY/MM/
    - Video: lưu vào /uploads/videos/YYYY/MM/
    
    Args:
        db: Database session
        file: File upload từ frontend
        uploaded_by: ID user upload
        
    Returns:
        Asset record đã tạo
    """
    # Validate file type
    mime_type = file.content_type or ""
    is_video = mime_type.startswith("video/")
    is_image = mime_type.startswith("image/")
    
    if not (is_video or is_image):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_file_type", "message": "Chỉ chấp nhận file ảnh hoặc video."}
        )
    
    # Đọc file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size (tối đa 500MB cho video, 10MB cho ảnh)
    max_size = 500 * 1024 * 1024 if is_video else 10 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "file_too_large",
                "message": f"File quá lớn. Tối đa {max_size // (1024*1024)}MB cho {'video' if is_video else 'ảnh'}."
            }
        )
    
    # Tạo tên file unique
    file_ext = Path(file.filename or "file").suffix
    file_name = f"{uuid4()}{file_ext}"
    
    from datetime import datetime
    year_month = datetime.now().strftime("%Y/%m")
    
    if is_video:
        # Video: lưu vào videos/YYYY/MM/
        save_dir = VIDEOS_DIR / year_month
        save_dir.mkdir(parents=True, exist_ok=True)
        object_key = f"videos/{year_month}/{file_name}"
    else:
        # Ảnh: lưu vào images/YYYY/MM/
        save_dir = IMAGES_DIR / year_month
        save_dir.mkdir(parents=True, exist_ok=True)
        object_key = f"images/{year_month}/{file_name}"
    
    # Lưu file
    file_path = save_dir / file_name
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Get metadata (nếu là ảnh)
    width, height = None, None
    if is_image:
        try:
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            # Nếu không đọc được metadata, vẫn lưu file
            pass
    
    # Tạo Asset record
    asset = Asset(
        storage="local",
        object_key=object_key,
        url=f"/uploads/{object_key}",
        mime_type=mime_type,
        byte_size=file_size,
        width=width,
        height=height,
        uploaded_by=uploaded_by,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return asset


def list_assets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    mime_type_filter: Optional[str] = None,
    q: Optional[str] = None,
) -> AssetListOut:
    """
    Lấy danh sách assets với pagination và filter.
    
    Args:
        db: Database session
        page: Số trang
        page_size: Số items mỗi trang
        mime_type_filter: Filter theo mime_type (ví dụ: "image/" hoặc "video/")
        q: Từ khoá tìm kiếm (search trong url và object_key)
        
    Returns:
        AssetListOut với danh sách assets và pagination meta
    """
    # Base query
    stmt = select(Asset).where(Asset.deleted_at.is_(None))
    
    # Filter by mime_type
    if mime_type_filter:
        stmt = stmt.where(Asset.mime_type.startswith(mime_type_filter))
    
    # Search (có thể search theo url hoặc object_key)
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            (Asset.url.ilike(search_term))
            | (Asset.object_key.ilike(search_term))
        )
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = db.scalar(count_stmt)
    
    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Asset.created_at.desc()).offset(offset).limit(page_size)
    
    assets = db.scalars(stmt).all()
    
    # Convert to output
    items = [
        AssetOut(
            id=asset.id,
            public_id=asset.public_id,
            url=asset.url or "",
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
        )
        for asset in assets
    ]
    
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
    
    return AssetListOut(
        items=items,
        meta=AssetListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )

