"""Deterministic reference External Execution provider (framework validation only)."""

from __future__ import annotations

from typing import Optional

from ..contracts import (
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
)
from ..contracts.base import BaseProvider
from ..fingerprint import fingerprint
from ..metadata import (
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderKind,
)

_KIND = ProviderKind.EXTERNAL_EXECUTION


class DeterministicExecutionProvider(BaseProvider):
    def __init__(self, *, provider_id: str = "deterministic-execution",
                 transport_failing: frozenset[str] = frozenset(),
                 timing_out: frozenset[str] = frozenset(),
                 pending: frozenset[str] = frozenset(),
                 outcomes: Optional[dict[str, ExecutionBusinessOutcome]] = None,
                 default: bool = True) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=_KIND, implementation_version="0.1.0",
            compatibility=ProviderCompatibility(contract_version="1.0.0"),
            capabilities=ProviderCapabilities(
                kind=_KIND, features=frozenset({"dispatch", "observe", "cancel"}),
                deterministic=True),
            factory=lambda: DeterministicExecutionProvider(
                provider_id=provider_id, transport_failing=transport_failing,
                timing_out=timing_out, pending=pending, outcomes=outcomes, default=default),
            vendor="framework-reference", default=default)
        super().__init__(descriptor)
        self._transport_failing, self._timing_out = transport_failing, timing_out
        self._pending = pending
        self._outcomes = outcomes or {}
        self._counter = 0
        self._dispatched: dict[str, str] = {}
        self._cancelled: set[str] = set()

    def dispatch(self, request: ExecutionDispatchRequest) -> ExecutionDispatchResult:
        at = request.action_type
        if at in self._transport_failing:
            return ExecutionDispatchResult(accepted=False, transport_error="mock transport down")
        self._counter += 1
        ext_id = f"refexec-{self._counter}"
        self._dispatched[ext_id] = at
        if at in self._timing_out:
            return ExecutionDispatchResult(accepted=True, external_request_id=ext_id, timed_out=True)
        if at in self._pending:
            return ExecutionDispatchResult(accepted=True, external_request_id=ext_id, pending=True)
        return ExecutionDispatchResult(accepted=True, external_request_id=ext_id,
                                       acknowledgement=f"ack:{ext_id}")

    def observe(self, *, external_request_id: str) -> ExecutionObservation:
        at = self._dispatched.get(external_request_id, "")
        if external_request_id in self._cancelled:
            outcome = ExecutionBusinessOutcome.REJECTED
        else:
            outcome = self._outcomes.get(at, ExecutionBusinessOutcome.SUCCEEDED)
        final = outcome not in (ExecutionBusinessOutcome.UNKNOWN, ExecutionBusinessOutcome.PENDING)
        fp = fingerprint({"ext": external_request_id, "outcome": outcome.value})
        return ExecutionObservation(business_outcome=outcome, final=final,
                                    reason=outcome.value,
                                    provider_trace_id=f"trace-{fp[:12]}", fingerprint=fp)

    def cancel(self, *, external_request_id: str) -> bool:
        if external_request_id in self._dispatched:
            self._cancelled.add(external_request_id)
            return True
        return False
