from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Asset, User
from app.services import auth_service

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


def _get_video_asset(db: Session, asset_id: int) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.deleted_at.is_(None)))
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "asset_not_found", "message": "Asset không tồn tại."},
        )
    if not asset.mime_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_video", "message": "Asset không phải video."},
        )
    return asset


def _get_video_path(asset: Asset) -> Path:
    if not asset.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "asset_no_url", "message": "Asset không có đường dẫn tệp."},
        )
    video_path = UPLOAD_DIR / asset.url.lstrip("/uploads/")
    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "file_not_found", "message": f"Không tìm thấy file: {video_path}"},
        )
    return video_path


def upload_asset_to_youtube(
    db: Session,
    *,
    asset_id: int,
    title: Optional[str],
    description: Optional[str],
    tags: Optional[list[str]],
    privacy_status: str = "unlisted",
    user_email: Optional[str] = None,
) -> str:
    """
    Upload một asset video lên YouTube.

    Returns: YouTube video id.
    """
    asset = _get_video_asset(db, asset_id)
    video_path = _get_video_path(asset)
    user: User = auth_service.get_user_for_google(db, email=user_email)

    access_token = auth_service.get_valid_access_token(db, user)

    # Bước 1: tạo upload session (resumable)
    snippet = {
        "title": title or Path(asset.object_key or video_path.name).stem,
        "description": description or "",
    }
    if tags:
        snippet["tags"] = tags
    body = {
        "snippet": snippet,
        "status": {"privacyStatus": privacy_status or "unlisted"},
    }

    start_resp = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": asset.mime_type,
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        json=body,
        timeout=15,
    )

    if start_resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "youtube_init_failed",
                "message": f"Không khởi tạo upload YouTube: {start_resp.text}",
            },
        )

    upload_url = start_resp.headers.get("Location")
    if not upload_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "youtube_missing_location",
                "message": "YouTube không trả Location cho resumable upload.",
            },
        )

    # Bước 2: upload file (single chunk)
    with open(video_path, "rb") as f:
        upload_resp = requests.put(
            upload_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": asset.mime_type,
                "Content-Length": str(video_path.stat().st_size),
            },
            data=f,
            timeout=600,
        )

    if upload_resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "youtube_upload_failed",
                "message": f"Upload video YouTube thất bại: {upload_resp.text}",
            },
        )

    vid = upload_resp.json().get("id")
    if not vid:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "youtube_no_id",
                "message": "YouTube không trả video id.",
            },
        )

    return vid
