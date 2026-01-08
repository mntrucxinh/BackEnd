from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class PushSubscriptionKeys(BaseModel):
  p256dh: str = Field(..., description="Client public key for message encryption")
  auth: str = Field(..., description="Auth secret for message encryption")


class PushSubscriptionCreate(BaseModel):
  endpoint: HttpUrl = Field(..., description="Push service endpoint")
  keys: PushSubscriptionKeys
  expirationTime: Optional[int] = Field(
      default=None, description="Expiration time (ms since epoch) if provided by browser"
  )
  user_id: Optional[int] = Field(
      default=None, description="Optional user id if available on the client"
  )


class PushSubscriptionOut(BaseModel):
  id: int
  endpoint: HttpUrl
  created_at: datetime

  class Config:
    orm_mode = True
