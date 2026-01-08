from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PushSubscription
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionOut


def upsert_subscription(
    db: Session, payload: PushSubscriptionCreate
) -> PushSubscriptionOut:
    existing = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )

    if existing:
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.expiration_time = payload.expirationTime
        if payload.user_id:
            existing.user_id = payload.user_id
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return PushSubscriptionOut.from_orm(existing)

    sub = PushSubscription(
        endpoint=str(payload.endpoint),
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        expiration_time=payload.expirationTime,
        user_id=payload.user_id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return PushSubscriptionOut.from_orm(sub)
