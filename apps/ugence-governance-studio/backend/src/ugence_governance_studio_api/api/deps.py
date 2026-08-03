"""Shared request context, envelope building and input resolution.

Routers stay thin: they resolve pinned inputs, call the orchestration service,
serialize the AWC result through the canonical projection, and wrap it in the
standard envelope. No policy logic lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import ugence_agent_workforce_composer.api as awc
from starlette.requests import Request

from ..contracts.envelope import ApiResponse, Diagnostic
from ..errors import ApiException
from ..scenarios.catalog import LOGICAL_TIME, ScenarioCatalog, ScenarioNotFound
from ..serialization.canonical import canonical_digest, to_jsonable
from ..services.orchestration import AwcOrchestrationService
from ..settings import ApiSettings

# Inline policy field → AWC model, for validating inline pinned inputs.
_INLINE_POLICY_MODELS: Dict[str, Any] = {
    "enterprise_policy": awc.EnterpriseAgentPolicy,
    "eligibility_policy": awc.EligibilityPolicy,
    "ranking_policy": awc.AgentRankingPolicy,
    "composition_policy": awc.TeamCompositionPolicy,
    "permission_policy": awc.PermissionBoundingPolicy,
    "fallback_policy": awc.AgentFallbackPolicy,
}


@dataclass
class AppContext:
    settings: ApiSettings
    catalog: ScenarioCatalog
    orchestration: AwcOrchestrationService


def get_context(request: Request) -> AppContext:
    return request.app.state.ctx


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def build_response(
    request: Request,
    *,
    operation: str,
    result: Any,
    scenario_id: Optional[str] = None,
    source_contract_version: Optional[str] = None,
    input_digests: Optional[Dict[str, str]] = None,
    diagnostics: Optional[List[Diagnostic]] = None,
    warnings: Optional[List[str]] = None,
) -> ApiResponse:
    return ApiResponse(
        request_id=request_id(request),
        operation=operation,
        scenario_id=scenario_id,
        source_contract_version=source_contract_version,
        awc_version=awc.__version__,
        input_digests=input_digests or {},
        result=to_jsonable(result),
        diagnostics=diagnostics or [],
        warnings=warnings or [],
    )


def require_scenario(ctx: AppContext, scenario_id: str) -> None:
    if scenario_id not in ctx.catalog.scenario_ids:
        raise ApiException(404, "scenario_not_found", f"unknown scenario {scenario_id!r}")


def validate_inline_inputs(inline) -> Dict[str, Any]:
    """Validate an :class:`InlineInputs` request block into AWC models.

    Validation failure surfaces as a 422 through the router. No filesystem or
    network access is performed.
    """
    data = inline.model_dump()
    try:
        s: Dict[str, Any] = {
            "scenario_id": None,
            "workflow": data["workflow"],
            "overlay": data.get("overlay") or {},
            "registry": awc.AgentRegistrySnapshot.model_validate(data["registry"]),
        }
        for key, model in _INLINE_POLICY_MODELS.items():
            s[key] = model.model_validate(data[key])
    except ApiException:
        raise
    except Exception as exc:  # invalid AWC artifact
        raise ApiException(422, "invalid_artifact", f"inline input failed AWC validation: {exc}")
    return s


def resolve_inputs(ctx: AppContext, req) -> Tuple[Dict[str, Any], float, Optional[str]]:
    """Resolve a scenario-or-inline compute request into (inputs, logical_time,
    scenario_id)."""
    logical_time = LOGICAL_TIME if req.logical_time is None else float(req.logical_time)
    if getattr(req, "scenario_id", None) is not None:
        require_scenario(ctx, req.scenario_id)
        return ctx.catalog.inputs(req.scenario_id), logical_time, req.scenario_id
    if getattr(req, "inputs", None) is not None:
        return validate_inline_inputs(req.inputs), logical_time, None
    raise ApiException(400, "missing_inputs", "provide scenario_id or inline inputs")


def scenario_input_digests(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Canonical per-input digests for envelope transparency (operational)."""
    digests: Dict[str, str] = {}
    for key, value in inputs.items():
        if key == "scenario_id" or value is None:
            continue
        digests[key] = canonical_digest(value)
    return digests
