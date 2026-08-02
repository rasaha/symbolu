"""Ugence Code Governance — shadow governance product (MVP 1A).

Read-only and non-enforcing. This package proves the shadow governance path:

    GitHub change event -> exact change identity -> immutable evidence ->
    Claim Manifest -> non-compensatory mandatory-claim evaluation ->
    TAP assertion evaluation -> explicit authorized-actor decision ->
    DecisionRecord -> ContextEnvelopeRecord (cer.v1) -> exact prepared action ->
    ActionGate shadow evaluation -> reconstructable governance chain ->
    shadow recommendation only.

Execution is disabled. There is no GitHub write path, no merge credential, no
Action Clearance, and no execution provider in this phase.

This ``__init__`` exposes an *intentional* public API — not every internal type.
Internal modules remain importable for advanced/test use but are not part of the
supported surface.
"""
from __future__ import annotations

from .version import EXECUTION_ENABLED, MVP_PHASE, __version__

# --- top-level service ---------------------------------------------------
from .api import CodeGovernanceService

# --- change identity + core vocabularies --------------------------------
from .models import (
    ClaimStatus,
    ClaimType,
    ExecutionStatus,
    GovernedChangeIdentity,
    MergeMethod,
    ReconstructionState,
    RiskTier,
    ValidatorTrustLevel,
    WorkflowMode,
    WorkflowState,
)

# --- evidence + claims ---------------------------------------------------
from .evidence import EvidenceRecord
from .claims import (
    ClaimEntry,
    ClaimEvaluation,
    ClaimInput,
    ClaimManifest,
    ClaimRequirement,
    EvidenceReference,
    ValidatorIdentity,
    build_claim_manifest,
    evaluate_claim_requirements,
)

# --- governance adapters (advisory + prepared action) -------------------
from .governance import (
    AuthorizedActor,
    DecisionInput,
    GovernanceRecommendation,
    PreparedMergeAction,
    RecommendationDisposition,
    ShadowActionEvaluation,
)

# --- policies ------------------------------------------------------------
from .policies import DEFAULT_POLICY, RepositoryPolicy

# --- reconstruction ------------------------------------------------------
from .reconstruction import GovernanceChainRecord, ReconstructionResult

# --- workflow records ----------------------------------------------------
from .workflow import WorkflowRevision

# --- MVP 1B: shadow Action Clearance integration -------------------------
from .clearance import (
    ActionClearanceEvaluationRecord,
    ActionClearanceShadowAdapter,
    AuthorityRole,
    CodeGovernanceClearanceProfile,
    CodeGovernanceOperationalSnapshot,
    HumanInterventionAssessment,
    InterventionRoutingPolicy,
    InterventionType,
    RepositoryClassification,
    SignalSourceEntry,
    TrustedSignalSourceProjection,
)

# --- errors --------------------------------------------------------------
from .errors import (
    ChainIncompleteError,
    CodeGovernanceError,
    DecisionAuthorityRequiredError,
    InvalidWorkflowTransitionError,
    MalformedEventError,
    SignatureVerificationError,
    StaleEvidenceError,
    TenantMismatchError,
    UnsupportedEventError,
)

__all__ = [
    "__version__",
    "MVP_PHASE",
    "EXECUTION_ENABLED",
    # service
    "CodeGovernanceService",
    # identity + vocab
    "GovernedChangeIdentity",
    "MergeMethod",
    "RiskTier",
    "ClaimType",
    "ClaimStatus",
    "ValidatorTrustLevel",
    "WorkflowState",
    "WorkflowMode",
    "ExecutionStatus",
    "ReconstructionState",
    # evidence + claims
    "EvidenceRecord",
    "ClaimManifest",
    "ClaimEntry",
    "ClaimInput",
    "ClaimRequirement",
    "ClaimEvaluation",
    "EvidenceReference",
    "ValidatorIdentity",
    "build_claim_manifest",
    "evaluate_claim_requirements",
    # governance
    "AuthorizedActor",
    "DecisionInput",
    "GovernanceRecommendation",
    "RecommendationDisposition",
    "PreparedMergeAction",
    "ShadowActionEvaluation",
    # policy
    "RepositoryPolicy",
    "DEFAULT_POLICY",
    # reconstruction + workflow
    "GovernanceChainRecord",
    "ReconstructionResult",
    "WorkflowRevision",
    # MVP 1B — shadow Action Clearance integration
    "ActionClearanceShadowAdapter",
    "CodeGovernanceClearanceProfile",
    "RepositoryClassification",
    "CodeGovernanceOperationalSnapshot",
    "TrustedSignalSourceProjection",
    "SignalSourceEntry",
    "ActionClearanceEvaluationRecord",
    "HumanInterventionAssessment",
    "InterventionRoutingPolicy",
    "InterventionType",
    "AuthorityRole",
    # errors
    "CodeGovernanceError",
    "DecisionAuthorityRequiredError",
    "ChainIncompleteError",
    "InvalidWorkflowTransitionError",
    "MalformedEventError",
    "UnsupportedEventError",
    "TenantMismatchError",
    "SignatureVerificationError",
    "StaleEvidenceError",
]
