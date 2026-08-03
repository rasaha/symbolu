"""Plan replay and comparison endpoints (§14).

Replay recomputes a plan from pinned inputs and compares its fingerprint against
the expected oracle (or an inline expected plan). Comparison diffs two
deterministically-produced plans. No filesystem paths are accepted.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import ComparePlansRequest, PlanSource, ReplayRequest
from ..errors import ApiException
from ..scenarios.catalog import LOGICAL_TIME
from ..serialization.canonical import to_jsonable
from .deps import build_response, get_context, require_scenario, resolve_inputs

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


@router.post("/replay", operation_id="replay_plan")
def replay_plan(request: Request, req: ReplayRequest):
    ctx = get_context(request)
    orch = ctx.orchestration

    if req.scenario_id is not None:
        require_scenario(ctx, req.scenario_id)
        lt = LOGICAL_TIME if req.logical_time is None else float(req.logical_time)
        inputs = ctx.catalog.inputs(req.scenario_id)
        pipeline = orch.run_pipeline(inputs, lt)
        observed_fp = pipeline.plan.plan_fingerprint
        if req.expected_plan is not None:
            expected_fp = req.expected_plan.get("plan_fingerprint")
        else:
            expected_fp = ctx.catalog.expected_fingerprints(req.scenario_id)["plan_fingerprint"]
        scenario_id = req.scenario_id
    else:
        inputs, lt, scenario_id = resolve_inputs(ctx, req)
        pipeline = orch.run_pipeline(inputs, lt)
        observed_fp = pipeline.plan.plan_fingerprint
        expected_fp = (req.expected_plan or {}).get("plan_fingerprint", observed_fp)

    match = observed_fp == expected_fp
    diagnostics = [] if match else [
        {"code": "replay_mismatch", "message": "replayed plan fingerprint differs from expected",
         "severity": "error"}
    ]
    result = {
        "expected_plan_fingerprint": expected_fp,
        "replayed_plan_fingerprint": observed_fp,
        "match": match,
        "plan_state": pipeline.plan.plan_state.value,
        "replay_record": to_jsonable(pipeline.replay),
        "diagnostics": diagnostics,
    }
    return build_response(
        request, operation="replay_plan", scenario_id=scenario_id, result=result,
    )


def _plan_for_source(ctx, source: PlanSource):
    require_scenario(ctx, source.scenario_id)
    lt = LOGICAL_TIME if source.logical_time is None else float(source.logical_time)
    inputs = ctx.catalog.inputs(source.scenario_id)
    if source.perturbation is not None:
        if source.perturbation.operation not in ctx.orchestration.SUPPORTED_PERTURBATIONS:
            raise ApiException(
                422, "unsupported_perturbation",
                f"unsupported perturbation {source.perturbation.operation!r}")
        inputs, lt, _ = ctx.orchestration.apply_perturbation(
            inputs, source.perturbation.operation, source.perturbation.params, lt)
    return ctx.orchestration.run_pipeline(inputs, lt).plan


@router.post("/compare", operation_id="compare_plans")
def compare_plans(request: Request, req: ComparePlansRequest):
    ctx = get_context(request)
    left = _plan_for_source(ctx, req.left)
    right = _plan_for_source(ctx, req.right)
    diff = ctx.orchestration.compare_plans(left, right)
    result = {
        "diff": to_jsonable(diff),
        "same_workflow": diff.same_workflow,
        "workflow_mismatch": diff.workflow_mismatch,
        "plan_a_fingerprint": diff.plan_a_fingerprint,
        "plan_b_fingerprint": diff.plan_b_fingerprint,
        "snapshot_changed": diff.snapshot_changed,
    }
    return build_response(request, operation="compare_plans", result=result)
