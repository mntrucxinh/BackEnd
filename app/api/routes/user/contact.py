from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.contact import ContactMessageCreate, ContactMessageOut
from app.services.user import contact_service

router = APIRouter(prefix="/contact", tags=["Public - Contact"])


@router.post("", response_model=ContactMessageOut)
def submit_contact_message(
    payload: ContactMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ContactMessageOut:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return contact_service.create_contact_message(db, payload, ip=ip, user_agent=user_agent)
