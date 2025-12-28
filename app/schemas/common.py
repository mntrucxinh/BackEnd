from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Chuẩn lỗi chung:
    - code: mã lỗi cho FE handle (i18n, mapping UI, ...)
    - message: mô tả ngắn gọn, có thể hiển thị cho user
    - fields: chi tiết lỗi theo field (validation)
    """

    code: str = Field(..., description="Mã lỗi ngắn, dùng cho FE handle.")
    message: str = Field(..., description="Mô tả lỗi có thể hiển thị cho người dùng.")
    fields: Optional[Dict[str, Any]] = Field(
        default=None, description="Chi tiết lỗi từng field (nếu là validation error)."
    )


