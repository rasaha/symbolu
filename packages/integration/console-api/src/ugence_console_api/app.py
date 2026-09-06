"""Ugence Console API — FastAPI application factory.

A dedicated service (separate from the Symbol-U research ``api_server``) that serves
the consolidated control-plane governed loop over one stable HTTP surface.

**What this application serves is closed (ruling CP-3).** Five routes: the four the
studio's frozen allowlist already names — two shadow-only governed-loop writes and two
audit reads — plus ``/health``. The three governance verbs (``/v1/actions/authorize``,
``/v1/actions/clear``, ``/v1/assertions/evaluate``) and the three introspection routes
(``/v1/modules``, ``/v1/scenarios``, ``/v1/gateway/minimize``) are **not served by the
packaged unit** until separately ruled. The underlying capabilities still exist and the
loop still runs all four of them in order; that is the point of the ruling — *a
capability does not become public API because the underlying function exists*. Each new
external surface is separately authorized, so the way to add one is an owner ruling,
not an added decorator.

**Every answer declares the audit ceiling (ruling CP-4).** The store is in-memory, and
:data:`~ugence_console_api.models.AUDIT_CEILING` rides on all five answers as the
``X-Ugence-Audit-Ceiling`` header, and inside the body of the two that carry a decision
trail. Nothing here infers durability from silence.

Run:
    uvicorn ugence_console_api.app:create_app --factory --port 8090
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .audit import AuditStore
from .capabilities import (
    action_control,
    context_gateway,
    operational_safety,
    truth_evidence,
)
from .models import (
    AUDIT_CEILING,
    AuditChain,
    GovernedLoopRequest,
    GovernedLoopResult,
)
from . import orchestrator, scenarios

#: CP-3. The complete served surface, as (method, path) pairs. The test suite asserts
#: the running application's routes are exactly this set, so a route added without a
#: ruling fails the build rather than reaching a deployment.
SERVED_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/health"),
    ("POST", "/v1/governed-loop/shadow"),
    ("POST", "/v1/governed-loop/scenario/{scenario_id}"),
    ("GET", "/v1/audit"),
    ("GET", "/v1/audit/{correlation_id}"),
)

#: CP-3. Routes the source once served and the packaged unit does not, recorded here
#: rather than deleted from memory: three governance verbs and three introspection
#: reads. Each needs its own ruling before it returns.
WITHHELD_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/v1/assertions/evaluate"),
    ("POST", "/v1/actions/authorize"),
    ("POST", "/v1/actions/clear"),
    ("GET", "/v1/modules"),
    ("GET", "/v1/scenarios"),
    ("POST", "/v1/gateway/minimize"),
)

#: CP-4. The header that carries the ceiling on every answer, including error answers.
AUDIT_CEILING_HEADER = "X-Ugence-Audit-Ceiling"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ugence AI Control Plane — Console API",
        version=__version__,
        description="The governed loop in SHADOW, and its in-process audit trail. "
                    "Serves two shadow-only writes and two audit reads (CP-3); grants, "
                    "authorizes, clears and executes on no surface it serves. Its audit "
                    "is one process's view, lost on restart (CP-4).",
    )
    # The console is served from a separate origin (Vite dev server / static host).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def declare_the_audit_ceiling(request: Request, call_next):
        """CP-4: no answer leaves without the ceiling, errors included."""
        response = await call_next(request)
        response.headers[AUDIT_CEILING_HEADER] = AUDIT_CEILING
        return response

    audit = AuditStore()

    # ---- meta ----------------------------------------------------------- #
    @app.get("/health")
    def health() -> dict:
        probes = {
            "context_minimization": context_gateway.available(),
            "tap": truth_evidence.available(),
            "actiongate": action_control.available(),
            "autonomous_control_plane": operational_safety.available(),
        }
        return {
            "status": "ok",
            "version": __version__,
            "audit_ceiling": AUDIT_CEILING,
            "modules": {k: {"available": ok, "reason": reason}
                        for k, (ok, reason) in probes.items()},
        }

    # ---- the governed loop (shadow only) -------------------------------- #
    @app.post("/v1/governed-loop/shadow", response_model=GovernedLoopResult)
    def governed_loop(req: GovernedLoopRequest) -> GovernedLoopResult:
        try:
            return orchestrator.run(req, audit)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/v1/governed-loop/scenario/{scenario_id}", response_model=GovernedLoopResult)
    def governed_loop_scenario(scenario_id: str) -> GovernedLoopResult:
        scenario = scenarios.SCENARIOS.get(scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail=f"unknown scenario '{scenario_id}'")
        # Fresh copy so each run gets its own correlation id.
        req = scenario["request"].model_copy(deep=True)
        req.correlation_id = None
        try:
            return orchestrator.run(req, audit)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    # ---- audit & reconstruction ----------------------------------------- #
    @app.get("/v1/audit", response_model=list[str])
    def audit_ids() -> list[str]:
        return audit.list_ids()

    @app.get("/v1/audit/{correlation_id}", response_model=AuditChain)
    def audit_chain(correlation_id: str) -> AuditChain:
        chain = audit.get(correlation_id)
        if chain is None:
            raise HTTPException(status_code=404, detail=f"no record for '{correlation_id}'")
        return chain

    return app


app = create_app()
