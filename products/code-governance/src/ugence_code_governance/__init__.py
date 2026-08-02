"""Ugence Code Governance — shadow governance product (MVP 1C).

Read-only and non-enforcing. This package proves the shadow governance path:

    GitHub change event -> exact change identity -> immutable evidence ->
    Claim Manifest -> non-compensatory mandatory-claim evaluation ->
    TAP assertion evaluation -> explicit authorized-actor decision ->
    DecisionRecord -> ContextEnvelopeRecord (cer.v1) -> exact prepared action ->
    ActionGate shadow evaluation -> reconstructable governance chain ->
    shadow recommendation only.

Execution is disabled. There is no GitHub write path, no merge credential, and no
execution provider in this phase. MVP 1B adds a shadow Action Clearance stage with
explainable human-intervention routing. MVP 1C adds an **opt-in** durable shadow
audit store (append-only, hash-linked, integrity-verified SQLite), restart-safe
recovery, integrity-verified reconstruction, and offline-verifiable audit bundles.
The durable store is a ``DURABLE_SHADOW_REFERENCE`` audit projection — never an
authoritative execution-consumption ledger.

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

# --- MVP 1C: durable shadow persistence (opt-in) -------------------------
from .persistence import (
    BundleVerification,
    DurableReconstructionResult,
    DurableReconstructionState,
    DurableShadowStore,
    DurableStoreConfig,
    PersistenceMode,
    RecordType,
    ReconstructionMode,
    RecoveryResult,
    RecoveryStatus,
    STORE_CLASSIFICATION,
    STORE_SCHEMA_VERSION,
    WorkflowEventType,
    open_durable_store,
)

# --- MVP 1D: read-only enterprise adapters + shadow pilot ----------------
from .adapters import (
    AdapterCapability,
    AdapterFailureCode,
    AdapterRegistryEntry,
    AdapterRegistryProjection,
    AdapterRequest,
    AdapterResult,
    ChangeWindowSnapshotAdapter,
    ControlStatusSnapshotAdapter,
    FactConsistency,
    FakeReadOnlyTransport,
    GitHubReadOnlyAdapter,
    IdentitySnapshotAdapter,
    IncidentSnapshotAdapter,
    NormalizedOperationalInput,
    ReadOnlyBoundaryViolation,
    ReadOnlyTransport,
    RetryPolicy,
    TargetHealthSnapshotAdapter,
    TransportPolicy,
    normalize_results,
)
from .pilot import (
    FeedbackAgreement,
    ObservedResolution,
    PilotBoundaryError,
    PilotReportVerification,
    PilotReviewerFeedback,
    PilotStatus,
    PilotThresholds,
    ShadowPilotConfig,
    ShadowPilotEvaluationRecord,
    ShadowPilotMetrics,
    ShadowPilotRunner,
    calculate_pilot_metrics,
    evaluate_pilot_status,
    export_shadow_pilot_report,
    verify_shadow_pilot_report,
)

# --- MVP 1E: deployable pilot operator -----------------------------------
from .pilot_operator import (
    CredentialReference,
    EvaluationCandidate,
    OperatorMetrics,
    PermissionVerification,
    PilotDeploymentConfig,
    PilotHealthStatus,
    PilotKillSwitchState,
    PilotLifecycleStatus,
    PilotOperator,
    PilotPreflightResult,
    PilotReadiness,
    PilotRecoveryResult,
    PilotRecoveryStatus,
    PilotRunRecord,
    PilotSecurityEvent,
    PilotStopThresholds,
    PreflightOutcome,
    ResolverKind,
    ReviewerQueueItem,
    ReviewerQueueStatus,
    SecurityEventKind,
    StopConditionKind,
    evaluate_stop_conditions,
    fingerprint_pilot_config,
    load_pilot_config,
    open_pilot_operator,
    recover_pilot,
    run_pilot_preflight,
    scan_for_credential,
    select_candidates,
    validate_pilot_config,
)

# --- MVP 1F: bounded shadow-pilot validation study -----------------------
from .pilot_study import (
    ActualOutcome,
    AdverseCaseKind,
    AmendmentReason,
    CalibrationAdjustment,
    CheckpointKind,
    CheckpointRecommendation,
    EvidenceStatus,
    IncrementalValue,
    IncrementalValueLabel,
    InterventionAssessment,
    PilotAdverseCase,
    PilotCalibrationRecommendation,
    PilotCandidate,
    PilotCandidateSelectionRecord,
    PilotCheckpointRecord,
    PilotCohort,
    PilotEvaluationAnnotation,
    PilotEvidenceClass,
    PilotPrePilotFreezeRecord,
    PilotReadinessAssessment,
    PilotReadinessVerdict,
    PilotReplayResult,
    PilotStudyEvaluation,
    PilotStudyManifest,
    PilotStudyMetrics,
    ReviewMode,
    RootCause,
    StatusAssessment,
    analyze_pilot_results,
    assess_enforcement_readiness,
    build_pilot_evidence_pack,
    collect_adverse_cases,
    create_pilot_checkpoint,
    freeze_pilot_study,
    generate_calibration_recommendations,
    replay_pilot_policy,
    run_pilot_security_verification,
    select_pilot_candidates,
    validate_study_manifest,
    verify_pilot_evidence_pack,
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
    # MVP 1C — durable shadow persistence
    "PersistenceMode",
    "DurableShadowStore",
    "DurableStoreConfig",
    "open_durable_store",
    "RecordType",
    "WorkflowEventType",
    "RecoveryStatus",
    "RecoveryResult",
    "ReconstructionMode",
    "DurableReconstructionState",
    "DurableReconstructionResult",
    "BundleVerification",
    "STORE_SCHEMA_VERSION",
    "STORE_CLASSIFICATION",
    # MVP 1D — read-only enterprise adapters
    "AdapterRequest",
    "AdapterResult",
    "AdapterCapability",
    "AdapterFailureCode",
    "FactConsistency",
    "ReadOnlyTransport",
    "FakeReadOnlyTransport",
    "TransportPolicy",
    "ReadOnlyBoundaryViolation",
    "AdapterRegistryEntry",
    "AdapterRegistryProjection",
    "NormalizedOperationalInput",
    "normalize_results",
    "GitHubReadOnlyAdapter",
    "RetryPolicy",
    "IdentitySnapshotAdapter",
    "ChangeWindowSnapshotAdapter",
    "IncidentSnapshotAdapter",
    "TargetHealthSnapshotAdapter",
    "ControlStatusSnapshotAdapter",
    # MVP 1D — shadow pilot
    "ShadowPilotConfig",
    "PilotThresholds",
    "PilotStatus",
    "ShadowPilotEvaluationRecord",
    "PilotReviewerFeedback",
    "FeedbackAgreement",
    "ObservedResolution",
    "ShadowPilotMetrics",
    "calculate_pilot_metrics",
    "evaluate_pilot_status",
    "ShadowPilotRunner",
    "PilotBoundaryError",
    "PilotReportVerification",
    "export_shadow_pilot_report",
    "verify_shadow_pilot_report",
    # MVP 1E — deployable pilot operator
    "PilotDeploymentConfig",
    "PilotStopThresholds",
    "validate_pilot_config",
    "fingerprint_pilot_config",
    "load_pilot_config",
    "CredentialReference",
    "ResolverKind",
    "scan_for_credential",
    "PilotOperator",
    "open_pilot_operator",
    "PilotLifecycleStatus",
    "PilotRunRecord",
    "PilotPreflightResult",
    "PreflightOutcome",
    "PermissionVerification",
    "run_pilot_preflight",
    "PilotHealthStatus",
    "PilotReadiness",
    "PilotRecoveryStatus",
    "PilotRecoveryResult",
    "recover_pilot",
    "EvaluationCandidate",
    "select_candidates",
    "StopConditionKind",
    "evaluate_stop_conditions",
    "ReviewerQueueItem",
    "ReviewerQueueStatus",
    "OperatorMetrics",
    "SecurityEventKind",
    "PilotSecurityEvent",
    "PilotKillSwitchState",
    # MVP 1F — bounded shadow-pilot validation study
    "PilotStudyManifest",
    "validate_study_manifest",
    "PilotPrePilotFreezeRecord",
    "freeze_pilot_study",
    "PilotEvidenceClass",
    "PilotCohort",
    "PilotCandidate",
    "PilotCandidateSelectionRecord",
    "select_pilot_candidates",
    "PilotEvaluationAnnotation",
    "ReviewMode",
    "StatusAssessment",
    "InterventionAssessment",
    "RootCause",
    "IncrementalValue",
    "IncrementalValueLabel",
    "ActualOutcome",
    "AmendmentReason",
    "CalibrationAdjustment",
    "AdverseCaseKind",
    "CheckpointKind",
    "CheckpointRecommendation",
    "PilotStudyEvaluation",
    "PilotStudyMetrics",
    "analyze_pilot_results",
    "PilotCalibrationRecommendation",
    "generate_calibration_recommendations",
    "PilotReplayResult",
    "replay_pilot_policy",
    "PilotAdverseCase",
    "collect_adverse_cases",
    "PilotCheckpointRecord",
    "create_pilot_checkpoint",
    "build_pilot_evidence_pack",
    "verify_pilot_evidence_pack",
    "PilotReadinessAssessment",
    "PilotReadinessVerdict",
    "assess_enforcement_readiness",
    "run_pilot_security_verification",
    "EvidenceStatus",
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
