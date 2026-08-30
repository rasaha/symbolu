"""Single-process deployment app (P3E §4, §5).

One ASGI application serves, behind one HTTPS listener and one auth gate:
    /                frontend SPA (index.html)
    /assets/*        frontend build assets
    /api/v1/*        frozen Governance Studio API (create_app)
    /health /ready /version   frozen operational endpoints (authenticated)
    /healthz         minimal deployment liveness (unauthenticated)
    /readyz          deployment readiness (unauthenticated)

The frozen backend is imported unmodified; the SPA fallback never captures /api/*.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from . import DEPLOYMENT_NAME
from .access_control import AccessGate, FailureTracker
from .config import DeploymentConfig
from .middleware import (
    BodySizeLimitMiddleware,
    ForwardedProtoGuardMiddleware,
    OriginGuardMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
)

_BACKEND_PATHS = ("/health", "/ready", "/version", "/docs", "/redoc", "/openapi.json")


def _build_backend(config: DeploymentConfig):
    """Instantiate the FROZEN backend, pinned to the synthetic scenario root."""
    from ugence_governance_studio_api.app import create_app
    from ugence_governance_studio_api.settings import ApiSettings

    settings = ApiSettings(
        environment="production",
        cors_allowed_origins=[],          # deployment origin guard handles cross-origin
        enable_docs=False,                # no unauthenticated docs/openapi surface
        enable_authentication=False,      # deployment access gate performs authentication
        scenario_root=os.path.abspath(config.scenarios_root),
    )
    return create_app(settings)


class _Dispatcher:
    """Route by path: backend API, static assets, SPA fallback, deployment health."""

    def __init__(self, config: DeploymentConfig, backend, readiness):
        self.config = config
        self.backend = backend
        self.readiness = readiness
        self.static = StaticFiles(directory=config.frontend_dir)
        self.index = os.path.join(config.frontend_dir, "index.html")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.backend(scope, receive, send)
        path = scope.get("path", "/")
        method = scope.get("method", "GET").upper()

        if path == "/healthz":
            return await JSONResponse({"status": "ok"})(scope, receive, send)
        if path == "/readyz":
            ready = self.readiness()
            body = {"status": "ready" if ready else "not_ready", "deployment": DEPLOYMENT_NAME}
            return await JSONResponse(body, status_code=200 if ready else 503)(scope, receive, send)

        if path.startswith("/api/") or path in _BACKEND_PATHS:
            return await self.backend(scope, receive, send)

        if path.startswith("/assets/"):
            return await self.static(scope, receive, send)

        # SPA fallback: only safe GET/HEAD for non-API routes
        if method in ("GET", "HEAD") and os.path.isfile(self.index):
            return await FileResponse(self.index, media_type="text/html")(scope, receive, send)
        return await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)


def build_app(config: DeploymentConfig, *, readiness=None, tracker: Optional[FailureTracker] = None, sleep=None):
    """Assemble the wrapped ASGI application (assumes startup integrity already passed)."""
    backend = _build_backend(config)
    ready_fn = readiness or (lambda: True)
    dispatcher = _Dispatcher(config, backend, ready_fn)

    # innermost -> outermost
    app = BodySizeLimitMiddleware(dispatcher, max_bytes=config.max_request_bytes)
    app = OriginGuardMiddleware(app, config)
    gate = AccessGate(config, tracker=tracker, sleep=sleep)
    app = BaseHTTPMiddleware(app, dispatch=gate.dispatch)
    app = TrustedHostMiddleware(app, config.allowed_hosts)
    if not config.terminates_tls:
        # The platform terminated TLS, so there is no handshake here to guarantee the
        # client leg was encrypted. Enforce it from the forwarded protocol instead,
        # outside the auth gate so a plaintext request is refused before credentials
        # are read from it.
        app = ForwardedProtoGuardMiddleware(app)
    app = SecurityHeadersMiddleware(app)  # outermost: headers on every response
    return app


def load_frontend_marker(frontend_dir: str) -> dict:
    marker = os.path.join(os.path.dirname(os.path.abspath(frontend_dir)), "frontend-build.json")
    if os.path.isfile(marker):
        try:
            return json.load(open(marker, encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}
