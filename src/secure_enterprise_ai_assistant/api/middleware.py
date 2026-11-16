"""Request correlation and security headers for every response."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from secure_enterprise_ai_assistant.core.logs import request_context

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
# Swagger UI loads its assets from jsdelivr; only the documentation pages get this policy.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
)

Handler = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request ID for logs and the audit trail; echo it in ``X-Request-ID``."""

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        incoming = request.headers.get("x-request-id", "")
        with request_context(incoming if _SAFE_REQUEST_ID.match(incoming) else None) as request_id:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative defaults for a JSON API (OWASP Secure Headers)."""

    def __init__(self, app: object, hsts: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        response = await call_next(request)
        is_docs = request.url.path.startswith(DOCS_PATHS)
        response.headers["Content-Security-Policy"] = DOCS_CSP if is_docs else API_CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        if self._hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
