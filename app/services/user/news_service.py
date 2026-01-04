from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus, PostType
from app.models.tables import Asset, Post, PostAsset
from app.schemas.asset import PublicAssetOut, PublicPostAssetOut
from app.schemas.news import NewsListMeta, PublicNewsListOut, PublicNewsOut


def _to_public_news_out(db: Session, post: Post) -> PublicNewsOut:
    """Convert Post → PublicNewsOut, chỉ trả về public_id, không có id và status."""
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
            PublicPostAssetOut(
                position=pa.position,
                caption=pa.caption,
                asset=PublicAssetOut(
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
    
    return PublicNewsOut(
        public_id=post.public_id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content_html=post.content_html,
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        content_assets=content_assets if content_assets else None,
        published_at=post.published_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def list_news(
    db: Session,
    *,
    page: int,
    page_size: int,
    q: Optional[str],
) -> PublicNewsListOut:
    """
    List tin tức công khai - chỉ trả về published posts.
    Hỗ trợ search và pagination.
    """
    base_stmt = select(Post).where(
        Post.post_type == PostType.NEWS,
        Post.status == ContentStatus.PUBLISHED,
        Post.deleted_at.is_(None),
    )
    count_stmt = select(func.count(Post.id)).where(
        Post.post_type == PostType.NEWS,
        Post.status == ContentStatus.PUBLISHED,
        Post.deleted_at.is_(None),
    )

    if q:
        ilike = f"%{q}%"
        base_stmt = base_stmt.where(
            (Post.title.ilike(ilike)) | (Post.slug.ilike(ilike)) | (Post.excerpt.ilike(ilike))
        )
        count_stmt = count_stmt.where(
            (Post.title.ilike(ilike)) | (Post.slug.ilike(ilike)) | (Post.excerpt.ilike(ilike))
        )

    # Sắp xếp theo published_at (mới nhất trước)
    base_stmt = base_stmt.order_by(
        Post.published_at.desc().nullslast(), Post.created_at.desc()
    )

    total_items = db.scalar(count_stmt) or 0
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0

    rows = db.scalars(
        base_stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        _to_public_news_out(db, row)
        for row in rows
    ]

    meta = NewsListMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    return PublicNewsListOut(items=items, meta=meta)


def get_news_by_slug(db: Session, slug: str) -> PublicNewsOut:
    """
    Lấy chi tiết tin tức công khai theo slug - chỉ trả về published posts.
    """
    stmt = (
        select(Post)
        .where(
            Post.post_type == PostType.NEWS,
            Post.status == ContentStatus.PUBLISHED,
            Post.slug == slug,
            Post.deleted_at.is_(None),
        )
    )
    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "news_not_found", "message": "Tin tức không tồn tại hoặc chưa được xuất bản."},
        )
    return _to_public_news_out(db, post)

