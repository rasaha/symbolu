"""Immutable ``workflow_ir.v2`` semantic-enrichment models.

Every model is a frozen ``CompilerModel`` (``extra='forbid'``) and carries
deterministic provenance. Fingerprints are content digests over the model's own
logical fields (excluding the fingerprint slot itself), so identical enrichment
yields identical fingerprints across processes.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..compiler.workflow_ir import WorkflowIR
from ..models.common import CompilerModel
from ..serialization import canonical_json, hashing
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


def stamp(model: "CompilerModel", field: str = "fingerprint") -> "CompilerModel":
    """Return a copy of ``model`` with ``field`` set to a content digest over the
    model's canonical form (with that field blanked). Deterministic and stable."""
    blanked = model.model_copy(update={field: ""})
    payload = canonical_json.to_canonical_obj(blanked)
    return model.model_copy(update={field: hashing.digest(payload)})


class PolicyProvenanceRef(CompilerModel):
    """Traceability for an enriched semantic value back to source policy and the
    deterministic compiler rule that produced it. Never carries a fabricated
    value: an unresolved derivation is marked ``UNRESOLVED``."""

    contract_version: str = WORKFLOW_IR_V2
    derivation_class: DerivationClass
    source_policy_id: str = ""
    source_policy_version: int = 0
    #: Source policy-object ids that fed the node this value describes.
    source_object_ids: Tuple[str, ...] = ()
    #: A short declaration reference (never free natural-language inference).
    source_declaration: str = ""
    #: External source references (SourceDocument / ProvenanceReference ids).
    source_refs: Tuple[str, ...] = ()
    #: The named, documented compiler rule that produced the value.
    compiler_rule: str = ""
    compiler_version: str = ""


class CapabilityRequirement(CompilerModel):
    """A role-relevant capability a node requires, with deterministic provenance."""

    contract_version: str = WORKFLOW_IR_V2
    capability_id: str
    requirement_level: RequirementLevel = RequirementLevel.REQUIRED
    source: CapabilityRequirementSource
    source_ref: str = ""
    resolution: ResolutionStatus = ResolutionStatus.DETERMINISTICALLY_INFERRED
    authority_context: str = ""
    provenance: PolicyProvenanceRef
    fingerprint: str = ""


class DataContractRef(CompilerModel):
    """A typed reference to a data contract flowing through a node."""

    contract_version: str = WORKFLOW_IR_V2
    contract_id: str
    contract_data_version: str = ""
    schema_ref: str = ""
    data_classification_ref: str = ""
    resolution: ResolutionStatus = ResolutionStatus.EXPLICITLY_DECLARED
    provenance: PolicyProvenanceRef


class NodeInputRequirement(CompilerModel):
    """A required input contract for a node, with its producer where resolvable."""

    contract_version: str = WORKFLOW_IR_V2
    contract_ref: DataContractRef
    producer_node_id: str = ""
    compatibility_requirement: str = "exact_or_unversioned"
    resolution: ResolutionStatus = ResolutionStatus.EXPLICITLY_DECLARED


class NodeOutputDeclaration(CompilerModel):
    """An output contract a node produces, with its consumers where resolvable."""

    contract_version: str = WORKFLOW_IR_V2
    contract_ref: DataContractRef
    consumer_node_ids: Tuple[str, ...] = ()
    resolution: ResolutionStatus = ResolutionStatus.EXPLICITLY_DECLARED


class HumanReviewRequirement(CompilerModel):
    """Whether a node requires human review / authority. The compiler classifies
    and references; it never grants, approves, or authorizes."""

    contract_version: str = WORKFLOW_IR_V2
    required: bool = False
    #: "human_authority" | "human_review" | "none"
    review_kind: str = "none"
    authority_type: str = ""
    governance_owner: str = ""
    resolution: ResolutionStatus = ResolutionStatus.DETERMINISTICALLY_INFERRED
    provenance: PolicyProvenanceRef


class WorkflowNodeSemantics(CompilerModel):
    """The compiler-owned semantic description of one role-relevant node."""

    contract_version: str = WORKFLOW_IR_V2
    node_id: str
    node_kind: str
    semantic_purpose: str
    semantic_description: str = ""
    role_relevance: RoleRelevance
    required_capability_refs: Tuple[CapabilityRequirement, ...] = ()
    optional_capability_refs: Tuple[CapabilityRequirement, ...] = ()
    required_input_contract_refs: Tuple[NodeInputRequirement, ...] = ()
    produced_output_contract_refs: Tuple[NodeOutputDeclaration, ...] = ()
    required_tool_refs: Tuple[str, ...] = ()
    data_classification_refs: Tuple[str, ...] = ()
    permission_intent_refs: Tuple[str, ...] = ()
    authority_disposition: str
    canonical_capability_owner: str
    human_review_requirement: HumanReviewRequirement
    human_authority_requirement: bool = False
    governance_boundary_refs: Tuple[str, ...] = ()
    source_policy_refs: Tuple[str, ...] = ()
    provenance: PolicyProvenanceRef
    fingerprint: str = ""


class WorkflowDependencySemantics(CompilerModel):
    """Explicit, role-relevant dependency semantics for one edge."""

    contract_version: str = WORKFLOW_IR_V2
    edge_id: str
    source_node_id: str
    target_node_id: str
    dependency_kind: DependencyKind
    condition_ref: str = ""
    input_contract_refs: Tuple[str, ...] = ()
    output_contract_refs: Tuple[str, ...] = ()
    authority_context: str = ""
    provenance: PolicyProvenanceRef
    fingerprint: str = ""


class SemanticFeature(CompilerModel):
    """A declared contract-capability flag for a v2 artifact."""

    name: SemanticFeatureName
    present: bool


class SemanticDiagnostic(CompilerModel):
    """A typed, deterministic diagnostic emitted during enrichment or validation."""

    code: str
    severity: str
    message: str = ""
    workflow_identity: str = ""
    node_id: str = ""
    edge_id: str = ""
    source_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    contract_version: str = WORKFLOW_IR_V2
    fingerprint: str = ""


class WorkflowIRv2(CompilerModel):
    """The enriched workflow contract.

    Embeds the untouched v1 graph (``base_ir``) and adds node-semantics,
    dependency-semantics, feature declarations, and reference manifests beside it.
    ``base_ir_digest`` pins the exact v1 graph; the v2 ``workflow_fingerprint``
    commits to the base digest plus every enriched field.
    """

    ir_version: str = WORKFLOW_IR_V2
    contract_version: str = WORKFLOW_IR_V2
    policy_pack_id: str
    policy_pack_version: int
    #: The embedded, byte-stable v1 graph. Its own digest is unchanged by v2.
    base_ir: WorkflowIR
    base_ir_digest: str
    node_semantics: Tuple[WorkflowNodeSemantics, ...] = ()
    dependency_semantics: Tuple[WorkflowDependencySemantics, ...] = ()
    semantic_features: Tuple[SemanticFeature, ...] = ()
    capability_reference_manifest: Tuple[str, ...] = ()
    contract_reference_manifest: Tuple[str, ...] = ()
    provenance_manifest: Tuple[str, ...] = ()
    diagnostics: Tuple[SemanticDiagnostic, ...] = ()
    compiler_version: str = ""
    workflow_fingerprint: str = ""

    def logical_digest(self) -> str:
        """Content digest over the base graph digest plus all enriched fields
        (excluding the stored ``workflow_fingerprint`` slot)."""
        return hashing.digest(
            {
                "ir_version": self.ir_version,
                "policy_pack_id": self.policy_pack_id,
                "policy_pack_version": self.policy_pack_version,
                "base_ir_digest": self.base_ir_digest,
                "node_semantics": list(self.node_semantics),
                "dependency_semantics": list(self.dependency_semantics),
                "semantic_features": list(self.semantic_features),
                "capability_reference_manifest": list(self.capability_reference_manifest),
                "contract_reference_manifest": list(self.contract_reference_manifest),
                "provenance_manifest": list(self.provenance_manifest),
                "diagnostics": list(self.diagnostics),
            }
        )


__all__ = [
    "stamp",
    "PolicyProvenanceRef",
    "CapabilityRequirement",
    "DataContractRef",
    "NodeInputRequirement",
    "NodeOutputDeclaration",
    "HumanReviewRequirement",
    "WorkflowNodeSemantics",
    "WorkflowDependencySemantics",
    "SemanticFeature",
    "SemanticDiagnostic",
    "WorkflowIRv2",
]
