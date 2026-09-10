"""The exchange lifecycle end to end, against a real PostgreSQL server.

Submit → claim → serve → record → acknowledge → purge, plus every way each of
those is supposed to refuse.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from ugence_model_egress_unit import (
    DeterministicFakeProvider,
    EgressRequest,
    EgressResult,
    EgressUnit,
    LiveEgressUnavailableProvider,
    RefusalReason,
    RequestState,
    ResultOutcome,
    content_digest,
)
from ugence_model_egress_unit.postgres import (
    RequestNotClaimable,
    ResultNotAcknowledgeable,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
LEASE = timedelta(minutes=5)

pytestmark = pytest.mark.postgres


def _request(tenant, content="summarize the attached record", model="reference-model-a"):
    return EgressRequest.create(
        request_id=uuid.uuid4(),
        tenant_id=tenant,
        submitted_at=NOW,
        model_id=model,
        purpose="reference-exchange",
        content=content,
    )


# --- the happy path ----------------------------------------------------------

def test_a_request_travels_from_pending_to_completed(worker_exchange, unit_exchange,
                                                     tenant):
    request = _request(tenant)
    request_digest = worker_exchange.submit(request)

    stored = worker_exchange.read_request(tenant, request.request_id)
    assert stored["state"] is RequestState.PENDING
    assert stored["request_digest"] == request_digest == request.digest()

    unit = EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1",
                      lease=LEASE)
    done = unit.run_once(tenant, now=NOW)

    assert done.request_id == request.request_id
    assert done.outcome is ResultOutcome.ANSWERED

    after = worker_exchange.read_request(tenant, request.request_id)
    assert after["state"] is RequestState.COMPLETED
    assert after["terminal_at"] == NOW
    assert after["lease_holder"] is None, "a terminal request holds no lease"

    result = worker_exchange.read_result(tenant, request.request_id)
    assert result["outcome"] is ResultOutcome.ANSWERED
    assert result["response_digest"] == done.response_digest
    assert result["content_sha256"] == content_digest(result["content"])


def test_an_idle_queue_reports_no_work(unit_exchange, tenant):
    unit = EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1")
    idle = unit.run_once(tenant, now=NOW)
    assert not idle.did_work and idle.outcome is None


def test_claiming_writes_a_lease_in_the_same_transaction(worker_exchange, unit_exchange,
                                                         tenant):
    """No window in which a row is claimed but unleased — the reconciler relies
    on every LEASED row having something it can expire."""

    request = _request(tenant)
    worker_exchange.submit(request)

    claimed = unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)
    assert claimed.request.request_id == request.request_id

    stored = worker_exchange.read_request(tenant, request.request_id)
    assert stored["state"] is RequestState.LEASED
    assert stored["lease_holder"] == "unit-1"
    assert stored["lease_expires_at"] == NOW + LEASE


def test_two_units_never_claim_the_same_request(worker_exchange, unit_exchange, tenant):
    """``SKIP LOCKED`` in effect: two claims over one request yield one and a miss."""

    request = _request(tenant)
    worker_exchange.submit(request)

    first = unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)
    second = unit_exchange.claim(tenant, holder="unit-2", now=NOW, lease=LEASE)

    assert first is not None
    assert second is None, "the only pending request was already claimed"


def test_the_queue_is_served_oldest_first(worker_exchange, unit_exchange, tenant):
    early = EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, submitted_at=NOW,
        model_id="m", purpose="p", content="first")
    late = EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant,
        submitted_at=NOW + timedelta(minutes=1),
        model_id="m", purpose="p", content="second")
    worker_exchange.submit(late)
    worker_exchange.submit(early)

    claimed = unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)
    assert claimed.request.request_id == early.request_id


# --- terminal refusals -------------------------------------------------------

def test_a_refusal_is_terminal_and_names_its_reason(worker_exchange, unit_exchange,
                                                    tenant):
    request = _request(tenant, model="a-model-this-unit-does-not-have")
    worker_exchange.submit(request)

    provider = DeterministicFakeProvider(
        available_models=frozenset({"reference-model-a"}))
    unit = EgressUnit(unit_exchange, provider, holder="unit-1", lease=LEASE)
    done = unit.run_once(tenant, now=NOW)

    assert done.outcome is ResultOutcome.REFUSED
    result = worker_exchange.read_result(tenant, request.request_id)
    assert result["refusal_reason"] is RefusalReason.MODEL_NOT_AVAILABLE
    assert result["content"] is None, "a refusal carries no content"

    after = worker_exchange.read_request(tenant, request.request_id)
    assert after["state"] is RequestState.REFUSED

    # Terminal means terminal: it is not returned to the queue for another try.
    assert unit.run_once(tenant, now=NOW).did_work is False


def test_a_unit_without_egress_refuses_rather_than_stalling(worker_exchange,
                                                            unit_exchange, tenant):
    """A deployment with no provider produces a proper terminal refusal, so the
    requester learns live egress does not exist here instead of watching a
    request sit pending forever."""

    request = _request(tenant)
    worker_exchange.submit(request)

    unit = EgressUnit(unit_exchange, LiveEgressUnavailableProvider(), holder="unit-1")
    done = unit.run_once(tenant, now=NOW)

    assert done.outcome is ResultOutcome.REFUSED
    result = worker_exchange.read_result(tenant, request.request_id)
    assert result["refusal_reason"] is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE


def test_a_result_cannot_be_recorded_against_an_unclaimed_request(worker_exchange,
                                                                  unit_exchange, tenant):
    request = _request(tenant)
    worker_exchange.submit(request)

    result = EgressResult.answered(
        request_id=request.request_id, tenant_id=tenant, recorded_at=NOW,
        provider_id="unit-1", content="an answer nobody claimed the right to give")

    with pytest.raises(RequestNotClaimable):
        unit_exchange.record_result(result)


def test_one_request_cannot_receive_two_results(worker_exchange, unit_exchange, tenant):
    """The result table is keyed by request id, so a second answer is a key
    violation rather than a silent overwrite of the first."""

    request = _request(tenant)
    worker_exchange.submit(request)
    unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=LEASE)

    first = EgressResult.answered(
        request_id=request.request_id, tenant_id=tenant, recorded_at=NOW,
        provider_id="unit-1", content="the answer")
    unit_exchange.record_result(first)

    with pytest.raises((RequestNotClaimable, psycopg.errors.UniqueViolation)):
        unit_exchange.record_result(first)


# --- consumption acknowledgement --------------------------------------------

def test_a_result_is_acknowledged_once(worker_exchange, unit_exchange, tenant):
    request = _request(tenant)
    worker_exchange.submit(request)
    EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1"
               ).run_once(tenant, now=NOW)

    assert worker_exchange.read_result(tenant, request.request_id)["acknowledged_at"] is None

    ack_at = NOW + timedelta(minutes=2)
    worker_exchange.acknowledge(tenant, request.request_id, at=ack_at)
    assert worker_exchange.read_result(
        tenant, request.request_id)["acknowledged_at"] == ack_at

    with pytest.raises(ResultNotAcknowledgeable):
        worker_exchange.acknowledge(tenant, request.request_id, at=ack_at)


def test_acknowledging_a_result_that_does_not_exist_is_refused(worker_exchange, tenant):
    with pytest.raises(ResultNotAcknowledgeable):
        worker_exchange.acknowledge(tenant, uuid.uuid4(), at=NOW)
