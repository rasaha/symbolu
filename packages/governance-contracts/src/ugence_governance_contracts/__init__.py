"""Ugence Governance Contracts — the canonical, neutral, reusable contract layer.

A **leaf** package: it defines the provider-neutral governance contracts (request
/ result envelopes, provider protocols, provider metadata, lifecycle states, and
the error taxonomy) that capabilities and the provider framework depend on. It
imports **only the Python standard library** — never a capability, product,
platform, console, or research package.

Authority note: these are neutral *contracts*, not authority. The meaning of each
result (advisory vs binding, authorization vs clearance vs execution) is owned by
the capability that produces it — this package does not change any authority
boundary.

Import the curated surface from :mod:`ugence_governance_contracts.api`.
"""

from __future__ import annotations

__version__ = "0.5.0"

#: The provider-contract version this package publishes (unchanged from the
#: pre-migration ``governance_providers`` framework value). The GV-2E-a evidence
#: contracts and the M-3R.3 neutral assessed-system identity contracts are new,
#: additive, backward-compatible neutral families; neither changes the provider
#: contract surface, so this value is deliberately unchanged. The G7 idempotency
#: and G8 validity families (0.4.0) are likewise additive neutral families: no
#: provider dataclass, protocol, enum or default moved.
CONTRACT_VERSION = "1.0.0"

from .errors import (  # noqa: E402
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
from .lifecycle import (  # noqa: E402
    ProviderLifecycleState,
    assert_transition,
    is_legal_transition,
)
from .metadata import (  # noqa: E402
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderHealth,
    ProviderKind,
)
from .contracts import (  # noqa: E402
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
    MetricClaim,
    MetricObservation,
    PopulationSlice,
    Provider,
    SourceBasis,
    SystemBindingAuthenticityStatus,
    SystemIdentityContractError,
    IdempotencyContractError,
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
    Validity,
    ValidityContractError,
    ValidityStatus,
    TransformationMethod,
    VerificationStatus,
)

from . import api  # noqa: E402,F401

__all__ = [
    "CONTRACT_VERSION",
    # errors
    "FailureClass", "ProviderError", "ProviderRegistrationError",
    "ProviderResolutionError", "ProviderCompatibilityError",
    "ProviderConfigurationError", "ProviderUnavailableError",
    "ProviderTimeoutError", "ProviderProtocolError", "ProviderResultValidationError",
    # lifecycle
    "ProviderLifecycleState", "is_legal_transition", "assert_transition",
    # metadata
    "ProviderKind", "ProviderCapabilities", "ProviderCompatibility",
    "ProviderDescriptor", "ProviderHealth",
    # contracts
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
    "api",
]
