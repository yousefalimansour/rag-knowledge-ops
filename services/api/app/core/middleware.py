"""Pure-ASGI middleware (request-id propagation + double-submit CSRF).

Both are written as raw ASGI callables instead of Starlette's
`BaseHTTPMiddleware` because the latter buffers the response body before
forwarding it — fatal for our SSE streaming endpoint, which spends 30+
seconds emitting tokens. Pure ASGI middleware passes `send` through
unchanged so the upstream stream is never consumed by the middleware.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from http.cookies import SimpleCookie
from typing import Any

from app.core.logging import new_request_id, request_id_ctx

logger = logging.getLogger("api.request")

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = b"x-csrf-token"
ACCESS_COOKIE = "access_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _parse_cookies(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    raw = b""
    for name, value in headers:
        if name == b"cookie":
            raw = value
            break
    if not raw:
        return {}
    jar: SimpleCookie[str] = SimpleCookie()
    jar.load(raw.decode("latin-1"))
    return {k: morsel.value for k, morsel in jar.items()}


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    name = name.lower()
    for n, v in headers:
        if n.lower() == name:
            return v
    return None


class RequestContextMiddleware:
    """Generates / propagates `x-request-id`, sets it on the response and
    logs the request completion event without touching the body."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        incoming_rid = _header_value(headers, b"x-request-id")
        rid = incoming_rid.decode("latin-1") if incoming_rid else new_request_id()
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                # Inject x-request-id without consuming the body stream.
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", rid.encode("latin-1")))
                message["headers"] = response_headers
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request.completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope["path"],
                    "status": status_holder["status"],
                    "latency_ms": latency_ms,
                },
            )


class CSRFMiddleware:
    """Double-submit cookie CSRF for cookie-authed state-changing requests.

    Skipped for safe methods, for unauthenticated requests (no access
    cookie), and for explicit exempt paths (login/signup — they're what
    create the cookie). On a mismatch, returns 403 RFC 7807 directly
    without ever entering the app.
    """

    EXEMPT_PATHS = frozenset({"/auth/login", "/auth/signup"})

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        headers = scope.get("headers", [])

        if method in SAFE_METHODS or path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        cookies = _parse_cookies(headers)
        if cookies.get(ACCESS_COOKIE) is None:
            await self.app(scope, receive, send)
            return

        cookie = cookies.get(CSRF_COOKIE)
        header_bytes = _header_value(headers, CSRF_HEADER)
        header = header_bytes.decode("latin-1") if header_bytes else None
        if not cookie or not header or not secrets.compare_digest(cookie, header):
            body = json.dumps(
                {
                    "type": "about:blank",
                    "title": "CSRF token missing or invalid",
                    "status": 403,
                    "detail": (
                        f"Provide a matching {CSRF_HEADER.decode()} header "
                        "for state-changing requests."
                    ),
                    "instance": path,
                }
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/problem+json"),
                        (b"content-length", str(len(body)).encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        await self.app(scope, receive, send)


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)
