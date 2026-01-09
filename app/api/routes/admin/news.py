from __future__ import annotations

import logging
from typing import List, Optional

from enum import Enum
from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import ContentStatus
from app.models.tables import User
from app.schemas.news import (
    NewsCreate,
    NewsListOut,
    NewsOut,
    NewsUpdate,
    SlugCheckOut,
)
from app.services import asset_service
from app.services.admin import news_service

logger = logging.getLogger(__name__)


class SortBy(str, Enum):
    """Các field có thể sort."""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PUBLISHED_AT = "published_at"
    TITLE = "title"
    STATUS = "status"
    CONTENT_HTML = "content_html"


class SortOrder(str, Enum):
    """Thứ tự sort."""
    ASC = "asc"
    DESC = "desc"


router = APIRouter(prefix="/admin/news", tags=["Admin - News"])


async def parse_files_from_request(request: Request) -> tuple[Optional[List[UploadFile]], bool]:
    """
    Parse files từ request thủ công để xử lý trường hợp client gửi string rỗng.
    
    Returns:
        (files_list, has_files_field)
        - files_list: List UploadFile nếu có, None nếu không có files hợp lệ
        - has_files_field: True nếu client có gửi field "files" (kể cả rỗng), False nếu không gửi
    """
    try:
        # Chỉ parse nếu là multipart/form-data
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return None, False
        
        # Parse form data
        form = await request.form()
        
        # Kiểm tra xem có field "files" không
        has_files_field = "files" in form
        
        # Lấy tất cả files với key "files"
        files_list = form.getlist("files")
        
        if not files_list:
            # Nếu có field nhưng rỗng → trả về (None, True) để xóa hết
            # Nếu không có field → trả về (None, False) để giữ nguyên
            return None, has_files_field
        
        # Filter chỉ lấy UploadFile objects, bỏ qua strings
        valid_files = []
        for item in files_list:
            # Nếu là UploadFile object → thêm vào
            if isinstance(item, (UploadFile, StarletteUploadFile)):
                valid_files.append(item)
            # Nếu là string (rỗng hoặc không) → bỏ qua nhưng vẫn đánh dấu là có field
            elif isinstance(item, str):
                # Có field nhưng là string rỗng → vẫn đánh dấu has_files_field = True
                continue
            else:
                # Trường hợp khác → bỏ qua
                continue
        
        # Nếu có valid files → trả về files
        # Nếu không có valid files nhưng có field "files" → trả về (None, True) để xóa hết
        return (valid_files if valid_files else None), has_files_field
    except Exception as e:
        # Nếu có lỗi khi parse → log và trả về None, False (giữ nguyên)
        logger.warning(
            "Error parsing files from request",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        return None, False




@router.get("", response_model=NewsListOut)
def list_news(
    *,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ContentStatus] = Query(
        None,
        alias="status",
        description="Lọc theo trạng thái: draft/published/archived. Bỏ trống = tất cả.",
    ),
    q: Optional[str] = Query(
        None,
        description="Từ khoá tìm kiếm theo tiêu đề/slug (ILIKE).",
    ),
    sort_by: SortBy = Query(
        SortBy.PUBLISHED_AT,
        description="Field để sort: created_at, updated_at, published_at, title, status, content_html.",
    ),
    sort_order: SortOrder = Query(
        SortOrder.DESC,
        description="Thứ tự sort: asc (tăng dần) hoặc desc (giảm dần).",
    ),
) -> NewsListOut:
    return news_service.list_news(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        q=q,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
    )


@router.get("/{news_id}", response_model=NewsOut)
def get_news_detail(
    news_id: int,
    db: Session = Depends(get_db),
) -> NewsOut:
    return news_service.get_news_detail(db, news_id)


@router.post("", response_model=NewsOut, status_code=status.HTTP_201_CREATED)
async def create_news(
    # Text fields
    title: str = Form(..., description="Tiêu đề bài viết"),
    excerpt: Optional[str] = Form(None, description="Mô tả ngắn"),
    content_html: str = Form(..., description="Nội dung HTML"),
    status: ContentStatus = Form(ContentStatus.DRAFT, description="Trạng thái: draft/published/archived"),
    publish_to_facebook: bool = Form(True, description="Có đăng lên Facebook hay không (chỉ áp dụng khi status = PUBLISHED)"),
    
    # Files - upload tất cả, hiển thị theo thứ tự
    files: Optional[List[UploadFile]] = File(
        None,
        description="Danh sách files (ảnh/video) - tất cả sẽ được hiển thị trong content theo thứ tự upload"
    ),
    
    # Meta
    meta_title: Optional[str] = Form(None, description="SEO title"),
    meta_description: Optional[str] = Form(None, description="SEO description"),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NewsOut:
    """
    Tạo bài viết - upload files trực tiếp, hiển thị theo thứ tự.
    
    **Luồng:**
    1. Upload tất cả files → tạo Assets
    2. Tất cả files đều được lưu vào content_assets theo thứ tự upload
    3. Tạo Post (slug tự động sinh từ title)
    4. Tự động đăng Facebook nếu publish (ảnh hoặc video)
    
    **Slug:**
    - Slug tự động sinh từ title, không cần truyền vào
    
    **Files:**
    - Upload gì → hiển thị cái đó trong content
    - Không phân biệt cover/video/content
    - Tất cả đều hiển thị theo thứ tự upload (chọn trước → hiển thị trước)
    - Ảnh lưu vào /uploads/images/YYYY/MM/
    - Video lưu vào /uploads/videos/YYYY/MM/
    """
    user_id = current_user.id
    
    # Upload tất cả files theo thứ tự
    content_asset_ids = []
    
    if files:
        for file in files:
            asset = await asset_service.upload_asset(db, file, user_id)
            content_asset_ids.append(asset.public_id)
    
    # Tạo payload - slug sẽ tự động sinh từ title trong service
    payload = NewsCreate(
        title=title,
        excerpt=excerpt,
        content_html=content_html,
        status=status,
        publish_to_facebook=publish_to_facebook,
        slug=None,  # Luôn None để tự động sinh từ title
        content_asset_public_ids=content_asset_ids if content_asset_ids else None,
        meta_title=meta_title,
        meta_description=meta_description,
    )
    
    # Tạo bài viết
    return news_service.create_news(db, payload, user=current_user)


@router.put("/{news_id}", response_model=NewsOut)
async def update_news(
    news_id: int,
    *,
    request: Request,  # Parse request để lấy files thủ công
    # Text fields - tất cả đều Optional để có thể update từng phần
    title: Optional[str] = Form(None, description="Tiêu đề bài viết (slug sẽ tự động tạo từ title)"),
    excerpt: Optional[str] = Form(None, description="Mô tả ngắn"),
    content_html: Optional[str] = Form(None, description="Nội dung HTML"),
    status: Optional[ContentStatus] = Form(None, description="Trạng thái: draft/published/archived"),
    publish_to_facebook: Optional[bool] = Form(None, description="Có đăng lên Facebook hay không (chỉ áp dụng khi status = PUBLISHED). Set null để giữ nguyên."),
    # Meta
    meta_title: Optional[str] = Form(None, description="SEO title"),
    meta_description: Optional[str] = Form(None, description="SEO description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NewsOut:
    """
    Cập nhật bài viết - upload files trực tiếp, hiển thị theo thứ tự.
    
    **QUAN TRỌNG:**
    - Phải gửi request với Content-Type: multipart/form-data (KHÔNG phải application/json)
    - Sử dụng FormData trong JavaScript hoặc multipart/form-data trong HTML form
    
    **Luồng:**
    1. Nếu có files → upload tất cả files → tạo Assets mới
    2. Nếu có files → thay thế toàn bộ content_assets cũ bằng files mới
    3. Cập nhật các field khác (title, content_html, status, etc.)
    4. Tự động đăng/xóa Facebook dựa trên status và publish_to_facebook
    
    **Lưu ý:**
    - Tất cả fields đều Optional → chỉ update những field được truyền vào
    - Nếu không truyền field nào → giữ nguyên giá trị cũ
    - Nếu truyền files → thay thế toàn bộ content_assets cũ
    - Nếu không truyền files → giữ nguyên content_assets cũ
    
    **Ví dụ JavaScript:**
    ```javascript
    const formData = new FormData();
    formData.append("title", "Tiêu đề mới");
    formData.append("content_html", "<p>Nội dung</p>");
    formData.append("files", file1);
    formData.append("files", file2);
    
    fetch("/admin/news/123", {
      method: "PUT",
      body: formData
    });
    ```
    """
    user_id = current_user.id
    
    # Parse files từ request thủ công (để xử lý trường hợp string rỗng)
    files, has_files_field = await parse_files_from_request(request)
    
    # Xử lý content_asset_ids:
    # - Nếu có files hợp lệ → upload và set content_asset_ids
    # - Nếu không có files nhưng có field "files" (rỗng) → set content_asset_ids = [] (xóa hết)
    # - Nếu không có field "files" → set content_asset_ids = None (giữ nguyên)
    content_asset_ids = None
    if files:
        # Có files hợp lệ → upload
        content_asset_ids = []
        for file in files:
            asset = await asset_service.upload_asset(db, file, user_id)
            content_asset_ids.append(asset.public_id)
    elif has_files_field:
        # Có field "files" nhưng rỗng → xóa hết content_assets
        content_asset_ids = []
    
    # Tạo payload - chỉ set những field được truyền vào
    # Slug sẽ tự động tạo từ title trong service (giống create_news)
    payload = NewsUpdate(
        title=title,
        excerpt=excerpt,
        content_html=content_html,
        status=status,
        publish_to_facebook=publish_to_facebook,
        slug=None,  # Luôn None để tự động tạo từ title (giống create_news)
        content_asset_public_ids=content_asset_ids,  # None = giữ nguyên, [] = xóa hết, [ids] = thay thế
        meta_title=meta_title,
        meta_description=meta_description,
    )
    
    # Cập nhật bài viết
    return news_service.update_news(db, news_id, payload, user=current_user)


@router.delete(
    "/{news_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_news(
    news_id: int,
    db: Session = Depends(get_db),
) -> Response:
    news_service.delete_news(db, news_id)
    # Trả về 204 No Content, không body (đúng chuẩn HTTP và FastAPI)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/slug/check", response_model=SlugCheckOut)
def check_slug_unique(
    title: str = Query(..., min_length=1),
    slug: Optional[str] = Query(
        None,
        description="Nếu truyền slug, API sẽ normalize và check; nếu không sẽ sinh từ title.",
    ),
    db: Session = Depends(get_db),
) -> SlugCheckOut:
    return news_service.check_slug_unique(db, title=title, slug=slug)

