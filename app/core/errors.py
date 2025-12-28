from __future__ import annotations

import traceback
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    """
    Đăng ký các exception handler chuẩn hoá cho toàn bộ ứng dụng.

    - HTTPException -> ErrorResponse với code/message/fields.
    - RequestValidationError (422) -> ErrorResponse với fields chi tiết.
    - Exception (500) -> ErrorResponse với message generic + log chi tiết.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        detail = exc.detail
        payload: Dict[str, Any]

        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            payload = {
                "code": str(detail.get("code")),
                "message": str(detail.get("message")),
                "fields": detail.get("fields"),
            }
        else:
            payload = {
                "code": "generic_http_error",
                "message": str(detail) if detail else str(exc.status_code),
                "fields": None,
            }

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(**payload).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: Dict[str, Any] = {}
        for err in exc.errors():
            loc = err.get("loc", [])
            if len(loc) >= 2:
                field_name = str(loc[1])
            elif loc:
                field_name = str(loc[-1])
            else:
                field_name = "non_field_error"

            messages = field_errors.setdefault(field_name, [])
            messages.append(err.get("msg"))

        payload = ErrorResponse(
            code="validation_error",
            message="Dữ liệu không hợp lệ.",
            fields=field_errors or None,
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Bắt mọi exception không được handle để tránh lỗi 500 raw.
        Log chi tiết để debug, nhưng chỉ trả về message generic cho client.
        """
        # Log chi tiết lỗi ra console để debug
        print("\n" + "=" * 80)
        print(f"❌ UNHANDLED EXCEPTION: {type(exc).__name__}")
        print(f"   Message: {exc}")
        print(f"   Path: {request.method} {request.url}")
        print(f"   Traceback:")
        print("-" * 80)
        traceback.print_exc()
        print("=" * 80 + "\n")

        payload = ErrorResponse(
            code="internal_server_error",
            message="Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
            fields=None,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())


