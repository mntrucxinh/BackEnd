from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus, PostType
from app.models.tables import Asset, Block, Post, PostAsset
from app.schemas.announcement import (
    AnnouncementListMeta,
    PublicAnnouncementListOut,
    PublicAnnouncementOut,
)
from app.schemas.asset import PublicAssetOut, PublicPostAssetOut


def _to_public_announcement_out(db: Session, post: Post) -> PublicAnnouncementOut:
    """Convert Post → PublicAnnouncementOut, chỉ trả về public_id, không có id và status."""
    # Load block info
    block = None
    if post.block_id:
        block = db.scalar(select(Block).where(Block.id == post.block_id))
    
    if not block:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "missing_block", "message": "Thông báo không có khối."},
        )
    
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
    
    return PublicAnnouncementOut(
        public_id=post.public_id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content_html=post.content_html,
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        content_assets=content_assets if content_assets else None,
        block_code=block.code,
        block_name=block.name,
        published_at=post.published_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def list_announcements(
    db: Session,
    *,
    page: int,
    page_size: int,
    grade: Optional[str] = None,
) -> PublicAnnouncementListOut:
    """
    List thông báo công khai - chỉ trả về published posts.
    Có thể filter theo grade (block code).
    """
    base_stmt = (
        select(Post)
        .join(Block, Post.block_id == Block.id)
        .where(
            Post.post_type == PostType.ANNOUNCEMENT,
            Post.status == ContentStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            Block.is_active.is_(True),
        )
    )
    count_stmt = (
        select(func.count(Post.id))
        .join(Block, Post.block_id == Block.id)
        .where(
            Post.post_type == PostType.ANNOUNCEMENT,
            Post.status == ContentStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            Block.is_active.is_(True),
        )
    )

    if grade:
        base_stmt = base_stmt.where(Block.code == grade)
        count_stmt = count_stmt.where(Block.code == grade)

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
        _to_public_announcement_out(db, row)
        for row in rows
    ]

    meta = AnnouncementListMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    return PublicAnnouncementListOut(items=items, meta=meta)


def get_announcement_by_slug_or_id(
    db: Session, slug_or_id: str
) -> PublicAnnouncementOut:
    """
    Lấy chi tiết thông báo công khai theo slug hoặc public_id - chỉ trả về published posts.
    """
    # Thử parse như UUID trước
    try:
        public_id = UUID(slug_or_id)
        stmt = (
            select(Post)
            .join(Block, Post.block_id == Block.id)
            .where(
                Post.post_type == PostType.ANNOUNCEMENT,
                Post.status == ContentStatus.PUBLISHED,
                Post.public_id == public_id,
                Post.deleted_at.is_(None),
                Block.is_active.is_(True),
            )
        )
    except ValueError:
        # Không phải UUID, coi như slug
        stmt = (
            select(Post)
            .join(Block, Post.block_id == Block.id)
            .where(
                Post.post_type == PostType.ANNOUNCEMENT,
                Post.status == ContentStatus.PUBLISHED,
                Post.slug == slug_or_id,
                Post.deleted_at.is_(None),
                Block.is_active.is_(True),
            )
        )

    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "announcement_not_found",
                "message": "Thông báo không tồn tại hoặc chưa được xuất bản.",
            },
        )
    return _to_public_announcement_out(db, post)

