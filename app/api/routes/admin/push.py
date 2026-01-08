from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.push_service import PushError, send_push_for_announcement

router = APIRouter(prefix="/admin/push", tags=["Admin - Push"])


@router.post("/announcement/{slug}")
def push_announcement(slug: str, db: Session = Depends(get_db)) -> dict:
    """
    Gửi Web Push dựa trên thông báo (announcement) slug cho tất cả subscription đã lưu.
    """
    try:
        result = send_push_for_announcement(db, slug=slug)
        return {"status": "ok", **result}
    except PushError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "push_error", "message": str(e)},
        )
