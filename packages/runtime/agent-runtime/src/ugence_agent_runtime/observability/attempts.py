"""Neutral provider-attempt telemetry (additive; deterministic; provider-neutral).

The retry loop invokes ``provider.execute(...)`` one or more times for a single task.
Each invocation is ONE attempt that may have consumed provider tokens — including a
failed, timed-out, or exception attempt. Before this seam the runtime only kept a
final attempt *count*, discarding the earlier attempts; this module lets a neutral
observer see every actual attempt without moving any provider-specific semantics into
the runtime.

Boundary: the runtime owns the authoritative ``attempt_number`` and the neutral
status. It NEVER imports a provider SDK and NEVER interprets provider-specific token
fields — a provider may attach an opaque neutral usage mapping to its
:class:`~ugence_agent_runtime.providers.interfaces.ToolResult` metadata (under
:data:`PROVIDER_USAGE_METADATA_KEY`) and the runtime forwards it verbatim, uninspected.
Normalizing that mapping into typed token fields is the job of an integration adapter,
not the runtime.

A governance HOLD/BLOCK/ESCALATE, an exact-action clearance/integrity rejection, or a
provider-not-found never reaches an attempt — the provider is not invoked — so NO
attempt is observed for those. Only an actual ``provider.execute`` call produces one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

#: The neutral key under which a provider MAY expose an opaque usage mapping on its
#: ``ToolResult.metadata``. The runtime forwards the mapping's value verbatim and never
#: interprets its contents (provider-specific token field names stay provider-specific).
PROVIDER_USAGE_METADATA_KEY = "token_usage"


class ProviderAttemptStatus(str, Enum):
    """The neutral disposition of ONE actual provider invocation."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    EXCEPTION = "EXCEPTION"


@dataclass(frozen=True)
class AttemptContext:
    """The task/workflow identity threaded into the execution loop for telemetry.

    Immutable and neutral: identities only, no arguments, prompts, credentials, or
    provider payloads.
    """

    workflow_id: Optional[str] = None
    instance_id: Optional[str] = None
    task_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderAttempt:
    """A neutral record of one actual ``provider.execute`` invocation.

    ``attempt_number`` is runtime-authoritative (1 for the first attempt, incremented
    per retry — retries are never collapsed into the final attempt). ``neutral_usage``
    is the provider's opaque usage mapping when supplied, else ``None`` (unknown — never
    fabricated). ``failure_category`` is the runtime's neutral classification string
    (e.g. the ``FailureCategory`` value), never a provider-specific code.
    """

    provider_id: str
    operation: str
    attempt_number: int
    status: ProviderAttemptStatus
    ok: bool
    provider_invoked: bool = True
    workflow_id: Optional[str] = None
    instance_id: Optional[str] = None
    task_id: Optional[str] = None
    correlation_id: Optional[str] = None
    neutral_usage: Optional[Mapping[str, Any]] = None
    failure_category: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "operation": self.operation,
            "attempt_number": self.attempt_number,
            "status": self.status.value,
            "ok": self.ok,
            "provider_invoked": self.provider_invoked,
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "neutral_usage": dict(self.neutral_usage) if self.neutral_usage is not None else None,
            "failure_category": self.failure_category,
        }


@runtime_checkable
class AttemptObserver(Protocol):
    """A neutral sink notified once per actual provider attempt.

    Implementations must be side-effect-tolerant and must never raise back into the
    execution loop (the runtime guards against a raising observer). They receive neutral
    telemetry only and must not be relied on to influence execution — observing an
    attempt can never change the provider action.
    """

    def on_attempt(self, attempt: ProviderAttempt) -> None: ...


@dataclass(frozen=True)
class AttemptObservationFailure:
    """A structured, neutral signal that an :class:`AttemptObserver` raised (F2).

    The runtime is **fail-open** with respect to provider execution: an observer raising
    never re-executes the provider, never erases a successful provider result, and never
    changes retry behavior. But the loss must not be silent — this record is emitted to an
    injected error reporter so the gap is visible.

    It carries only SAFE identity plus ``error_type`` (the exception *type name* only). It
    deliberately excludes the exception message/args and any provider payload, because an
    arbitrary exception's payload may contain provider data (prompts, responses, tool
    arguments, credentials).
    """

    provider_id: str
    operation: str
    attempt_number: int
    status: ProviderAttemptStatus
    error_type: str
    workflow_id: Optional[str] = None
    instance_id: Optional[str] = None
    task_id: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "operation": self.operation,
            "attempt_number": self.attempt_number,
            "status": self.status.value,
            "error_type": self.error_type,
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
        }


@runtime_checkable
class AttemptObservationErrorReporter(Protocol):
    """A neutral sink notified when an :class:`AttemptObserver` fails (F2).

    Exactly one :class:`AttemptObservationFailure` is delivered per observer failure. A
    reporter that itself raises is contained by the runtime and never masks the provider
    result. The reporter must not attempt provider execution.
    """

    def on_observation_failure(self, failure: AttemptObservationFailure) -> None: ...


@dataclass
class RecordingObservationErrorReporter:
    """A deterministic in-memory :class:`AttemptObservationErrorReporter` (test/reference)."""

    failures: list = field(default_factory=list)

    def on_observation_failure(self, failure: AttemptObservationFailure) -> None:
        self.failures.append(failure)


@dataclass
class RecordingAttemptObserver:
    """A deterministic in-memory :class:`AttemptObserver` (test/reference only).

    Retains every attempt in invocation order so a test can assert that retries and
    failed attempts are each recorded distinctly (never collapsed).
    """

    attempts: list = field(default_factory=list)

    def on_attempt(self, attempt: ProviderAttempt) -> None:
        self.attempts.append(attempt)

    def for_task(self, task_id: str) -> list:
        return [a for a in self.attempts if a.task_id == task_id]
