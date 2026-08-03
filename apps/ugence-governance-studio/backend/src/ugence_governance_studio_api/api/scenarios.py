"""Scenario endpoints (§8, §10-§12, §15, §16).

All scenario execution endpoints run the REAL AWC pipeline and verify observed
fingerprints against the frozen oracle. Typed non-success domain outcomes
(NO_FEASIBLE_TEAM, etc.) are returned with HTTP 200 — they are valid results.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from starlette.requests import Request

from ..contracts.requests import WhatIfRequest
from ..serialization.canonical import to_jsonable
from ..services.explain import plan_explanation
from ..services.scenario_service import ScenarioService
from .deps import build_response, get_context, require_scenario

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


def _service(ctx) -> ScenarioService:
    return ScenarioService(ctx.catalog, ctx.orchestration)


@router.get("", operation_id="list_scenarios")
def list_scenarios(request: Request):
    ctx = get_context(request)
    return build_response(
        request, operation="list_scenarios",
        result={"scenarios": ctx.catalog.list_metadata()},
    )


@router.get("/{scenario_id}", operation_id="get_scenario")
def get_scenario(request: Request, scenario_id: str):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    sm = ctx.catalog.scenario_manifest(scenario_id)
    meta = ctx.catalog.metadata(scenario_id)
    result = {
        "metadata": meta,
        "manifest": sm,
        "workflow_identity": sm.get("digests", {}).get("workflow_adaptation_fingerprint"),
        "narrative": sm["demonstration"].get("headline"),
        "input_artifacts": list(sm.get("input_files", {}).keys()),
        "expected_outputs": list(sm.get("expected_output_files", {}).keys()),
        "maturity_labels": {"synthetic": True, "planning_only": True},
        "synthetic_data_notice": "Synthetic demonstration data — planning only; no agent execution.",
    }
    return build_response(request, operation="get_scenario", scenario_id=scenario_id, result=result)


@router.get("/{scenario_id}/workflow", operation_id="get_scenario_workflow")
def get_scenario_workflow(request: Request, scenario_id: str):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    projection = _service(ctx).workflow_projection(scenario_id)
    return build_response(
        request, operation="get_scenario_workflow", scenario_id=scenario_id,
        source_contract_version=projection["contract_version"], result=projection,
    )


@router.get("/{scenario_id}/registry", operation_id="get_scenario_registry")
def get_scenario_registry(request: Request, scenario_id: str):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    registry = ctx.catalog.inputs(scenario_id)["registry"]
    return build_response(
        request, operation="get_scenario_registry", scenario_id=scenario_id,
        result={"registry_snapshot": to_jsonable(registry)},
    )


@router.get("/{scenario_id}/eligibility", operation_id="get_scenario_eligibility")
def get_scenario_eligibility(
    request: Request, scenario_id: str, verify_expected: bool = Query(True)
):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    svc = _service(ctx)
    pipeline, _ = svc.run(scenario_id)
    result = {
        "workflow_eligibility": to_jsonable(pipeline.eligibility),
        "role_reports": to_jsonable(list(pipeline.role_reports.values())),
    }
    if verify_expected:
        result["verification"] = svc.verify(scenario_id, pipeline)
    return build_response(
        request, operation="get_scenario_eligibility", scenario_id=scenario_id,
        source_contract_version=pipeline.adaptation.source_contract_version, result=result,
    )


@router.get("/{scenario_id}/ranking", operation_id="get_scenario_ranking")
def get_scenario_ranking(
    request: Request, scenario_id: str, verify_expected: bool = Query(True)
):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    svc = _service(ctx)
    pipeline, _ = svc.run(scenario_id)
    result = {"rankings": to_jsonable([r for r in pipeline.rankings])}
    if verify_expected:
        result["verification"] = svc.verify(scenario_id, pipeline)
    return build_response(
        request, operation="get_scenario_ranking", scenario_id=scenario_id, result=result,
    )


@router.get("/{scenario_id}/plan", operation_id="get_scenario_plan")
def get_scenario_plan(
    request: Request, scenario_id: str, verify_expected: bool = Query(True)
):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    svc = _service(ctx)
    pipeline, _ = svc.run(scenario_id)
    result = {
        "plan_state": pipeline.plan.plan_state.value,
        "agent_team_plan": to_jsonable(pipeline.plan),
        "composition": to_jsonable(pipeline.composition),
        "replay_record": to_jsonable(pipeline.replay),
    }
    if verify_expected:
        result["verification"] = svc.verify(scenario_id, pipeline)
    return build_response(
        request, operation="get_scenario_plan", scenario_id=scenario_id, result=result,
    )


@router.get("/{scenario_id}/export", operation_id="export_scenario")
def export_scenario(request: Request, scenario_id: str):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    bundle = _service(ctx).export_bundle(scenario_id)
    return build_response(
        request, operation="export_scenario", scenario_id=scenario_id, result=bundle,
    )


@router.post("/{scenario_id}/what-if", operation_id="scenario_what_if")
def scenario_what_if(request: Request, scenario_id: str, req: WhatIfRequest):
    ctx = get_context(request)
    require_scenario(ctx, scenario_id)
    from ..scenarios.catalog import LOGICAL_TIME

    lt = LOGICAL_TIME if req.logical_time is None else float(req.logical_time)
    orch = ctx.orchestration

    baseline_inputs = ctx.catalog.inputs(scenario_id)
    baseline = orch.run_pipeline(baseline_inputs, lt)

    perturbed_inputs = ctx.catalog.inputs(scenario_id)  # fresh copy — fixtures untouched
    modified_inputs, eff_time, applied = orch.apply_perturbation(
        perturbed_inputs, req.operation.value, req.params, lt
    )
    modified = orch.run_pipeline(modified_inputs, eff_time)
    diff = orch.compare_plans(baseline.plan, modified.plan)

    from ..serialization.canonical import canonical_digest

    result = {
        "baseline_plan": to_jsonable(baseline.plan),
        "modified_plan": to_jsonable(modified.plan),
        "plan_diff": to_jsonable(diff),
        "perturbation_applied": applied,
        "changed_input_digests": {
            key: canonical_digest(modified_inputs[key])
            for key in modified_inputs
            if key != "scenario_id" and modified_inputs.get(key) is not baseline_inputs.get(key)
        },
        "explanation": plan_explanation(modified),
        "baseline_state": baseline.plan.plan_state.value,
        "modified_state": modified.plan.plan_state.value,
    }
    return build_response(
        request, operation="scenario_what_if", scenario_id=scenario_id, result=result,
    )
