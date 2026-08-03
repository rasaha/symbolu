"""Typed API errors and exception handlers (§18).

HTTP mapping:
    400  malformed request envelope / bad parameter
    404  unknown scenario or resource
    409  incompatible workflow/overlay conflict
    413  request too large (enforced in middleware)
    422  schema or input validation failure
    429  rate-limit boundary (seam)
    500  unexpected internal failure (sanitized; never a stack trace in prod)
    503  service not ready

Typed AWC non-success domain outcomes (NO_FEASIBLE_TEAM, NO_ELIGIBLE_AGENT,
SEARCH_SPACE_EXCEEDED, PARTIAL, INVALID_INPUT) are NOT errors — they are returned
as ordinary 200 domain results by the routers and never reach these handlers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from .contracts.envelope import ApiError, Diagnostic, ErrorEnvelope


class ApiException(Exception):
    """A typed, HTTP-mapped API error raised by routers/services."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        field_path: Optional[str] = None,
        diagnostics: Optional[List[Diagnostic]] = None,
        safe_details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_path = field_path
        self.diagnostics = diagnostics or []
        self.safe_details = safe_details or {}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_response(request: Request, status_code: int, code: str, message: str,
                    *, field_path=None, diagnostics=None, safe_details=None) -> JSONResponse:
    envelope = ErrorEnvelope(error=ApiError(
        code=code, message=message, field_path=field_path,
        diagnostics=diagnostics or [], request_id=_request_id(request),
        safe_details=safe_details or {},
    ))
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _handle_api(request: Request, exc: ApiException):
        return _error_response(
            request, exc.status_code, exc.code, exc.message,
            field_path=exc.field_path, diagnostics=exc.diagnostics, safe_details=exc.safe_details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first_path = None
        if errors:
            loc = errors[0].get("loc", ())
            first_path = ".".join(str(p) for p in loc)
        diagnostics = [
            Diagnostic(code=str(e.get("type", "validation_error")),
                       message=str(e.get("msg", "")),
                       severity="error",
                       field_path=".".join(str(p) for p in e.get("loc", ())))
            for e in errors[:20]
        ]
        return _error_response(
            request, 422, "validation_error",
            "request failed schema or input validation",
            field_path=first_path, diagnostics=diagnostics,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed", 415: "unsupported_media_type"}.get(
            exc.status_code, "http_error")
        return _error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        # Sanitized: never leak a stack trace or internal message in production.
        settings = getattr(request.app.state, "settings", None)
        message = "an unexpected internal error occurred"
        safe: Dict[str, Any] = {}
        if settings is not None and not settings.is_production:
            safe = {"exception_type": type(exc).__name__}
        return _error_response(request, 500, "internal_error", message, safe_details=safe)
