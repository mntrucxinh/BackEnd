from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import ContactMessage
from app.schemas.contact import ContactMessageCreate, ContactMessageOut


def create_contact_message(
    db: Session,
    payload: ContactMessageCreate,
    *,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> ContactMessageOut:
    subject = (payload.subject or "").strip()
    message = payload.message.strip()
    if subject:
        message = f"Chu de: {subject}\n{message}"

    phone = payload.phone.strip() if payload.phone else None
    email = payload.email.strip() if payload.email else None

    contact = ContactMessage(
        full_name=payload.full_name.strip(),
        phone=phone or None,
        email=email or None,
        message=message,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactMessageOut.from_orm(contact)
