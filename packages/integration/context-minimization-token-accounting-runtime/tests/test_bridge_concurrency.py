"""F4 — bridge diagnostics are concurrency-safe; attempt & summary settlement never double.

Barrier-synchronized threads (no sleep). skipped_attempts increments are not lost; the
H22-D reservation is never settled twice across the per-attempt and summary paths.
"""

from __future__ import annotations

import threading

import pytest

from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus
from ugence_agent_runtime.orchestration import (
    BudgetCoordinator,
    BudgetRequirement,
    PortfolioBudget,
)

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    aggregate_logical_request_usage,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)

from ugence_cm_token_accounting_runtime import (
    DEFAULT_TOKEN_DIMENSION,
    RuntimeTokenAccountingBridge,
    settle_budget_from_summary,
    settle_budget_from_usage,
)

from support_itg import sample_minimization_result


def _att(instance_id, task_id, n=1):
    return ProviderAttempt(
        provider_id="vendor", operation="op", attempt_number=n,
        status=ProviderAttemptStatus.SUCCEEDED, ok=True, provider_invoked=True,
        instance_id=instance_id, task_id=task_id, correlation_id="corr",
    )


def _run_barrier(fns):
    barrier = threading.Barrier(len(fns))
    errors = []

    def wrap(fn):
        def inner():
            barrier.wait()
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        return inner

    ts = [threading.Thread(target=wrap(fn)) for fn in fns]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return errors


def test_concurrent_skip_increments_are_not_lost():
    sink = InMemoryTokenAccountingSink()
    bridge = RuntimeTokenAccountingBridge(sink)  # nothing registered → every attempt skips
    n = 100
    atts = [_att(f"wf-{i}", "t") for i in range(n)]
    errors = _run_barrier([lambda a=a: bridge.on_attempt(a) for a in atts])
    assert errors == []
    assert bridge.skipped_attempts == n  # no lost increments
    assert sink.records == ()


def test_no_double_settlement_between_attempt_and_summary_paths():
    """Both settlement entry points target the same reservation; the second is a no-op."""
    coord = BudgetCoordinator(PortfolioBudget({DEFAULT_TOKEN_DIMENSION: 10000.0}))
    coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 5000.0}))

    prep = prepare_api_call_measurement(
        minimization_result=sample_minimization_result(), logical_request_id="lr", provider_id="vendor"
    )
    usage = ProviderTokenUsage(input_tokens=2000, output_tokens=300, total_tokens=2300)
    rec = reconcile_api_call_measurement(prep, attempt_id="a1", attempt_number=1,
                                         status=AttemptStatus.SUCCEEDED, provider_usage=usage)
    summary = aggregate_logical_request_usage([rec])

    # Per-attempt settlement charges the measured amount and pops the hold.
    s1 = settle_budget_from_usage(coord, "wf-1", usage)
    assert s1.charged[DEFAULT_TOKEN_DIMENSION] == 2300.0
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 2300.0

    # A second settlement via the summary path finds NO active hold → no-op (no double charge).
    s2 = settle_budget_from_summary(coord, "wf-1", summary)
    assert s2.charged == {}
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 2300.0  # unchanged


def test_concurrent_settlement_calls_charge_once():
    coord = BudgetCoordinator(PortfolioBudget({DEFAULT_TOKEN_DIMENSION: 10000.0}))
    coord.reserve("wf-1", BudgetRequirement({DEFAULT_TOKEN_DIMENSION: 5000.0}))
    usage = ProviderTokenUsage(input_tokens=1000, output_tokens=100, total_tokens=1100)
    # Many threads race to settle the same reservation; exactly one charge lands.
    _run_barrier([lambda: settle_budget_from_usage(coord, "wf-1", usage) for _ in range(16)])
    assert coord.consumed(DEFAULT_TOKEN_DIMENSION) == 1100.0
    assert coord.reserved(DEFAULT_TOKEN_DIMENSION) == 0.0
