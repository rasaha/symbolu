"""Deterministic mock ExecutionProvider — validates the framework."""
from __future__ import annotations

from typing import Mapping, Optional

from ..contracts import BaseProvider, BusinessOutcome, DispatchReceipt, ObservationReport
from ..metadata import ProviderCapabilities, ProviderKind, ProviderMetadata


class MockExecutionProvider(BaseProvider):
    """Accepts dispatch + observes SUCCEEDED by default; configurable per action type."""

    def __init__(self, *, name: str = "mock-execution",
                 transport_failing: frozenset[str] = frozenset(),
                 timing_out: frozenset[str] = frozenset(),
                 outcomes: Optional[dict[str, BusinessOutcome]] = None) -> None:
        super().__init__(
            ProviderMetadata(name=name, version="0.1.0", kind=ProviderKind.EXECUTION,
                             kernel_port_version="1.0.0", description="deterministic mock",
                             vendor="framework-tests"),
            ProviderCapabilities(kind=ProviderKind.EXECUTION,
                                 features=frozenset({"dispatch", "observe"}),
                                 deterministic=True))
        self._transport_failing, self._timing_out = transport_failing, timing_out
        self._outcomes = outcomes or {}
        self._counter = 0
        self._dispatched: dict[str, str] = {}  # ext_id -> action_type

    def dispatch(self, *, action_type: str, parameters: Mapping[str, str]) -> DispatchReceipt:
        if action_type in self._transport_failing:
            return DispatchReceipt(accepted=False, transport_error="mock transport down")
        self._counter += 1
        ext_id = f"mockexec-{self._counter}"
        self._dispatched[ext_id] = action_type
        if action_type in self._timing_out:
            return DispatchReceipt(accepted=True, external_request_id=ext_id, timed_out=True)
        return DispatchReceipt(accepted=True, external_request_id=ext_id,
                               acknowledgement=f"ack:{ext_id}")

    def observe(self, *, external_request_id: str) -> ObservationReport:
        action_type = self._dispatched.get(external_request_id, "")
        outcome = self._outcomes.get(action_type, BusinessOutcome.SUCCEEDED)
        final = outcome is not BusinessOutcome.UNKNOWN
        return ObservationReport(business_outcome=outcome, final=final,
                                 reason=outcome.value)
