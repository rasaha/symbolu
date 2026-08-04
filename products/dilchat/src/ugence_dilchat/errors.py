"""Structured error model (RFC 7807-style problem+json) and canonical error codes.

Every API error is emitted as a ``Problem`` envelope with a stable machine
``code``. Cross-private access uses ``NOT_FOUND`` (never ``FORBIDDEN``) so the
existence of another user's private resource is not disclosed (INV-9).
"""

from __future__ import annotations

import enum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, enum.Enum):
    # Auth
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_SESSION_REVOKED = "AUTH_SESSION_REVOKED"
    AUTH_REFRESH_REUSE = "AUTH_REFRESH_REUSE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    # Authorization / scope
    SCOPE_DENIED = "SCOPE_DENIED"
    COUPLE_NOT_ACTIVE = "COUPLE_NOT_ACTIVE"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    # Resources
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    # Invitations
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_USED = "INVITATION_USED"
    INVITATION_INVALID = "INVITATION_INVALID"
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AMBIGUOUS_LOCAL_TIME = "AMBIGUOUS_LOCAL_TIME"
    NONEXISTENT_LOCAL_TIME = "NONEXISTENT_LOCAL_TIME"
    # Astrology
    EPHEMERIS_UNAVAILABLE = "EPHEMERIS_UNAVAILABLE"
    PROVIDER_DISABLED = "PROVIDER_DISABLED"
    # Generic
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL = "INTERNAL"


_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_SESSION_REVOKED: 401,
    ErrorCode.AUTH_REFRESH_REUSE: 401,
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.SCOPE_DENIED: 403,
    ErrorCode.COUPLE_NOT_ACTIVE: 403,
    ErrorCode.CONSENT_REQUIRED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.INVITATION_EXPIRED: 409,
    ErrorCode.INVITATION_USED: 409,
    ErrorCode.INVITATION_INVALID: 404,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.AMBIGUOUS_LOCAL_TIME: 422,
    ErrorCode.NONEXISTENT_LOCAL_TIME: 422,
    ErrorCode.EPHEMERIS_UNAVAILABLE: 503,
    ErrorCode.PROVIDER_DISABLED: 503,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL: 500,
}


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: ErrorCode
    detail: str | None = None
    correlation_id: str | None = None
    errors: list[dict[str, Any]] | None = None


class DilChatError(Exception):
    """Base application error carrying a canonical code."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str | None = None,
        *,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.status = _STATUS_BY_CODE[code]
        self.detail = detail
        self.errors = errors
        super().__init__(detail or code.value)

    def to_problem(self, correlation_id: str | None = None) -> Problem:
        return Problem(
            title=self.code.value.replace("_", " ").title(),
            status=self.status,
            code=self.code,
            detail=self.detail,
            correlation_id=correlation_id,
            errors=self.errors,
        )


# Convenience constructors for the most security-sensitive cases.
def not_found(detail: str | None = None) -> DilChatError:
    """Uniform 404 used for genuine absence AND for existence non-disclosure."""
    return DilChatError(ErrorCode.NOT_FOUND, detail)


def scope_denied(detail: str | None = None) -> DilChatError:
    return DilChatError(ErrorCode.SCOPE_DENIED, detail)


async def dilchat_error_handler(request: Request, exc: DilChatError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    problem = exc.to_problem(correlation_id)
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    problem = Problem(
        title="Internal Server Error",
        status=500,
        code=ErrorCode.INTERNAL,
        detail=None,  # never leak internals
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=500,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )
