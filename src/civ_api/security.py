"""Security headers middleware.

Adds a set of defensive HTTP headers to every response:

- ``Content-Security-Policy`` — prevents inline scripts/styles and restricts
  resource loading to ``self``. The Swagger UI (served by FastAPI under
  ``/docs``) requires its own relaxed CSP, applied via a route-specific
  override in ``app.py``.
- ``X-Content-Type-Options: nosniff`` — stops browsers from MIME-sniffing
  JSON/text responses into executable types.
- ``X-Frame-Options: DENY`` — prevents clickjacking by forbidding framing of
  the app (the docs iframe is sandboxed separately).
- ``Referrer-Policy: no-referrer`` — avoids leaking URLs in the Referer header.
- ``Strict-Transport-Security`` — enforces HTTPS for one year once a client
  has spoken to us over TLS. Harmless on plain HTTP (ignored by browsers).

These are belt-and-braces: Pydantic validates all input and all API
responses are JSON, but the headers add defence in depth for the web UI
and any future HTML rendering.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive security headers to every response."""

    DEFAULT_CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self'"
    )

    # Swagger UI (FastAPI's /docs) loads inline scripts/styles, so it needs a
    # more permissive CSP. Kept as narrow as possible while still functional.
    SWAGGER_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        csp = self.SWAGGER_CSP if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi.json") else self.DEFAULT_CSP
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response