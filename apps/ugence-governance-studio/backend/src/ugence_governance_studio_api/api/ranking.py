"""Ranking evaluation endpoint (§11).

No scoring logic exists in the API service — ranking is delegated to
``awc.rank_eligible_candidates``. Returns role candidate rankings with criterion
contributions, total scores, tie groups, tie-break values, evidence references
and ranking fingerprints.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import ScenarioComputeRequest
from ..serialization.canonical import to_jsonable
from .deps import build_response, get_context, resolve_inputs, scenario_input_digests

router = APIRouter(prefix="/api/v1/ranking", tags=["ranking"])


@router.post("/evaluate", operation_id="evaluate_ranking")
def evaluate_ranking(request: Request, req: ScenarioComputeRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    orch = ctx.orchestration
    adaptation = orch.adapt_v1_frozen(inputs["workflow"], inputs["overlay"] or {})
    _, reports = orch.evaluate_eligibility(
        adaptation, inputs["registry"], inputs["enterprise_policy"],
        inputs["eligibility_policy"], logical_time,
    )
    rankings = orch.rank(adaptation, reports, inputs["registry"], inputs["ranking_policy"], logical_time)
    result = {"rankings": to_jsonable([r for r in rankings])}
    return build_response(
        request, operation="evaluate_ranking", scenario_id=scenario_id,
        source_contract_version=adaptation.source_contract_version, result=result,
        input_digests=scenario_input_digests(inputs),
    )
