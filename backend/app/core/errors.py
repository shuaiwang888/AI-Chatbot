"""自定义异常 + FastAPI 异常处理."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用层业务异常的基类."""

    code: str = "app_error"
    status_code: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        retryable: bool | None = None,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if retryable is not None:
            self.retryable = retryable
        self.detail = detail or {}


class DocumentNotFoundError(AppError):
    code = "document_not_found"
    status_code = 404


class IngestionFailedError(AppError):
    code = "ingestion_failed"
    status_code = 500
    retryable = True


class LLMUnavailableError(AppError):
    code = "llm_unavailable"
    status_code = 503
    retryable = True


class VectorStoreUnavailableError(AppError):
    code = "vector_store_unavailable"
    status_code = 503
    retryable = True


def install_exception_handlers(app: FastAPI) -> None:
    """挂载全局异常处理. 由 main.py 在创建 app 后调用."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "detail": exc.detail,
            },
        )
