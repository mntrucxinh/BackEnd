from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus, PostType
from app.models.tables import Asset, Post, PostAsset, PostRevision
from app.schemas.asset import AssetOut, PostAssetOut
from app.schemas.news import (
    NewsCreate,
    NewsListMeta,
    NewsListOut,
    NewsOut,
    NewsUpdate,
    SlugCheckOut,
)
from app.services.facebook_service import (
    upload_images_to_facebook,
    upload_video_to_facebook,
)
from app.utils.text import slugify

logger = logging.getLogger(__name__)


def _get_news_or_404(db: Session, news_id: int) -> Post:
    stmt = (
        select(Post)
        .where(
            Post.id == news_id,
            Post.post_type == PostType.NEWS,
            Post.deleted_at.is_(None),
        )
    )
    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "news_not_found", "message": "Tin tức không tồn tại."},
        )
    return post


def _resolve_asset_ids(
    db: Session, asset_public_ids: Optional[list[UUID]]
) -> list[int]:
    """Resolve danh sách public_id → asset_id."""
    if not asset_public_ids:
        return []
    
    assets = db.scalars(
        select(Asset).where(
            Asset.public_id.in_(asset_public_ids),
            Asset.deleted_at.is_(None),
        )
    ).all()
    
    # Validate tất cả public_id đều tồn tại
    found_public_ids = {asset.public_id for asset in assets}
    missing = set(asset_public_ids) - found_public_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_asset",
                "message": f"Asset không tồn tại hoặc đã bị xoá: {list(missing)}",
            },
        )
    
    # Tạo dict để giữ thứ tự
    asset_map = {asset.public_id: asset.id for asset in assets}
    return [asset_map[pid] for pid in asset_public_ids]


def _ensure_unique_slug(
    db: Session, slug: str, *, exclude_post_id: Optional[int] = None
) -> None:
    stmt = select(Post.id).where(
        Post.post_type == PostType.NEWS,
        Post.slug == slug,
        Post.deleted_at.is_(None),
    )
    if exclude_post_id is not None:
        stmt = stmt.where(Post.id != exclude_post_id)

    exists = db.scalar(stmt)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "slug_conflict",
                "message": "Slug đã được sử dụng cho một tin tức khác.",
            },
        )


def _to_news_out(db: Session, post: Post) -> NewsOut:
    """Convert Post → NewsOut, join Asset để lấy public_id và content_assets."""
    # Load content_assets với join để tránh N+1 query
    post_assets = db.scalars(
        select(PostAsset)
        .where(PostAsset.post_id == post.id)
        .order_by(PostAsset.position)
    ).all()
    
    if not post_assets:
        content_assets = []
    else:
        # Query tất cả assets một lần để tránh N+1
        asset_ids = [pa.asset_id for pa in post_assets]
        assets = {
            asset.id: asset
            for asset in db.scalars(
                select(Asset).where(
                    Asset.id.in_(asset_ids),
                    Asset.deleted_at.is_(None),
                )
            ).all()
        }
        
        content_assets = [
            PostAssetOut(
                position=pa.position,
                caption=pa.caption,
                asset=AssetOut(
                    id=asset.id,
                    public_id=asset.public_id,
                    url=asset.url or "",
                    mime_type=asset.mime_type,
                    byte_size=asset.byte_size,
                    width=asset.width,
                    height=asset.height,
                ),
            )
            for pa in post_assets
            if (asset := assets.get(pa.asset_id))
        ]
    
    return NewsOut(
        id=post.id,
        public_id=post.public_id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content_html=post.content_html,
        status=post.status,
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        content_assets=content_assets if content_assets else None,
        published_at=post.published_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _publish_to_facebook(
    db: Session,
    post: Post,
    content_asset_public_ids: Optional[list[UUID]],
) -> None:
    """
    Đăng bài viết lên Facebook khi publish.
    
    Logic:
    - Có video → chỉ đăng video (bỏ qua ảnh)
    - Không có video nhưng có ảnh → đăng ảnh
    - Không có cả 2 → đăng text
    
    Args:
        db: Database session
        post: Post object đã được tạo/cập nhật
        content_asset_public_ids: Danh sách public_id của content assets
    """
    post_url = f"{os.getenv('APP_BASE_URL', 'https://your-site.com')}/news/{post.slug}"
    
    log_context = {
        "post_id": post.id,
        "post_slug": post.slug,
        "post_title": post.title,
    }
    
    try:
        logger.info(
            "Starting Facebook publish",
            extra={**log_context, "action": "facebook_publish_start"}
        )
        
        # Lấy content assets
        all_assets = []
        if content_asset_public_ids:
            all_assets = db.scalars(
                select(Asset).where(Asset.public_id.in_(content_asset_public_ids))
            ).all()
        
        # Phân loại ảnh và video
        fb_images = [
            asset for asset in all_assets 
            if asset and asset.mime_type.startswith("image/")
        ]
        fb_video = next(
            (asset for asset in all_assets if asset and asset.mime_type.startswith("video/")),
            None,
        )
        
        logger.debug(
            "Assets classified for Facebook",
            extra={
                **log_context,
                "total_assets": len(all_assets),
                "image_count": len(fb_images),
                "has_video": fb_video is not None,
            }
        )
        
        if fb_video:
            # Có video → chỉ đăng video (bỏ qua ảnh)
            logger.info(
                "Publishing video to Facebook",
                extra={**log_context, "video_asset_id": fb_video.id, "media_type": "video"}
            )
            fb_post_id = upload_video_to_facebook(post, fb_video, post_url)
            logger.info(
                "Video published to Facebook successfully",
                extra={**log_context, "facebook_post_id": fb_post_id, "media_type": "video"}
            )
        elif fb_images:
            # Có ảnh → upload ảnh lên Facebook
            logger.info(
                "Publishing images to Facebook",
                extra={**log_context, "image_count": len(fb_images), "media_type": "images"}
            )
            fb_post_id = upload_images_to_facebook(
                post=post,
                post_url=post_url,
                content_assets=fb_images,
            )
            logger.info(
                "Images published to Facebook successfully",
                extra={**log_context, "facebook_post_id": fb_post_id, "media_type": "images"}
            )
        else:
            # Chỉ có text → đăng text
            logger.info(
                "Publishing text-only post to Facebook",
                extra={**log_context, "media_type": "text"}
            )
            fb_post_id = upload_images_to_facebook(
                post=post,
                post_url=post_url,
                content_assets=[],
            )
            logger.info(
                "Text post published to Facebook successfully",
                extra={**log_context, "facebook_post_id": fb_post_id, "media_type": "text"}
            )
            
    except Exception as e:
        # Rollback transaction nếu Facebook fail
        db.rollback()
        logger.error(
            "Failed to publish post to Facebook",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "facebook_post_failed",
                "message": f"Đăng bài lên Facebook thất bại: {str(e)}",
            },
        )


def list_news(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: Optional[ContentStatus],
    q: Optional[str],
) -> NewsListOut:
    base_stmt = select(Post).where(
        Post.post_type == PostType.NEWS,
        Post.deleted_at.is_(None),
    )
    count_stmt = select(func.count(Post.id)).where(
        Post.post_type == PostType.NEWS,
        Post.deleted_at.is_(None),
    )

    if status_filter is not None:
        base_stmt = base_stmt.where(Post.status == status_filter)
        count_stmt = count_stmt.where(Post.status == status_filter)

    if q:
        ilike = f"%{q}%"
        base_stmt = base_stmt.where(
            (Post.title.ilike(ilike)) | (Post.slug.ilike(ilike))
        )
        count_stmt = count_stmt.where(
            (Post.title.ilike(ilike)) | (Post.slug.ilike(ilike))
        )

    base_stmt = base_stmt.order_by(
        Post.published_at.desc().nullslast(), Post.created_at.desc()
    )

    total_items = db.scalar(count_stmt) or 0
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0

    rows = db.scalars(
        base_stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        _to_news_out(db, row)
        for row in rows
    ]

    meta = NewsListMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    return NewsListOut(items=items, meta=meta)


def get_news_detail(db: Session, news_id: int) -> NewsOut:
    post = _get_news_or_404(db, news_id)
    return _to_news_out(db, post)


def create_news(db: Session, payload: NewsCreate) -> NewsOut:
    """Tạo bài viết mới."""
    logger.info(
        "Creating new news post",
        extra={"action": "create_news", "title": payload.title, "status": payload.status.value}
    )
    
    slug = payload.slug or slugify(payload.title)
    if not slug:
        logger.warning("Failed to generate slug from title", extra={"title": payload.title})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_slug",
                "message": "Không thể sinh slug hợp lệ từ tiêu đề.",
            },
        )

    _ensure_unique_slug(db, slug)

    now = datetime.now(timezone.utc)
    published_at = now if payload.status == ContentStatus.PUBLISHED else None

    post = Post(
        post_type=PostType.NEWS,
        status=payload.status,
        title=payload.title,
        slug=slug,
        excerpt=payload.excerpt,
        content_html=payload.content_html,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        published_at=published_at,
    )
    db.add(post)
    db.flush()

    logger.debug(
        "Post created, adding assets",
        extra={"post_id": post.id, "asset_count": len(payload.content_asset_public_ids or [])}
    )

    # Lưu content_assets
    if payload.content_asset_public_ids:
        asset_ids = _resolve_asset_ids(db, payload.content_asset_public_ids)
        for position, asset_id in enumerate(asset_ids):
            post_asset = PostAsset(
                post_id=post.id,
                asset_id=asset_id,
                position=position,
            )
            db.add(post_asset)

    revision = PostRevision(
        post_id=post.id,
        editor_id=None,
        title=post.title,
        excerpt=post.excerpt,
        content_html=post.content_html,
    )
    db.add(revision)

    # Tự động đăng Facebook khi publish
    if payload.status == ContentStatus.PUBLISHED:
        _publish_to_facebook(db, post, payload.content_asset_public_ids)

    db.commit()
    db.refresh(post)
    
    logger.info(
        "News post created successfully",
        extra={"post_id": post.id, "slug": post.slug, "status": post.status.value}
    )
    
    return _to_news_out(db, post)


def update_news(db: Session, news_id: int, payload: NewsUpdate) -> NewsOut:
    """Cập nhật bài viết."""
    logger.info("Updating news post", extra={"action": "update_news", "news_id": news_id})
    
    post = _get_news_or_404(db, news_id)

    if payload.title is not None:
        post.title = payload.title

    if payload.slug is not None:
        new_slug = payload.slug or slugify(post.title)
        if not new_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_slug",
                    "message": "Không thể sinh slug hợp lệ từ tiêu đề.",
                },
            )
        _ensure_unique_slug(db, new_slug, exclude_post_id=post.id)
        post.slug = new_slug

    if payload.excerpt is not None:
        post.excerpt = payload.excerpt
    if payload.content_html is not None:
        post.content_html = payload.content_html
    if payload.meta_title is not None:
        post.meta_title = payload.meta_title
    if payload.meta_description is not None:
        post.meta_description = payload.meta_description

    # Xử lý content_assets: xóa cũ, thêm mới
    if payload.content_asset_public_ids is not None:
        # Xóa tất cả post_assets cũ
        db.execute(delete(PostAsset).where(PostAsset.post_id == post.id))
        
        # Thêm mới theo thứ tự
        if payload.content_asset_public_ids:
            asset_ids = _resolve_asset_ids(db, payload.content_asset_public_ids)
            for position, asset_id in enumerate(asset_ids):
                post_asset = PostAsset(
                    post_id=post.id,
                    asset_id=asset_id,
                    position=position,
                )
                db.add(post_asset)

    if payload.status is not None:
        previous_status = post.status
        post.status = payload.status
        now = datetime.now(timezone.utc)
        
        if (
            previous_status != ContentStatus.PUBLISHED
            and payload.status == ContentStatus.PUBLISHED
        ):
            post.published_at = now
            
            # Tự động đăng Facebook khi publish
            # Lấy content_asset_public_ids từ PostAsset
            post_assets = db.scalars(
                select(PostAsset)
                .where(PostAsset.post_id == post.id)
                .order_by(PostAsset.position)
            ).all()
            
            if post_assets:
                asset_ids = [pa.asset_id for pa in post_assets]
                assets = db.scalars(
                    select(Asset).where(
                        Asset.id.in_(asset_ids),
                        Asset.deleted_at.is_(None),
                    )
                ).all()
                content_asset_public_ids = [asset.public_id for asset in assets]
            else:
                content_asset_public_ids = None
            
            _publish_to_facebook(db, post, content_asset_public_ids)
        elif (
            previous_status == ContentStatus.PUBLISHED
            and payload.status != ContentStatus.PUBLISHED
        ):
            post.published_at = None

    post.updated_at = datetime.now(timezone.utc)

    revision = PostRevision(
        post_id=post.id,
        editor_id=None,
        title=post.title,
        excerpt=post.excerpt,
        content_html=post.content_html,
    )
    db.add(revision)

    db.commit()
    db.refresh(post)
    
    logger.info(
        "News post updated successfully",
        extra={"post_id": post.id, "slug": post.slug, "status": post.status.value}
    )
    
    return _to_news_out(db, post)


def delete_news(db: Session, news_id: int) -> None:
    """Xóa bài viết (soft delete)."""
    logger.info("Deleting news post", extra={"action": "delete_news", "news_id": news_id})
    
    post = _get_news_or_404(db, news_id)
    post.deleted_at = datetime.now(timezone.utc)
    db.add(post)
    db.commit()
    
    logger.info("News post deleted successfully", extra={"post_id": post.id, "slug": post.slug})


def check_slug_unique(
    db: Session,
    *,
    title: str,
    slug: Optional[str],
) -> SlugCheckOut:
    normalized = slug or slugify(title)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_slug",
                "message": "Không thể sinh slug hợp lệ từ title/slug truyền vào.",
            },
        )

    stmt = select(Post.id).where(
        Post.post_type == PostType.NEWS,
        Post.slug == normalized,
        Post.deleted_at.is_(None),
    )
    exists = db.scalar(stmt)
    return SlugCheckOut(is_unique=not bool(exists), normalized_slug=normalized)


