"""Canonical public API for the Ugence Governance Contracts.

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_governance_contracts`). Internal
lifecycle mechanics (``is_legal_transition`` / ``assert_transition``) are **not**
exposed here — they remain available on the full namespace for the provider
framework but are not part of the curated contract API.

Every symbol below is ``PUBLIC_STABLE`` and matches, field-for-field and
enum-for-enum, the frozen ``governance_providers`` contract surface it was
extracted from (see Project_documentation/repository/docs/migrations/governance_contracts/PUBLIC_API_INVENTORY.md).
"""

from __future__ import annotations

from . import CONTRACT_VERSION, __version__
from .errors import (
    FailureClass,
    ProviderCompatibilityError,
    ProviderConfigurationError,
    ProviderError,
    ProviderProtocolError,
    ProviderRegistrationError,
    ProviderResolutionError,
    ProviderResultValidationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from .lifecycle import ProviderLifecycleState
from .metadata import (
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderHealth,
    ProviderKind,
)
from .contracts import (
    ActionGovernanceOutcome,
    ActionGovernanceProvider,
    ActionGovernanceRequest,
    ActionGovernanceResult,
    AssertionCoverage,
    AssertionGovernanceProvider,
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
    AssessedSystemBinding,
    AssessmentWindow,
    AttestationStatus,
    AttributionStatus,
    AuditContractError,
    AuditReference,
    BaseProvider,
    BenchmarkReference,
    ConfidenceBasis,
    EvidenceContractError,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceUsageScope,
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
    ExternalExecutionProvider,
    ForecastHorizon,
    IdempotencyContractError,
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
    MetricClaim,
    MetricObservation,
    PopulationSlice,
    Provider,
    SourceBasis,
    SystemBindingAuthenticityStatus,
    SystemIdentityContractError,
    TransformationMethod,
    Validity,
    ValidityContractError,
    ValidityStatus,
    VerificationStatus,
)

__all__ = [
    "__version__", "CONTRACT_VERSION",
    "FailureClass", "ProviderError", "ProviderRegistrationError",
    "ProviderResolutionError", "ProviderCompatibilityError",
    "ProviderConfigurationError", "ProviderUnavailableError",
    "ProviderTimeoutError", "ProviderProtocolError", "ProviderResultValidationError",
    "ProviderLifecycleState",
    "ProviderKind", "ProviderCapabilities", "ProviderCompatibility",
    "ProviderDescriptor", "ProviderHealth",
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
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus",
    "SystemIdentityContractError",
    # G7 neutral idempotency contract (additive)
    "IdempotencyScope", "IdempotencyKey", "IdempotencyDisposition",
    "IdempotencyResolution", "IdempotencyContractError",
    # G8 neutral validity contract (additive)
    "ValidityStatus", "Validity", "ValidityContractError",
    # G4 neutral audit reference (additive)
    "AuditReference", "AuditContractError",
]
