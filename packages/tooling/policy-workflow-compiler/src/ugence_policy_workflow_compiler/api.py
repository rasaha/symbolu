"""Curated public API for the Ugence Policy Workflow Compiler.

This is the single supported import surface:

    import ugence_policy_workflow_compiler.api as api

It re-exports the structured policy-pack object model, the validator, the
capability registry, the workflow IR, the compiler, assurance/audit/approval/diff
types, and the top-level convenience functions. Internal helpers are not exposed.
The name set is frozen against ``artifacts/public_api.json``.
"""

from __future__ import annotations

# -- object model --------------------------------------------------------------
from .models import (
    ActionConstraint,
    ApprovalDecision,
    ApprovalPath,
    ApprovalStep,
    AssuranceManifest,
    AuditFieldDefinition,
    AuditRequirement,
    AuditSchema,
    AuthorityDisposition,
    AuthorityRequirement,
    AuthorityType,
    BlockBehavior,
    CapabilityId,
    Comparator,
    ConnectorMapping,
    ConstraintKind,
    CoverageMatrix,
    DecisionRule,
    EvidenceKind,
    ExceptionRule,
    ExpectedOutcome,
    HumanApprovalRecord,
    LegitimateCounterexample,
    ObjectType,
    OverrideRule,
    PolicyObject,
    PolicyPack,
    PolicyPackStatus,
    Predicate,
    ProhibitedCondition,
    ProvenanceReference,
    ProvenanceSourceType,
    ProvenanceStatus,
    ReplayCase,
    RequiredEvidence,
    SequenceRiskPattern,
    SourceDocument,
    TestCategory,
    TestScenario,
    is_legal_transition,
)

# -- validation ----------------------------------------------------------------
from .validation import (
    PolicyPackValidator,
    Severity,
    ValidationDiagnostic,
    ValidationReport,
    validate_policy_pack,
)

# -- capability registry + IR + compiler ---------------------------------------
from .compiler import (
    CapabilityDefinition,
    CapabilityManifest,
    CapabilityRegistry,
    CompilationResult,
    CompiledReleasePackage,
    EdgeKind,
    GovernedWorkflowCompiler,
    NodeKind,
    ReleaseManifest,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
    compile_policy_pack,
)

# -- approval ------------------------------------------------------------------
from .approval import ApprovalService, build_approval_record, compute_pack_digest

# -- diff ----------------------------------------------------------------------
from .diff import ChangeType, ImpactSummary, ObjectChange, PolicyPackDiff, diff_policy_packs

# -- verification --------------------------------------------------------------
from .verification import (
    CompiledPackageVerifier,
    VerificationReport,
    verify_compiled_package,
)

# -- P2: workflow_ir.v2 semantic enrichment (additive) -------------------------
from .semantics import (
    CapabilityRequirement,
    CapabilityRequirementSource,
    DataContractRef,
    DependencyKind,
    DerivationClass,
    HumanReviewRequirement,
    NodeInputRequirement,
    NodeOutputDeclaration,
    PolicyProvenanceRef,
    RequirementLevel,
    ResolutionStatus,
    RoleRelevance,
    SemanticDiagnostic,
    SemanticFeature,
    SemanticFeatureName,
    WorkflowDependencySemantics,
    WorkflowIRv2,
    WorkflowNodeSemantics,
    classify_role_relevance,
    compile_workflow_v2,
    enrich_workflow,
    upgrade_workflow_ir,
)
from .validation.release_validator import (
    CompiledReleaseValidator,
    ReleaseValidationCode,
    ReleaseValidationResult,
    ReleaseValidationState,
    validate_compiled_release,
)

# -- version -------------------------------------------------------------------
from .version import (
    SUPPORTED_WORKFLOW_IR_VERSIONS,
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION,
    WORKFLOW_IR_V2,
    WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION,
    UnsupportedContractVersion,
    VersionInfo,
    digest_compiler_version_for,
    version_info,
)

__all__ = [
    # object model
    "PolicyPack",
    "PolicyPackStatus",
    "PolicyObject",
    "ObjectType",
    "SourceDocument",
    "ProvenanceReference",
    "ProvenanceSourceType",
    "ProvenanceStatus",
    "DecisionRule",
    "Predicate",
    "Comparator",
    "ProhibitedCondition",
    "RequiredEvidence",
    "EvidenceKind",
    "AuthorityRequirement",
    "AuthorityType",
    "AuthorityDisposition",
    "ApprovalPath",
    "ApprovalStep",
    "ExceptionRule",
    "OverrideRule",
    "ActionConstraint",
    "ConstraintKind",
    "SequenceRiskPattern",
    "LegitimateCounterexample",
    "ConnectorMapping",
    "AuditRequirement",
    "AuditFieldDefinition",
    "AuditSchema",
    "TestScenario",
    "TestCategory",
    "ReplayCase",
    "ExpectedOutcome",
    "CoverageMatrix",
    "AssuranceManifest",
    "HumanApprovalRecord",
    "ApprovalDecision",
    "BlockBehavior",
    "CapabilityId",
    "is_legal_transition",
    # validation
    "PolicyPackValidator",
    "ValidationReport",
    "ValidationDiagnostic",
    "Severity",
    "validate_policy_pack",
    # registry + IR + compiler
    "CapabilityRegistry",
    "CapabilityDefinition",
    "CapabilityManifest",
    "WorkflowIR",
    "WorkflowNode",
    "WorkflowEdge",
    "NodeKind",
    "EdgeKind",
    "GovernedWorkflowCompiler",
    "CompilationResult",
    "CompiledReleasePackage",
    "ReleaseManifest",
    "compile_policy_pack",
    # approval
    "ApprovalService",
    "build_approval_record",
    "compute_pack_digest",
    # diff
    "PolicyPackDiff",
    "ObjectChange",
    "ImpactSummary",
    "ChangeType",
    "diff_policy_packs",
    # verification
    "VerificationReport",
    "CompiledPackageVerifier",
    "verify_compiled_package",
    # -- P2: workflow_ir.v2 semantic enrichment --
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
    "enrich_workflow",
    "compile_workflow_v2",
    "upgrade_workflow_ir",
    "CompiledReleaseValidator",
    "ReleaseValidationResult",
    "ReleaseValidationState",
    "ReleaseValidationCode",
    "validate_compiled_release",
    # version
    "version_info",
    "VersionInfo",
    "WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION",
    "WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION",
    "digest_compiler_version_for",
    "UnsupportedContractVersion",
]
