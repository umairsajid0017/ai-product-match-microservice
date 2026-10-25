"""
API key authentication middleware.

The AI service should only accept requests from your Laravel backend.
All requests except /health must include the X-Internal-API-Key header.
The service refuses to start without a configured key (see
`app.config.validate_runtime_security`), and requests are denied when it is
missing at runtime.
"""

import hmac

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class InternalAPIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates the X-Internal-API-Key header."""

    # Paths that don't require authentication
    SKIP_PATHS = {"/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        expected = (settings.internal_api_key or "").strip()
        if not expected:
            # Defense in depth: never fail open, even if startup validation is
            # bypassed (for example by constructing the app directly).
            return JSONResponse(
                status_code=503,
                content={"detail": "Service authentication is not configured"},
            )

        provided = (request.headers.get("X-Internal-API-Key") or "").strip()
        if not provided or not hmac.compare_digest(provided, expected):
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: invalid or missing API key"},
            )

        return await call_next(request)
