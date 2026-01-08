from __future__ import annotations

import os
from typing import Optional

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Post, PushSubscription
from app.models.enums import ContentStatus, PostType


class PushError(Exception):
    pass


def _get_frontend_url() -> str:
    origin = os.getenv("FRONTEND_ORIGINS", "").split(",")[0].strip()
    if origin:
        return origin
    return os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:3000")


def send_push_for_announcement(db: Session, *, slug: str) -> dict:
    """
    Gửi Web Push cho tất cả subscription dựa trên thông báo (announcement) theo slug.
    """
    vapid_public = os.getenv("VAPID_PUBLIC_KEY")
    vapid_private = os.getenv("VAPID_PRIVATE_KEY")
    if not vapid_public or not vapid_private:
        raise PushError("VAPID keys are not configured")

    announcement = db.scalar(
        select(Post).where(
            Post.slug == slug,
            Post.type == PostType.ANNOUNCEMENT,
            Post.status == ContentStatus.PUBLISHED,
        )
    )
    if not announcement:
        raise PushError("Announcement not found or not published")

    target_url = f"{_get_frontend_url().rstrip('/')}/notice/{announcement.slug}"
    title = announcement.title or "Thông báo mới"
    body = announcement.excerpt or "Có thông báo mới từ Trúc Xinh"

    subs = db.scalars(select(PushSubscription)).all()
    if not subs:
        return {"sent": 0, "failed": 0, "removed": 0}

    sent = failed = removed = 0
    for sub in subs:
        payload = {
            "title": title,
            "body": body,
            "url": target_url,
            "tag": f"announcement-{announcement.public_id}",
        }
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=str(payload),
                vapid_private_key=vapid_private,
                vapid_public_key=vapid_public,
                ttl=3600,
            )
            sent += 1
        except WebPushException as exc:
            failed += 1
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                # subscription invalid, remove
                db.delete(sub)
                removed += 1
        except Exception:
            failed += 1
    db.commit()
    return {"sent": sent, "failed": failed, "removed": removed}
