"""Request correlation-ID middleware.

Assigns (or accepts) a correlation id per request, stores it on ``request.state``
and in structlog contextvars, and echoes it back in the ``X-Correlation-ID``
header. Audit events reference this id.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER)
        correlation_id = _sanitize(incoming) or uuid.uuid4().hex
        request.state.correlation_id = correlation_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


def _sanitize(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    # Accept only compact, safe identifiers to avoid log/response injection.
    if 8 <= len(value) <= 64 and all(c.isalnum() or c in "-_" for c in value):
        return value
    return None
