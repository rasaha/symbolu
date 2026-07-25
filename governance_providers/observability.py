"""Provider observability — structured invocation records (framework layer).

Provider operations produce structured records sufficient to audit selection and
invocation. These are **provider-framework** records — deliberately distinct from
DGM kernel milestone audit events, and they never carry vendor payloads or
secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

from .errors import FailureClass, ProviderError

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderInvocationRecord:
    provider_id: str
    kind: str
    operation: str
    completed: bool
    outcome: str = ""
    trace_id: str = ""
    error_class: Optional[str] = None
    failure_class: Optional[str] = None
    fallback_provider_id: str = ""


class ProviderInvocationLog:
    """An in-memory sink for provider invocation records (framework observability)."""

    def __init__(self) -> None:
        self._records: list[ProviderInvocationRecord] = []

    def append(self, record: ProviderInvocationRecord) -> None:
        self._records.append(record)

    def all(self) -> tuple[ProviderInvocationRecord, ...]:
        return tuple(self._records)


def record_invocation(provider_id: str, kind: str, operation: str,
                      fn: Callable[[], T], *, log: Optional[ProviderInvocationLog] = None,
                      trace_id: str = "") -> T:
    """Invoke ``fn`` and record the outcome; provider errors are classified, not swallowed."""
    try:
        result = fn()
    except ProviderError as exc:
        if log is not None:
            log.append(ProviderInvocationRecord(
                provider_id=provider_id, kind=kind, operation=operation, completed=False,
                error_class=type(exc).__name__,
                failure_class=getattr(exc, "failure_class", FailureClass.TERMINAL).value,
                trace_id=trace_id))
        raise
    if log is not None:
        log.append(ProviderInvocationRecord(
            provider_id=provider_id, kind=kind, operation=operation, completed=True,
            outcome=str(getattr(result, "outcome", getattr(result, "coverage",
                        getattr(result, "business_outcome", "")))),
            trace_id=getattr(result, "provider_trace_id", trace_id)))
    return result
