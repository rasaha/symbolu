"""Ugence Console API — FastAPI application factory.

A dedicated service (separate from the Symbol-U research ``api_server``) that
exposes the consolidated control-plane governed loop and its constituent modules
over one stable HTTP surface for the console frontend.

Run:
    uvicorn ugence_console_api.app:create_app --factory --port 8090
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .audit import AuditStore
from .capabilities import (
    action_control,
    context_gateway,
    operational_safety,
    registry,
    truth_evidence,
)
from .models import (
    ActionRequest,
    ActionVerdict,
    AssertionRequest,
    AssertionVerdict,
    AuditChain,
    ClearanceVerdict,
    GovernedLoopRequest,
    GovernedLoopResult,
    MinimizeRequest,
    MinimizeResult,
    ModuleInfo,
    OperationalSignals,
)
from . import orchestrator, scenarios


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ugence AI Control Plane — Console API",
        version=__version__,
        description="Consolidated governed-execution surface for the Ugence platform's "
                    "Specialized-AI-Systems and AI-Control-Plane layers (excludes KVPro "
                    "and the Cloud Scaling Controller).",
    )
    # The console is served from a separate origin (Vite dev server / static host).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            "modules": {k: {"available": ok, "reason": reason}
                        for k, (ok, reason) in probes.items()},
        }

    @app.get("/v1/modules", response_model=list[ModuleInfo])
    def modules() -> list[ModuleInfo]:
        return registry.MODULES

    @app.get("/v1/scenarios")
    def list_scenarios() -> list[dict]:
        return scenarios.summaries()

    # ---- individual capabilities ---------------------------------------- #
    @app.post("/v1/gateway/minimize", response_model=MinimizeResult)
    def minimize(req: MinimizeRequest) -> MinimizeResult:
        try:
            return context_gateway.minimize(req.units)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/v1/assertions/evaluate", response_model=AssertionVerdict)
    def evaluate_assertion(req: AssertionRequest) -> AssertionVerdict:
        try:
            return truth_evidence.evaluate(req)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/v1/actions/authorize", response_model=ActionVerdict)
    def authorize_action(req: ActionRequest) -> ActionVerdict:
        try:
            return action_control.authorize(req)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/v1/actions/clear", response_model=ClearanceVerdict)
    def clear_action(signals: OperationalSignals) -> ClearanceVerdict:
        return operational_safety.clear(signals)

    # ---- the governed loop ---------------------------------------------- #
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
