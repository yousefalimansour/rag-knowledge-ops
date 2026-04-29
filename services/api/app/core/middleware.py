from __future__ import annotations

import logging
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import new_request_id, request_id_ctx

logger = logging.getLogger("api.request")

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
ACCESS_COOKIE = "access_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or new_request_id()
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = rid
        logger.info(
            "request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": getattr(response, "status_code", 0),
                "latency_ms": latency_ms,
            },
        )
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF for cookie-authed state-changing requests.

    Skipped for safe methods, for unauthenticated requests (no access cookie),
    and for explicit exempt paths (login/signup — they create the cookie).
    """

    EXEMPT_PATHS = {"/auth/login", "/auth/signup"}

    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS or request.url.path in self.EXEMPT_PATHS:
            response = await call_next(request)
        elif request.cookies.get(ACCESS_COOKIE) is None:
            # No session cookie → bearer-token or unauth flow; CSRF doesn't apply.
            response = await call_next(request)
        else:
            cookie = request.cookies.get(CSRF_COOKIE)
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                from app.core.errors import _problem

                return _problem(
                    status_code=403,
                    title="CSRF token missing or invalid",
                    detail=f"Provide a matching {CSRF_HEADER} header for state-changing requests.",
                    instance=str(request.url.path),
                )
            response = await call_next(request)
        return response


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)
