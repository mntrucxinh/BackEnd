from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import ContentStatus
from app.schemas.news import (
    NewsCreate,
    NewsListOut,
    NewsOut,
    NewsUpdate,
    SlugCheckOut,
)
from app.services import asset_service
from app.services.admin import news_service


router = APIRouter(prefix="/admin/news", tags=["Admin - News"])


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
) -> NewsListOut:
    return news_service.list_news(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        q=q,
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
    
    # Files - upload tất cả, hiển thị theo thứ tự
    files: Optional[List[UploadFile]] = File(
        None,
        description="Danh sách files (ảnh/video) - tất cả sẽ được hiển thị trong content theo thứ tự upload"
    ),
    
    # Meta
    meta_title: Optional[str] = Form(None, description="SEO title"),
    meta_description: Optional[str] = Form(None, description="SEO description"),
    
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # Uncomment khi có auth
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
    # TODO: Uncomment khi có auth
    # user_id = current_user.id
    user_id = None  # Tạm thời
    
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
        slug=None,  # Luôn None để tự động sinh từ title
        content_asset_public_ids=content_asset_ids if content_asset_ids else None,
        meta_title=meta_title,
        meta_description=meta_description,
    )
    
    # Tạo bài viết
    return news_service.create_news(db, payload)


@router.put("/{news_id}", response_model=NewsOut)
def update_news(
    news_id: int,
    payload: NewsUpdate,
    db: Session = Depends(get_db),
) -> NewsOut:
    return news_service.update_news(db, news_id, payload)


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

