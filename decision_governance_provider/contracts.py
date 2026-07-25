"""Provider contracts (application layer).

Abstract, implementation-neutral provider interfaces and their provider-native
result types. These are **application-layer** contracts — deliberately *not*
kernel contracts and *not* kernel ports. They are kernel-free: a provider speaks
in these neutral types, and the adapter layer translates them onto the frozen
kernel ports. This keeps providers decoupled from kernel contract shapes.

Three provider kinds mirror the three kernel port seams:

* :class:`AssertionProvider`     — resolve a finalized upstream record
* :class:`AuthorizationProvider` — authorize a prepared action under controls
* :class:`ExecutionProvider`     — dispatch to, and observe, an external system
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Protocol, runtime_checkable

from .metadata import ProviderCapabilities, ProviderKind, ProviderMetadata


# --- lifecycle --------------------------------------------------------------

class LifecycleState(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class HealthStatus:
    healthy: bool
    detail: str = ""


# --- provider-native result types (kernel-free) -----------------------------

@dataclass(frozen=True)
class AssertionResult:
    """A provider's neutral view of a finalized upstream record."""

    found: bool
    record_type: str = ""
    record_id: str = ""
    version: int = 1
    tenant_id: str = ""
    finalized: bool = False
    blocked: bool = False
    subject_ref: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationContext:
    """The neutral inputs an authorization provider decides on."""

    action_type: str
    parameters: Mapping[str, str]
    tenant_id: str = ""
    subject_refs: tuple[str, ...] = ()
    correlation_id: str = ""
    policy_refs: tuple[str, ...] = ()
    cer_expired: bool = False


class AuthorizationOutcome(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class AuthorizationVerdict:
    outcome: AuthorizationOutcome
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class DispatchReceipt:
    """The *transport* result of dispatching — never a business outcome."""

    accepted: bool
    external_request_id: str = ""
    acknowledgement: str = ""
    timed_out: bool = False
    transport_error: str = ""


class BusinessOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ObservationReport:
    """An *observed* business outcome from the external system."""

    business_outcome: BusinessOutcome
    observed_parameters: Mapping[str, str] = field(default_factory=dict)
    final: bool = True
    reason: str = ""


# --- provider protocols -----------------------------------------------------

@runtime_checkable
class Provider(Protocol):
    """Common managed-provider surface: identity, capabilities, lifecycle."""

    def metadata(self) -> ProviderMetadata: ...
    def capabilities(self) -> ProviderCapabilities: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def health(self) -> HealthStatus: ...


@runtime_checkable
class AssertionProvider(Provider, Protocol):
    """Resolves a domain record into a neutral assertion (→ ``LinkedRecordPort``)."""

    def resolve_assertion(
        self, *, tenant_id: str, record_type: str, record_id: str,
        version: Optional[int] = None,
    ) -> AssertionResult: ...


@runtime_checkable
class AuthorizationProvider(Provider, Protocol):
    """Authorizes a prepared action (→ ``ActionControlPlanePort``)."""

    def authorize(self, context: AuthorizationContext) -> AuthorizationVerdict: ...


@runtime_checkable
class ExecutionProvider(Provider, Protocol):
    """Dispatches to and observes an external system (→ ``ExternalExecutionPort``)."""

    def dispatch(self, *, action_type: str, parameters: Mapping[str, str]) -> DispatchReceipt: ...
    def observe(self, *, external_request_id: str) -> ObservationReport: ...


# --- convenience concrete base ---------------------------------------------

class BaseProvider:
    """A concrete base handling identity, capabilities, and lifecycle bookkeeping.

    Real and mock providers may subclass this and implement their kind-specific
    method(s); the registry uses the lifecycle here. Structural typing means
    subclassing is optional — any object satisfying a provider Protocol works.
    """

    def __init__(self, metadata: ProviderMetadata, capabilities: ProviderCapabilities) -> None:
        self._metadata = metadata
        self._capabilities = capabilities
        self._state = LifecycleState.CREATED

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    @property
    def state(self) -> LifecycleState:
        return self._state

    def start(self) -> None:
        self._state = LifecycleState.STARTED

    def stop(self) -> None:
        self._state = LifecycleState.STOPPED

    def health(self) -> HealthStatus:
        return HealthStatus(healthy=self._state is LifecycleState.STARTED,
                            detail=self._state.value)
