"""workflow_ir.v2 compatibility adapter (AWC P2.1).

Consumes the Policy Workflow Compiler's enriched ``workflow_ir.v2`` document
directly — node semantics, functional capability requirements, typed contracts,
authority / human-review classification and policy provenance — instead of the
temporary overlay compensation the v1 path required. The v1 adapter
(:func:`adapter.adapt_compiled_workflow`) is left BYTE-FROZEN; this module adds a
parallel v2 path and an explicit contract-version dispatcher.

Ownership discipline (unchanged from P1/P2):

* the compiler supplies node meaning, functional capability, typed contracts,
  authority disposition, human-review requirement and provenance;
* the enterprise overlay still supplies provider/residency/deployment/security/
  permission/evidence/tool/SLA policy — those are NEVER taken from the compiler;
* AWC still derives node disposition, eligibility, ranking, composition,
  permission proposals and fallback — this adapter changes none of those
  algorithms. It only changes how the formal job description is read.

The merge of compiler semantics and enterprise policy is monotonic with respect
to authority and security: enterprise policy may narrow, strengthen, or add
review; it may never broaden authority or erase a governance boundary.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from .adapter import _OVERLAY_FIELDS, _opt_float, _tuple, classify_node
from .canonical import AwcModel, digest
from .contracts import (
    AuthorityDisposition,
    CapabilityOwner,
    NodeDisposition,
    NodeKind,
)
from .dependency import RoleDependency, RoleDependencyGraph, RoleInterfaceRequirement
from .fingerprint import stamp_fingerprint
from .version import COMPOSITION_CONTRACT_VERSION, CONTRACT_VERSION
from .workflow import (
    AuthorityContext,
    CompilerAdaptationResult,
    NonAgentDisposition,
    Provenance,
    WorkflowNodeDisposition,
    WorkflowRoleRequirement,
)

#: The compiler contracts this adapter understands.
WORKFLOW_IR_V1 = "workflow_ir.v1"
WORKFLOW_IR_V2 = "workflow_ir.v2"
SUPPORTED_COMPILER_CONTRACTS = (WORKFLOW_IR_V1, WORKFLOW_IR_V2)

#: The adapter's own contract version (adaptation metadata only; NOT part of the
#: frozen awc.v1 / awc.composition.v1 planning contracts).
COMPILER_ADAPTER_CONTRACT_VERSION = "awc.compiler_adapter.v2"


class CompilerContractVersion(str, Enum):
    V1 = WORKFLOW_IR_V1
    V2 = WORKFLOW_IR_V2


class CompilerAdapterMode(str, Enum):
    V1_FROZEN = "V1_FROZEN"
    V2_SEMANTIC = "V2_SEMANTIC"


class AdapterDiagnosticCode(str, Enum):
    UNSUPPORTED_COMPILER_CONTRACT = "UNSUPPORTED_COMPILER_CONTRACT"
    UNRESOLVED_COMPILER_SEMANTICS = "UNRESOLVED_COMPILER_SEMANTICS"
    OVERLAY_CONFLICTS_WITH_COMPILER_SEMANTICS = "OVERLAY_CONFLICTS_WITH_COMPILER_SEMANTICS"
    OVERLAY_BROADENS_AUTHORITY = "OVERLAY_BROADENS_AUTHORITY"
    OVERLAY_REMOVES_HUMAN_REVIEW = "OVERLAY_REMOVES_HUMAN_REVIEW"
    OVERLAY_REMOVES_GOVERNANCE_BOUNDARY = "OVERLAY_REMOVES_GOVERNANCE_BOUNDARY"
    OVERLAY_CONTRACT_MISMATCH = "OVERLAY_CONTRACT_MISMATCH"
    OVERLAY_CAPABILITY_CONFLICT = "OVERLAY_CAPABILITY_CONFLICT"
    OVERLAY_PROVENANCE_CONFLICT = "OVERLAY_PROVENANCE_CONFLICT"
    INVALID_OVERLAY_FIELD = "INVALID_OVERLAY_FIELD"
    MALFORMED_V2_DOCUMENT = "MALFORMED_V2_DOCUMENT"


class AdapterDiagnostic(AwcModel):
    code: str
    severity: str = "FATAL"
    node_id: str = ""
    message: str = ""


class AdaptationResultV2(AwcModel):
    """The v2 adaptation envelope: the canonical planning result plus adapter
    metadata and the v2-native dependency graph. The embedded
    ``adaptation_result`` is the ordinary :class:`CompilerAdaptationResult` the
    frozen P1/P2 pipeline consumes unchanged."""

    compiler_adapter_contract_version: str = COMPILER_ADAPTER_CONTRACT_VERSION
    adapter_mode: str
    source_contract_version: str
    source_compiler_distribution_version: str = ""
    source_compiler_product_version: str = ""
    source_package_digest: str = ""
    overlay_fields_consumed: Tuple[str, ...] = ()
    compiler_fields_consumed: Tuple[str, ...] = ()
    deferred_fields: Tuple[str, ...] = ()
    adaptation_result: CompilerAdaptationResult
    role_dependency_graph: RoleDependencyGraph
    diagnostics: Tuple[AdapterDiagnostic, ...] = ()
    ok: bool = True
    adaptation_envelope_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# reduced-overlay merge policy (which overlay fields the compiler now supplies)
# --------------------------------------------------------------------------- #

#: Overlay fields the compiler v2 contract now emits canonically. In the v2 path
#: these are taken from the compiler; if an overlay still supplies one it is an
#: OPTIONAL override (stricter accepted, authority/governance-broadening rejected).
_COMPILER_EMITTED_OVERLAY_FIELDS = frozenset({
    "role_name", "role_description", "human_review_requirement",
})
#: Enterprise-owned overlay fields that ALWAYS remain external (never compiler).
_ENTERPRISE_OVERLAY_FIELDS = frozenset(_OVERLAY_FIELDS - _COMPILER_EMITTED_OVERLAY_FIELDS)


def reduce_overlay(full_overlay: Mapping[str, Mapping]) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Split a full v1 overlay into (reduced_enterprise_overlay, removed_fields).

    Removed = the compiler-compensation fields the compiler v2 contract now emits
    (currently ``role_name`` / ``role_description`` / ``human_review_requirement``).
    Everything else is enterprise policy and is retained verbatim."""
    reduced: Dict[str, dict] = {}
    removed: Dict[str, dict] = {}
    for node_id, fields in full_overlay.items():
        keep, drop = {}, {}
        for k, v in fields.items():
            (drop if k in _COMPILER_EMITTED_OVERLAY_FIELDS else keep)[k] = v
        reduced[node_id] = keep
        if drop:
            removed[node_id] = drop
    return reduced, removed


# --------------------------------------------------------------------------- #
# v2 document extraction
# --------------------------------------------------------------------------- #

def _parse_enum(enum_cls, raw):
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except Exception:
        return None


def _fail(diags, wf_id="", wf_ver=0, src_ver=WORKFLOW_IR_V2, src_digest="",
          mode=CompilerAdapterMode.V2_SEMANTIC) -> AdaptationResultV2:
    res = CompilerAdaptationResult(
        workflow_identity=wf_id, workflow_version=wf_ver,
        source_contract_version=src_ver, source_package_digest=src_digest or "",
        node_dispositions=(), role_requirements=(), non_agent_dispositions=(),
        diagnostics=(), ok=False)
    res = stamp_fingerprint(res, "adaptation_fingerprint")
    env = AdaptationResultV2(
        adapter_mode=mode.value, source_contract_version=src_ver,
        source_package_digest=src_digest or "", adaptation_result=res,
        role_dependency_graph=RoleDependencyGraph(), diagnostics=tuple(diags), ok=False)
    return stamp_fingerprint(env, "adaptation_envelope_fingerprint")


def adapt_compiled_workflow_v2(
    document: Mapping,
    *,
    source_package_digest: Optional[str] = None,
    role_overlay: Optional[Mapping[str, Mapping]] = None,
) -> AdaptationResultV2:
    """Adapt a serialized ``workflow_ir.v2`` document into canonical planning
    objects, consuming compiler-emitted semantics. ``role_overlay`` is the REDUCED
    enterprise overlay (the compiler now supplies role name/description and human
    review); enterprise policy fields are retained and merged monotonically."""
    diags: List[AdapterDiagnostic] = []
    if not isinstance(document, Mapping):
        return _fail([AdapterDiagnostic(
            code=AdapterDiagnosticCode.MALFORMED_V2_DOCUMENT.value,
            message="document is not a mapping")])

    src_ver = str(document.get("ir_version") or document.get("contract_version") or "")
    if src_ver != WORKFLOW_IR_V2:
        return _fail([AdapterDiagnostic(
            code=AdapterDiagnosticCode.UNSUPPORTED_COMPILER_CONTRACT.value,
            message=f"v2 adapter requires {WORKFLOW_IR_V2!r}, got {src_ver!r}")],
            src_ver=src_ver)

    base_ir = document.get("base_ir")
    if not isinstance(base_ir, Mapping):
        return _fail([AdapterDiagnostic(
            code=AdapterDiagnosticCode.MALFORMED_V2_DOCUMENT.value,
            message="v2 document has no base_ir")], src_ver=src_ver)

    wf_id = str(base_ir.get("policy_pack_id", ""))
    wf_ver = int(base_ir.get("policy_pack_version", 0) or 0)
    src_digest = source_package_digest or str(document.get("base_ir_digest", "")) or ""
    if not src_digest:
        return _fail([AdapterDiagnostic(
            code=AdapterDiagnosticCode.MALFORMED_V2_DOCUMENT.value,
            message="no source package digest present")], wf_id, wf_ver, src_ver)

    overlay = dict(role_overlay or {})
    for nid, fields in overlay.items():
        bad = set(fields) - _OVERLAY_FIELDS
        if bad:
            return _fail([AdapterDiagnostic(
                code=AdapterDiagnosticCode.INVALID_OVERLAY_FIELD.value, node_id=str(nid),
                message=f"undeclared overlay fields: {sorted(bad)}")], wf_id, wf_ver, src_ver)

    semantics_by_id = {str(s.get("node_id")): s
                       for s in (document.get("node_semantics") or ())
                       if isinstance(s, Mapping)}

    nodes = base_ir.get("nodes") or ()
    node_ids: List[str] = []
    node_dispositions: List[WorkflowNodeDisposition] = []
    roles: List[WorkflowRoleRequirement] = []
    non_agents: List[NonAgentDisposition] = []
    compiler_fields: set = set()
    overlay_fields: set = set()

    synthetic = bool((document.get("release_metadata") or {}).get("synthetic", False)) \
        or bool((base_ir.get("release_metadata") or {}).get("synthetic", False))

    for raw in nodes:
        node = dict(raw) if isinstance(raw, Mapping) else {}
        node_id = str(node.get("node_id", ""))
        node_ids.append(node_id)
        kind = _parse_enum(NodeKind, node.get("kind"))
        owner = _parse_enum(CapabilityOwner, node.get("owning_capability"))
        disp = _parse_enum(AuthorityDisposition, node.get("disposition"))
        authority_type = str(node.get("authority_type", "") or "")
        # IDENTICAL classification as v1 — dispositions are byte-equivalent.
        disposition, reasons = classify_node(kind, owner, disp, authority_type)
        src_kind = kind if kind is not None else NodeKind.TERMINAL_OUTCOME

        auth_ctx = AuthorityContext(
            owning_capability=owner or CapabilityOwner.COMPILER,
            authority_disposition=disp or AuthorityDisposition.ADVISORY,
            authority_type=authority_type,
            public_contract_target=str(node.get("public_contract_target", "") or ""))

        sem = semantics_by_id.get(node_id, {})
        provenance = _provenance(wf_id, wf_ver, node_id, sem, synthetic, src_ver)

        if disposition is NodeDisposition.AI_AGENT_ELIGIBLE and kind is not None:
            role, cf, of, node_diags = _build_role_v2(
                wf_id, wf_ver, node, node_id, kind, auth_ctx, provenance, src_digest,
                sem, overlay.get(node_id, {}))
            diags.extend(node_diags)
            compiler_fields |= cf
            overlay_fields |= of
            roles.append(role)
            node_dispositions.append(WorkflowNodeDisposition(
                node_id=node_id, source_node_kind=kind, disposition=disposition,
                reason_codes=reasons, role_id=role.role_id, is_agent_role=True))
        else:
            na = _non_agent_v2(wf_id, node_id, src_kind, disposition, reasons, owner,
                               auth_ctx, provenance, src_digest, sem)
            non_agents.append(na)
            node_dispositions.append(WorkflowNodeDisposition(
                node_id=node_id, source_node_kind=src_kind, disposition=disposition,
                reason_codes=reasons, is_agent_role=False))

    dep_graph, dep_diags = _dependency_graph_v2(document, roles, wf_id, wf_ver, synthetic)
    diags.extend(dep_diags)

    ok = not any(d.severity == "FATAL" for d in diags)
    result = CompilerAdaptationResult(
        workflow_identity=wf_id, workflow_version=wf_ver,
        source_contract_version=src_ver, source_package_digest=src_digest,
        node_dispositions=tuple(node_dispositions), role_requirements=tuple(roles),
        non_agent_dispositions=tuple(non_agents), diagnostics=(), ok=ok)
    result = stamp_fingerprint(result, "adaptation_fingerprint")

    env = AdaptationResultV2(
        adapter_mode=CompilerAdapterMode.V2_SEMANTIC.value,
        source_contract_version=src_ver,
        source_compiler_distribution_version=str(document.get("compiler_version", "")),
        source_compiler_product_version=str(document.get("compiler_version", "")),
        source_package_digest=src_digest,
        overlay_fields_consumed=tuple(sorted(overlay_fields)),
        compiler_fields_consumed=tuple(sorted(compiler_fields)),
        deferred_fields=("data_classification", "permission_intent", "required_tools"),
        adaptation_result=result, role_dependency_graph=dep_graph,
        diagnostics=tuple(diags), ok=ok)
    return stamp_fingerprint(env, "adaptation_envelope_fingerprint")


def _provenance(wf_id, wf_ver, node_id, sem, synthetic, src_ver) -> Provenance:
    cp = sem.get("provenance", {}) if isinstance(sem, Mapping) else {}
    rule = cp.get("compiler_rule", "")
    cver = cp.get("compiler_version", "")
    notes = (f"compiler_contract={src_ver}; compiler_rule={rule}; "
             f"compiler_version={cver}; derivation={cp.get('derivation_class','')}") \
        if cp else f"compiler_contract={src_ver}"
    return Provenance(
        source_kind="compiler_workflow_ir_v2", synthetic=synthetic,
        source_ref=f"{wf_id}@v{wf_ver}:{node_id}", notes=notes)


def _capability_ids(sem: Mapping) -> Tuple[str, ...]:
    out = []
    for c in (sem.get("required_capability_refs") or ()):
        if isinstance(c, Mapping) and c.get("capability_id"):
            out.append(str(c["capability_id"]))
    return tuple(out)


def _build_role_v2(wf_id, wf_ver, node, node_id, kind, auth_ctx, provenance, src_digest,
                   sem, overlay) -> Tuple[WorkflowRoleRequirement, set, set, List[AdapterDiagnostic]]:
    diags: List[AdapterDiagnostic] = []
    compiler_fields: set = set()
    overlay_fields: set = set(k for k in overlay)

    # -- role name/description: compiler-emitted (overlay may override, tracked) --
    role_name = str(sem.get("semantic_purpose") or node.get("label") or kind.value)
    role_description = str(sem.get("semantic_description") or node.get("output_contract", "") or "")
    if sem.get("semantic_purpose"):
        compiler_fields.add("semantic_purpose")
    if overlay.get("role_name"):  # optional override
        role_name = str(overlay["role_name"])
    if overlay.get("role_description"):
        role_description = str(overlay["role_description"])

    # -- capabilities: compiler functional caps UNION reduced-overlay specialist --
    compiler_caps = set(_capability_ids(sem))
    if compiler_caps:
        compiler_fields.add("required_capability_refs")
    overlay_caps = set(_tuple(overlay.get("required_capabilities")))
    required_caps = tuple(sorted(compiler_caps | overlay_caps))

    # -- human review: compiler-emitted; overlay may only STRENGTHEN (add), not remove --
    hr = sem.get("human_review_requirement", {}) if isinstance(sem, Mapping) else {}
    compiler_hr = bool(hr.get("required", False))
    if isinstance(sem, Mapping) and "human_review_requirement" in sem:
        compiler_fields.add("human_review_requirement")
    overlay_hr = overlay.get("human_review_requirement")
    if overlay_hr is False and compiler_hr:
        diags.append(AdapterDiagnostic(
            code=AdapterDiagnosticCode.OVERLAY_REMOVES_HUMAN_REVIEW.value, node_id=node_id,
            message="overlay attempts to remove a compiler-declared human review"))
    human_review = compiler_hr or bool(overlay_hr)

    # -- contracts: sourced from the base_ir node (identical to v1) so interface
    #    compatibility in composition is unchanged. Compiler typed refs are richer
    #    metadata surfaced in the envelope, not re-typed onto the role here.
    input_refs = _tuple(node.get("input_object_ids"))
    output_refs = _tuple(node.get("output_contract")) if node.get("output_contract") else ()

    role = WorkflowRoleRequirement(
        contract_version=CONTRACT_VERSION, role_id=f"role::{node_id}",
        workflow_id=wf_id, workflow_version=wf_ver, source_node_id=node_id,
        source_node_kind=kind, role_name=role_name, role_description=role_description,
        required_capabilities=required_caps, input_contract_refs=input_refs,
        output_contract_refs=output_refs, authority_context=auth_ctx,
        provenance=provenance, source_package_digest=src_digest,
        # enterprise-policy-derived (retained from the reduced overlay verbatim)
        optional_capabilities=tuple(sorted(set(_tuple(overlay.get("optional_capabilities"))))),
        required_tools=_tuple(overlay.get("required_tools")),
        prohibited_tools=_tuple(overlay.get("prohibited_tools")),
        domain_requirements=_tuple(overlay.get("domain_requirements")),
        data_classification=str(overlay.get("data_classification", "") or ""),
        residency_constraints=_tuple(overlay.get("residency_constraints")),
        provider_constraints=_tuple(overlay.get("provider_constraints")),
        deployment_constraints=_tuple(overlay.get("deployment_constraints")),
        required_permissions=_tuple(overlay.get("required_permissions")),
        prohibited_permissions=_tuple(overlay.get("prohibited_permissions")),
        authority_ceiling=int(overlay.get("authority_ceiling", 0) or 0),
        required_audit_capabilities=_tuple(overlay.get("required_audit_capabilities")),
        required_security_classification=int(overlay.get("required_security_classification", 0) or 0),
        required_evidence_classes=_tuple(overlay.get("required_evidence_classes")),
        state_requirement=str(overlay.get("state_requirement", "") or ""),
        human_review_requirement=human_review,
        minimum_quality_constraint=_opt_float(overlay.get("minimum_quality_constraint")),
        maximum_latency_constraint=_opt_float(overlay.get("maximum_latency_constraint")),
        maximum_cost_constraint=_opt_float(overlay.get("maximum_cost_constraint")),
        model_requirement_refs=_tuple(overlay.get("model_requirement_refs")),
        fallback_policy_ref=str(overlay.get("fallback_policy_ref", "") or ""),
        evidence_refs=_tuple(overlay.get("evidence_refs")),
        policy_refs=_tuple(overlay.get("policy_refs")))
    role = stamp_fingerprint(role, "role_fingerprint")
    return role, compiler_fields, overlay_fields, diags


def _non_agent_v2(wf_id, node_id, src_kind, disposition, reasons, owner, auth_ctx,
                  provenance, src_digest, sem) -> NonAgentDisposition:
    na = NonAgentDisposition(
        workflow_id=wf_id, node_id=node_id, source_node_kind=src_kind,
        disposition=disposition, reason_codes=reasons,
        canonical_owner=(owner.value if owner else ""), authority_context=auth_ctx,
        source_capability=(owner.value if owner else ""),
        human_review_required=disposition in (
            NodeDisposition.HUMAN_REVIEW_REQUIRED, NodeDisposition.HUMAN_AUTHORITY_REQUIRED),
        provenance=provenance, source_package_digest=src_digest)
    return stamp_fingerprint(na, "fingerprint")


# --------------------------------------------------------------------------- #
# v2 dependency semantics -> AWC role dependency graph
# --------------------------------------------------------------------------- #

_DEP_EDGE_KIND = {
    "DATA_DEPENDENCY": "DATA_CONTRACT", "CONTROL_DEPENDENCY": "CONTROL",
    "ORDERING_DEPENDENCY": "ORDERING", "REVIEW_DEPENDENCY": "REVIEW",
    "AUTHORITY_DEPENDENCY": "AUTHORITY", "GOVERNANCE_DEPENDENCY": "GOVERNANCE",
    "CONDITIONAL_DEPENDENCY": "CONDITIONAL",
}


def _dependency_graph_v2(document, roles, wf_id, wf_ver, synthetic
                         ) -> Tuple[RoleDependencyGraph, List[AdapterDiagnostic]]:
    """Build the role dependency graph directly from compiler v2 dependency
    semantics (never reconstructed from node ordering). Only role->role edges
    carrying a data contract become RoleDependency edges; edges terminating at
    non-agent (human/governance) nodes are recorded via interface requirements."""
    diags: List[AdapterDiagnostic] = []
    role_by_node = {r.source_node_id: r for r in roles}
    role_ids = tuple(r.role_id for r in roles)
    interfaces = tuple(RoleInterfaceRequirement(
        role_id=r.role_id, required_input_contracts=r.input_contract_refs,
        produced_output_contracts=r.output_contract_refs) for r in roles)

    deps: List[RoleDependency] = []
    for d in (document.get("dependency_semantics") or ()):
        if not isinstance(d, Mapping):
            continue
        up_node, dn_node = str(d.get("source_node_id")), str(d.get("target_node_id"))
        up, dn = role_by_node.get(up_node), role_by_node.get(dn_node)
        if up is None or dn is None:
            continue  # edge touches a non-agent node — kept out of role->role deps
        out_contracts = tuple(str(c) for c in (d.get("output_contract_refs") or ()))
        linking = out_contracts[0] if out_contracts else (
            up.output_contract_refs[0] if up.output_contract_refs else "")
        prov = Provenance(
            source_kind="compiler_workflow_ir_v2_dependency", synthetic=synthetic,
            source_ref=f"{wf_id}@v{wf_ver}:{d.get('edge_id','')}",
            notes=f"dependency_kind={d.get('dependency_kind','')}; "
                  f"compiler_rule={(d.get('provenance') or {}).get('compiler_rule','')}")
        dep = RoleDependency(
            upstream_role_id=up.role_id, downstream_role_id=dn.role_id,
            edge_kind=_DEP_EDGE_KIND.get(str(d.get("dependency_kind")), "DATA_CONTRACT"),
            required_output_contract=linking,
            required_input_contract=(dn.input_contract_refs[0] if dn.input_contract_refs else linking),
            data_classification="", authority_context=str(d.get("authority_context", "")),
            provenance=prov)
        deps.append(stamp_fingerprint(dep, "dependency_fingerprint"))

    # dedupe logical edges deterministically
    seen, uniq = set(), []
    for dep in sorted(deps, key=lambda x: (x.upstream_role_id, x.downstream_role_id, x.edge_kind)):
        key = (dep.upstream_role_id, dep.downstream_role_id, dep.required_output_contract)
        if key not in seen:
            seen.add(key)
            uniq.append(dep)
    graph = RoleDependencyGraph(
        roles=role_ids, interface_requirements=interfaces, dependencies=tuple(uniq),
        has_cycle=False)
    return stamp_fingerprint(graph, "graph_fingerprint"), diags


# --------------------------------------------------------------------------- #
# explicit contract-version dispatch
# --------------------------------------------------------------------------- #

def declared_contract_version(document: Mapping) -> str:
    """Read the contract version a document explicitly declares (never guessed
    from field presence). A v2 document declares ``ir_version=workflow_ir.v2`` at
    the top; a v1 CompiledReleasePackage/WorkflowIR declares ``workflow_ir.v1``."""
    if not isinstance(document, Mapping):
        return ""
    top = str(document.get("ir_version") or document.get("contract_version") or "")
    if top:
        return top
    wf = document.get("workflow_ir")
    if isinstance(wf, Mapping):
        return str(wf.get("ir_version", ""))
    return ""


__all__ = [
    "WORKFLOW_IR_V1", "WORKFLOW_IR_V2", "SUPPORTED_COMPILER_CONTRACTS",
    "COMPILER_ADAPTER_CONTRACT_VERSION",
    "CompilerContractVersion", "CompilerAdapterMode", "AdapterDiagnosticCode",
    "AdapterDiagnostic", "AdaptationResultV2",
    "reduce_overlay", "adapt_compiled_workflow_v2", "declared_contract_version",
]
