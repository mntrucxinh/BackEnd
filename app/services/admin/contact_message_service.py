from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContactStatus
from app.models.tables import ContactMessage
from app.schemas.contact import (
    ContactMessageAdminOut,
    ContactMessageListMeta,
    ContactMessageListOut,
)


def _get_contact_message_or_404(db: Session, message_id: int) -> ContactMessage:
    message = db.scalar(
        select(ContactMessage).where(ContactMessage.id == message_id)
    )
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "contact_message_not_found", "message": "Contact message not found."},
        )
    return message


def list_contact_messages(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: Optional[ContactStatus] = None,
    q: Optional[str] = None,
) -> ContactMessageListOut:
    base_stmt = select(ContactMessage)
    count_stmt = select(func.count(ContactMessage.id))

    if status_filter is not None:
        base_stmt = base_stmt.where(ContactMessage.status == status_filter)
        count_stmt = count_stmt.where(ContactMessage.status == status_filter)

    if q:
        ilike = f"%{q}%"
        base_stmt = base_stmt.where(
            (ContactMessage.full_name.ilike(ilike))
            | (ContactMessage.email.ilike(ilike))
            | (ContactMessage.phone.ilike(ilike))
            | (ContactMessage.message.ilike(ilike))
        )
        count_stmt = count_stmt.where(
            (ContactMessage.full_name.ilike(ilike))
            | (ContactMessage.email.ilike(ilike))
            | (ContactMessage.phone.ilike(ilike))
            | (ContactMessage.message.ilike(ilike))
        )

    base_stmt = base_stmt.order_by(
        ContactMessage.created_at.desc(),
        ContactMessage.id.desc(),
    )

    total_items = db.scalar(count_stmt) or 0
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0

    rows = db.scalars(
        base_stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [ContactMessageAdminOut.from_orm(row) for row in rows]
    meta = ContactMessageListMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
    return ContactMessageListOut(items=items, meta=meta)


def update_contact_message_status(
    db: Session,
    message_id: int,
    *,
    status: ContactStatus,
) -> ContactMessageAdminOut:
    message = _get_contact_message_or_404(db, message_id)
    message.status = status
    db.commit()
    db.refresh(message)
    return ContactMessageAdminOut.from_orm(message)


def delete_contact_message(db: Session, message_id: int) -> None:
    message = _get_contact_message_or_404(db, message_id)
    db.delete(message)
    db.commit()
