"""Replaceable external-execution port + deterministic hiring test adapter (H4).

The execution port is the framework's neutral ``ExternalExecutionProvider`` contract
(dispatch / observe / cancel). The core hiring domain depends only on this port — it
imports **no** HRIS/email/calendar/payroll/workflow SDKs. Real integrations are
supplied by application-local adapters implementing this port. A deterministic
in-memory adapter covers the H4 test scenarios (success, timeout, transient/permanent
failure, duplicate, partial, malformed, target mismatch, delayed completion) with the
transport result kept strictly separate from the observed business outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ugence_governance_provider_framework.api import (
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
    ExternalExecutionProvider,  # noqa: F401  (the port contract)
)


@dataclass
class DeterministicHiringExecutionAdapter:
    """In-memory external-execution adapter for tests / development."""

    adapter_id: str = "deterministic-hiring-exec"
    transport_fail: bool = False
    transport_retryable: bool = True
    timeout: bool = False
    pending_then_final: bool = False        # dispatch PENDING; observe returns final
    business_outcome: ExecutionBusinessOutcome = ExecutionBusinessOutcome.SUCCEEDED
    observed_params_override: tuple[tuple[str, str], ...] = ()  # if set, receipt params
    observed_target: str = ""               # if set, adds ('target', value) → mismatch
    duplicate_on_repeat: bool = False       # repeat idempotency_key → DUPLICATE
    malformed: bool = False                 # observe returns UNKNOWN/no-usable-outcome
    _counter: int = 0
    _by_ext: dict = field(default_factory=dict)
    _by_key: dict = field(default_factory=dict)

    # --- ExternalExecutionProvider protocol --------------------------------
    def descriptor(self):  # minimal descriptor-like shim
        return type("D", (), {"provider_id": self.adapter_id})()

    def dispatch(self, request: ExecutionDispatchRequest) -> ExecutionDispatchResult:
        if self.transport_fail:
            return ExecutionDispatchResult(accepted=False, transport_error="transport down",
                                           retryable=self.transport_retryable)
        key = request.idempotency_key
        if self.duplicate_on_repeat and key in self._by_key:
            ext = self._by_key[key]
            # idempotent: same external id, flagged as a duplicate observation
            self._by_ext[ext] = {"params": dict(request.parameters), "duplicate": True}
            return ExecutionDispatchResult(accepted=True, external_request_id=ext,
                                           acknowledgement="duplicate")
        self._counter += 1
        ext = f"hexec-{self._counter}"
        self._by_ext[ext] = {"params": dict(request.parameters), "duplicate": False}
        self._by_key[key] = ext
        if self.timeout:
            return ExecutionDispatchResult(accepted=True, external_request_id=ext, timed_out=True)
        if self.pending_then_final:
            return ExecutionDispatchResult(accepted=True, external_request_id=ext, pending=True)
        return ExecutionDispatchResult(accepted=True, external_request_id=ext,
                                       acknowledgement=f"ack:{ext}")

    def observe(self, *, external_request_id: str) -> ExecutionObservation:
        ctx = self._by_ext.get(external_request_id, {"params": {}, "duplicate": False})
        if self.malformed:
            return ExecutionObservation(business_outcome=ExecutionBusinessOutcome.UNKNOWN,
                                        final=False, reason="malformed", provider_trace_id="",
                                        fingerprint="")
        if ctx.get("duplicate"):
            return ExecutionObservation(business_outcome=ExecutionBusinessOutcome.DUPLICATE,
                                        final=True, reason="duplicate external execution")
        outcome = self.business_outcome
        params = dict(self.observed_params_override) if self.observed_params_override \
            else dict(ctx["params"])
        if self.observed_target:
            params["target"] = self.observed_target
        return ExecutionObservation(
            business_outcome=outcome, observed_parameters=params,
            final=outcome not in (ExecutionBusinessOutcome.PENDING, ExecutionBusinessOutcome.UNKNOWN),
            reason=outcome.value, provider_trace_id=f"trace-{external_request_id}",
            fingerprint=f"fp-{external_request_id}")

    def cancel(self, *, external_request_id: str) -> bool:
        return external_request_id in self._by_ext
