"""Workflow validation & adaptation endpoints (§9).

Adaptation dispatches EXPLICITLY by declared contract version; unknown/unsupported
versions fail closed with a typed 422. Version is never guessed from field
presence.
"""
from __future__ import annotations

import ugence_agent_workforce_composer.api as awc
from fastapi import APIRouter
from starlette.requests import Request

from ..contracts.requests import (
    AdaptWorkflowRequest,
    CompareAdaptationsRequest,
    ValidateWorkflowRequest,
)
from ..errors import ApiException
from ..scenarios.catalog import LOGICAL_TIME
from ..serialization.canonical import canonical_digest, to_jsonable
from .deps import build_response, get_context, require_scenario

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def _normalize_contract(document, contract_version) -> str:
    return contract_version or awc.declared_contract_version(document)


@router.post("/validate", operation_id="validate_workflow")
def validate_workflow(request: Request, req: ValidateWorkflowRequest):
    declared = _normalize_contract(req.workflow, req.contract_version)
    supported = declared in awc.SUPPORTED_COMPILER_CONTRACTS
    integrity = {"checked": req.source_digest is not None}
    if req.source_digest is not None:
        computed = canonical_digest(req.workflow)
        integrity["source_digest"] = req.source_digest
        integrity["computed_digest"] = computed
        integrity["match"] = computed.endswith(req.source_digest) or computed == req.source_digest

    diagnostics = []
    valid = supported
    envelope = None
    if supported:
        envelope = awc.adapt_workflow(req.workflow, contract_version=declared)
        valid = envelope.ok
        diagnostics = to_jsonable(envelope.diagnostics)

    result = {
        "validation_state": "VALID" if valid else "INVALID",
        "declared_contract_version": declared,
        "supported_version": supported,
        "supported_contracts": list(awc.SUPPORTED_COMPILER_CONTRACTS),
        "integrity": integrity,
        "diagnostics": diagnostics,
    }
    return build_response(
        request, operation="validate_workflow",
        source_contract_version=declared, result=result,
    )


@router.post("/adapt", operation_id="adapt_workflow")
def adapt_workflow(request: Request, req: AdaptWorkflowRequest):
    declared = _normalize_contract(req.workflow, req.contract_version)
    if declared not in awc.SUPPORTED_COMPILER_CONTRACTS:
        raise ApiException(
            422, "unsupported_contract_version",
            f"unsupported workflow contract version {declared!r}",
            field_path="contract_version",
            safe_details={"supported": list(awc.SUPPORTED_COMPILER_CONTRACTS)},
        )
    envelope = awc.adapt_workflow(
        req.workflow, contract_version=declared, role_overlay=req.overlay,
        source_package_digest=req.source_package_digest,
    )
    adaptation = envelope.adaptation_result
    result = {
        "adaptation_envelope": to_jsonable(envelope),
        "adapter_mode": envelope.adapter_mode,
        "node_dispositions": to_jsonable(adaptation.node_dispositions),
        "role_requirements": to_jsonable(adaptation.role_requirements),
        "non_agent_dispositions": to_jsonable(adaptation.non_agent_dispositions),
        "role_dependency_graph": to_jsonable(envelope.role_dependency_graph),
        "diagnostics": to_jsonable(envelope.diagnostics),
        "ok": envelope.ok,
        "adaptation_fingerprint": adaptation.adaptation_fingerprint,
        "adaptation_envelope_fingerprint": envelope.adaptation_envelope_fingerprint,
    }
    return build_response(
        request, operation="adapt_workflow",
        source_contract_version=declared, result=result,
        input_digests={"workflow": canonical_digest(req.workflow)},
    )


@router.post("/compare-adaptations", operation_id="compare_adaptations")
def compare_adaptations(request: Request, req: CompareAdaptationsRequest):
    ctx = get_context(request)
    orch = ctx.orchestration
    if req.scenario_id is not None:
        require_scenario(ctx, req.scenario_id)
        v2s = ctx.catalog.v2_inputs(req.scenario_id)
        out = orch.run_v1v2_comparison(v2s, LOGICAL_TIME)
        scenario_id = req.scenario_id
    else:
        v1_env = awc.adapt_workflow(
            req.v1_workflow, contract_version="workflow_ir.v1", role_overlay=req.v1_overlay)
        v2_env = awc.adapt_workflow(
            req.v2_workflow, contract_version="workflow_ir.v2", role_overlay=req.v2_overlay)
        out = {"v1_env": v1_env, "v2_env": v2_env,
               "report": orch.compare_adaptations(v1_env, v2_env)}
        scenario_id = None
    result = {
        "equivalence_state": out["report"].state,
        "report": to_jsonable(out["report"]),
        "v1_adaptation_fingerprint": out["v1_env"].adaptation_result.adaptation_fingerprint,
        "v2_adaptation_fingerprint": out["v2_env"].adaptation_result.adaptation_fingerprint,
    }
    return build_response(
        request, operation="compare_adaptations", scenario_id=scenario_id, result=result,
    )
