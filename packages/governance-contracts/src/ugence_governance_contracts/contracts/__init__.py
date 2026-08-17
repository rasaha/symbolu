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
]
