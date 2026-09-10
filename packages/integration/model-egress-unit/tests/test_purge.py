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

from ugence_model_egress_unit import (
    DeterministicFakeProvider,
    EgressRequest,
    EgressUnit,
    RequestState,
    content_digest,
)
from ugence_model_egress_unit.postgres import SCHEMA_NAME

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
ACK = NOW + timedelta(minutes=2)
PURGE = NOW + timedelta(hours=1)

pytestmark = pytest.mark.postgres

PROMPT = "the prompt that must not survive the purge"


def _answered(worker_exchange, unit_exchange, tenant):
    request = EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, submitted_at=NOW,
        model_id="reference-model-a", purpose="reference-exchange", content=PROMPT)
    worker_exchange.submit(request)
    EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1"
               ).run_once(tenant, now=NOW)
    return request


def test_purge_destroys_content_on_both_sides_and_keeps_every_digest(
        worker_exchange, unit_exchange, tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    before_request = worker_exchange.read_request(tenant, request.request_id)
    before_result = worker_exchange.read_result(tenant, request.request_id)
    answer = before_result["content"]
    assert before_request["content"] == PROMPT and answer is not None

    assert worker_exchange.purge_content(tenant, request.request_id, at=PURGE) is True

    after_request = worker_exchange.read_request(tenant, request.request_id)
    after_result = worker_exchange.read_result(tenant, request.request_id)

    # Gone.
    assert after_request["content"] is None
    assert after_result["content"] is None
    assert after_request["content_purged_at"] == PURGE
    assert after_result["content_purged_at"] == PURGE

    # Still there, and unchanged.
    assert after_request["content_sha256"] == before_request["content_sha256"]
    assert after_request["request_digest"] == before_request["request_digest"]
    assert after_result["content_sha256"] == before_result["content_sha256"]
    assert after_result["response_digest"] == before_result["response_digest"]

    # The tombstone answers "was it this?" for a reader who has a candidate...
    assert after_request["content_sha256"] == content_digest(PROMPT)
    assert after_result["content_sha256"] == content_digest(answer)
    # ...and refuses the wrong candidate.
    assert after_request["content_sha256"] != content_digest(PROMPT + " ")


def test_the_request_digest_is_still_recomputable_from_the_tombstone(
        worker_exchange, unit_exchange, tenant):
    """The reason content is digested separately rather than inlined.

    Had the request digest covered the content itself, purging would leave a
    digest nobody could ever recheck — a claim with no way to test it. Every
    field the digest covers survives the purge, so the tombstone can be verified
    against itself.
    """

    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)
    worker_exchange.purge_content(tenant, request.request_id, at=PURGE)

    row = worker_exchange.read_request(tenant, request.request_id)
    assert row["content"] is None

    rebuilt = EgressRequest(
        request_id=row["request_id"],
        tenant_id=row["tenant_id"],
        submitted_at=row["submitted_at"],
        model_id=row["model_id"],
        purpose=row["purpose"],
        content=None,
        content_sha256=row["content_sha256"],
        parameters=row["parameters"],
    )
    assert rebuilt.digest() == row["request_digest"]


def test_an_unacknowledged_result_is_not_purgeable(worker_exchange, unit_exchange,
                                                   tenant):
    """Purge is gated on consumption, so a sweep cannot destroy an answer that
    nobody has read — which would be indistinguishable afterwards from one that
    had been read and retired."""

    request = _answered(worker_exchange, unit_exchange, tenant)

    assert worker_exchange.purge_content(tenant, request.request_id, at=PURGE) is False
    assert worker_exchange.read_result(tenant, request.request_id)["content"] is not None


def test_purge_is_idempotent(worker_exchange, unit_exchange, tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    assert worker_exchange.purge_content(tenant, request.request_id, at=PURGE) is True
    assert worker_exchange.purge_content(
        tenant, request.request_id, at=PURGE + timedelta(hours=1)) is False
    assert worker_exchange.read_result(
        tenant, request.request_id)["content_purged_at"] == PURGE, (
        "a second purge must not restamp the first one's time")


def test_one_tenant_cannot_purge_anothers_content(worker_exchange, unit_exchange,
                                                  tenant, other_tenant):
    request = _answered(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, request.request_id, at=ACK)

    assert worker_exchange.purge_content(
        other_tenant, request.request_id, at=PURGE) is False
    assert worker_exchange.read_result(tenant, request.request_id)["content"] is not None


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
                    (request_id, tenant_id, submitted_at, state, model_id, purpose,
                     parameters, content, content_sha256, request_digest,
                     content_purged_at)
                    VALUES (%s, %s, now(), 'PENDING', 'm', 'p', '{{}}',
                            'still here', repeat('0', 64), repeat('0', 64), now())""",
                (str(uuid.uuid4()), str(tenant)),
            )
