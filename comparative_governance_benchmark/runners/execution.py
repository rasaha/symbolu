"""External-execution harness (benchmark-owned, kernel API only).

Builds the same deterministic execution adapter every strategy uses (fairness
B12) and offers a direct-dispatch path for strategies without an authorized DGM
execution lifecycle (No Governance, Assertion Only). Imports no provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

from decision_governance.api.contracts import BusinessOutcome
from decision_governance.api.ports import OfflineDeterministicExecutionAdapter

from enterprise_validation_pilot.schemas.scenario import ExecutionSpec


def build_execution_adapter(action_type: str, spec: ExecutionSpec, *,
                            id_factory=None, clock=None) -> OfflineDeterministicExecutionAdapter:
    transport = frozenset({action_type}) if spec.transport_fail else frozenset()
    timing = frozenset({action_type}) if spec.timeout else frozenset()
    outcomes: Optional[dict] = None
    if spec.business_outcome and spec.business_outcome != "SUCCEEDED":
        outcomes = {action_type: BusinessOutcome[spec.business_outcome]}
    overrides = {action_type: dict(spec.observed_overrides)} if spec.observed_overrides else None
    extra = {}
    if id_factory is not None:
        extra["id_factory"] = id_factory
    if clock is not None:
        extra["clock"] = clock
    return OfflineDeterministicExecutionAdapter(
        transport_failing=transport, timing_out=timing, outcomes=outcomes,
        observed_parameter_overrides=overrides, **extra)


@dataclass(frozen=True)
class DirectExecution:
    dispatched: bool
    transport_status: str
    business_outcome: str
    observed_parameters: dict


def direct_dispatch(adapter: OfflineDeterministicExecutionAdapter, action_type: str,
                    parameters: dict) -> DirectExecution:
    """Dispatch straight through the adapter (no DGM authorization lifecycle)."""
    intent = SimpleNamespace(action_type=action_type,
                             authorized_parameters=dict(parameters))
    resp = adapter.dispatch(intent)
    transport = resp.transport_status.value
    # a dispatch attempt was made regardless of transport result (parity with the
    # DGM execution path, so `dispatched` means the same thing for every strategy)
    if transport == "TRANSPORT_FAILED":
        return DirectExecution(True, transport, "TRANSPORT_FAILED", {})
    if transport == "TIMED_OUT":
        return DirectExecution(True, transport, "TIMED_OUT", {})
    status = adapter.query_status(resp.external_request_id)
    return DirectExecution(True, transport, status.business_outcome.value,
                           dict(status.observed_parameters))
