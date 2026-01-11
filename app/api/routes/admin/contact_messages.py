from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import ContactStatus
from app.models.tables import User
from app.schemas.contact import (
    ContactMessageAdminOut,
    ContactMessageListOut,
    ContactMessageStatusUpdate,
)
from app.services.admin import contact_message_service

router = APIRouter(prefix="/admin/contact-messages", tags=["Admin - Contact Messages"])


@router.get("", response_model=ContactMessageListOut)
def list_contact_messages(
    *,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ContactStatus] = Query(
        None,
        alias="status",
        description="Filter by status: new/handled/spam.",
    ),
    q: Optional[str] = Query(
        None,
        description="Search by name/email/phone/message (ILIKE).",
    ),
) -> ContactMessageListOut:
    return contact_message_service.list_contact_messages(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        q=q,
    )


@router.patch("/{message_id}", response_model=ContactMessageAdminOut)
def update_contact_message_status(
    message_id: int,
    payload: ContactMessageStatusUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ContactMessageAdminOut:
    return contact_message_service.update_contact_message_status(
        db,
        message_id,
        status=payload.status,
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_contact_message(
    message_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Response:
    contact_message_service.delete_contact_message(db, message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
