"""RFC 7807 Problem Details + typed domain exceptions."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code: int = 400
    title: str = "Domain error"

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail)
        self.detail = detail or self.title


class NotFoundError(DomainError):
    status_code = 404
    title = "Not found"


class PermissionDeniedError(DomainError):
    status_code = 403
    title = "Permission denied"


class IngestionError(DomainError):
    status_code = 422
    title = "Ingestion failed"


class RetrievalError(DomainError):
    status_code = 502
    title = "Retrieval failed"


class LLMError(DomainError):
    status_code = 502
    title = "LLM call failed"


class RateLimitedError(DomainError):
    status_code = 429
    title = "Rate limited"


def _problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    type_: str = "about:blank",
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        },
        media_type="application/problem+json",
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=str(request.url.path),
        )

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> JSONResponse:
        return _problem(
            status_code=exc.status_code,
            title=str(exc.detail) if exc.status_code >= 500 else exc.__class__.__name__,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail="; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            )
            or "invalid request",
            instance=str(request.url.path),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return _problem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal server error",
            detail="An unexpected error occurred.",
            instance=str(request.url.path),
        )
