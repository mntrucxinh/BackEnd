"""
Service xử lý Media (images và videos) từ albums cho public API.
Chỉ lấy những ảnh và video được upload trong các album published.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, distinct
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus
from app.models.tables import Album, AlbumItem, AlbumVideo, Asset, VideoEmbed
from app.schemas.asset import AssetListMeta, PublicAssetListOut, PublicAssetOut


def list_images_from_albums(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
) -> PublicAssetListOut:
    """
    Lấy danh sách ảnh từ các album published.
    Chỉ lấy những ảnh được upload trong album (không lấy cover).
    """
    # Query để lấy asset_ids từ AlbumItem của các album published
    subquery = (
        select(AlbumItem.asset_id)
        .join(Album, AlbumItem.album_id == Album.id)
        .where(
            Album.deleted_at.is_(None),
            Album.status == ContentStatus.PUBLISHED,
        )
        .distinct()
    )
    
    # Base query cho assets
    stmt = (
        select(Asset)
        .where(
            Asset.deleted_at.is_(None),
            Asset.id.in_(subquery),
            Asset.mime_type.startswith("image/"),
        )
    )
    
    # Search
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
        PublicAssetOut(
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
    
    return PublicAssetListOut(
        items=items,
        meta=AssetListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


def list_videos_from_albums(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
) -> PublicAssetListOut:
    """
    Lấy danh sách videos từ các album published.
    Chỉ lấy local videos (từ Asset), không lấy external videos (YouTube, Facebook).
    """
    # Lấy VideoEmbed IDs từ AlbumVideo của các album published
    video_embed_subquery = (
        select(AlbumVideo.video_id)
        .join(Album, AlbumVideo.album_id == Album.id)
        .where(
            Album.deleted_at.is_(None),
            Album.status == ContentStatus.PUBLISHED,
        )
        .distinct()
    )
    
    # Lấy VideoEmbeds
    video_embed_ids = db.scalars(video_embed_subquery).all()
    video_embeds = []
    if video_embed_ids:
        video_embeds = db.scalars(
            select(VideoEmbed).where(VideoEmbed.id.in_(video_embed_ids))
        ).all()
    
    # Lọc local videos (provider=LOCAL)
    from app.models.enums import EmbedProvider
    local_video_embeds = [ve for ve in video_embeds if ve.provider == EmbedProvider.LOCAL]
    
    # Lấy URLs từ local VideoEmbeds
    local_video_urls = [ve.url for ve in local_video_embeds if ve.url]
    
    if not local_video_urls:
        # Không có local videos
        return PublicAssetListOut(
            items=[],
            meta=AssetListMeta(
                page=page,
                page_size=page_size,
                total_items=0,
                total_pages=0,
            ),
        )
    
    # Query Assets cho local videos (match theo url)
    stmt = (
        select(Asset)
        .where(
            Asset.deleted_at.is_(None),
            Asset.mime_type.startswith("video/"),
            Asset.url.in_(local_video_urls),
        )
    )
    
    # Search
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
        PublicAssetOut(
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
    
    return PublicAssetListOut(
        items=items,
        meta=AssetListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )

