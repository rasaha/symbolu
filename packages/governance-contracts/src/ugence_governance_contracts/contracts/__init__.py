"""Provider contracts — three distinct, non-interchangeable governance families."""
from __future__ import annotations

from .base import BaseProvider, Provider
from .assertion import (
    AssertionCoverage,
    AssertionGovernanceProvider,
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
)
from .action import (
    ActionGovernanceOutcome,
    ActionGovernanceProvider,
    ActionGovernanceRequest,
    ActionGovernanceResult,
)
from .execution import (
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
    ExternalExecutionProvider,
)
from .system_identity import (
    AssessedSystemBinding,
    SystemBindingAuthenticityStatus,
    SystemIdentityContractError,
)
from .idempotency import (
    IdempotencyContractError,
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
)
from .validity import (
    Validity,
    ValidityContractError,
    ValidityStatus,
)
from .audit import (
    AuditContractError,
    AuditReference,
)
from .data_classification import (
    DataClassificationContractError,
    DataClassificationLabel,
)
from .evidence import (
    AssessmentWindow,
    AttestationStatus,
    AttributionStatus,
    BenchmarkReference,
    ConfidenceBasis,
    EvidenceContractError,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceUsageScope,
    ForecastHorizon,
    MetricClaim,
    MetricObservation,
    PopulationSlice,
    SourceBasis,
    TransformationMethod,
    VerificationStatus,
)

__all__ = [
    "Provider", "BaseProvider",
    "AssertionGovernanceProvider", "AssertionGovernanceRequest",
    "AssertionGovernanceResult", "AssertionCoverage",
    "ActionGovernanceProvider", "ActionGovernanceRequest",
    "ActionGovernanceResult", "ActionGovernanceOutcome",
    "ExternalExecutionProvider", "ExecutionDispatchRequest",
    "ExecutionDispatchResult", "ExecutionObservation", "ExecutionBusinessOutcome",
    # GV-2E-a neutral evidence contracts (additive)
    "SourceBasis", "TransformationMethod", "AttestationStatus",
    "AttributionStatus", "VerificationStatus", "EvidenceUsageScope",
    "EvidenceContractError",
    "EvidenceReference", "EvidenceProvenance", "BenchmarkReference",
    "AssessmentWindow", "ForecastHorizon", "PopulationSlice", "ConfidenceBasis",
    "MetricClaim", "MetricObservation",
    # M-3R.3 neutral assessed-system identity (additive)
    "AssessedSystemBinding",
    "SystemBindingAuthenticityStatus",
    "SystemIdentityContractError",
    # G7 neutral idempotency contract (additive)
    "IdempotencyScope", "IdempotencyKey", "IdempotencyDisposition",
    "IdempotencyResolution", "IdempotencyContractError",
    # G8 neutral validity contract (additive)
    "ValidityStatus", "Validity", "ValidityContractError",
    # G4 neutral audit reference (additive)
    "AuditReference", "AuditContractError",
    # DE-5 neutral data-classification label (additive)
    "DataClassificationLabel", "DataClassificationContractError",
]
