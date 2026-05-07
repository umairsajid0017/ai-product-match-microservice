"""
API key authentication middleware.

The AI service should only accept requests from your Laravel backend.
All requests (except /health) must include the X-Internal-API-Key header.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class InternalAPIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates the X-Internal-API-Key header."""

    # Paths that don't require authentication
    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and docs
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Skip auth if no API key is configured (dev mode)
        if not settings.internal_api_key:
            return await call_next(request)

        key = request.headers.get("X-Internal-API-Key")
        if key != settings.internal_api_key:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: invalid or missing API key"},
            )

        return await call_next(request)
