"""Curated public API of ugence-reasoning-method-governance (slice 1)."""

from .contracts.assessment import (
    EVIDENCE_STATUS_SOURCE_V1,
    FIT_SCHEMA_VERSION,
    USAGE_SCOPE_RESEARCH_ONLY,
    DominationRecord,
    FitOutcome,
    QualityDirection,
    QualityResult,
    ReasoningMethodFitAssessment,
    ResourceDelta,
)
from .contracts.catalog import (
    CATALOG_SCHEMA_VERSION,
    COMPLEXITY_SIGNAL_TOKENS,
    SCALAR_LABEL_FIELD_NAMES,
    ImplementationEvidence,
    ImplementationEvidenceKind,
    ImplementationStatus,
    ReasoningMethodCatalog,
    ReasoningMethodCatalogRef,
    ReasoningMethodEntry,
    ReasoningMethodRef,
    derive_implementation_status,
)
from .contracts.envelopes import (
    ATTESTATION_ENVELOPE_SCHEMA_VERSION,
    VERIFICATION_ENVELOPE_SCHEMA_VERSION,
    AttestationEnvelope,
    EvidenceStatusView,
    VerificationEnvelope,
)
from .contracts.plan import (
    RESEARCH_PLAN_SCHEMA_VERSION,
    ChallengerSamplingPolicy,
    ResearchComparisonPlan,
    SamplingKind,
)
from .contracts.ports import (
    AUTHORITY_RESOLUTION_BASIS_V1,
    COMPARISON_REQUEST_SCHEMA_VERSION,
    COMPARISON_RESULT_SCHEMA_VERSION,
    ReadinessComparisonRequest,
    ReadinessComparisonResult,
    Refusal,
    ResolvedAdmission,
    ResolvedAuthority,
)
from .contracts.record import (
    EVIDENCE_AXIS_FIELD_NAMES,
    RECORD_SCHEMA_VERSION,
    RECORD_V1_ATTESTATION_STATUS,
    RECORD_V1_SOURCE_BASIS,
    RECORD_V1_VERIFICATION_STATUS,
    ArtifactKind,
    ArtifactRef,
    BindingRef,
    CountBasis,
    ExecutionTelemetry,
    ReasoningMethodExecutionRecord,
    TokenUsageSnapshot,
    UsageAvailabilityToken,
)
from .contracts.task_class import (
    HIGH_CONSEQUENCE_CLASSES,
    PROFILE_SCHEMA_VERSION,
    RESOURCE_DIMENSION_ORDER,
    TASK_CLASS_SCHEMA_VERSION,
    AggregationRef,
    ComparisonPolicy,
    ConsequenceClass,
    EvidenceAdmissionRef,
    ResourceDimension,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
    compatible,
)
from .errors import ContractError, ContractErrorCode, RefusalCode
from .version import __version__

__all__ = [
    "__version__",
    # errors
    "ContractError", "ContractErrorCode", "RefusalCode",
    # catalog
    "CATALOG_SCHEMA_VERSION", "COMPLEXITY_SIGNAL_TOKENS", "SCALAR_LABEL_FIELD_NAMES",
    "ImplementationEvidenceKind", "ImplementationStatus", "ImplementationEvidence",
    "derive_implementation_status", "ReasoningMethodCatalogRef", "ReasoningMethodRef",
    "ReasoningMethodEntry", "ReasoningMethodCatalog",
    # task class
    "PROFILE_SCHEMA_VERSION", "TASK_CLASS_SCHEMA_VERSION", "TaskReversibility", "ConsequenceClass",
    "HIGH_CONSEQUENCE_CLASSES", "SufficiencyKind", "ResourceDimension", "RESOURCE_DIMENSION_ORDER",
    "AggregationRef", "EvidenceAdmissionRef", "SufficiencyRule", "ComparisonPolicy", "TaskProfile",
    "TaskClassIdentity", "compatible",
    # record
    "RECORD_SCHEMA_VERSION", "RECORD_V1_SOURCE_BASIS", "RECORD_V1_ATTESTATION_STATUS",
    "RECORD_V1_VERIFICATION_STATUS", "EVIDENCE_AXIS_FIELD_NAMES", "ArtifactKind", "ArtifactRef",
    "CountBasis", "UsageAvailabilityToken", "TokenUsageSnapshot", "ExecutionTelemetry", "BindingRef",
    "ReasoningMethodExecutionRecord",
    # assessment
    "FIT_SCHEMA_VERSION", "EVIDENCE_STATUS_SOURCE_V1", "USAGE_SCOPE_RESEARCH_ONLY", "FitOutcome",
    "QualityDirection", "QualityResult", "ResourceDelta", "DominationRecord", "ReasoningMethodFitAssessment",
    # envelopes
    "ATTESTATION_ENVELOPE_SCHEMA_VERSION", "VERIFICATION_ENVELOPE_SCHEMA_VERSION", "AttestationEnvelope",
    "VerificationEnvelope", "EvidenceStatusView",
    # ports
    "COMPARISON_REQUEST_SCHEMA_VERSION", "COMPARISON_RESULT_SCHEMA_VERSION", "AUTHORITY_RESOLUTION_BASIS_V1",
    "ResolvedAuthority", "ResolvedAdmission", "Refusal", "ReadinessComparisonRequest", "ReadinessComparisonResult",
    # plan
    "RESEARCH_PLAN_SCHEMA_VERSION", "SamplingKind", "ChallengerSamplingPolicy", "ResearchComparisonPlan",
]
