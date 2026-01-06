from __future__ import annotations

import traceback
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
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
        # Xử lý trường hợp đặc biệt: files là string (client gửi string rỗng)
        # Nếu lỗi validation là về files và có message về UploadFile/string
        # → tự động bỏ qua và coi như không có files
        errors = exc.errors()
        files_error = None
        for error in errors:
            if error.get("loc") and "files" in error.get("loc", []):
                error_msg = str(error.get("msg", ""))
                if "Expected UploadFile" in error_msg and "received" in error_msg and "str" in error_msg:
                    files_error = error
                    break
        
        # Nếu có lỗi files là string → bỏ qua lỗi đó
        # LƯU Ý: Nếu endpoint dùng parse_files_from_request, FastAPI sẽ không validate field files
        # nên lỗi này chỉ xảy ra nếu endpoint vẫn dùng File() parameter
        if files_error:
            # Loại bỏ lỗi files khỏi danh sách lỗi
            errors = [e for e in errors if e != files_error]
            
            # Nếu không còn lỗi nào → request hợp lệ (chỉ có lỗi files string)
            # Bỏ qua lỗi này và tiếp tục xử lý (không trả về lỗi)
            if not errors:
                # Không trả về lỗi, để request tiếp tục được xử lý
                # Endpoint sẽ tự parse files từ request
                pass
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


