"""Canonical public API for the Ugence Governance Contracts.

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_governance_contracts`). Internal
lifecycle mechanics (``is_legal_transition`` / ``assert_transition``) are **not**
exposed here — they remain available on the full namespace for the provider
framework but are not part of the curated contract API.

Every symbol below is ``PUBLIC_STABLE`` and matches, field-for-field and
enum-for-enum, the frozen ``governance_providers`` contract surface it was
extracted from (see docs/migrations/governance_contracts/PUBLIC_API_INVENTORY.md).
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
    BaseProvider,
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
    ExternalExecutionProvider,
    Provider,
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
]
