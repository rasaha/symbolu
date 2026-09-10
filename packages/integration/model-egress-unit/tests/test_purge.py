"""Content purge leaves a digest-only tombstone that can still be checked.

The property that makes a tombstone worth keeping: after the content is gone, the
row can still answer *"was it this?"* for a reader holding a candidate, and can
still not answer *"what was it?"* for anyone. Both halves are asserted — a purge
that destroyed the digests too would pass the second and fail the point, and a
purge that kept the content would pass the first and fail everything.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from _fixtures import CONTEXT, LEASE, NOW, request as _make_request
from ugence_model_egress_unit import (
    HARD_RETENTION_DEADLINE,
    DeterministicFakeProvider,
    EgressRequest,
    EgressUnit,
    RequestState,
    minimized_context_digest,
    payload_digest,
)
from ugence_model_egress_unit.postgres import SCHEMA_NAME

ACK = NOW + timedelta(minutes=2)
#: Late enough that both clocks have run out, so a purge is unconditionally due.
PURGE = NOW + HARD_RETENTION_DEADLINE

pytestmark = pytest.mark.postgres

def _answered(worker_exchange, unit_exchange, tenant):
    request = _make_request(tenant)
    worker_exchange.submit(request)
    EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1",
               lease=LEASE).run_once(tenant, now=NOW)
    return request


def test_purge_destroys_content_on_both_sides_and_keeps_every_digest(
        worker_exchange, unit_exchange, tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    before_request = worker_exchange.read_request(tenant, request.request_id)
    before_result = worker_exchange.read_result(tenant, request.request_id)
    answer = before_result["payload"]
    assert before_request["minimized_context"] == CONTEXT and answer is not None

    assert request.request_id in worker_exchange.purge_due(tenant, now=PURGE).results

    after_request = worker_exchange.read_request(tenant, request.request_id)
    after_result = worker_exchange.read_result(tenant, request.request_id)

    # Gone.
    assert after_request["minimized_context"] is None
    assert after_result["payload"] is None
    assert after_request["content_purged_at"] == PURGE
    assert after_result["content_purged_at"] == PURGE

    # Still there, and unchanged.
    assert after_request["content_digest"] == before_request["content_digest"]
    assert after_request["request_digest"] == before_request["request_digest"]
    assert after_result["content_digest"] == before_result["content_digest"]
    assert after_result["response_digest"] == before_result["response_digest"]

    # The tombstone answers "was it this?" for a reader who has a candidate...
    assert after_request["content_digest"] == minimized_context_digest(CONTEXT)
    assert after_result["content_digest"] == payload_digest(answer)
    # ...and refuses the wrong candidate.
    assert after_request["content_digest"] != minimized_context_digest(CONTEXT[:1])


# The "a purged request still recomputes its own request digest" property lives in
# test_conformance.py, beside the ruling it comes from. One copy, so the two cannot
# drift into disagreeing about what a tombstone owes.


def test_an_unacknowledged_result_survives_only_until_the_hard_deadline(
        worker_exchange, unit_exchange, tenant):
    """Acknowledgement is a grace, not a gate — and this is where that bites.

    Before the ruling of 2026-09-10 this package treated the acknowledgement as a
    precondition for purging at all, so an unread answer lived forever. The ruling
    is the other way round: the acknowledgement only *shortens* retention, and the
    24-hour deadline is unconditional. An unread answer is destroyed on time.
    """

    request = _answered(worker_exchange, unit_exchange, tenant)

    early = NOW + timedelta(hours=23)
    assert request.request_id not in worker_exchange.purge_due(tenant, now=early).results
    assert worker_exchange.read_result(tenant, request.request_id)["payload"] is not None

    assert request.request_id in worker_exchange.purge_due(tenant, now=PURGE).results
    assert worker_exchange.read_result(tenant, request.request_id)["payload"] is None


def test_purge_is_idempotent(worker_exchange, unit_exchange, tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    assert request.request_id in worker_exchange.purge_due(tenant, now=PURGE).results
    assert request.request_id not in worker_exchange.purge_due(
        tenant, now=PURGE + timedelta(hours=1)).results
    assert worker_exchange.read_result(
        tenant, request.request_id)["content_purged_at"] == PURGE, (
        "a second purge must not restamp the first one's time")


def test_one_tenant_cannot_purge_anothers_content(worker_exchange, unit_exchange,
                                                  tenant, other_tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    assert worker_exchange.purge_due(other_tenant, now=PURGE).count == 0
    assert worker_exchange.read_result(tenant, request.request_id)["payload"] is not None


def test_the_database_refuses_a_purge_stamp_without_a_purge(database, tenant):
    """The check constraint, asserted directly.

    Application code is not the only thing that writes to a database. A row
    claiming its content was destroyed while still holding it would be a false
    record of a destruction, so the constraint refuses it regardless of who is
    writing.
    """

    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                f"""INSERT INTO {SCHEMA_NAME}.egress_request
                    (tenant_id, request_id, correlation_id, exchange_schema_version,
                     submitted_at, not_valid_after, state, clearance_ref,
                     clearance_digest, authorized_vendor, authorized_model, policy_id,
                     reservation_id, parameters, minimized_context, content_digest,
                     content_created_at, request_digest, content_purged_at)
                    VALUES (%s, %s, %s, 'v1', now(), now() + interval '1 hour',
                            'PENDING', 'cer-raw', repeat('0', 64), 'v', 'm', 'p',
                            'rsv', '{{}}', '[{{"unit_id":"u","text":"still here",
                            "token_count":1}}]', repeat('0', 64), now(),
                            repeat('0', 64), now())""",
                (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())),
            )
