"""Expired leases become terminal ``OUTCOME_UNKNOWN`` — never a retry.

The property under test is a decision, not an implementation detail: when a lease
expires the exchange cannot tell whether the vendor was called. Retrying would
turn "we don't know" into "we did it twice", and a duplicated exchange cannot be
undone. So the sweep closes the request and stops.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ugence_model_egress_unit import (
    DeterministicFakeProvider,
    EgressRequest,
    EgressResult,
    EgressUnit,
    ReconciliationScheduler,
    RequestState,
    ResultOutcome,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
LEASE = timedelta(minutes=5)
AFTER = NOW + LEASE + timedelta(seconds=1)

pytestmark = pytest.mark.postgres


def _slow_answer(request, tenant):
    """The answer of a unit that returns after its lease expired but before the
    sweep managed to write. It still holds the lease, so it records directly."""

    return EgressResult.answered(
        request_id=request.request_id, tenant_id=tenant, recorded_at=AFTER,
        provider_id="unit-slow", content="an answer that arrived late")


def _request(tenant, content="work that may or may not have happened"):
    return EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, submitted_at=NOW,
        model_id="reference-model-a", purpose="reference-exchange", content=content)


def test_an_expired_lease_becomes_terminal_outcome_unknown(worker_exchange,
                                                           unit_exchange, tenant):
    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-that-crashed", now=NOW, lease=LEASE)

    swept = ReconciliationScheduler(unit_exchange).sweep(tenant, now=AFTER)

    assert swept.reconciled == [request.request_id]
    after = worker_exchange.read_request(tenant, request.request_id)
    assert after["state"] is RequestState.OUTCOME_UNKNOWN
    assert after["terminal_at"] == AFTER

    result = worker_exchange.read_result(tenant, request.request_id)
    assert result["outcome"] is ResultOutcome.OUTCOME_UNKNOWN
    assert result["content"] is None and result["content_sha256"] is None
    assert result["refusal_reason"] is None, (
        "an unknown outcome is not a refusal: nobody decided anything")


def test_an_unexpired_lease_is_left_alone(worker_exchange, unit_exchange, tenant):
    """The positive control. Without it a sweep that expired everything would
    also satisfy the test above."""

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)

    swept = ReconciliationScheduler(unit_exchange).sweep(
        tenant, now=NOW + timedelta(minutes=1))

    assert swept.reconciled == [] and swept.expired == []
    assert worker_exchange.read_request(
        tenant, request.request_id)["state"] is RequestState.LEASED


def test_a_reconciled_request_is_never_returned_to_the_queue(worker_exchange,
                                                             unit_exchange, tenant):
    """The whole point. A unit polling after the sweep must find nothing.

    If reconciliation returned the request to ``PENDING``, this would claim it
    again — dispatching a second time an exchange that may already have happened.
    """

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-that-crashed", now=NOW, lease=LEASE)
    ReconciliationScheduler(unit_exchange).sweep(tenant, now=AFTER)

    unit = EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-2")
    assert unit.run_once(tenant, now=AFTER).did_work is False


def test_a_result_landing_before_the_sweep_is_not_overwritten(worker_exchange,
                                                              unit_exchange, tenant):
    """A known outcome must never be replaced by an unknown one.

    The race is real: the sweep reads expired leases, then writes. A slow unit
    can record a genuine answer in between. ``record_result`` is told to expect
    ``LEASED``, so the write is refused and the request is counted as skipped
    rather than clobbered.
    """

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-slow", now=NOW, lease=LEASE)

    scheduler = ReconciliationScheduler(unit_exchange)
    expired = unit_exchange.expired_leases(tenant, now=AFTER)
    assert [r for r, _ in expired] == [request.request_id]

    # The slow unit's answer arrives now, between the sweep's read and its write.
    # It already holds the lease, so it records directly rather than claiming
    # again — which is exactly what a unit returning late actually does.
    unit_exchange.record_result(_slow_answer(request, tenant))

    swept = scheduler.sweep(tenant, now=AFTER)

    assert swept.reconciled == [], "nothing was still leased by the time it wrote"
    result = worker_exchange.read_result(tenant, request.request_id)
    assert result["outcome"] is ResultOutcome.ANSWERED, (
        "the sweep must not replace a known outcome with an unknown one")


def test_the_sweep_reports_what_it_skipped(worker_exchange, unit_exchange, tenant,
                                           monkeypatch):
    """The skip path is reported, not swallowed.

    Driven by making the request terminal between the scheduler's read and its
    write — the exact interleaving the ``expect_states`` guard exists for.
    """

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-slow", now=NOW, lease=LEASE)

    scheduler = ReconciliationScheduler(unit_exchange)
    real_expired = unit_exchange.expired_leases

    def expired_then_answer(tenant_id, *, now):
        rows = real_expired(tenant_id, now=now)
        unit_exchange.record_result(_slow_answer(request, tenant_id))
        return rows

    monkeypatch.setattr(unit_exchange, "expired_leases", expired_then_answer)
    swept = scheduler.sweep(tenant, now=AFTER)

    assert swept.skipped == [request.request_id]
    assert swept.reconciled == []
    assert worker_exchange.read_result(
        tenant, request.request_id)["outcome"] is ResultOutcome.ANSWERED


def test_the_lease_window_is_half_open(worker_exchange, unit_exchange, tenant):
    """A lease is operational validity, so its window is ``[claimed, expires)``.

    At exactly ``lease_expires_at`` the lease is already over and the request is
    swept; one microsecond earlier it is still held. This follows the repository's
    ratified temporal categories rather than being a local choice — operational
    validity is half-open, and a lease that stayed valid *at* its expiry instant
    would be authority surviving its own boundary.

    It also pins the other property worth having: no wall clock anywhere in the
    path, so the sweep is a pure function of the instant it is handed.
    """

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)

    scheduler = ReconciliationScheduler(unit_exchange)
    exactly_at_expiry = NOW + LEASE

    assert scheduler.sweep(tenant, now=exactly_at_expiry - timedelta(microseconds=1)
                           ).reconciled == []
    assert scheduler.sweep(tenant, now=exactly_at_expiry).reconciled == [
        request.request_id], "at expires_at the lease has ended, not is ending"


def test_one_tenants_sweep_does_not_touch_anothers_leases(worker_exchange,
                                                          unit_exchange, tenant,
                                                          other_tenant):
    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)

    swept = ReconciliationScheduler(unit_exchange).sweep(other_tenant, now=AFTER)

    assert swept.expired == []
    assert worker_exchange.read_request(
        tenant, request.request_id)["state"] is RequestState.LEASED
