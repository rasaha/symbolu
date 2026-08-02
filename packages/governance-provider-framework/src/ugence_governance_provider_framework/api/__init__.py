"""Governance Provider Framework — public API surface.

Provider implementations (future TAP, ActionGate, third parties) and applications
import from here. Re-exports contracts, metadata, registry, resolution,
configuration, adapters, errors, observability, and lifecycle with preserved
object identity.
"""
from __future__ import annotations

from ..version import CONTRACT_VERSION, __version__
from ..metadata import (
    ProviderCapabilities, ProviderCompatibility, ProviderDescriptor, ProviderHealth,
    ProviderKind)
from ..lifecycle import ProviderLifecycleState
from ..contracts import (
    ActionGovernanceOutcome, ActionGovernanceProvider, ActionGovernanceRequest,
    ActionGovernanceResult, AssertionCoverage, AssertionGovernanceProvider,
    AssertionGovernanceRequest, AssertionGovernanceResult, BaseProvider,
    ExecutionBusinessOutcome, ExecutionDispatchRequest, ExecutionDispatchResult,
    ExecutionObservation, ExternalExecutionProvider, Provider)
from ..registry import ProviderRegistry
from ..resolution import (
    ResolutionRecord, ResolutionRequest, SelectionRule, resolve)
from ..configuration import ProviderEntry, ProvidersConfiguration
from ..adapters import (
    ActionGovernanceControlPlaneAdapter, AssertionAssessment,
    AssertionAssessmentIntegration, AssertionLinkedRecordAdapter,
    ExternalExecutionAdapter)
from ..observability import (
    ProviderInvocationLog, ProviderInvocationRecord, record_invocation)
from ..errors import (
    FailureClass, ProviderCompatibilityError, ProviderConfigurationError, ProviderError,
    ProviderProtocolError, ProviderRegistrationError, ProviderResolutionError,
    ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)

__all__ = [
    "__version__", "CONTRACT_VERSION",
    "ProviderKind", "ProviderDescriptor", "ProviderCapabilities",
    "ProviderCompatibility", "ProviderHealth", "ProviderLifecycleState",
    "Provider", "BaseProvider",
    "AssertionGovernanceProvider", "AssertionGovernanceRequest",
    "AssertionGovernanceResult", "AssertionCoverage",
    "ActionGovernanceProvider", "ActionGovernanceRequest", "ActionGovernanceResult",
    "ActionGovernanceOutcome",
    "ExternalExecutionProvider", "ExecutionDispatchRequest", "ExecutionDispatchResult",
    "ExecutionObservation", "ExecutionBusinessOutcome",
    "ProviderRegistry", "resolve", "ResolutionRequest", "ResolutionRecord", "SelectionRule",
    "ProvidersConfiguration", "ProviderEntry",
    "ActionGovernanceControlPlaneAdapter", "ExternalExecutionAdapter",
    "AssertionAssessmentIntegration", "AssertionAssessment", "AssertionLinkedRecordAdapter",
    "ProviderInvocationLog", "ProviderInvocationRecord", "record_invocation",
    "ProviderError", "ProviderRegistrationError", "ProviderResolutionError",
    "ProviderCompatibilityError", "ProviderConfigurationError", "ProviderUnavailableError",
    "ProviderTimeoutError", "ProviderProtocolError", "ProviderResultValidationError",
    "FailureClass",
]
