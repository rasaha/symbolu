"""Security middleware seams (§21).

* ``SecurityHeadersMiddleware`` — sets conservative response headers on every
  response.
* ``BodySizeLimitMiddleware`` — rejects request bodies over the configured limit
  with a typed 413 (before the body is parsed).
* ``RateLimitSeamMiddleware`` — a disabled-by-default seam; when enabled it is a
  no-op placeholder so the wiring exists without introducing shared mutable state
  or a real limiter in P3B.

Authentication is intentionally NOT implemented here — a disabled seam lives in
``security/auth.py`` and belongs to a later phase.
"""
from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


class BodySizeLimitMiddleware:
    """Pure-ASGI request-body cap.

    Buffers the request body (enforcing the byte ceiling as it reads) BEFORE the
    application sees it, then replays the buffered body downstream. Requests over
    the limit get a typed 413 and the application is never invoked. Implemented as
    pure ASGI (not ``BaseHTTPMiddleware``) so body replay is reliable.
    """

    def __init__(self, app, max_request_bytes: int):
        self.app = app
        self._max = max_request_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers") or []}
        cl = headers.get(b"content-length")
        if cl is not None:
            try:
                if int(cl) > self._max:
                    return await self._reject(send)
            except ValueError:
                pass

        body = b""
        more = True
        while more:
            message = await receive()
            if message.get("type") != "http.request":
                # forward non-body events untouched by short-circuiting to app
                async def _passthrough(_msg=message):
                    return _msg
                return await self.app(scope, _passthrough, send)
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > self._max:
                while more:  # drain the remainder before responding
                    drained = await receive()
                    more = drained.get("more_body", False)
                return await self._reject(send)

        replayed = {"sent": False}

        async def buffered_receive():
            if not replayed["sent"]:
                replayed["sent"] = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        return await self.app(scope, buffered_receive, send)

    async def _reject(self, send):
        payload = json.dumps({
            "api_version": "governance_studio.api.v1",
            "error": {"code": "request_too_large",
                      "message": f"request body exceeds {self._max} bytes",
                      "request_id": None, "diagnostics": [], "safe_details": {}},
        }).encode("utf-8")
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})


class RateLimitSeamMiddleware(BaseHTTPMiddleware):
    """Disabled-by-default rate-limit seam. Enabled only wires an identity pass so
    the seam is exercisable without a real limiter or shared mutable state."""

    def __init__(self, app, enabled: bool):
        super().__init__(app)
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if self._enabled:
            response.headers.setdefault("X-RateLimit-Seam", "enabled")
        return response


def _rid(request: Request):
    return getattr(request.state, "request_id", None)
