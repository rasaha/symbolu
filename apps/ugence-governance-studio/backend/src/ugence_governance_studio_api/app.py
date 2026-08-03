"""Application factory (§5).

``create_app`` is explicit and side-effect-light: it builds the read-only scenario
catalog and the stateless orchestration service once, wires the routers, security
middleware, CORS and typed error handlers, and stores everything on ``app.state``.
No large fixture is loaded at import time and there is no mutable global state.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .api import (
    composition,
    eligibility,
    explanations,
    operational,
    plans,
    ranking,
    scenarios,
    workflows,
)
from .api.deps import AppContext
from .errors import install_error_handlers
from .scenarios.catalog import ScenarioCatalog
from .security.middleware import (
    BodySizeLimitMiddleware,
    RateLimitSeamMiddleware,
    SecurityHeadersMiddleware,
)
from .services.orchestration import AwcOrchestrationService
from .settings import ApiSettings
from .version import API_CONTRACT_VERSION, version_info

_TITLE = "Ugence Governance Studio API"
_SUMMARY = (
    "Deterministic, offline demonstration API over the merged Agent Workforce "
    "Composer v1/v2 planning surface. Synthetic data; planning only; no agent "
    "execution, permission granting or business-action authorization."
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.request_id = "req_" + uuid.uuid4().hex
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request.state.request_id)
        return response


class MediaTypeMiddleware(BaseHTTPMiddleware):
    """Reject non-JSON request bodies with a typed 415."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in {"POST", "PUT", "PATCH"}:
            cl = request.headers.get("content-length")
            has_body = cl is not None and cl != "0"
            ctype = request.headers.get("content-type", "")
            if has_body and not ctype.split(";")[0].strip().lower() == "application/json":
                return JSONResponse(status_code=415, content={
                    "api_version": API_CONTRACT_VERSION,
                    "error": {"code": "unsupported_media_type",
                              "message": "request body must be application/json",
                              "request_id": getattr(request.state, "request_id", None),
                              "diagnostics": [], "safe_details": {}},
                })
        return await call_next(request)


def _openapi_metadata(app: FastAPI, settings: ApiSettings) -> None:
    """Attach deterministic, host-free OpenAPI metadata (§6, §24)."""
    facts = version_info(build_commit=settings.build_commit, build_id=settings.build_id)
    app.openapi_version = "3.1.0"
    # Enrich info with AWC/contract facts (no timestamps, no host URLs).
    app.description = (
        f"{_SUMMARY}\n\n"
        f"- API contract: {API_CONTRACT_VERSION}\n"
        f"- AWC version: {facts['awc_distribution_version']}\n"
        f"- Supported workflow contracts: "
        f"{', '.join(facts['supported_workflow_contracts'])}"
    )


def create_app(settings: Optional[ApiSettings] = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    catalog = ScenarioCatalog.from_settings(settings)
    orchestration = AwcOrchestrationService()

    app = FastAPI(
        title=_TITLE,
        version=API_CONTRACT_VERSION,
        summary=_SUMMARY,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
        servers=[],  # host-free: no server URLs baked into the contract
    )
    app.state.settings = settings
    app.state.ctx = AppContext(settings=settings, catalog=catalog, orchestration=orchestration)

    # Routers.
    app.include_router(operational.router)
    app.include_router(scenarios.router)
    app.include_router(workflows.router)
    app.include_router(eligibility.router)
    app.include_router(ranking.router)
    app.include_router(composition.router)
    app.include_router(explanations.router)
    app.include_router(plans.router)

    # Error handlers.
    install_error_handlers(app)

    # Middleware (added innermost-first; last added is outermost).
    app.add_middleware(MediaTypeMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_request_bytes=settings.max_request_bytes)
    app.add_middleware(RateLimitSeamMiddleware, enabled=settings.enable_rate_limit)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
        )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)

    _openapi_metadata(app, settings)
    return app
