"""Eligibility evaluation endpoint (§10).

Delegates entirely to the AWC eligibility engine. Returns one role eligibility
report per role and one eligibility result per role-agent pair, with eligible /
ineligible / indeterminate counts, elimination reasons, evidence and policy
references and result fingerprints.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import ScenarioComputeRequest
from ..serialization.canonical import to_jsonable
from .deps import build_response, get_context, resolve_inputs, scenario_input_digests

router = APIRouter(prefix="/api/v1/eligibility", tags=["eligibility"])


@router.post("/evaluate", operation_id="evaluate_eligibility")
def evaluate_eligibility(request: Request, req: ScenarioComputeRequest):
    ctx = get_context(request)
    inputs, logical_time, scenario_id = resolve_inputs(ctx, req)
    adaptation = ctx.orchestration.adapt_v1_frozen(inputs["workflow"], inputs["overlay"] or {})
    workflow_result, reports = ctx.orchestration.evaluate_eligibility(
        adaptation, inputs["registry"], inputs["enterprise_policy"],
        inputs["eligibility_policy"], logical_time,
    )
    role_reports = list(reports.values())
    counts = {
        "eligible": sum(len(r.eligible_agent_ids) for r in role_reports),
        "ineligible": sum(len(r.eliminated_agent_ids) for r in role_reports),
        "indeterminate": sum(len(r.indeterminate_agent_ids) for r in role_reports),
    }
    result = {
        "workflow_eligibility": to_jsonable(workflow_result),
        "role_reports": to_jsonable(role_reports),
        "counts": counts,
        "workflow_eligibility_fingerprint": workflow_result.workflow_fingerprint,
    }
    return build_response(
        request, operation="evaluate_eligibility", scenario_id=scenario_id,
        source_contract_version=adaptation.source_contract_version, result=result,
        input_digests=scenario_input_digests(inputs),
    )
