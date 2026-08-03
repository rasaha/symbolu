"""Read-only, data-only adapter over the Policy Workflow Compiler ``WorkflowIR``.

The adapter consumes a **serialized** ``workflow_ir.v1`` document — a plain dict
(from ``CompiledReleasePackage.model_dump()`` / ``WorkflowIR.model_dump()`` or its
JSON). It never imports ``ugence_policy_workflow_compiler``, so AWC stays a leaf
capability importable outside the monorepo. It never invents a second workflow
graph: it classifies exactly the nodes the compiler emitted.

Fail-closed rules (Phase 0 authority preservation):
  * unknown IR contract version            -> adaptation failure (ok=False)
  * missing source digest                  -> adaptation failure
  * unknown node kind                       -> UNSUPPORTED_NODE
  * missing authority metadata              -> INVALID_NODE (never an agent role)
  * authoritative governance node           -> never AI_AGENT_ELIGIBLE
  * duplicate node id / conflicting owner    -> FATAL diagnostic
  * edge referencing a missing node          -> FATAL diagnostic (invalid graph reference)
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from .canonical import digest
from .contracts import (
    ADVISORY_GOVERNANCE_OWNERS,
    AUTHORITATIVE_GOVERNANCE_OWNERS,
    HUMAN_AUTHORITY_TYPES,
    AuthorityDisposition,
    CapabilityOwner,
    NodeDisposition,
    NodeKind,
)
from .fingerprint import stamp_fingerprint
from .version import CONTRACT_VERSION, SUPPORTED_IR_VERSIONS
from .workflow import (
    AdaptationDiagnostic,
    AuthorityContext,
    CompilerAdaptationResult,
    NonAgentDisposition,
    Provenance,
    WorkflowNodeDisposition,
    WorkflowRoleRequirement,
)

#: Base capability requirement implied purely by node kind (source-derived).
_KIND_BASE_CAPABILITIES: Dict[NodeKind, Tuple[str, ...]] = {
    NodeKind.EVIDENCE_REQUIREMENT: ("evidence_extraction",),
}

#: Overlay fields the caller may inject (enterprise-policy-derived). Any other key
#: is rejected — the adapter never accepts undeclared role data.
_OVERLAY_FIELDS = frozenset(
    {
        "role_name",
        "role_description",
        "required_capabilities",
        "optional_capabilities",
        "required_tools",
        "prohibited_tools",
        "domain_requirements",
        "data_classification",
        "residency_constraints",
        "provider_constraints",
        "deployment_constraints",
        "required_permissions",
        "prohibited_permissions",
        "authority_ceiling",
        "required_audit_capabilities",
        "required_security_classification",
        "required_evidence_classes",
        "state_requirement",
        "human_review_requirement",
        "minimum_quality_constraint",
        "maximum_latency_constraint",
        "maximum_cost_constraint",
        "model_requirement_refs",
        "fallback_policy_ref",
        "evidence_refs",
        "policy_refs",
    }
)


def _parse_enum(enum_cls, raw):
    try:
        return enum_cls(raw)
    except (ValueError, KeyError):
        return None


def classify_node(
    kind: Optional[NodeKind],
    owner: Optional[CapabilityOwner],
    disposition: Optional[AuthorityDisposition],
    authority_type: str,
) -> Tuple[NodeDisposition, Tuple[str, ...]]:
    """Deterministically classify a node into a disposition + reason codes.

    Pure function of the identity-defining metadata. Ordered, explainable, and
    fail-closed: it never returns ``AI_AGENT_ELIGIBLE`` for an authoritative or
    governance-owned node, and never guesses on missing metadata.
    """
    if kind is None:
        return NodeDisposition.UNSUPPORTED_NODE, ("unknown_node_kind",)
    if owner is None or disposition is None:
        return NodeDisposition.INVALID_NODE, ("missing_authority_metadata",)

    # 1. human authority / approval / override (checked first so a human gate is
    #    never absorbed into a generic governance-owner disposition).
    if kind in (NodeKind.APPROVAL_GATE, NodeKind.OVERRIDE_GATE):
        return NodeDisposition.HUMAN_AUTHORITY_REQUIRED, (f"human_authority_node:{kind.value}",)
    if authority_type and authority_type.upper() in HUMAN_AUTHORITY_TYPES:
        return NodeDisposition.HUMAN_AUTHORITY_REQUIRED, (f"human_authority_type:{authority_type}",)
    if kind is NodeKind.AUTHORITY_CHECK:
        return NodeDisposition.HUMAN_AUTHORITY_REQUIRED, ("authority_determination",)
    # 2. segregation of duties -> human review.
    if kind is NodeKind.SEGREGATION_OF_DUTIES_GATE:
        return NodeDisposition.HUMAN_REVIEW_REQUIRED, ("segregation_of_duties",)
    # 3. authoritative governance capability owns the step.
    if owner in AUTHORITATIVE_GOVERNANCE_OWNERS and disposition is AuthorityDisposition.AUTHORITATIVE:
        return (
            NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP,
            (f"authoritative_governance_owner:{owner.value}",),
        )
    # 4. advisory governance capability owns its step.
    if owner in ADVISORY_GOVERNANCE_OWNERS:
        return (
            NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP,
            (f"advisory_governance_owner:{owner.value}",),
        )
    # 5. residual authoritative disposition (non-governance owner) -> fail closed to human.
    if disposition is AuthorityDisposition.AUTHORITATIVE:
        return NodeDisposition.HUMAN_AUTHORITY_REQUIRED, ("residual_authoritative_node",)
    # 6. deterministic services (validators, admissibility, constraints, audit, rules).
    if kind in (
        NodeKind.EVIDENCE_ADMISSIBILITY,
        NodeKind.PROHIBITED_CONDITION,
        NodeKind.ACTION_CONSTRAINT,
        NodeKind.AUDIT_EMISSION,
        NodeKind.DECISION_RULE,
        NodeKind.ACTION_CLEARANCE_REQUIREMENT,
        NodeKind.SEQUENCE_RISK_CHECK,
    ):
        return NodeDisposition.DETERMINISTIC_SERVICE_PREFERRED, (f"deterministic_kind:{kind.value}",)
    # 7. purely structural -> no agent required.
    if kind in (NodeKind.TERMINAL_OUTCOME, NodeKind.EXCEPTION_BRANCH):
        return NodeDisposition.NO_AI_AGENT_REQUIRED, (f"structural_kind:{kind.value}",)
    # 8. advisory, compiler-structural cognitive work -> AI-agent eligible.
    if (
        kind is NodeKind.EVIDENCE_REQUIREMENT
        and owner is CapabilityOwner.COMPILER
        and disposition is AuthorityDisposition.ADVISORY
    ):
        return NodeDisposition.AI_AGENT_ELIGIBLE, ("advisory_evidence_work",)
    # 9. fail-closed default: never invent an agent role.
    return NodeDisposition.NO_AI_AGENT_REQUIRED, ("default_non_agent",)


def _extract_ir(document: Mapping) -> Tuple[Optional[dict], Optional[str], List[AdaptationDiagnostic]]:
    """Return (workflow_ir_dict, source_package_digest, diagnostics)."""
    diags: List[AdaptationDiagnostic] = []
    if not isinstance(document, Mapping):
        diags.append(AdaptationDiagnostic(severity="FATAL", code="MALFORMED_DOCUMENT",
                                          message="document is not a mapping"))
        return None, None, diags
    # A CompiledReleasePackage carries workflow_ir + structural_digest; a bare IR is itself.
    if "workflow_ir" in document:
        ir = document.get("workflow_ir")
        src_digest = document.get("structural_digest") or (
            document.get("manifest", {}) or {}).get("structural_digest")
    else:
        ir = document
        src_digest = document.get("source_package_digest") or document.get("structural_digest")
    if not isinstance(ir, Mapping):
        diags.append(AdaptationDiagnostic(severity="FATAL", code="MISSING_WORKFLOW_IR",
                                          message="no workflow_ir object present"))
        return None, None, diags
    return dict(ir), (str(src_digest) if src_digest else None), diags


def adapt_compiled_workflow(
    document: Mapping,
    *,
    source_package_digest: Optional[str] = None,
    role_overlay: Optional[Mapping[str, Mapping]] = None,
) -> CompilerAdaptationResult:
    """Adapt a serialized compiled workflow into the canonical planning objects.

    ``document`` is a serialized ``CompiledReleasePackage`` or ``WorkflowIR``.
    ``source_package_digest`` overrides / supplies the digest when the document
    does not carry one. ``role_overlay`` maps a node id to enterprise-policy role
    constraints (validated against :data:`_OVERLAY_FIELDS`).
    """
    ir, doc_digest, diagnostics = _extract_ir(document)
    src_digest = source_package_digest or doc_digest
    overlay = dict(role_overlay or {})

    def _fail(diags: List[AdaptationDiagnostic], wf_id: str = "", wf_ver: int = 0,
              src_ver: str = "") -> CompilerAdaptationResult:
        res = CompilerAdaptationResult(
            workflow_identity=wf_id, workflow_version=wf_ver,
            source_contract_version=src_ver, source_package_digest=src_digest or "",
            node_dispositions=(), role_requirements=(), non_agent_dispositions=(),
            diagnostics=tuple(diags), ok=False,
        )
        return stamp_fingerprint(res, "adaptation_fingerprint")  # type: ignore[return-value]

    if ir is None:
        return _fail(diagnostics)

    src_ver = str(ir.get("ir_version", ""))
    wf_id = str(ir.get("policy_pack_id", ""))
    wf_ver = int(ir.get("policy_pack_version", 0) or 0)

    if src_ver not in SUPPORTED_IR_VERSIONS:
        diagnostics.append(AdaptationDiagnostic(
            severity="FATAL", code="UNSUPPORTED_IR_VERSION",
            message=f"ir_version {src_ver!r} not in {list(SUPPORTED_IR_VERSIONS)}"))
        return _fail(diagnostics, wf_id, wf_ver, src_ver)
    if not src_digest:
        diagnostics.append(AdaptationDiagnostic(
            severity="FATAL", code="MISSING_SOURCE_DIGEST",
            message="no source package digest supplied or present"))
        return _fail(diagnostics, wf_id, wf_ver, src_ver)

    nodes = ir.get("nodes") or ()
    edges = ir.get("edges") or ()

    # overlay key validation (fail closed on undeclared role data).
    for nid, fields in overlay.items():
        bad = set(fields) - _OVERLAY_FIELDS
        if bad:
            diagnostics.append(AdaptationDiagnostic(
                severity="FATAL", code="INVALID_OVERLAY_FIELD", node_id=str(nid),
                message=f"undeclared overlay fields: {sorted(bad)}"))
            return _fail(diagnostics, wf_id, wf_ver, src_ver)

    node_ids: List[str] = []
    node_dispositions: List[WorkflowNodeDisposition] = []
    roles: List[WorkflowRoleRequirement] = []
    non_agents: List[NonAgentDisposition] = []
    seen_ids: set = set()

    for raw in nodes:
        node = dict(raw) if isinstance(raw, Mapping) else {}
        node_id = str(node.get("node_id", ""))
        if not node_id:
            diagnostics.append(AdaptationDiagnostic(
                severity="FATAL", code="MALFORMED_NODE", message="node with empty node_id"))
            return _fail(diagnostics, wf_id, wf_ver, src_ver)
        if node_id in seen_ids:
            diagnostics.append(AdaptationDiagnostic(
                severity="FATAL", code="DUPLICATE_NODE_ID", node_id=node_id,
                message="conflicting node ownership: duplicate node id"))
            return _fail(diagnostics, wf_id, wf_ver, src_ver)
        seen_ids.add(node_id)
        node_ids.append(node_id)

        kind = _parse_enum(NodeKind, node.get("kind"))
        owner = _parse_enum(CapabilityOwner, node.get("owning_capability"))
        disp = _parse_enum(AuthorityDisposition, node.get("disposition"))
        authority_type = str(node.get("authority_type", "") or "")
        disposition, reasons = classify_node(kind, owner, disp, authority_type)

        src_kind = kind if kind is not None else NodeKind.TERMINAL_OUTCOME  # placeholder for record
        auth_ctx = AuthorityContext(
            owning_capability=owner or CapabilityOwner.COMPILER,
            authority_disposition=disp or AuthorityDisposition.ADVISORY,
            authority_type=authority_type,
            public_contract_target=str(node.get("public_contract_target", "") or ""),
        )
        provenance = Provenance(
            source_kind="compiler_workflow_ir",
            synthetic=bool((document.get("release_metadata") or {}).get("synthetic", False))
            if isinstance(document, Mapping) else False,
            source_ref=f"{wf_id}@v{wf_ver}:{node_id}",
        )

        if disposition is NodeDisposition.AI_AGENT_ELIGIBLE and kind is not None:
            role = _build_role(
                wf_id, wf_ver, node, node_id, kind, auth_ctx, provenance, src_digest,
                overlay.get(node_id, {}))
            roles.append(role)
            node_dispositions.append(WorkflowNodeDisposition(
                node_id=node_id, source_node_kind=kind, disposition=disposition,
                reason_codes=reasons, role_id=role.role_id, is_agent_role=True))
        else:
            na = NonAgentDisposition(
                workflow_id=wf_id, node_id=node_id, source_node_kind=src_kind,
                disposition=disposition, reason_codes=reasons,
                canonical_owner=(owner.value if owner else ""),
                authority_context=auth_ctx,
                source_capability=(owner.value if owner else ""),
                human_review_required=disposition in (
                    NodeDisposition.HUMAN_REVIEW_REQUIRED,
                    NodeDisposition.HUMAN_AUTHORITY_REQUIRED),
                provenance=provenance, source_package_digest=src_digest)
            na = stamp_fingerprint(na, "fingerprint")
            non_agents.append(na)
            node_dispositions.append(WorkflowNodeDisposition(
                node_id=node_id, source_node_kind=src_kind, disposition=disposition,
                reason_codes=reasons, is_agent_role=False))

    # edge integrity: every endpoint must resolve to a known node.
    idset = set(node_ids)
    for raw in edges:
        e = dict(raw) if isinstance(raw, Mapping) else {}
        for endpoint in ("source_id", "target_id"):
            ref = str(e.get(endpoint, ""))
            if ref and ref not in idset:
                diagnostics.append(AdaptationDiagnostic(
                    severity="FATAL", code="INVALID_GRAPH_REFERENCE",
                    node_id=ref, message=f"edge {e.get('edge_id','?')} references missing node {ref!r}"))
                return _fail(diagnostics, wf_id, wf_ver, src_ver)

    result = CompilerAdaptationResult(
        workflow_identity=wf_id, workflow_version=wf_ver,
        source_contract_version=src_ver, source_package_digest=src_digest,
        node_dispositions=tuple(node_dispositions),
        role_requirements=tuple(roles),
        non_agent_dispositions=tuple(non_agents),
        diagnostics=tuple(diagnostics), ok=True,
    )
    return stamp_fingerprint(result, "adaptation_fingerprint")  # type: ignore[return-value]


def _tuple(value) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return (str(value),)


def _build_role(
    wf_id: str, wf_ver: int, node: dict, node_id: str, kind: NodeKind,
    auth_ctx: AuthorityContext, provenance: Provenance, src_digest: str,
    overlay: Mapping,
) -> WorkflowRoleRequirement:
    base_caps = set(_KIND_BASE_CAPABILITIES.get(kind, ()))
    base_caps |= set(_tuple(overlay.get("required_capabilities")))
    role = WorkflowRoleRequirement(
        contract_version=CONTRACT_VERSION,
        role_id=f"role::{node_id}",
        workflow_id=wf_id,
        workflow_version=wf_ver,
        source_node_id=node_id,
        source_node_kind=kind,
        role_name=str(overlay.get("role_name") or node.get("label") or kind.value),
        role_description=str(overlay.get("role_description") or node.get("output_contract", "") or ""),
        required_capabilities=tuple(sorted(base_caps)),
        input_contract_refs=_tuple(node.get("input_object_ids")),
        output_contract_refs=_tuple(node.get("output_contract")) if node.get("output_contract") else (),
        authority_context=auth_ctx,
        provenance=provenance,
        source_package_digest=src_digest,
        # enterprise-policy-derived
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
        human_review_requirement=bool(overlay.get("human_review_requirement", False)),
        # later-phase (typed, never ranked in P1)
        minimum_quality_constraint=_opt_float(overlay.get("minimum_quality_constraint")),
        maximum_latency_constraint=_opt_float(overlay.get("maximum_latency_constraint")),
        maximum_cost_constraint=_opt_float(overlay.get("maximum_cost_constraint")),
        model_requirement_refs=_tuple(overlay.get("model_requirement_refs")),
        fallback_policy_ref=str(overlay.get("fallback_policy_ref", "") or ""),
        evidence_refs=_tuple(overlay.get("evidence_refs")),
        policy_refs=_tuple(overlay.get("policy_refs")),
    )
    return stamp_fingerprint(role, "role_fingerprint")  # type: ignore[return-value]


def _opt_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CompilerWorkflowAdapter:
    """Object wrapper over :func:`adapt_compiled_workflow` (parity with siblings)."""

    supported_ir_versions = SUPPORTED_IR_VERSIONS

    def adapt(
        self,
        document: Mapping,
        *,
        source_package_digest: Optional[str] = None,
        role_overlay: Optional[Mapping[str, Mapping]] = None,
    ) -> CompilerAdaptationResult:
        return adapt_compiled_workflow(
            document, source_package_digest=source_package_digest, role_overlay=role_overlay)


__all__ = [
    "CompilerWorkflowAdapter",
    "adapt_compiled_workflow",
    "classify_node",
]
