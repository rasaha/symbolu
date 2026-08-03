"""Explicit contract-version dispatch and v1/v2 adaptation equivalence.

``adapt_workflow`` routes a serialized compiled workflow to the frozen v1 adapter
or the v2 semantic adapter by the contract version the document explicitly
declares — never by guessing from field presence. ``compare_adaptations`` and
``compare_workforce_plans`` classify how a v1+full-overlay adaptation relates to a
v2+reduced-overlay adaptation of the same logical workflow.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from .adapter import adapt_compiled_workflow
from .canonical import AwcModel
from .fingerprint import stamp_fingerprint
from .adapter_v2 import (
    COMPILER_ADAPTER_CONTRACT_VERSION,
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V2,
    AdaptationResultV2,
    AdapterDiagnostic,
    AdapterDiagnosticCode,
    CompilerAdapterMode,
    adapt_compiled_workflow_v2,
    declared_contract_version,
)
from .workflow import CompilerAdaptationResult
from .dependency import RoleDependencyGraph


class AdaptationEquivalenceState(str, Enum):
    BYTE_IDENTICAL = "BYTE_IDENTICAL"
    SEMANTICALLY_EQUIVALENT = "SEMANTICALLY_EQUIVALENT"
    INTENTIONALLY_DIFFERENT = "INTENTIONALLY_DIFFERENT"
    INCOMPATIBLE = "INCOMPATIBLE"


class EquivalenceDifference(AwcModel):
    field: str
    v1_value: str = ""
    v2_value: str = ""
    reason: str = ""
    compiler_source: str = ""
    policy_source: str = ""
    impact: str = "none"
    approval_status: str = "expected"


class AdaptationEquivalenceReport(AwcModel):
    dimension: str
    state: str
    v1_fingerprint: str = ""
    v2_fingerprint: str = ""
    differences: Tuple[EquivalenceDifference, ...] = ()
    semantic_equivalence_fingerprint: str = ""
    report_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# explicit dispatch
# --------------------------------------------------------------------------- #

def adapt_workflow(
    document: Mapping,
    *,
    contract_version: Optional[str] = None,
    source_package_digest: Optional[str] = None,
    role_overlay: Optional[Mapping[str, Mapping]] = None,
) -> AdaptationResultV2:
    """Adapt a serialized compiled workflow, dispatching EXPLICITLY by contract
    version. ``contract_version`` may be given; otherwise the version the document
    declares is used. Unknown versions fail closed. Returns a uniform
    :class:`AdaptationResultV2` envelope (v1 results are wrapped, mode V1_FROZEN)."""
    declared = contract_version or declared_contract_version(document)
    if declared == WORKFLOW_IR_V2:
        return adapt_compiled_workflow_v2(
            document, source_package_digest=source_package_digest, role_overlay=role_overlay)
    if declared == WORKFLOW_IR_V1:
        # frozen v1 path — behaviour byte-identical to adapt_compiled_workflow.
        res = adapt_compiled_workflow(
            document, source_package_digest=source_package_digest, role_overlay=role_overlay)
        return _wrap_v1(res)
    # explicit fail-closed on unknown/unsupported contract
    env = AdaptationResultV2(
        adapter_mode=CompilerAdapterMode.V1_FROZEN.value,
        source_contract_version=str(declared),
        adaptation_result=_empty_result(str(declared)),
        role_dependency_graph=RoleDependencyGraph(),
        diagnostics=(AdapterDiagnostic(
            code=AdapterDiagnosticCode.UNSUPPORTED_COMPILER_CONTRACT.value,
            message=f"unsupported contract version {declared!r}"),),
        ok=False)
    return stamp_fingerprint(env, "adaptation_envelope_fingerprint")


def _empty_result(src_ver: str) -> CompilerAdaptationResult:
    res = CompilerAdaptationResult(
        workflow_identity="", workflow_version=0, source_contract_version=src_ver,
        source_package_digest="", node_dispositions=(), role_requirements=(),
        non_agent_dispositions=(), diagnostics=(), ok=False)
    return stamp_fingerprint(res, "adaptation_fingerprint")


def _wrap_v1(res: CompilerAdaptationResult) -> AdaptationResultV2:
    from .dependency import build_role_dependency_graph
    dep = build_role_dependency_graph(res.role_requirements) if res.ok else RoleDependencyGraph()
    env = AdaptationResultV2(
        adapter_mode=CompilerAdapterMode.V1_FROZEN.value,
        source_contract_version=res.source_contract_version,
        source_package_digest=res.source_package_digest,
        adaptation_result=res, role_dependency_graph=dep, ok=res.ok)
    return stamp_fingerprint(env, "adaptation_envelope_fingerprint")


# --------------------------------------------------------------------------- #
# adaptation-level equivalence
# --------------------------------------------------------------------------- #

def _role_planning_projection(role) -> dict:
    """The planning-relevant projection of a role requirement (fields that feed
    eligibility / ranking / composition). Excludes role_name / provenance /
    contract version, which legitimately differ between v1 and v2."""
    return {
        "role_id": role.role_id,
        "source_node_id": role.source_node_id,
        "required_capabilities": sorted(role.required_capabilities),
        "input_contract_refs": sorted(role.input_contract_refs),
        "output_contract_refs": sorted(role.output_contract_refs),
        "required_evidence_classes": sorted(role.required_evidence_classes),
        "data_classification": role.data_classification,
        "required_permissions": sorted(role.required_permissions),
        "required_security_classification": role.required_security_classification,
        "residency_constraints": sorted(role.residency_constraints),
        "provider_constraints": sorted(role.provider_constraints),
        "human_review_requirement": role.human_review_requirement,
        "authority_disposition": role.authority_context.authority_disposition.value,
    }


def _disposition_projection(ad: CompilerAdaptationResult) -> dict:
    return {d.node_id: (d.disposition.value, d.is_agent_role) for d in ad.node_dispositions}


def compare_adaptations(v1_env: AdaptationResultV2,
                        v2_env: AdaptationResultV2) -> AdaptationEquivalenceReport:
    """Compare a v1 and a v2 adaptation of the same logical workflow at the
    adaptation level. Node dispositions are expected BYTE_IDENTICAL; role planning
    projections SEMANTICALLY_EQUIVALENT (role name / provenance / source contract
    legitimately differ)."""
    a, b = v1_env.adaptation_result, v2_env.adaptation_result
    diffs: List[EquivalenceDifference] = []

    # dispositions must be byte-identical
    disp_equal = _disposition_projection(a) == _disposition_projection(b)
    if not disp_equal:
        diffs.append(EquivalenceDifference(
            field="node_dispositions", reason="node disposition set differs",
            impact="authority", approval_status="unexpected"))

    # role planning projections must match set-wise (keyed by source_node_id)
    a_roles = {r.source_node_id: _role_planning_projection(r) for r in a.role_requirements}
    b_roles = {r.source_node_id: _role_planning_projection(r) for r in b.role_requirements}
    roles_equal = a_roles == b_roles
    if not roles_equal:
        for nid in sorted(set(a_roles) | set(b_roles)):
            if a_roles.get(nid) != b_roles.get(nid):
                diffs.append(EquivalenceDifference(
                    field=f"role[{nid}]", v1_value=str(a_roles.get(nid)),
                    v2_value=str(b_roles.get(nid)),
                    reason="planning-relevant role field differs",
                    impact="planning", approval_status="unexpected"))

    fp_equal = a.adaptation_fingerprint == b.adaptation_fingerprint
    if disp_equal and roles_equal:
        state = (AdaptationEquivalenceState.BYTE_IDENTICAL if fp_equal
                 else AdaptationEquivalenceState.SEMANTICALLY_EQUIVALENT)
    else:
        state = AdaptationEquivalenceState.INTENTIONALLY_DIFFERENT if _only_expected(diffs) \
            else AdaptationEquivalenceState.INCOMPATIBLE

    from .canonical import digest
    sef = digest({"dispositions": _disposition_projection(a),
                  "roles": sorted(a_roles.values(), key=lambda r: r["role_id"])})
    rep = AdaptationEquivalenceReport(
        dimension="adaptation", state=state.value,
        v1_fingerprint=a.adaptation_fingerprint, v2_fingerprint=b.adaptation_fingerprint,
        differences=tuple(diffs), semantic_equivalence_fingerprint=sef)
    return stamp_fingerprint(rep, "report_fingerprint")


def _only_expected(diffs) -> bool:
    return all(d.approval_status == "expected" for d in diffs)


# --------------------------------------------------------------------------- #
# plan-level equivalence (runs the frozen pipeline on both; compares projections)
# --------------------------------------------------------------------------- #

def _plan_projection(plan) -> dict:
    return {
        "plan_state": plan.plan_state.value,
        "assignments": {a.role_id: f"{a.primary_agent_id}@{a.primary_agent_version}"
                        for a in plan.role_assignments},
        "unfilled_roles": sorted(plan.unfilled_roles),
        "fallbacks": {fp.role_id: fp.fallback_state.value for fp in plan.role_fallback_plans},
        "permissions": {p.role_id: sorted(p.proposed_permissions)
                        for p in plan.permission_bound_proposals},
        "non_agent_nodes": sorted(na["node_id"] for na in plan.non_agent_dispositions),
    }


def compare_workforce_plans(v1_plan, v2_plan) -> AdaptationEquivalenceReport:
    """Compare the workforce-planning outcome of a v1 and v2 adaptation. The plan
    fingerprints legitimately differ (v2 carries richer provenance and a different
    source contract), but the planning projection — assignments, eligibility-driven
    fills, fallbacks, permissions, non-agent nodes — must be identical."""
    from .canonical import digest
    pa, pb = _plan_projection(v1_plan), _plan_projection(v2_plan)
    diffs: List[EquivalenceDifference] = []
    if pa != pb:
        for k in sorted(set(pa) | set(pb)):
            if pa.get(k) != pb.get(k):
                diffs.append(EquivalenceDifference(
                    field=k, v1_value=str(pa.get(k)), v2_value=str(pb.get(k)),
                    reason="planning outcome differs", impact="planning",
                    approval_status="unexpected"))
    fp_equal = v1_plan.plan_fingerprint == v2_plan.plan_fingerprint
    if pa == pb:
        state = (AdaptationEquivalenceState.BYTE_IDENTICAL if fp_equal
                 else AdaptationEquivalenceState.SEMANTICALLY_EQUIVALENT)
    else:
        state = AdaptationEquivalenceState.INCOMPATIBLE
    rep = AdaptationEquivalenceReport(
        dimension="workforce_plan", state=state.value,
        v1_fingerprint=v1_plan.plan_fingerprint, v2_fingerprint=v2_plan.plan_fingerprint,
        differences=tuple(diffs), semantic_equivalence_fingerprint=digest(pa))
    return stamp_fingerprint(rep, "report_fingerprint")


__all__ = [
    "AdaptationEquivalenceState", "EquivalenceDifference", "AdaptationEquivalenceReport",
    "adapt_workflow", "compare_adaptations", "compare_workforce_plans",
    "COMPILER_ADAPTER_CONTRACT_VERSION",
]
