"""Single-process deployment app (P3E §4, §5).

One ASGI application serves, behind one HTTPS listener and one auth gate:
    /                frontend SPA (index.html)
    /assets/*        frontend build assets
    /api/v1/*        frozen Governance Studio API (create_app)
    /api/v2/*        additive Governed Agent Studio API (create_v2_app), mounted behind v1
                     by create_combined_app (CR-2); the review screens relay to the
                     governed review service named by UGENCE_STUDIO_REVIEW_SERVICE_URL
                     and report a typed gap when it is unset
    /health /ready /version   frozen operational endpoints (authenticated)
    /healthz         minimal deployment liveness (unauthenticated)
    /readyz          deployment readiness (unauthenticated)

The frozen backend is imported unmodified; the SPA fallback never captures /api/*.
The approver-proof header (ID-1) is not read here: it travels through this process to
the v2 decision route and from there to the review service, verbatim, and is never
logged or stored.
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
    OriginGuardMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
)

_BACKEND_PATHS = ("/health", "/ready", "/version", "/docs", "/redoc", "/openapi.json")


def _build_backend(config: DeploymentConfig):
    """Instantiate the FROZEN v1 backend with v2 mounted behind it (CR-2), pinned to
    the synthetic scenario root.

    The v2 studio context receives from this deployment: the review service base URL
    (CR-2); when a registry path is configured, the activation root of front-door seam
    1 (FD-5); and when policy identities are configured too, the Authority screen's
    read-only, tenant-bound registry view and those identities (seam 2, FD-6); and
    when the simulation provider is enabled, a registry holding the one pinned
    in-image provider (seam 3, FD-7); and when a system registry path is configured,
    the tenant-bound system registry the Registration screen records into, with this
    deployment's name and version as ``registered_by`` (seam 5, FD-9); and when a
    data-use declarations path is configured, the tenant-bound declarations file the
    Data use screen declares into, with this deployment's name and version as the
    recording composition (seam 8, FD-12). No decision
    store, governance hook (FD-7.3: the runtime's fail-closed default stays; FD-7.5:
    nothing permissive is ever handed) or console URL: those screens report their
    gaps rather than a stand-in.
    """
    from ugence_governance_studio_api.app_v2 import build_studio_context, create_combined_app
    from ugence_governance_studio_api.settings import ApiSettings

    settings = ApiSettings(
        environment="production",
        cors_allowed_origins=[],          # deployment origin guard handles cross-origin
        enable_docs=False,                # no unauthenticated docs/openapi surface
        enable_authentication=False,      # deployment access gate performs authentication
        scenario_root=os.path.abspath(config.scenarios_root),
    )
    activation_root = None
    policy_registry = None
    policy_identities: tuple = ()
    if config.constitution_registry_path:
        from .activation import (
            ReadOnlyTenantBoundRegistry,
            build_studio_activation_root_over,
            open_studio_policy_registry,
        )

        # One registry, opened once: the activation root (seam 1) and the Authority
        # screen's read-only, tenant-bound view (seam 2) share the same instance.
        registry = open_studio_policy_registry(config.constitution_registry_path,
                                               production_mode=config.is_production)
        activation_root = build_studio_activation_root_over(registry)
        if config.policy_identities:
            policy_registry = ReadOnlyTenantBoundRegistry(registry, tenant_id=config.tenant_id)
            policy_identities = tuple(f"{entry}|{config.tenant_id}" for entry in config.policy_identities)
    provider_registry = None
    if config.simulation_provider_enabled:
        from .simulation import build_simulation_registry

        provider_registry = build_simulation_registry()
    system_registry = None
    registered_by = ""
    if config.system_registry_path:
        from .registration import REGISTERED_BY, open_system_registry

        system_registry = open_system_registry(config.system_registry_path, tenant_id=config.tenant_id,
                                               production_mode=config.is_production)
        registered_by = REGISTERED_BY
    data_use_declarations = None
    recorded_by = ""
    if config.data_use_declarations_path:
        from .declarations import RECORDED_BY, open_data_use_declarations

        data_use_declarations = open_data_use_declarations(
            config.data_use_declarations_path, tenant_id=config.tenant_id,
            production_mode=config.is_production)
        recorded_by = RECORDED_BY
    studio = build_studio_context(
        activation_root=activation_root,
        policy_registry=policy_registry,
        policy_identities=policy_identities,
        provider_registry=provider_registry,
        review_service_base_url=config.review_service_url or None,
        system_registry=system_registry,
        registered_by=registered_by,
        data_use_declarations=data_use_declarations,
        recorded_by=recorded_by,
    )
    from .simulation import refuse_permissive_hook

    refuse_permissive_hook(studio)  # FD-7.5, before anything binds
    return create_combined_app(settings, studio=studio)


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
