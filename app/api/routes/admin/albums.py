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
    
    # Upload new files và phân biệt ảnh/video
    new_image_asset_public_ids = []
    new_video_public_ids = []
    if new_files:
        new_captions_list = new_captions or []
        for idx, file in enumerate(new_files):
            asset = await asset_service.upload_asset(db, file, user_id)
            caption = new_captions_list[idx] if idx < len(new_captions_list) else None
            
            # Phân biệt ảnh và video
            if asset.mime_type.startswith("video/"):
                # Video → tạo VideoEmbed
                from app.models.enums import EmbedProvider
                from app.models.tables import VideoEmbed
                
                video_embed = VideoEmbed(
                    provider=EmbedProvider.LOCAL,
                    url=asset.url or "",
                    title=file.filename or None,
                    created_by=user_id,
                )
                db.add(video_embed)
                db.flush()  # Flush để lấy public_id
                new_video_public_ids.append(video_embed.public_id)
            else:
                # Ảnh → thêm vào items
                new_image_asset_public_ids.append((asset.public_id, caption))
    
    # Build items list (chỉ ảnh)
    items = []
    position = 0
    
    # Add new image files
    for asset_public_id, caption in new_image_asset_public_ids:
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
    
    # Build videos list (từ new videos + existing videos)
    videos = []
    # Add new videos (từ upload)
    for video_public_id in new_video_public_ids:
        videos.append(
            AlbumVideoCreate(
                video_public_id=video_public_id,
                position=position,
            )
        )
        position += 1
    
    # Add existing videos
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
async def update_album(
    album_id: int,
    # Text fields - tất cả Optional
    title: Optional[str] = Form(None, description="Tên album"),
    description: Optional[str] = Form(None, description="Mô tả album"),
    status: Optional[ContentStatus] = Form(None, description="Trạng thái: draft/published/archived"),
    slug: Optional[str] = Form(None, description="Slug (nếu bỏ trống, tự động sinh từ title)"),
    # Cover
    cover_asset_public_id: Optional[UUID] = Form(
        None, description="Public ID của ảnh cover (nếu None, giữ nguyên)"
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
    Cập nhật album.
    
    **Workflow:**
    1. Upload new_files (nếu có) → tạo Assets mới
    2. Lấy existing_asset_public_ids (nếu có) → dùng assets có sẵn
    3. Lấy video_public_ids (nếu có) → thêm videos
    4. Merge tất cả theo thứ tự → tạo album_items và album_videos
    5. Set cover (nếu có)
    
    **Lưu ý:**
    - Nếu có new_files, existing_asset_public_ids, hoặc video_public_ids → thay thế toàn bộ items/videos
    - Nếu không có → giữ nguyên items/videos cũ
    - Tất cả fields đều Optional → chỉ update những field được truyền vào
    """
    user_id = current_user.id
    
    # Upload new files và phân biệt ảnh/video
    new_image_asset_public_ids = []
    new_video_public_ids = []
    if new_files:
        new_captions_list = new_captions or []
        for idx, file in enumerate(new_files):
            asset = await asset_service.upload_asset(db, file, user_id)
            caption = new_captions_list[idx] if idx < len(new_captions_list) else None
            
            # Phân biệt ảnh và video
            if asset.mime_type.startswith("video/"):
                # Video → tạo VideoEmbed
                from app.models.enums import EmbedProvider
                from app.models.tables import VideoEmbed
                
                video_embed = VideoEmbed(
                    provider=EmbedProvider.LOCAL,
                    url=asset.url or "",
                    title=file.filename or None,
                    created_by=user_id,
                )
                db.add(video_embed)
                db.flush()  # Flush để lấy public_id
                new_video_public_ids.append(video_embed.public_id)
            else:
                # Ảnh → thêm vào items
                new_image_asset_public_ids.append((asset.public_id, caption))
    
    # Build items list nếu có new image files hoặc existing_asset_public_ids
    # Logic: nếu có bất kỳ field nào → thay thế toàn bộ items
    items = None
    has_items_update = (new_image_asset_public_ids and len(new_image_asset_public_ids) > 0) or existing_asset_public_ids is not None
    if has_items_update:
        items = []
        position = 0
        
        # Add new image files trước
        for asset_public_id, caption in new_image_asset_public_ids:
            items.append(
                AlbumItemCreate(
                    asset_public_id=asset_public_id,
                    position=position,
                    caption=caption,
                )
            )
            position += 1
        
        # Add existing assets sau
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
    
    # Build videos list nếu có new videos hoặc video_public_ids
    videos = None
    has_videos_update = (new_video_public_ids and len(new_video_public_ids) > 0) or video_public_ids is not None
    if has_videos_update:
        videos = []
        position = 0
        # Nếu có items, position bắt đầu từ cuối items
        if items:
            position = len(items)
        
        # Add new videos trước
        for video_public_id in new_video_public_ids:
            videos.append(
                AlbumVideoCreate(
                    video_public_id=video_public_id,
                    position=position,
                )
            )
            position += 1
        
        # Add existing videos sau
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
    payload = AlbumUpdate(
        title=title,
        slug=slug,
        description=description,
        status=status,
        cover_asset_public_id=cover_asset_public_id,
        items=items,
        videos=videos,
    )
    
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

