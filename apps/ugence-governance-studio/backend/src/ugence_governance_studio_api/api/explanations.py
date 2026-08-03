"""Explanation endpoints (§13).

These serialize existing AWC explanation outputs into frontend-friendly
projections. They invent no reasons — every condition, reason, evidence ref and
selection state comes from AWC result objects.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import ExplanationRequest
from ..services.explain import eligibility_explanation, plan_explanation, ranking_explanation
from .deps import build_response, get_context, resolve_inputs

router = APIRouter(prefix="/api/v1/explanations", tags=["explanations"])


@router.post("/eligibility", operation_id="explain_eligibility")
def explain_eligibility(request: Request, req: ExplanationRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    orch = ctx.orchestration
    adaptation = orch.adapt_v1_frozen(inputs["workflow"], inputs["overlay"] or {})
    _, reports = orch.evaluate_eligibility(
        adaptation, inputs["registry"], inputs["enterprise_policy"],
        inputs["eligibility_policy"], logical_time,
    )
    result = eligibility_explanation(reports, req.role_id)
    return build_response(
        request, operation="explain_eligibility", scenario_id=scenario_id, result=result,
    )


@router.post("/ranking", operation_id="explain_ranking")
def explain_ranking(request: Request, req: ExplanationRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    orch = ctx.orchestration
    adaptation = orch.adapt_v1_frozen(inputs["workflow"], inputs["overlay"] or {})
    _, reports = orch.evaluate_eligibility(
        adaptation, inputs["registry"], inputs["enterprise_policy"],
        inputs["eligibility_policy"], logical_time,
    )
    rankings = orch.rank(adaptation, reports, inputs["registry"], inputs["ranking_policy"], logical_time)
    result = ranking_explanation(rankings)
    return build_response(
        request, operation="explain_ranking", scenario_id=scenario_id, result=result,
    )


@router.post("/plan", operation_id="explain_plan")
def explain_plan(request: Request, req: ExplanationRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    pipeline = ctx.orchestration.run_pipeline(inputs, logical_time)
    result = plan_explanation(pipeline)
    return build_response(
        request, operation="explain_plan", scenario_id=scenario_id, result=result,
    )
