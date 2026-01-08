from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import ContentStatus
from app.models.tables import User
from app.schemas.announcement import (
    AdminAnnouncementListOut,
    AdminAnnouncementOut,
    AnnouncementCreate,
    AnnouncementUpdate,
)
from app.services import asset_service
from app.services.admin import announcement_service

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/admin/announcements", tags=["Admin - Announcements"])


async def parse_files_from_request(request: Request) -> tuple[Optional[List[UploadFile]], bool]:
    """
    Parse files từ request thủ công để xử lý trường hợp client gửi string rỗng.

    Returns:
        (files_list, has_files_field)
        - files_list: List UploadFile nếu có, None nếu không có files hợp lệ
        - has_files_field: True nếu client có gửi field "files" (kể cả rỗng), False nếu không gửi
    """
    try:
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return None, False

        form = await request.form()

        has_files_field = "files" in form

        files_list = form.getlist("files")
        if not files_list:
            return None, has_files_field

        valid_files: list[UploadFile] = []
        for item in files_list:
            if isinstance(item, (UploadFile, StarletteUploadFile)):
                valid_files.append(item)
            elif isinstance(item, str):
                # String rỗng → bỏ qua nhưng vẫn coi là có field
                continue
            else:
                continue

        return (valid_files if valid_files else None), has_files_field
    except Exception as e:
        logger.warning(
            "Error parsing files from request (announcements)",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return None, False


@router.get("", response_model=AdminAnnouncementListOut)
def list_announcements(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ContentStatus] = Query(
        None,
        alias="status",
        description="Lọc theo trạng thái: draft/published/archived. Bỏ trống = tất cả.",
    ),
    grade: Optional[str] = Query(
        None,
        description="Lọc theo mã khối (bee/mouse/bear/dolphin). Bỏ trống để lấy tất cả.",
    ),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm theo tiêu đề/slug (ILIKE).",
    ),
) -> AdminAnnouncementListOut:
    return announcement_service.list_announcements(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        grade=grade,
        q=q,
    )


@router.get("/{announcement_id}", response_model=AdminAnnouncementOut)
def get_announcement_detail(
    announcement_id: int,
    db: Session = Depends(get_db),
) -> AdminAnnouncementOut:
    return announcement_service.get_announcement_detail(db, announcement_id)


@router.post("", response_model=AdminAnnouncementOut, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    # Text fields
    title: str = Form(..., description="Tiêu đề thông báo"),
    excerpt: Optional[str] = Form(None, description="Mô tả ngắn"),
    content_html: str = Form(..., description="Nội dung HTML"),
    status: ContentStatus = Form(
        ContentStatus.DRAFT, description="Trạng thái: draft/published/archived"
    ),
    publish_to_facebook: bool = Form(
        True,
        description="Có đăng lên Facebook hay không (chỉ áp dụng khi status = PUBLISHED)",
    ),
    block_code: str = Form(
        ...,
        description="Mã khối (bee/mouse/bear/dolphin) - bắt buộc.",
    ),
    # Files
    files: Optional[List[UploadFile]] = File(
        None,
        description="Danh sách files (ảnh/video) - tất cả sẽ được hiển thị trong content theo thứ tự upload",
    ),
    # Meta
    meta_title: Optional[str] = Form(None, description="SEO title"),
    meta_description: Optional[str] = Form(None, description="SEO description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminAnnouncementOut:
    """
    Tạo thông báo - bắt buộc chọn khối (bee/mouse/bear/dolphin), upload files trực tiếp.
    """
    user_id = current_user.id

    content_asset_ids: list[UUID] = []
    if files:
        for file in files:
            asset = await asset_service.upload_asset(db, file, user_id)
            content_asset_ids.append(asset.public_id)

    payload = AnnouncementCreate(
        title=title,
        excerpt=excerpt,
        content_html=content_html,
        status=status,
        publish_to_facebook=publish_to_facebook,
        slug=None,
        content_asset_public_ids=content_asset_ids if content_asset_ids else None,
        meta_title=meta_title,
        meta_description=meta_description,
        block_code=block_code,
    )

    return announcement_service.create_announcement(db, payload, user=current_user)


@router.put("/{announcement_id}", response_model=AdminAnnouncementOut)
async def update_announcement(
    announcement_id: int,
    *,
    request: Request,
    # Text fields (Optional)
    title: Optional[str] = Form(None, description="Tiêu đề thông báo"),
    excerpt: Optional[str] = Form(None, description="Mô tả ngắn"),
    content_html: Optional[str] = Form(None, description="Nội dung HTML"),
    status: Optional[ContentStatus] = Form(
        None, description="Trạng thái: draft/published/archived"
    ),
    publish_to_facebook: Optional[bool] = Form(
        None,
        description="Có đăng lên Facebook hay không (chỉ áp dụng khi status = PUBLISHED). Set null để giữ nguyên.",
    ),
    block_code: Optional[str] = Form(
        None,
        description="Mã khối mới (bee/mouse/bear/dolphin). Bỏ trống để giữ nguyên.",
    ),
    # Meta
    meta_title: Optional[str] = Form(None, description="SEO title"),
    meta_description: Optional[str] = Form(None, description="SEO description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminAnnouncementOut:
    """
    Cập nhật thông báo.

    - Nếu gửi field `files` rỗng → xoá hết content_assets.
    - Nếu không gửi field `files` → giữ nguyên content_assets.
    - Nếu gửi files mới → thay thế toàn bộ content_assets bằng files mới.
    """
    user_id = current_user.id

    files, has_files_field = await parse_files_from_request(request)

    content_asset_ids: Optional[list[UUID]] = None
    if files:
        content_asset_ids = []
        for file in files:
            asset = await asset_service.upload_asset(db, file, user_id)
            content_asset_ids.append(asset.public_id)
    elif has_files_field:
        # Có field "files" nhưng rỗng → xoá hết content_assets
        content_asset_ids = []

    payload = AnnouncementUpdate(
        title=title,
        excerpt=excerpt,
        content_html=content_html,
        status=status,
        publish_to_facebook=publish_to_facebook,
        slug=None,
        content_asset_public_ids=content_asset_ids,
        meta_title=meta_title,
        meta_description=meta_description,
        block_code=block_code,
    )

    return announcement_service.update_announcement(db, announcement_id, payload, user=current_user)


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
) -> Response:
    announcement_service.delete_announcement(db, announcement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



