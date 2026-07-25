"""External execution contract (peer family — NOT assertion governance).

An external-execution provider dispatches to and observes an external business
system. It adapts onto the frozen kernel ``ExternalExecutionPort``. Assertion
governance must never be placed behind this interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from .base import Provider


class ExecutionBusinessOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExecutionDispatchRequest:
    action_type: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    idempotency_key: str = ""
    correlation_id: str = ""


@dataclass(frozen=True)
class ExecutionDispatchResult:
    """A *transport* result — never a business outcome."""

    accepted: bool
    external_request_id: str = ""
    acknowledgement: str = ""
    pending: bool = False
    timed_out: bool = False
    transport_error: str = ""
    retryable: bool = True


@dataclass(frozen=True)
class ExecutionObservation:
    """An *observed* business outcome."""

    business_outcome: ExecutionBusinessOutcome
    observed_parameters: Mapping[str, str] = field(default_factory=dict)
    final: bool = True
    reason: str = ""
    provider_trace_id: str = ""
    fingerprint: str = ""


@runtime_checkable
class ExternalExecutionProvider(Provider, Protocol):
    """Dispatch to and observe an external system; optional cancellation."""

    def dispatch(self, request: ExecutionDispatchRequest) -> ExecutionDispatchResult: ...
    def observe(self, *, external_request_id: str) -> ExecutionObservation: ...
    def cancel(self, *, external_request_id: str) -> bool: ...
