"""Controlled public API failures."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.field_errors = field_errors or {}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            {"code": exc.code, "message": exc.message, "fieldErrors": exc.field_errors},
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, list[str]] = {}
        for error in exc.errors():
            path = (
                ".".join(
                    str(part) for part in error["loc"] if part not in ("body", "query", "path")
                )
                or "request"
            )
            fields.setdefault(path, []).append(str(error["msg"]))
        return JSONResponse(
            {"code": "VALIDATION_ERROR", "message": "Invalid request", "fieldErrors": fields},
            status_code=422,
        )

    @app.exception_handler(IntegrityError)
    async def conflict_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            {
                "code": "CONFLICT",
                "message": "The record conflicts with existing data",
                "fieldErrors": {},
            },
            status_code=409,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            {"code": code, "message": "Request unavailable", "fieldErrors": {}},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            {"code": "INTERNAL_ERROR", "message": "Request failed", "fieldErrors": {}},
            status_code=500,
        )
