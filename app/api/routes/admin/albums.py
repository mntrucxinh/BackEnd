"""
API endpoints để quản lý albums (admin).
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import ContentStatus
from app.models.tables import User
from app.schemas.album import (
    AlbumCreate,
    AlbumItemCreate,
    AlbumListOut,
    AlbumOut,
    AlbumUpdate,
    AlbumVideoCreate,
    SlugCheckOut,
)
from app.services import asset_service
from app.services.admin import album_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/albums", tags=["Admin - Albums"])


@router.get("", response_model=AlbumListOut)
def list_albums(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số items mỗi trang"),
    status: Optional[ContentStatus] = Query(
        None, description="Lọc theo status (draft/published/archived). Bỏ trống để lấy tất cả."
    ),
    q: Optional[str] = Query(
        None, description="Từ khoá tìm kiếm theo tiêu đề/slug/description (ILIKE)."
    ),
    current_user: User = Depends(get_current_user),
) -> AlbumListOut:
    """
    Lấy danh sách albums với pagination và filter.
    """
    return album_service.list_albums(
        db,
        page=page,
        page_size=page_size,
        status_filter=status,
        q=q,
    )


@router.get("/{album_id}", response_model=AlbumOut)
def get_album_detail(
    album_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumOut:
    """
    Lấy chi tiết album.
    """
    return album_service.get_album_detail(db, album_id)


@router.post("", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
async def create_album(
    # Text fields
    title: str = Form(..., description="Tên album"),
    description: Optional[str] = Form(None, description="Mô tả album"),
    status: ContentStatus = Form(
        ContentStatus.PUBLISHED, description="Trạng thái: draft/published/archived"
    ),
    slug: Optional[str] = Form(
        None, description="Slug (nếu bỏ trống, tự động sinh từ title)"
    ),
    # Cover
    cover_asset_public_id: Optional[UUID] = Form(
        None, description="Public ID của ảnh cover (nếu None, tự động lấy ảnh đầu tiên)"
    ),
    # Files - upload mới
    new_files: Optional[List[UploadFile]] = File(
        None, description="Danh sách files mới để upload (ảnh/video)"
    ),
    new_captions: Optional[List[str]] = Form(
        None, description="Danh sách captions tương ứng với new_files (theo thứ tự)"
    ),
    # Assets có sẵn
    existing_asset_public_ids: Optional[List[UUID]] = Form(
        None, description="Danh sách public_id của assets có sẵn"
    ),
    existing_captions: Optional[List[str]] = Form(
        None, description="Danh sách captions tương ứng với existing_asset_public_ids"
    ),
    # Videos
    video_public_ids: Optional[List[UUID]] = Form(
        None, description="Danh sách public_id của videos"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumOut:
    """
    Tạo album mới.
    
    **Workflow:**
    1. Upload new_files (nếu có) → tạo Assets mới
    2. Lấy existing_asset_public_ids (nếu có) → dùng assets có sẵn
    3. Lấy video_public_ids (nếu có) → thêm videos
    4. Merge tất cả theo thứ tự → tạo album_items và album_videos
    5. Set cover (nếu có, không thì auto lấy ảnh đầu tiên)
    6. Tạo Album
    
    **Thứ tự items:**
    - new_files trước (theo thứ tự upload)
    - existing_asset_public_ids sau (theo thứ tự trong list)
    - videos cuối cùng (theo thứ tự trong list)
    """
    user_id = current_user.id
    
    # Upload new files
    new_asset_public_ids = []
    if new_files:
        for file in new_files:
            asset = await asset_service.upload_asset(db, file, user_id)
            new_asset_public_ids.append(asset.public_id)
    
    # Build items list
    items = []
    position = 0
    
    # Add new files
    if new_asset_public_ids:
        new_captions_list = new_captions or []
        for idx, asset_public_id in enumerate(new_asset_public_ids):
            caption = new_captions_list[idx] if idx < len(new_captions_list) else None
            items.append(
                AlbumItemCreate(
                    asset_public_id=asset_public_id,
                    position=position,
                    caption=caption,
                )
            )
            position += 1
    
    # Add existing assets
    if existing_asset_public_ids:
        existing_captions_list = existing_captions or []
        for idx, asset_public_id in enumerate(existing_asset_public_ids):
            caption = (
                existing_captions_list[idx]
                if idx < len(existing_captions_list)
                else None
            )
            items.append(
                AlbumItemCreate(
                    asset_public_id=asset_public_id,
                    position=position,
                    caption=caption,
                )
            )
            position += 1
    
    # Build videos list
    videos = []
    if video_public_ids:
        for video_public_id in video_public_ids:
            videos.append(
                AlbumVideoCreate(
                    video_public_id=video_public_id,
                    position=position,
                )
            )
            position += 1
    
    # Create payload
    payload = AlbumCreate(
        title=title,
        slug=slug,
        description=description,
        status=status,
        cover_asset_public_id=cover_asset_public_id,
        items=items if items else None,
        videos=videos if videos else None,
    )
    
    # Create album
    return album_service.create_album(db, payload, user=current_user)


@router.put("/{album_id}", response_model=AlbumOut)
def update_album(
    album_id: int,
    payload: AlbumUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumOut:
    """
    Cập nhật album.
    
    **Lưu ý:**
    - Để cập nhật items/videos, dùng endpoints riêng (sẽ implement sau)
    - Endpoint này chỉ cập nhật metadata (title, description, status, cover)
    """
    return album_service.update_album(db, album_id, payload, user=current_user)


@router.delete(
    "/{album_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_album(
    album_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Xóa album (soft delete).
    """
    album_service.delete_album(db, album_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/slug/check", response_model=SlugCheckOut)
def check_slug(
    slug: str = Query(..., description="Slug cần kiểm tra"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SlugCheckOut:
    """
    Kiểm tra slug có unique không.
    """
    return album_service.check_slug(db, slug)

