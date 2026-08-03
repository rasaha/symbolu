"""Deterministic extraction of ``workflow_ir.v2`` semantics from a compiled v1
graph and its source policy pack.

Every emitted value is derived from one of: an explicit source-policy
declaration, a typed workflow node kind, a registered compiler capability
mapping, a typed contract string, or a graph edge — and each carries provenance
naming the exact deterministic rule that produced it. There is **no**
natural-language inference, no keyword/substring guessing, and no LLM. Values that
cannot be resolved are marked unresolved, never fabricated.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..compiler.workflow_ir import EdgeKind, NodeKind, WorkflowIR, WorkflowNode
from ..models.common import AuthorityDisposition, CapabilityId
from ..models.policy_pack import PolicyPack
from .contracts import (
    CapabilityRequirementSource,
    DependencyKind,
    DerivationClass,
    RequirementLevel,
    ResolutionStatus,
    RoleRelevance,
    SemanticFeatureName,
    WORKFLOW_IR_V2,
)
from .models import (
    CapabilityRequirement,
    DataContractRef,
    HumanReviewRequirement,
    NodeInputRequirement,
    NodeOutputDeclaration,
    PolicyProvenanceRef,
    SemanticDiagnostic,
    SemanticFeature,
    WorkflowDependencySemantics,
    WorkflowIRv2,
    WorkflowNodeSemantics,
    stamp,
)

# --------------------------------------------------------------------------- #
# deterministic, documented mappings (the compiler's registered rules)
# --------------------------------------------------------------------------- #

#: Canonical, non-natural-language semantic purpose per node kind.
_NODE_KIND_PURPOSE: Dict[NodeKind, str] = {
    NodeKind.EVIDENCE_REQUIREMENT: "collect and extract evidence for a governed decision",
    NodeKind.EVIDENCE_ADMISSIBILITY: "assess admissibility of collected evidence",
    NodeKind.DECISION_RULE: "apply a governed decision rule",
    NodeKind.AUTHORITY_CHECK: "verify decision authority",
    NodeKind.APPROVAL_GATE: "require human approval",
    NodeKind.SEGREGATION_OF_DUTIES_GATE: "enforce segregation of duties",
    NodeKind.PROHIBITED_CONDITION: "block a prohibited condition",
    NodeKind.EXCEPTION_BRANCH: "handle a governed exception",
    NodeKind.OVERRIDE_GATE: "require an authorized override",
    NodeKind.ACTION_CONSTRAINT: "constrain a governed action",
    NodeKind.SEQUENCE_RISK_CHECK: "advise on sequence risk",
    NodeKind.ACTION_CLEARANCE_REQUIREMENT: "require commit-time action clearance",
    NodeKind.AUDIT_EMISSION: "emit a governed audit record",
    NodeKind.TERMINAL_OUTCOME: "terminal workflow outcome",
}

#: Functional (agent-relevant) capability a node kind structurally requires. Only
#: advisory cognitive work maps to a functional capability; governance/authority
#: nodes carry their owning-capability requirement instead (see below).
_NODE_KIND_CAPABILITY: Dict[NodeKind, Tuple[str, ...]] = {
    NodeKind.EVIDENCE_REQUIREMENT: ("evidence_extraction",),
}

#: Advisory governance capabilities (own their step; not agent-eligible).
_ADVISORY_GOVERNANCE_OWNERS = {
    CapabilityId.TAP,
    CapabilityId.STORYGRAPH,
    CapabilityId.MODEL_SELECTION,
}

#: Node kinds that assert human authority.
_HUMAN_AUTHORITY_KINDS = {
    NodeKind.APPROVAL_GATE,
    NodeKind.OVERRIDE_GATE,
    NodeKind.AUTHORITY_CHECK,
}

#: The main-flow edge kinds (data/control spine). Others are conditional branches.
_SPINE_EDGES = {EdgeKind.ON_PASS, EdgeKind.NEXT}


def classify_role_relevance(node: WorkflowNode) -> RoleRelevance:
    """Deterministically classify a node's role relevance. Fail-closed: an
    authoritative or governance-owned node is never advisory-agent-eligible."""
    kind = node.kind
    if kind in _HUMAN_AUTHORITY_KINDS:
        return RoleRelevance.HUMAN_AUTHORITY
    if kind is NodeKind.SEGREGATION_OF_DUTIES_GATE:
        return RoleRelevance.HUMAN_REVIEW
    if node.disposition is AuthorityDisposition.AUTHORITATIVE:
        return RoleRelevance.GOVERNANCE_OWNED
    if node.owning_capability in _ADVISORY_GOVERNANCE_OWNERS:
        return RoleRelevance.GOVERNANCE_OWNED
    if (
        kind is NodeKind.EVIDENCE_REQUIREMENT
        and node.owning_capability is CapabilityId.COMPILER
        and node.disposition is AuthorityDisposition.ADVISORY
    ):
        return RoleRelevance.ADVISORY_AGENT_ELIGIBLE
    if kind in (NodeKind.AUDIT_EMISSION, NodeKind.TERMINAL_OUTCOME):
        return RoleRelevance.DETERMINISTIC_SERVICE
    return RoleRelevance.UNSUPPORTED


def _prov(pack_id: str, pack_version: int, node: WorkflowNode,
          derivation: DerivationClass, rule: str, compiler_version: str,
          source_refs: Tuple[str, ...] = ()) -> PolicyProvenanceRef:
    return PolicyProvenanceRef(
        derivation_class=derivation,
        source_policy_id=pack_id,
        source_policy_version=pack_version,
        source_object_ids=tuple(node.input_object_ids),
        source_declaration=node.output_contract or node.label,
        source_refs=source_refs,
        compiler_rule=rule,
        compiler_version=compiler_version,
    )


def _capabilities(pack_id: str, pack_version: int, node: WorkflowNode,
                  relevance: RoleRelevance, compiler_version: str
                  ) -> Tuple[CapabilityRequirement, ...]:
    reqs: List[CapabilityRequirement] = []
    if relevance is RoleRelevance.ADVISORY_AGENT_ELIGIBLE:
        for cap in _NODE_KIND_CAPABILITY.get(node.kind, ()):  # functional capability
            reqs.append(stamp(CapabilityRequirement(
                capability_id=cap,
                requirement_level=RequirementLevel.REQUIRED,
                source=CapabilityRequirementSource.NODE_KIND_MAPPING,
                source_ref=node.kind.value,
                resolution=ResolutionStatus.DETERMINISTICALLY_INFERRED,
                authority_context=node.disposition.value,
                provenance=_prov(pack_id, pack_version, node,
                                 DerivationClass.DETERMINISTIC_MAPPING,
                                 "node_kind_capability_mapping", compiler_version))))
    else:
        # governance / authority / advisory-governance nodes carry their
        # owning-capability requirement (never an agent capability).
        if node.owning_capability is not CapabilityId.COMPILER:
            reqs.append(stamp(CapabilityRequirement(
                capability_id=node.owning_capability.value,
                requirement_level=RequirementLevel.REQUIRED,
                source=CapabilityRequirementSource.CAPABILITY_OWNER_MAPPING,
                source_ref=node.owning_capability.value,
                resolution=ResolutionStatus.DETERMINISTICALLY_INFERRED,
                authority_context=node.disposition.value,
                provenance=_prov(pack_id, pack_version, node,
                                 DerivationClass.DETERMINISTIC_MAPPING,
                                 "capability_owner_mapping", compiler_version))))
    return tuple(reqs)


def _contract_ref(pack_id: str, pack_version: int, node: WorkflowNode,
                  contract_id: str, compiler_version: str) -> DataContractRef:
    return DataContractRef(
        contract_id=contract_id,
        contract_data_version="",  # v1 IR carries no explicit contract version
        resolution=ResolutionStatus.EXPLICITLY_DECLARED,
        provenance=_prov(pack_id, pack_version, node,
                         DerivationClass.DERIVED_FROM_CONTRACT,
                         "node_output_contract", compiler_version),
    )


def _io_contracts(pack: PolicyPack, ir: WorkflowIR, node: WorkflowNode,
                  by_id: Dict[str, WorkflowNode], compiler_version: str
                  ) -> Tuple[Tuple[NodeInputRequirement, ...], Tuple[NodeOutputDeclaration, ...]]:
    pid, pver = ir.policy_pack_id, ir.policy_pack_version
    # outputs: this node's declared output contract, with spine consumers.
    outputs: List[NodeOutputDeclaration] = []
    if node.output_contract:
        consumers = tuple(sorted(
            e.target_id for e in ir.edges
            if e.source_id == node.node_id and e.kind in _SPINE_EDGES))
        outputs.append(NodeOutputDeclaration(
            contract_ref=_contract_ref(pid, pver, node, node.output_contract, compiler_version),
            consumer_node_ids=consumers,
            resolution=ResolutionStatus.EXPLICITLY_DECLARED))
    # inputs: the output contracts of spine predecessors (typed data flow).
    inputs: List[NodeInputRequirement] = []
    for e in ir.edges:
        if e.target_id != node.node_id or e.kind not in _SPINE_EDGES:
            continue
        producer = by_id.get(e.source_id)
        if producer is None or not producer.output_contract:
            continue
        inputs.append(NodeInputRequirement(
            contract_ref=_contract_ref(pid, pver, producer, producer.output_contract, compiler_version),
            producer_node_id=producer.node_id,
            compatibility_requirement="exact_or_unversioned",
            resolution=ResolutionStatus.EXPLICITLY_DECLARED))
    inputs.sort(key=lambda r: (r.contract_ref.contract_id, r.producer_node_id))
    return tuple(inputs), tuple(outputs)


def _human_review(pack_id: str, pack_version: int, node: WorkflowNode,
                  relevance: RoleRelevance, compiler_version: str) -> HumanReviewRequirement:
    if relevance is RoleRelevance.HUMAN_AUTHORITY:
        kind = "human_authority"
        required = True
    elif relevance is RoleRelevance.HUMAN_REVIEW:
        kind = "human_review"
        required = True
    else:
        kind = "none"
        required = False
    return HumanReviewRequirement(
        required=required, review_kind=kind, authority_type=node.authority_type,
        governance_owner=node.owning_capability.value if required else "",
        resolution=ResolutionStatus.DETERMINISTICALLY_INFERRED,
        provenance=_prov(pack_id, pack_version, node,
                         DerivationClass.DETERMINISTIC_MAPPING,
                         "human_review_classification", compiler_version))


def extract_node_semantics(pack: PolicyPack, ir: WorkflowIR, node: WorkflowNode,
                           by_id: Dict[str, WorkflowNode], compiler_version: str
                           ) -> WorkflowNodeSemantics:
    relevance = classify_role_relevance(node)
    caps = _capabilities(ir.policy_pack_id, ir.policy_pack_version, node, relevance, compiler_version)
    inputs, outputs = _io_contracts(pack, ir, node, by_id, compiler_version)
    hr = _human_review(ir.policy_pack_id, ir.policy_pack_version, node, relevance, compiler_version)
    governance_refs = ()
    if relevance in (RoleRelevance.GOVERNANCE_OWNED, RoleRelevance.HUMAN_AUTHORITY,
                     RoleRelevance.HUMAN_REVIEW) and node.public_contract_target:
        governance_refs = (node.public_contract_target,)
    sem = WorkflowNodeSemantics(
        node_id=node.node_id,
        node_kind=node.kind.value,
        semantic_purpose=_NODE_KIND_PURPOSE.get(node.kind, node.kind.value),
        semantic_description=node.label,
        role_relevance=relevance,
        required_capability_refs=caps,
        required_input_contract_refs=inputs,
        produced_output_contract_refs=outputs,
        data_classification_refs=(),
        permission_intent_refs=(),
        authority_disposition=node.disposition.value,
        canonical_capability_owner=node.owning_capability.value,
        human_review_requirement=hr,
        human_authority_requirement=relevance is RoleRelevance.HUMAN_AUTHORITY,
        governance_boundary_refs=governance_refs,
        source_policy_refs=tuple(node.input_object_ids),
        provenance=_prov(ir.policy_pack_id, ir.policy_pack_version, node,
                         DerivationClass.DETERMINISTIC_MAPPING,
                         "node_semantics_extraction", compiler_version),
    )
    return stamp(sem)


def _dependency_kind(edge_kind: EdgeKind, source: WorkflowNode, target: WorkflowNode,
                     relevance_of: Dict[str, RoleRelevance]) -> DependencyKind:
    if edge_kind not in _SPINE_EDGES:
        return DependencyKind.CONDITIONAL_DEPENDENCY
    tgt_rel = relevance_of.get(target.node_id)
    if tgt_rel is RoleRelevance.HUMAN_AUTHORITY:
        return DependencyKind.AUTHORITY_DEPENDENCY
    if tgt_rel is RoleRelevance.HUMAN_REVIEW:
        return DependencyKind.REVIEW_DEPENDENCY
    if tgt_rel is RoleRelevance.GOVERNANCE_OWNED:
        return DependencyKind.GOVERNANCE_DEPENDENCY
    if source.output_contract:
        return DependencyKind.DATA_DEPENDENCY
    return DependencyKind.ORDERING_DEPENDENCY


def extract_dependencies(ir: WorkflowIR, by_id: Dict[str, WorkflowNode],
                         relevance_of: Dict[str, RoleRelevance], compiler_version: str
                         ) -> Tuple[WorkflowDependencySemantics, ...]:
    deps: List[WorkflowDependencySemantics] = []
    for e in ir.edges:
        src = by_id.get(e.source_id)
        tgt = by_id.get(e.target_id)
        if src is None or tgt is None:
            continue
        dep_kind = _dependency_kind(e.kind, src, tgt, relevance_of)
        cond = e.kind.value if dep_kind is DependencyKind.CONDITIONAL_DEPENDENCY else ""
        out_contracts = (src.output_contract,) if src.output_contract else ()
        dep = WorkflowDependencySemantics(
            edge_id=e.edge_id, source_node_id=e.source_id, target_node_id=e.target_id,
            dependency_kind=dep_kind, condition_ref=cond,
            input_contract_refs=out_contracts if dep_kind is DependencyKind.DATA_DEPENDENCY else (),
            output_contract_refs=out_contracts if dep_kind is DependencyKind.DATA_DEPENDENCY else (),
            authority_context=tgt.disposition.value,
            provenance=PolicyProvenanceRef(
                derivation_class=DerivationClass.DERIVED_FROM_EDGE,
                source_policy_id=ir.policy_pack_id,
                source_policy_version=ir.policy_pack_version,
                source_object_ids=(e.source_id, e.target_id),
                source_declaration=e.kind.value,
                compiler_rule="edge_dependency_mapping",
                compiler_version=compiler_version))
        deps.append(stamp(dep))
    deps.sort(key=lambda d: (d.source_node_id, d.target_node_id, d.edge_id))
    return tuple(deps)


def enrich_workflow(ir: WorkflowIR, pack: Optional[PolicyPack] = None, *,
                    compiler_version: str) -> WorkflowIRv2:
    """Enrich a compiled v1 IR into a ``workflow_ir.v2`` artifact. Deterministic
    and total: every node and edge is classified; nothing is fabricated."""
    by_id = {n.node_id: n for n in ir.nodes}
    relevance_of = {n.node_id: classify_role_relevance(n) for n in ir.nodes}
    effective_pack = pack if pack is not None else _MinimalPack(ir)

    node_semantics = tuple(sorted(
        (extract_node_semantics(effective_pack, ir, n, by_id, compiler_version)
         for n in ir.nodes),
        key=lambda s: s.node_id))
    deps = extract_dependencies(ir, by_id, relevance_of, compiler_version)

    cap_ids = sorted({c.capability_id
                      for s in node_semantics for c in s.required_capability_refs}
                     | {c.capability_id
                        for s in node_semantics for c in s.optional_capability_refs})
    contract_ids = sorted({o.contract_ref.contract_id
                           for s in node_semantics for o in s.produced_output_contract_refs})
    prov_refs = sorted({s.provenance.source_policy_id for s in node_semantics
                        if s.provenance.source_policy_id})

    features = (
        SemanticFeature(name=SemanticFeatureName.ROLE_SEMANTICS, present=True),
        SemanticFeature(name=SemanticFeatureName.TYPED_CONTRACT_REFS, present=bool(contract_ids)),
        SemanticFeature(name=SemanticFeatureName.DEPENDENCY_SEMANTICS, present=bool(deps)),
        SemanticFeature(name=SemanticFeatureName.AUTHORITY_SEMANTICS, present=True),
        SemanticFeature(name=SemanticFeatureName.HUMAN_REVIEW_SEMANTICS, present=True),
        SemanticFeature(name=SemanticFeatureName.POLICY_PROVENANCE, present=True),
    )

    v2 = WorkflowIRv2(
        policy_pack_id=ir.policy_pack_id,
        policy_pack_version=ir.policy_pack_version,
        base_ir=ir,
        base_ir_digest=ir.logical_digest(),
        node_semantics=node_semantics,
        dependency_semantics=deps,
        semantic_features=features,
        capability_reference_manifest=tuple(cap_ids),
        contract_reference_manifest=tuple(contract_ids),
        provenance_manifest=tuple(prov_refs),
        diagnostics=(),
        compiler_version=compiler_version,
    )
    # The v2 workflow fingerprint IS the v2 logical digest (which already excludes
    # the fingerprint slot), so it is re-verifiable by recomputation.
    return v2.model_copy(update={"workflow_fingerprint": v2.logical_digest()})


def compile_workflow_v2(pack: PolicyPack, approval=None, *, registry=None,
                        require_approval: bool = True, compiler_version: Optional[str] = None
                        ) -> WorkflowIRv2:
    """Compile a policy pack to v1 (via the unchanged pipeline) and enrich it to
    ``workflow_ir.v2``. Raises ``ValueError`` if the v1 compilation fails."""
    from ..compiler.compiler import compile_policy_pack
    from ..version import WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION

    # v2 fingerprints commit to the explicit v2 semantic identity, not the package
    # version, so a distribution bump never perturbs a v2 fingerprint on its own.
    cv = compiler_version or WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION
    result = compile_policy_pack(pack, approval, registry=registry,
                                 require_approval=require_approval)
    if not result.success or result.workflow_ir is None:
        codes = ", ".join(sorted({d.code for d in result.diagnostics}))
        raise ValueError(f"v1 compilation failed; cannot enrich: {codes}")
    return enrich_workflow(result.workflow_ir, pack, compiler_version=cv)


def upgrade_workflow_ir(ir: WorkflowIR, pack: Optional[PolicyPack] = None, *,
                        compiler_version: Optional[str] = None) -> WorkflowIRv2:
    """Deterministic, non-destructive v1->v2 enrichment. It preserves ALL v1
    information (the exact v1 graph is embedded and its digest pinned) and is
    lossless only in that narrow sense — no v1 data is discarded. It does NOT
    recover source-policy facts absent from v1: semantics that cannot be derived
    from the v1 graph are explicitly labeled derived, defaulted, deferred or
    unresolved via their provenance derivation class, never invented. Identical to
    :func:`enrich_workflow` (enrichment is a pure function of the v1 graph)."""
    from ..version import WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION
    return enrich_workflow(
        ir, pack, compiler_version=compiler_version or WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION)


class _MinimalPack:
    """A tiny stand-in exposing only what extraction reads when no real pack is
    supplied (upgrade path). It never invents policy content."""

    def __init__(self, ir: WorkflowIR):
        self.pack_id = ir.policy_pack_id
        self.version = ir.policy_pack_version


__all__ = [
    "classify_role_relevance",
    "extract_node_semantics",
    "extract_dependencies",
    "enrich_workflow",
    "compile_workflow_v2",
    "upgrade_workflow_ir",
]
