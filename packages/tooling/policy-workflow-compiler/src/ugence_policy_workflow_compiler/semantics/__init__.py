"""Additive ``workflow_ir.v2`` semantic-enrichment layer (Policy Workflow
Compiler P2). The v1 contract and its fingerprints are unchanged."""

from __future__ import annotations

from .contracts import (
    CapabilityRequirementSource,
    DependencyKind,
    DerivationClass,
    RequirementLevel,
    ResolutionStatus,
    RoleRelevance,
    SUPPORTED_WORKFLOW_IR_VERSIONS,
    SemanticFeatureName,
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V2,
)
from .extraction import (
    classify_role_relevance,
    compile_workflow_v2,
    enrich_workflow,
    extract_dependencies,
    extract_node_semantics,
    upgrade_workflow_ir,
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
)

__all__ = [
    "WORKFLOW_IR_V1",
    "WORKFLOW_IR_V2",
    "SUPPORTED_WORKFLOW_IR_VERSIONS",
    "RoleRelevance",
    "RequirementLevel",
    "CapabilityRequirementSource",
    "DependencyKind",
    "ResolutionStatus",
    "DerivationClass",
    "SemanticFeatureName",
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
    "classify_role_relevance",
    "extract_node_semantics",
    "extract_dependencies",
    "enrich_workflow",
    "compile_workflow_v2",
    "upgrade_workflow_ir",
]
