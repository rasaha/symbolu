"""Decision Governance — Provider Framework (application-layer kernel extension).

A generic framework that lets applications consume external governance
capabilities — assertion, authorization, and execution providers — without
importing any specific implementation. Providers are registered as descriptors,
discovered and selected by configuration (name / capability / default / mock),
and adapted onto the frozen kernel ports. The kernel (``decision_governance``)
never imports this framework; this framework depends only on the kernel's public
API (``decision_governance.api``).

Dependency direction: ``applications`` → ``decision_governance_provider`` →
``decision_governance``. The reverse never holds.
"""
from __future__ import annotations

from .version import __version__
from .metadata import (
    ProviderCapabilities,
    ProviderKind,
    ProviderMetadata,
)
from .contracts import (
    AssertionProvider,
    AssertionResult,
    AuthorizationContext,
    AuthorizationOutcome,
    AuthorizationProvider,
    AuthorizationVerdict,
    BaseProvider,
    BusinessOutcome,
    DispatchReceipt,
    ExecutionProvider,
    HealthStatus,
    LifecycleState,
    ObservationReport,
    Provider,
)
from .descriptor import ProviderDescriptor
from .registry import ProviderRegistry
from .resolution import (
    ProviderConfiguration,
    ProviderSelection,
    resolve_configuration,
    resolve_provider,
)
from .errors import (
    IncompatibleProviderVersionError,
    ProviderCapabilityError,
    ProviderConflictError,
    ProviderError,
    ProviderLifecycleError,
    ProviderNotFoundError,
    ProviderResolutionError,
)

__all__ = [
    "__version__",
    # metadata
    "ProviderKind", "ProviderMetadata", "ProviderCapabilities",
    # contracts
    "Provider", "AssertionProvider", "AuthorizationProvider", "ExecutionProvider",
    "BaseProvider", "LifecycleState", "HealthStatus",
    "AssertionResult", "AuthorizationContext", "AuthorizationOutcome",
    "AuthorizationVerdict", "DispatchReceipt", "ObservationReport", "BusinessOutcome",
    # registry / descriptor / resolution
    "ProviderDescriptor", "ProviderRegistry",
    "ProviderSelection", "ProviderConfiguration", "resolve_provider", "resolve_configuration",
    # errors
    "ProviderError", "ProviderNotFoundError", "ProviderConflictError",
    "IncompatibleProviderVersionError", "ProviderCapabilityError",
    "ProviderResolutionError", "ProviderLifecycleError",
]
