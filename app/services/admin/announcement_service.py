from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.enums import ContentStatus, JobStatus, PostType
from app.models.tables import (
    Asset,
    Block,
    FacebookPostLog,
    Post,
    PostAsset,
    PostRevision,
    User,
)
from app.schemas.announcement import (
    AdminAnnouncementListMeta,
    AdminAnnouncementListOut,
    AdminAnnouncementOut,
    AnnouncementCreate,
    AnnouncementUpdate,
)
from app.schemas.asset import AssetOut, PostAssetOut
from app.services import facebook_service
from app.services.facebook_service import (
    delete_facebook_post,
    get_valid_facebook_token,
    upload_images_to_facebook,
    upload_video_to_facebook,
)
from app.utils.text import slugify

logger = logging.getLogger(__name__)


ALLOWED_BLOCK_CODES = {"bee", "mouse", "bear", "dolphin"}


def _get_block_by_code_or_400(db: Session, block_code: str) -> Block:
    if block_code not in ALLOWED_BLOCK_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_block_code",
                "message": "Mã khối không hợp lệ. Chỉ chấp nhận: bee, mouse, bear, dolphin.",
            },
        )

    block = db.scalar(
        select(Block).where(Block.code == block_code, Block.is_active.is_(True))
    )
    if not block:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "block_not_found",
                "message": "Khối không tồn tại hoặc đã bị vô hiệu hoá.",
            },
        )
    return block


def _get_post_content_asset_public_ids(
    db: Session, post_id: int
) -> Optional[list[UUID]]:
    """Lấy danh sách content_asset_public_ids từ PostAsset."""
    post_assets = db.scalars(
        select(PostAsset)
        .where(PostAsset.post_id == post_id)
        .order_by(PostAsset.position)
    ).all()

    if not post_assets:
        return None

    asset_ids = [pa.asset_id for pa in post_assets]
    assets = db.scalars(
        select(Asset).where(
            Asset.id.in_(asset_ids),
            Asset.deleted_at.is_(None),
        )
    ).all()

    return [asset.public_id for asset in assets]


def _get_facebook_post_id(db: Session, post_id: int) -> Optional[str]:
    log_entry = db.scalar(
        select(FacebookPostLog)
        .where(
            FacebookPostLog.post_id == post_id,
            FacebookPostLog.fb_post_id.isnot(None),
        )
        .order_by(FacebookPostLog.created_at.desc())
    )
    return log_entry.fb_post_id if log_entry else None


def _save_facebook_post_log(
    db: Session,
    post_id: int,
    fb_post_id: str,
    status: JobStatus,
) -> FacebookPostLog:
    log_entry = db.scalar(
        select(FacebookPostLog).where(FacebookPostLog.post_id == post_id)
    )

    if log_entry:
        log_entry.fb_post_id = fb_post_id
        log_entry.status = status
        log_entry.updated_at = datetime.now(timezone.utc)
    else:
        log_entry = FacebookPostLog(
            post_id=post_id,
            fb_post_id=fb_post_id,
            status=status,
        )
        db.add(log_entry)

    db.flush()
    return log_entry


def _delete_from_facebook(
    db: Session,
    post_id: int,
    user: Optional[User] = None,
) -> bool:
    fb_post_id = _get_facebook_post_id(db, post_id)
    if not fb_post_id:
        logger.debug(
            "No Facebook post to delete",
            extra={"post_id": post_id, "action": "delete_facebook"},
        )
        return True

    log_context = {
        "post_id": post_id,
        "fb_post_id": fb_post_id,
        "action": "delete_facebook",
    }

    try:
        page_id = None
        access_token = None

        if user:
            try:
                page_id, access_token = get_valid_facebook_token(db, user)
            except ValueError:
                logger.warning(
                    "Cannot get user token, using env token",
                    extra={**log_context, "user_id": user.id},
                )

        success = delete_facebook_post(
            fb_post_id=fb_post_id,
            page_id=page_id,
            access_token=access_token,
        )

        if success:
            log_entry = db.scalar(
                select(FacebookPostLog).where(FacebookPostLog.post_id == post_id)
            )
            if log_entry:
                log_entry.status = JobStatus.SUCCEEDED
                log_entry.updated_at = datetime.now(timezone.utc)

            logger.info(
                "Facebook post deleted successfully",
                extra={**log_context},
            )
        else:
            logger.warning(
                "Facebook post deletion failed or post not found",
                extra={**log_context},
            )

        return success

    except Exception as e:
        logger.error(
            "Failed to delete Facebook post",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return False


def _publish_to_facebook(
    db: Session,
    post: Post,
    content_asset_public_ids: Optional[list[UUID]],
    user: Optional[User] = None,
) -> None:
    """
    Đăng thông báo lên Facebook khi publish.
    - Nếu có video: đăng video (bỏ qua ảnh).
    - Nếu có ảnh: đăng album ảnh.
    - Nếu không có media: đăng text/link.
    """
    post_url = f"{os.getenv('APP_BASE_URL', 'https://your-site.com')}/announcements/{post.slug}"

    log_context = {
        "post_id": post.id,
        "post_slug": post.slug,
        "post_title": post.title,
    }

    try:
        page_id = None
        access_token = None

        if user:
            try:
                page_id, access_token = facebook_service.get_valid_facebook_token(db, user)
                logger.info(
                    "Using user Facebook token",
                    extra={**log_context, "user_id": user.id, "page_id": page_id, "action": "facebook_publish_start"},
                )
            except ValueError as e:
                logger.error(
                    "Cannot refresh Facebook token",
                    extra={**log_context, "user_id": user.id, "error": str(e)},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "facebook_token_expired",
                        "message": str(e),
                        "action": "link_facebook",
                    },
                )
        else:
            logger.warning(
                "No user provided, skipping Facebook publish",
                extra={**log_context, "action": "facebook_publish_skipped"},
            )
            return

        logger.info(
            "Starting Facebook publish",
            extra={**log_context, "action": "facebook_publish_start"},
        )

        all_assets = []
        if content_asset_public_ids:
            all_assets = db.scalars(
                select(Asset).where(Asset.public_id.in_(content_asset_public_ids))
            ).all()

        fb_images = [
            asset for asset in all_assets if asset and asset.mime_type.startswith("image/")
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
            },
        )

        if fb_video:
            fb_post_id = upload_video_to_facebook(
                post,
                fb_video,
                post_url,
                page_id=page_id,
                access_token=access_token,
            )
        elif fb_images:
            fb_post_id = upload_images_to_facebook(
                post=post,
                post_url=post_url,
                content_assets=fb_images,
                page_id=page_id,
                access_token=access_token,
            )
        else:
            fb_post_id = upload_images_to_facebook(
                post=post,
                post_url=post_url,
                content_assets=[],
                page_id=page_id,
                access_token=access_token,
            )

        if fb_post_id:
            _save_facebook_post_log(db, post.id, fb_post_id, JobStatus.SUCCEEDED)

    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to publish announcement to Facebook",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "facebook_post_failed",
                "message": f"Đăng bài lên Facebook thất bại: {str(e)}",
            },
        )


def _resolve_asset_ids(
    db: Session, asset_public_ids: Optional[list[UUID]]
) -> list[int]:
    if not asset_public_ids:
        return []

    assets = db.scalars(
        select(Asset).where(
            Asset.public_id.in_(asset_public_ids),
            Asset.deleted_at.is_(None),
        )
    ).all()

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

    asset_map = {asset.public_id: asset.id for asset in assets}
    return [asset_map[pid] for pid in asset_public_ids]


def _ensure_unique_slug(
    db: Session, slug: str, *, exclude_post_id: Optional[int] = None
) -> None:
    stmt = select(func.count(Post.id)).where(
        Post.post_type == PostType.ANNOUNCEMENT,
        Post.slug == slug,
        Post.deleted_at.is_(None),
    )
    if exclude_post_id is not None:
        stmt = stmt.where(Post.id != exclude_post_id)

    count = db.scalar(stmt) or 0
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "slug_not_unique",
                "message": "Slug đã tồn tại. Vui lòng chọn tiêu đề khác.",
            },
        )


def _to_admin_announcement_out(db: Session, post: Post) -> AdminAnnouncementOut:
    """Convert Post → AdminAnnouncementOut, join Block & Asset."""
    block = None
    if post.block_id:
        block = db.scalar(select(Block).where(Block.id == post.block_id))

    if not block:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "missing_block", "message": "Thông báo không có khối."},
        )

    post_assets = db.scalars(
        select(PostAsset)
        .where(PostAsset.post_id == post.id)
        .order_by(PostAsset.position)
    ).all()

    if not post_assets:
        content_assets: list[PostAssetOut] = []
    else:
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

    return AdminAnnouncementOut(
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
    status_filter: Optional[ContentStatus] = None,
    grade: Optional[str] = None,
    q: Optional[str] = None,
) -> AdminAnnouncementListOut:
    """List thông báo cho admin CMS (có thể lọc theo status, block, search)."""
    base_stmt = (
        select(Post)
        .join(Block, Post.block_id == Block.id)
        .where(
            Post.post_type == PostType.ANNOUNCEMENT,
            Post.deleted_at.is_(None),
        )
    )
    count_stmt = (
        select(func.count(Post.id))
        .join(Block, Post.block_id == Block.id)
        .where(
            Post.post_type == PostType.ANNOUNCEMENT,
            Post.deleted_at.is_(None),
        )
    )

    if status_filter:
        base_stmt = base_stmt.where(Post.status == status_filter)
        count_stmt = count_stmt.where(Post.status == status_filter)

    if grade:
        base_stmt = base_stmt.where(Block.code == grade)
        count_stmt = count_stmt.where(Block.code == grade)

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

    items = [_to_admin_announcement_out(db, row) for row in rows]

    meta = AdminAnnouncementListMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    return AdminAnnouncementListOut(items=items, meta=meta)


def get_announcement_detail(db: Session, announcement_id: int) -> AdminAnnouncementOut:
    stmt = select(Post).where(
        Post.id == announcement_id,
        Post.post_type == PostType.ANNOUNCEMENT,
        Post.deleted_at.is_(None),
    )
    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "announcement_not_found",
                "message": "Thông báo không tồn tại.",
            },
        )
    return _to_admin_announcement_out(db, post)


def create_announcement(
    db: Session, payload: AnnouncementCreate, user: Optional[User] = None
) -> AdminAnnouncementOut:
    logger.info(
        "Creating new announcement",
        extra={"action": "create_announcement", "title": payload.title},
    )

    block = _get_block_by_code_or_400(db, payload.block_code)

    slug = payload.slug or slugify(payload.title)
    if not slug:
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
        post_type=PostType.ANNOUNCEMENT,
        status=payload.status,
        title=payload.title,
        slug=slug,
        excerpt=payload.excerpt,
        content_html=payload.content_html,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        block_id=block.id,
        published_at=published_at,
    )
    db.add(post)
    db.flush()

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

    # Đăng Facebook khi publish + publish_to_facebook = True
    if payload.status == ContentStatus.PUBLISHED and payload.publish_to_facebook:
        _publish_to_facebook(db, post, payload.content_asset_public_ids, user=user)

    db.commit()
    db.refresh(post)

    return _to_admin_announcement_out(db, post)


def update_announcement(
    db: Session, announcement_id: int, payload: AnnouncementUpdate, user: Optional[User] = None
) -> AdminAnnouncementOut:
    logger.info(
        "Updating announcement",
        extra={"action": "update_announcement", "announcement_id": announcement_id},
    )

    stmt = select(Post).where(
        Post.id == announcement_id,
        Post.post_type == PostType.ANNOUNCEMENT,
        Post.deleted_at.is_(None),
    )
    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "announcement_not_found",
                "message": "Thông báo không tồn tại.",
            },
        )

    previous_status = post.status

    if payload.title is not None:
        post.title = payload.title
        new_slug = slugify(post.title)
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

    if payload.block_code is not None:
        block = _get_block_by_code_or_400(db, payload.block_code)
        post.block_id = block.id

    content_assets_changed = False
    if payload.content_asset_public_ids is not None:
        db.execute(delete(PostAsset).where(PostAsset.post_id == post.id))
        content_assets_changed = True

        if payload.content_asset_public_ids:
            asset_ids = _resolve_asset_ids(db, payload.content_asset_public_ids)
            for position, asset_id in enumerate(asset_ids):
                post_asset = PostAsset(
                    post_id=post.id,
                    asset_id=asset_id,
                    position=position,
                )
                db.add(post_asset)

        db.flush()

    publish_to_facebook = payload.publish_to_facebook

    if payload.status is not None:
        post.status = payload.status
        now = datetime.now(timezone.utc)

        if previous_status != ContentStatus.PUBLISHED and payload.status == ContentStatus.PUBLISHED:
            post.published_at = now
            if publish_to_facebook is None or publish_to_facebook:
                content_asset_public_ids = _get_post_content_asset_public_ids(db, post.id)
                _publish_to_facebook(db, post, content_asset_public_ids, user=user)
        elif previous_status == ContentStatus.PUBLISHED and payload.status != ContentStatus.PUBLISHED:
            post.published_at = None
            _delete_from_facebook(db, post.id, user=user)
        elif (
            previous_status == ContentStatus.PUBLISHED
            and payload.status == ContentStatus.PUBLISHED
            and publish_to_facebook is not None
        ):
            if not publish_to_facebook:
                _delete_from_facebook(db, post.id, user=user)
            else:
                fb_post_id = _get_facebook_post_id(db, post.id)
                if not fb_post_id:
                    content_asset_public_ids = _get_post_content_asset_public_ids(db, post.id)
                    _publish_to_facebook(db, post, content_asset_public_ids, user=user)

    has_content_changes = (
        payload.title is not None
        or payload.content_html is not None
        or payload.excerpt is not None
        or payload.slug is not None
        or payload.content_asset_public_ids is not None
        or payload.meta_title is not None
        or payload.meta_description is not None
    )

    if (
        post.status == ContentStatus.PUBLISHED
        and previous_status == ContentStatus.PUBLISHED
        and has_content_changes
    ):
        if publish_to_facebook is False:
            _delete_from_facebook(db, post.id, user=user)
        else:
            _delete_from_facebook(db, post.id, user=user)
            if content_assets_changed:
                db.flush()
            if publish_to_facebook is not False:
                content_asset_public_ids = _get_post_content_asset_public_ids(db, post.id)
                _publish_to_facebook(db, post, content_asset_public_ids, user=user)

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

    return _to_admin_announcement_out(db, post)


def delete_announcement(db: Session, announcement_id: int, user: Optional[User] = None) -> None:
    logger.info(
        "Deleting announcement",
        extra={"action": "delete_announcement", "announcement_id": announcement_id},
    )

    stmt = select(Post).where(
        Post.id == announcement_id,
        Post.post_type == PostType.ANNOUNCEMENT,
        Post.deleted_at.is_(None),
    )
    post = db.scalar(stmt)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "announcement_not_found",
                "message": "Thông báo không tồn tại.",
            },
        )

    if post.status == ContentStatus.PUBLISHED:
        _delete_from_facebook(db, post.id, user=user)

    post.deleted_at = datetime.now(timezone.utc)
    db.commit()



