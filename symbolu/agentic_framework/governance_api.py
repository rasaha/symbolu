"""
Governance API — FastAPI External Authorization Service

Thin HTTP wrapper over GovernanceService. Exposes existing agentic framework
governance decisions to external agents via POST /authorize.

ENDPOINTS:
    POST /authorize  — Evaluate an action authorization request
    GET  /health     — Service health check
    GET  /version    — Service version and metadata

USAGE:
    # Start the server:
    uvicorn symbolu.agentic_framework.governance_api:app --host 0.0.0.0 --port 8100

    # Call from any agent:
    curl -X POST http://localhost:8100/authorize \\
      -H "Content-Type: application/json" \\
      -d '{"actor_id": "my-agent", "action_type": "file_read"}'

SECURITY NOTES:
    - Request body limited to 1MB
    - Strict Pydantic validation on all inputs
    - No tool execution — decision only
    - No secrets in audit logs
    - Add API key auth / TLS in production deployment
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from symbolu.agentic_framework.governance_models import (
    AuthorizationRequest,
    AuthorizationResponse,
)
from symbolu.agentic_framework.governance_service import (
    GovernanceService,
    SERVICE_VERSION,
)


# =============================================================================
# Service Singleton
# =============================================================================

_service: GovernanceService | None = None


def get_service() -> GovernanceService:
    """Get or create the governance service singleton."""
    global _service
    if _service is None:
        _service = GovernanceService()
    return _service


def set_service(service: GovernanceService) -> None:
    """Override the governance service (for testing)."""
    global _service
    _service = service


# =============================================================================
# App Configuration
# =============================================================================

MAX_REQUEST_SIZE = 1_048_576  # 1MB


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize service on startup."""
    get_service()
    yield


app = FastAPI(
    title="Symbolu Governance API",
    description=(
        "External authorization service for agentic AI governance. "
        "Evaluates proposed actions against safety contracts, confidence gates, "
        "and risk classification. Does NOT execute actions."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject oversized requests."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": f"Request body too large. Max {MAX_REQUEST_SIZE} bytes."},
        )
    return await call_next(request)


# =============================================================================
# Endpoints
# =============================================================================


@app.post(
    "/authorize",
    response_model=AuthorizationResponse,
    summary="Evaluate action authorization",
    description=(
        "Submit a proposed action for governance evaluation. "
        "Returns ALLOW, DENY, or DEFER with full rationale, risk assessment, "
        "and audit metadata. Does NOT execute the action."
    ),
    responses={
        200: {"description": "Authorization decision returned"},
        422: {"description": "Invalid request schema"},
        500: {"description": "Internal error (fail-closed: DENY)"},
    },
)
async def authorize(request: AuthorizationRequest) -> AuthorizationResponse:
    """
    Evaluate an authorization request from an external agent.

    The request is evaluated against:
    - Tool risk classification (READ_ONLY → PRIVILEGED)
    - Forbidden capability blocking
    - Confidence-gated execution control
    - Safety contract preconditions (6 checks, all-or-nothing)

    Returns a structured governance decision with full audit trail.
    """
    service = get_service()
    return service.authorize(request)


@app.get(
    "/health",
    summary="Health check",
    response_model=Dict[str, Any],
)
async def health() -> Dict[str, Any]:
    """Service health status."""
    service = get_service()
    return {
        "status": "healthy",
        "service": "symbolu-governance-api",
        "version": SERVICE_VERSION,
        "audit_events": service.get_audit_count(),
    }


@app.get(
    "/version",
    summary="Service version",
    response_model=Dict[str, str],
)
async def version() -> Dict[str, str]:
    """Service version and metadata."""
    return {
        "service": "symbolu-governance-api",
        "version": SERVICE_VERSION,
        "framework": "symbolu-agentic-framework",
        "framework_version": "1.7.0",
        "governance_model": "fail-closed-default",
    }
