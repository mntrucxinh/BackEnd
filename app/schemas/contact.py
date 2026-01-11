from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContactStatus


class ContactMessageCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    subject: Optional[str] = Field(default=None, max_length=255)
    message: str = Field(..., min_length=1)


class ContactMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ContactStatus
    created_at: datetime


class ContactMessageAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: Optional[str]
    email: Optional[str]
    message: str
    status: ContactStatus
    ip: Optional[str]
    user_agent: Optional[str]
    spam_score: Optional[float]
    created_at: datetime


class ContactMessageListMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class ContactMessageListOut(BaseModel):
    items: list[ContactMessageAdminOut]
    meta: ContactMessageListMeta


class ContactMessageStatusUpdate(BaseModel):
    status: ContactStatus
