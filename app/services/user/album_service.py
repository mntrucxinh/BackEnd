"""
Service xử lý Album cho public API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus
from app.models.tables import Album, AlbumItem, AlbumVideo, Asset, VideoEmbed
from app.schemas.album import (
    AlbumListMeta,
    PublicAlbumItemOut,
    PublicAlbumListOut,
    PublicAlbumOut,
    PublicAlbumVideoOut,
)
from app.schemas.asset import PublicAssetOut


def _to_public_album_out(db: Session, album: Album) -> PublicAlbumOut:
    """Convert Album → PublicAlbumOut (chỉ trả về public_id, không có id nội bộ)."""
    # Load items và videos
    items = db.scalars(
        select(AlbumItem)
        .where(AlbumItem.album_id == album.id)
        .order_by(AlbumItem.position)
    ).all()
    
    videos = db.scalars(
        select(AlbumVideo)
        .where(AlbumVideo.album_id == album.id)
        .order_by(AlbumVideo.position)
    ).all()
    
    # Load assets
    asset_ids = [item.asset_id for item in items]
    assets = {}
    if asset_ids:
        assets = {
            asset.id: asset
            for asset in db.scalars(
                select(Asset).where(
                    Asset.id.in_(asset_ids),
                    Asset.deleted_at.is_(None),
                )
            ).all()
        }
    
    # Load videos
    video_ids = [video.video_id for video in videos]
    video_embeds = {}
    if video_ids:
        video_embeds = {
            video.id: video
            for video in db.scalars(
                select(VideoEmbed).where(VideoEmbed.id.in_(video_ids))
            ).all()
        }
    
    # Build items
    album_items = []
    for item in items:
        asset = assets.get(item.asset_id)
        if asset:
            album_items.append(
                PublicAlbumItemOut(
                    position=item.position,
                    caption=item.caption,
                    asset=PublicAssetOut(
                        public_id=asset.public_id,
                        url=asset.url or "",
                        mime_type=asset.mime_type,
                        byte_size=asset.byte_size,
                        width=asset.width,
                        height=asset.height,
                    ),
                )
            )
    
    # Build videos
    album_videos = []
    for video in videos:
        video_embed = video_embeds.get(video.video_id)
        if video_embed:
            album_videos.append(
                PublicAlbumVideoOut(
                    position=video.position,
                    video={
                        "public_id": str(video_embed.public_id),
                        "provider": video_embed.provider.value,
                        "url": video_embed.url,
                        "title": video_embed.title,
                        "thumbnail_url": video_embed.thumbnail_url,
                    },
                )
            )
    
    # Load cover asset
    cover = None
    if album.cover_asset_id:
        cover_asset = db.scalar(
            select(Asset).where(
                Asset.id == album.cover_asset_id,
                Asset.deleted_at.is_(None),
            )
        )
        if cover_asset:
            cover = PublicAssetOut(
                public_id=cover_asset.public_id,
                url=cover_asset.url or "",
                mime_type=cover_asset.mime_type,
                byte_size=cover_asset.byte_size,
                width=cover_asset.width,
                height=cover_asset.height,
            )
    
    return PublicAlbumOut(
        public_id=album.public_id,
        title=album.title,
        slug=album.slug,
        description=album.description,
        cover=cover,
        items=album_items if album_items else None,
        videos=album_videos if album_videos else None,
        item_count=len(items) + len(videos),
        image_count=len(items),
        video_count=len(videos),
        created_at=album.created_at,
        updated_at=album.updated_at,
    )


def list_albums(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
) -> PublicAlbumListOut:
    """Lấy danh sách albums công khai (chỉ published)."""
    # Base query - chỉ lấy published
    stmt = select(Album).where(
        Album.deleted_at.is_(None),
        Album.status == ContentStatus.PUBLISHED,
    )
    
    # Search
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            (Album.title.ilike(search_term))
            | (Album.slug.ilike(search_term))
            | (Album.description.ilike(search_term))
        )
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = db.scalar(count_stmt)
    
    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Album.created_at.desc()).offset(offset).limit(page_size)
    
    albums = db.scalars(stmt).all()
    
    # Convert to output
    items = [_to_public_album_out(db, album) for album in albums]
    
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
    
    return PublicAlbumListOut(
        items=items,
        meta=AlbumListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


def get_album_by_slug(db: Session, slug: str) -> PublicAlbumOut:
    """Lấy chi tiết album công khai theo slug (chỉ published)."""
    album = db.scalar(
        select(Album).where(
            Album.slug == slug,
            Album.deleted_at.is_(None),
            Album.status == ContentStatus.PUBLISHED,
        )
    )
    
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "album_not_found", "message": "Album không tồn tại hoặc chưa được xuất bản."},
        )
    
    return _to_public_album_out(db, album)

