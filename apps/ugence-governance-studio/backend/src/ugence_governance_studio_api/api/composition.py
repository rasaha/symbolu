"""Composition endpoint (§12).

Runs the full team-composition pipeline through AWC and returns the composition
result, permission-bound proposals, fallback plans and the AgentTeamPlan. A
typed non-success state (NO_FEASIBLE_TEAM, SEARCH_SPACE_EXCEEDED, PARTIAL,
INVALID_INPUT) is a valid HTTP 200 domain result — never a 500.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import ScenarioComputeRequest
from ..serialization.canonical import to_jsonable
from .deps import build_response, get_context, resolve_inputs, scenario_input_digests

router = APIRouter(prefix="/api/v1/composition", tags=["composition"])


@router.post("/compose", operation_id="compose_workforce")
def compose_workforce(request: Request, req: ScenarioComputeRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    pipeline = ctx.orchestration.run_pipeline(inputs, logical_time)
    plan = pipeline.plan
    result = {
        "composition_state": pipeline.composition.composition_state.value,
        "plan_state": plan.plan_state.value,
        "composition": to_jsonable(pipeline.composition),
        "role_assignments": to_jsonable(plan.role_assignments),
        "team_constraint_results": to_jsonable(plan.team_constraint_results),
        "team_objective_results": to_jsonable(plan.team_objective_results),
        "search_statistics": to_jsonable(plan.search_statistics),
        "permission_bound_proposals": to_jsonable(plan.permission_bound_proposals),
        "role_fallback_plans": to_jsonable(plan.role_fallback_plans),
        "unfilled_roles": list(plan.unfilled_roles),
        "agent_team_plan": to_jsonable(plan),
        "plan_fingerprint": plan.plan_fingerprint,
    }
    return build_response(
        request, operation="compose_workforce", scenario_id=scenario_id,
        source_contract_version=pipeline.adaptation.source_contract_version, result=result,
        input_digests=scenario_input_digests(inputs),
    )
