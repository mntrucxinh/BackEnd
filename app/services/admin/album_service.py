"""
Service xử lý Album cho admin API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus
from app.models.tables import Album, AlbumItem, AlbumVideo, Asset, User, VideoEmbed
from app.schemas.album import (
    AlbumCreate,
    AlbumItemOut,
    AlbumListMeta,
    AlbumListOut,
    AlbumOut,
    AlbumUpdate,
    AlbumVideoOut,
    SlugCheckOut,
)
from app.schemas.asset import AssetOut
from app.utils.text import slugify

logger = logging.getLogger(__name__)


def _get_album_or_404(db: Session, album_id: int) -> Album:
    """Lấy album theo ID, raise 404 nếu không tồn tại hoặc đã xóa."""
    stmt = select(Album).where(
        Album.id == album_id,
        Album.deleted_at.is_(None),
    )
    album = db.scalar(stmt)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "album_not_found", "message": "Album không tồn tại."},
        )
    return album


def _resolve_asset_ids(
    db: Session, asset_public_ids: Optional[list[UUID]]
) -> dict[UUID, int]:
    """Resolve danh sách public_id → {public_id: asset_id}."""
    if not asset_public_ids:
        return {}
    
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
    
    return {asset.public_id: asset.id for asset in assets}


def _resolve_video_ids(
    db: Session, video_public_ids: Optional[list[UUID]]
) -> dict[UUID, int]:
    """Resolve danh sách video public_id → {public_id: video_id}."""
    if not video_public_ids:
        return {}
    
    videos = db.scalars(
        select(VideoEmbed).where(VideoEmbed.public_id.in_(video_public_ids))
    ).all()
    
    # Validate tất cả public_id đều tồn tại
    found_public_ids = {video.public_id for video in videos}
    missing = set(video_public_ids) - found_public_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_video",
                "message": f"Video không tồn tại: {list(missing)}",
            },
        )
    
    return {video.public_id: video.id for video in videos}


def _ensure_unique_slug(
    db: Session, slug: str, *, exclude_album_id: Optional[int] = None
) -> None:
    """Kiểm tra slug có unique không, raise 409 nếu conflict."""
    stmt = select(Album.id).where(
        Album.slug == slug,
        Album.deleted_at.is_(None),
    )
    if exclude_album_id is not None:
        stmt = stmt.where(Album.id != exclude_album_id)

    exists = db.scalar(stmt)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "slug_conflict",
                "message": "Slug đã được sử dụng cho một album khác.",
            },
        )


def _to_album_out(db: Session, album: Album) -> AlbumOut:
    """Convert Album → AlbumOut, join Asset và VideoEmbed."""
    # Load items và videos với join để tránh N+1 query
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
                AlbumItemOut(
                    position=item.position,
                    caption=item.caption,
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
            )
    
    # Build videos
    album_videos = []
    for video in videos:
        video_embed = video_embeds.get(video.video_id)
        if video_embed:
            album_videos.append(
                AlbumVideoOut(
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
            cover = AssetOut(
                id=cover_asset.id,
                public_id=cover_asset.public_id,
                url=cover_asset.url or "",
                mime_type=cover_asset.mime_type,
                byte_size=cover_asset.byte_size,
                width=cover_asset.width,
                height=cover_asset.height,
            )
    
    return AlbumOut(
        id=album.id,
        public_id=album.public_id,
        title=album.title,
        slug=album.slug,
        description=album.description,
        status=album.status,
        cover=cover,
        items=album_items if album_items else None,
        videos=album_videos if album_videos else None,
        item_count=len(items) + len(videos),
        image_count=len(items),
        video_count=len(videos),
        created_by=album.created_by,
        created_at=album.created_at,
        updated_at=album.updated_at,
    )


def list_albums(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[ContentStatus] = None,
    q: Optional[str] = None,
) -> AlbumListOut:
    """Lấy danh sách albums với pagination và filter."""
    # Base query
    stmt = select(Album).where(Album.deleted_at.is_(None))
    
    # Filter by status
    if status_filter:
        stmt = stmt.where(Album.status == status_filter)
    
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
    items = [_to_album_out(db, album) for album in albums]
    
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
    
    return AlbumListOut(
        items=items,
        meta=AlbumListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


def get_album_detail(db: Session, album_id: int) -> AlbumOut:
    """Lấy chi tiết album."""
    album = _get_album_or_404(db, album_id)
    return _to_album_out(db, album)


def create_album(
    db: Session, payload: AlbumCreate, user: Optional[User] = None
) -> AlbumOut:
    """Tạo album mới."""
    logger.info(
        "Creating new album",
        extra={"action": "create_album", "title": payload.title, "status": payload.status.value}
    )
    
    # Generate slug
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
    
    # Resolve assets và videos
    asset_map = {}
    if payload.items:
        asset_public_ids = [item.asset_public_id for item in payload.items]
        asset_map = _resolve_asset_ids(db, asset_public_ids)
    
    video_map = {}
    if payload.videos:
        video_public_ids = [video.video_public_id for video in payload.videos]
        video_map = _resolve_video_ids(db, video_public_ids)
    
    # Resolve cover asset
    cover_asset_id = None
    if payload.cover_asset_public_id:
        cover_map = _resolve_asset_ids(db, [payload.cover_asset_public_id])
        cover_asset_id = cover_map.get(payload.cover_asset_public_id)
    elif payload.items:
        # Auto set cover = ảnh đầu tiên
        first_item = payload.items[0]
        cover_asset_id = asset_map.get(first_item.asset_public_id)
    
    # Create album
    album = Album(
        title=payload.title,
        slug=slug,
        description=payload.description,
        cover_asset_id=cover_asset_id,
        status=payload.status,
        created_by=user.id if user else None,
    )
    db.add(album)
    db.flush()
    
    # Create items
    if payload.items:
        for item in payload.items:
            asset_id = asset_map.get(item.asset_public_id)
            if asset_id:
                album_item = AlbumItem(
                    album_id=album.id,
                    asset_id=asset_id,
                    position=item.position,
                    caption=item.caption,
                )
                db.add(album_item)
    
    # Create videos
    if payload.videos:
        for video in payload.videos:
            video_id = video_map.get(video.video_public_id)
            if video_id:
                album_video = AlbumVideo(
                    album_id=album.id,
                    video_id=video_id,
                    position=video.position,
                )
                db.add(album_video)
    
    db.commit()
    db.refresh(album)
    
    logger.info(
        "Album created successfully",
        extra={"album_id": album.id, "slug": album.slug, "status": album.status.value}
    )
    
    return _to_album_out(db, album)


def update_album(
    db: Session, album_id: int, payload: AlbumUpdate, user: Optional[User] = None
) -> AlbumOut:
    """Cập nhật album."""
    logger.info("Updating album", extra={"action": "update_album", "album_id": album_id})
    
    album = _get_album_or_404(db, album_id)
    
    # Update fields
    if payload.title is not None:
        album.title = payload.title
        # Auto generate slug từ title
        new_slug = slugify(album.title)
        if new_slug:
            _ensure_unique_slug(db, new_slug, exclude_album_id=album.id)
            album.slug = new_slug
    
    if payload.slug is not None:
        _ensure_unique_slug(db, payload.slug, exclude_album_id=album.id)
        album.slug = payload.slug
    
    if payload.description is not None:
        album.description = payload.description
    
    if payload.status is not None:
        album.status = payload.status
    
    if payload.cover_asset_public_id is not None:
        if payload.cover_asset_public_id:
            cover_map = _resolve_asset_ids(db, [payload.cover_asset_public_id])
            album.cover_asset_id = cover_map.get(payload.cover_asset_public_id)
        else:
            album.cover_asset_id = None
    
    album.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(album)
    
    logger.info(
        "Album updated successfully",
        extra={"album_id": album.id, "slug": album.slug}
    )
    
    return _to_album_out(db, album)


def delete_album(db: Session, album_id: int) -> None:
    """Xóa album (soft delete)."""
    logger.info("Deleting album", extra={"action": "delete_album", "album_id": album_id})
    
    album = _get_album_or_404(db, album_id)
    album.deleted_at = datetime.now(timezone.utc)
    
    db.commit()
    
    logger.info("Album deleted successfully", extra={"album_id": album_id})


def check_slug(db: Session, slug: str) -> SlugCheckOut:
    """Kiểm tra slug có unique không."""
    normalized_slug = slugify(slug)
    if not normalized_slug:
        return SlugCheckOut(is_unique=False, normalized_slug="")
    
    _ensure_unique_slug(db, normalized_slug)
    return SlugCheckOut(is_unique=True, normalized_slug=normalized_slug)

