from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionOut
from app.services.user import push_subscription_service

router = APIRouter(prefix="/public/push-subscriptions", tags=["Public - Push Subscriptions"])


@router.post("", response_model=PushSubscriptionOut)
def save_push_subscription(
    payload: PushSubscriptionCreate, db: Session = Depends(get_db)
) -> PushSubscriptionOut:
    """
    Lưu hoặc cập nhật subscription từ trình duyệt PWA để dùng cho Web Push.
    Endpoint được unique, lần gửi sau sẽ update keys/expiration/user_id.
    """
    return push_subscription_service.upsert_subscription(db, payload)
