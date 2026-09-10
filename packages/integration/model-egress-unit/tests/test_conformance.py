"""Conformance with the rulings of 2026-09-10, asserted item by item.

Each test names the ruling it comes from. They are gathered here rather than
scattered so that a reader checking the exchange against
`SPEC_MODEL_EGRESS_UNIT.md` and `OWNER_RATIFICATION_MEU_EXCHANGE_TENANCY.md` has
one place to look, and so a future amendment has one place to break.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import psycopg
import pytest

from _fixtures import CONTEXT, LEASE, MODEL, NOW, VENDOR, binding, request
from ugence_model_egress_unit import (
    ACKNOWLEDGEMENT_GRACE,
    EXCHANGE_SCHEMA_VERSION,
    HARD_RETENTION_DEADLINE,
    TRUST_LEVEL,
    AuthorizationBinding,
    DeterministicFakeProvider,
    DispatchAttempt,
    EgressRequest,
    EgressResult,
    EgressUnit,
    LiveEgressUnavailableProvider,
    MinimizedUnit,
    ProvenanceKind,
    ReconciliationScheduler,
    RefusalReason,
    RequestState,
    ResultOutcome,
    minimized_context_digest,
    purge_deadline,
)
from ugence_model_egress_unit.postgres import SCHEMA_NAME

pytestmark = pytest.mark.postgres


def _served(worker, unit, tenant, **kw):
    req = request(tenant, **kw)
    worker.submit(req)
    EgressUnit(unit, DeterministicFakeProvider(), holder="unit-1", lease=LEASE
               ).run_once(tenant, now=NOW)
    return req


# --- 1. the authorization binding -------------------------------------------

def test_the_binding_travels_with_the_request(worker_exchange, unit_exchange, tenant):
    """§4.1: clearance reference and digest, tenant, vendor, model, policy and
    reservation are carried so the unit can verify them."""

    req = request(tenant)
    worker_exchange.submit(req)

    claimed = unit_exchange.claim(tenant, holder="u", now=NOW, lease=LEASE)
    a = claimed.request.authorization
    assert a.clearance_ref == req.authorization.clearance_ref
    assert a.clearance_digest == req.authorization.clearance_digest
    assert (a.authorized_vendor, a.authorized_model) == (VENDOR, MODEL)
    assert a.policy_id and a.reservation_id
    assert a.tenant_id == tenant


def test_the_unit_verifies_the_target_and_refuses_a_mismatch(worker_exchange,
                                                             unit_exchange, tenant):
    """§4.1: the MEU may not modify, broaden or reinterpret the binding. Claiming
    work confers no authority over what was claimed."""

    req = request(tenant, authorization=binding(tenant, vendor="some-other-vendor"))
    worker_exchange.submit(req)

    unit = EgressUnit(unit_exchange, DeterministicFakeProvider(vendor=VENDOR),
                      holder="unit-1", lease=LEASE)
    done = unit.run_once(tenant, now=NOW)

    assert done.outcome is ResultOutcome.REFUSED
    stored = worker_exchange.read_result(tenant, req.request_id)
    assert stored["refusal_reason"] is RefusalReason.TARGET_NOT_AUTHORIZED


def test_a_binding_cannot_name_a_tenant_the_request_does_not(tenant, other_tenant):
    with pytest.raises(ValueError, match="clearance did not name"):
        request(tenant, authorization=binding(other_tenant))


def test_an_incomplete_binding_is_unrepresentable(tenant):
    with pytest.raises(ValueError, match="incomplete"):
        AuthorizationBinding(
            clearance_ref="cer-x", clearance_digest="d", tenant_id=tenant,
            authorized_vendor="v", authorized_model="m", policy_id="p",
            reservation_id="")


def test_the_binding_authorizes_one_exact_target(tenant):
    a = binding(tenant)
    assert a.authorizes(vendor=VENDOR, model=MODEL, tenant_id=tenant)
    assert not a.authorizes(vendor=VENDOR, model=MODEL + "-v2", tenant_id=tenant)
    assert not a.authorizes(vendor=VENDOR + "x", model=MODEL, tenant_id=tenant)
    assert not a.authorizes(vendor=VENDOR, model=MODEL, tenant_id=uuid.uuid4())


# --- 2. ordered minimized context, and what the digest binds ----------------

def test_the_context_digest_binds_order(tenant):
    """§4.4: ordered unit identifiers and exact text. The same units in a
    different order are a different prompt."""

    assert minimized_context_digest(CONTEXT) != minimized_context_digest(
        tuple(reversed(CONTEXT)))


def test_the_context_digest_binds_identifier_and_text_but_not_token_count(tenant):
    """Token count is metering that survives a purge; a declared count that
    disagreed with the text must not make the content unverifiable."""

    base = minimized_context_digest(CONTEXT)
    renamed = (MinimizedUnit("other-id", CONTEXT[0].text, CONTEXT[0].token_count),
               CONTEXT[1])
    retexted = (MinimizedUnit(CONTEXT[0].unit_id, "different", CONTEXT[0].token_count),
                CONTEXT[1])
    recounted = (MinimizedUnit(CONTEXT[0].unit_id, CONTEXT[0].text, 999), CONTEXT[1])

    assert minimized_context_digest(renamed) != base
    assert minimized_context_digest(retexted) != base
    assert minimized_context_digest(recounted) == base


def test_the_request_digest_binds_the_ratified_fields(tenant):
    """§4.4: tenant, exchange schema version, content digest, vendor/model
    binding, parameters and clearance identity all move the digest."""

    base = request(tenant, request_id=uuid.uuid4()).digest()

    def digest(**kw):
        return request(tenant, request_id=uuid.uuid4(), **kw).digest()

    assert digest() != base, "request_id alone must move it"
    assert digest(context=tuple(reversed(CONTEXT))) != base
    assert digest(parameters={"temperature_milli": 1}) != base
    assert digest(authorization=binding(tenant, model="other")) != base
    assert digest(authorization=binding(tenant, policy_id="other-policy")) != base
    assert digest(authorization=binding(tenant, reservation_id="rsv-other")) != base
    assert request(uuid.uuid4()).digest() != base, "tenant must move it"


def test_the_exchange_schema_version_is_bound(tenant):
    """§4.1: a request cannot be reinterpreted under a later schema."""

    req = request(tenant)
    assert req.exchange_schema_version == EXCHANGE_SCHEMA_VERSION
    assert "exchange_schema_version" in req.digest_body()

    later = EgressRequest(**{**req.__dict__, "exchange_schema_version": "…/v2"})
    assert later.digest() != req.digest()


def test_submitted_at_is_bound_and_lease_timestamps_are_not(tenant):
    """§4.4 excludes mutable lease, claim, attempt and processing timestamps. A
    creation instant is immutable, so it stays bound."""

    body = request(tenant).digest_body()
    assert "submitted_at" in body
    for mutable in ("lease_holder", "lease_expires_at", "dispatched_at",
                    "terminal_at", "state"):
        assert mutable not in body, mutable


def test_the_content_digest_is_validated_while_content_exists(worker_exchange,
                                                              unit_exchange, tenant):
    """A substituted prompt under unchanged identifiers is a different logical
    action, and must be refused rather than served."""

    req = request(tenant)
    worker_exchange.submit(req)
    tampered = EgressRequest(**{**req.__dict__, "content_digest": "f" * 64})
    assert not tampered.content_matches_digest()

    provider = DeterministicFakeProvider()
    refusal = provider.execute(tampered, now=NOW)
    assert refusal.refusal_reason is RefusalReason.CONTENT_DIGEST_MISMATCH


def test_a_purged_request_is_not_a_digest_mismatch(tenant):
    """A tombstone has no content to disagree with its digest."""

    req = request(tenant)
    purged = EgressRequest(**{**req.__dict__, "minimized_context": None})
    assert purged.content_matches_digest()


# --- 3. retention: two clocks, earlier wins ---------------------------------

def test_the_acknowledgement_grace_and_the_hard_deadline(tenant):
    created = NOW
    assert purge_deadline(content_created_at=created, acknowledged_at=None) == (
        created + HARD_RETENTION_DEADLINE)
    ack = created + timedelta(minutes=30)
    assert purge_deadline(content_created_at=created, acknowledged_at=ack) == (
        ack + ACKNOWLEDGEMENT_GRACE)


def test_a_late_acknowledgement_never_extends_the_hard_deadline(tenant):
    """The ruling's sharpest edge: absence *or* lateness of an acknowledgement
    never lets content survive past 24 hours."""

    created = NOW
    ack = created + timedelta(hours=23, minutes=59)
    assert purge_deadline(content_created_at=created, acknowledged_at=ack) == (
        created + HARD_RETENTION_DEADLINE)


def test_unacknowledged_content_is_purged_at_the_hard_deadline(worker_exchange,
                                                               unit_exchange, tenant):
    req = _served(worker_exchange, unit_exchange, tenant)

    just_before = NOW + HARD_RETENTION_DEADLINE - timedelta(seconds=1)
    assert worker_exchange.purge_due(tenant, now=just_before).count == 0
    assert worker_exchange.read_request(
        tenant, req.request_id)["minimized_context"] is not None

    swept = worker_exchange.purge_due(tenant, now=NOW + HARD_RETENTION_DEADLINE)
    assert req.request_id in swept.requests and req.request_id in swept.results
    assert worker_exchange.read_request(
        tenant, req.request_id)["minimized_context"] is None
    assert worker_exchange.read_result(tenant, req.request_id)["payload"] is None


def test_acknowledged_content_is_purged_an_hour_later(worker_exchange,
                                                      unit_exchange, tenant):
    req = _served(worker_exchange, unit_exchange, tenant)
    ack = NOW + timedelta(minutes=5)
    worker_exchange.acknowledge(tenant, req.request_id, at=ack)

    assert worker_exchange.purge_due(
        tenant, now=ack + ACKNOWLEDGEMENT_GRACE - timedelta(seconds=1)).count == 0
    swept = worker_exchange.purge_due(tenant, now=ack + ACKNOWLEDGEMENT_GRACE)
    assert req.request_id in swept.results


def test_the_two_artifacts_are_governed_independently(worker_exchange,
                                                      unit_exchange, tenant):
    """§4.4: each content-bearing artifact has its own creation clock, so a
    response created later than its request outlives it under the hard deadline."""

    req = request(tenant, submitted_at=NOW)
    worker_exchange.submit(req)
    later = NOW + timedelta(hours=6)
    EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="u", lease=LEASE
               ).run_once(tenant, now=later)

    at = NOW + HARD_RETENTION_DEADLINE
    swept = worker_exchange.purge_due(tenant, now=at)
    assert req.request_id in swept.requests, "the request's own clock has run out"
    assert req.request_id not in swept.results, "the response's has not"

    swept2 = worker_exchange.purge_due(tenant, now=later + HARD_RETENTION_DEADLINE)
    assert req.request_id in swept2.results


# --- 4. the tombstone --------------------------------------------------------

def test_the_tombstone_keeps_exactly_the_approved_set(worker_exchange,
                                                      unit_exchange, tenant):
    req = _served(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, req.request_id, at=NOW + timedelta(minutes=1))
    worker_exchange.purge_due(tenant, now=NOW + HARD_RETENTION_DEADLINE)

    t = worker_exchange.tombstone(tenant, req.request_id)

    for key in ("tenant_id", "request_id", "correlation_id", "clearance_ref",
                "clearance_digest", "reservation_id", "authorized_vendor",
                "authorized_model", "policy_id", "request_digest",
                "request_content_digest", "response_digest", "outcome",
                "acknowledged_at", "request_content_purged_at",
                "response_content_purged_at", "provenance", "genuine_call",
                "exchange_schema_version"):
        assert t[key] is not None, key

    assert "minimized_context" not in t and "payload" not in t, (
        "a tombstone selects no column that could carry content")
    assert t["correlation_id"] == req.correlation_id
    assert t["reservation_id"] == req.authorization.reservation_id
    assert t["genuine_call"] is False


def test_the_request_digest_recomputes_from_the_tombstone(worker_exchange,
                                                          unit_exchange, tenant):
    """The reason content is digested rather than inlined: a purged row can still
    be checked against a candidate context."""

    req = _served(worker_exchange, unit_exchange, tenant)
    worker_exchange.acknowledge(tenant, req.request_id, at=NOW + timedelta(minutes=1))
    worker_exchange.purge_due(tenant, now=NOW + HARD_RETENTION_DEADLINE)

    row = worker_exchange.read_request(tenant, req.request_id)
    assert row["minimized_context"] is None
    rebuilt = EgressRequest(
        request_id=row["request_id"], tenant_id=row["tenant_id"],
        correlation_id=row["correlation_id"], submitted_at=row["submitted_at"],
        not_valid_after=row["not_valid_after"],
        authorization=AuthorizationBinding(
            clearance_ref=row["clearance_ref"], clearance_digest=row["clearance_digest"],
            tenant_id=row["tenant_id"], authorized_vendor=row["authorized_vendor"],
            authorized_model=row["authorized_model"], policy_id=row["policy_id"],
            reservation_id=row["reservation_id"]),
        minimized_context=None, content_digest=row["content_digest"],
        parameters=row["parameters"],
        exchange_schema_version=row["exchange_schema_version"])
    assert rebuilt.digest() == row["request_digest"]
    assert row["content_digest"] == minimized_context_digest(CONTEXT), (
        "and a holder of the candidate context can still prove it was the one")


# --- 5. ambiguous dispatch ---------------------------------------------------

def test_an_ambiguous_dispatch_writes_a_distinct_record(worker_exchange,
                                                        unit_exchange, tenant):
    """§4.2: not a partially filled response record. Every provider-side fact is
    explicitly UNKNOWN."""

    req = request(tenant)
    worker_exchange.submit(req)
    unit_exchange.claim(tenant, holder="crashed", now=NOW, lease=LEASE)
    unit_exchange.mark_dispatched(tenant, req.request_id, at=NOW)

    after = NOW + LEASE + timedelta(seconds=1)
    swept = ReconciliationScheduler(unit_exchange).sweep(tenant, now=after)
    assert swept.reconciled == [req.request_id]

    stored = worker_exchange.read_result(tenant, req.request_id)
    assert stored["outcome"] is ResultOutcome.OUTCOME_UNKNOWN
    assert stored["provenance_kind"] is ProvenanceKind.DISPATCH_ATTEMPT
    p = stored["provenance"]
    for unknown in ("provider_receipt", "provider_acceptance", "provider_completion",
                    "billed", "token_usage", "cost", "response_exists"):
        assert p[unknown] == "UNKNOWN", unknown
    assert p["genuine_call"] is False
    assert stored["correlation_id"] == req.correlation_id


def test_the_database_refuses_an_unknown_outcome_shaped_as_a_response(database, tenant):
    """The constraint, asserted directly: application code is not the only thing
    that writes to a database."""

    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                f"""INSERT INTO {SCHEMA_NAME}.egress_result
                    (tenant_id, request_id, correlation_id, recorded_at, trust,
                     outcome, adapter_id, provenance_kind, genuine_call, provenance,
                     content_created_at, response_digest)
                    VALUES (%s,%s,%s,now(),'UNTRUSTED_EVIDENCE','OUTCOME_UNKNOWN','a',
                            'RESPONSE',false,'{{}}',now(),repeat('0',64))""",
                (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())))


# --- 6. OUTCOME_UNKNOWN is terminal; the reservation is never released -------

def test_the_reservation_is_never_released(worker_exchange, unit_exchange, tenant,
                                           database):
    req = request(tenant)
    worker_exchange.submit(req)
    unit_exchange.claim(tenant, holder="crashed", now=NOW, lease=LEASE)
    unit_exchange.mark_dispatched(tenant, req.request_id, at=NOW)
    after = NOW + LEASE + timedelta(seconds=1)
    ReconciliationScheduler(unit_exchange).sweep(tenant, now=after)

    assert worker_exchange.read_result(
        tenant, req.request_id)["reservation_released"] is False

    # Purging the content does not purge the obligation.
    worker_exchange.purge_due(tenant, now=NOW + HARD_RETENTION_DEADLINE)
    t = worker_exchange.tombstone(tenant, req.request_id)
    assert t["reservation_released"] is False
    assert t["reservation_id"] == req.authorization.reservation_id
    assert t["authorized_vendor"] == VENDOR, (
        "a purged OUTCOME_UNKNOWN still names the vendor, or D-5's reconciliation "
        "could not be performed")

    # And the database will not let anyone say otherwise.
    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                f"UPDATE {SCHEMA_NAME}.egress_result SET reservation_released = true")


def test_an_undispatched_expiry_returns_the_request_to_the_queue(worker_exchange,
                                                                 unit_exchange, tenant):
    """§4.3: before dispatch, an expired lease may make the request claimable
    again. No call was made, so nothing is at risk in serving it."""

    req = request(tenant)
    worker_exchange.submit(req)
    unit_exchange.claim(tenant, holder="stalled", now=NOW, lease=LEASE)

    after = NOW + LEASE + timedelta(seconds=1)
    swept = ReconciliationScheduler(unit_exchange).sweep(tenant, now=after)

    assert swept.requeued == [req.request_id] and swept.reconciled == []
    assert worker_exchange.read_request(
        tenant, req.request_id)["state"] is RequestState.PENDING

    done = EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-2",
                      lease=LEASE).run_once(tenant, now=after)
    assert done.request_id == req.request_id, "and it is served"


def test_a_dispatched_expiry_never_returns_to_the_queue(worker_exchange,
                                                        unit_exchange, tenant):
    req = request(tenant)
    worker_exchange.submit(req)
    unit_exchange.claim(tenant, holder="crashed", now=NOW, lease=LEASE)
    unit_exchange.mark_dispatched(tenant, req.request_id, at=NOW)

    after = NOW + LEASE + timedelta(seconds=1)
    ReconciliationScheduler(unit_exchange).sweep(tenant, now=after)

    assert worker_exchange.read_request(
        tenant, req.request_id)["state"] is RequestState.OUTCOME_UNKNOWN
    assert EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-2"
                      ).run_once(tenant, now=after).did_work is False


def test_a_dispatch_marker_landing_mid_sweep_is_not_undone(worker_exchange,
                                                           unit_exchange, tenant):
    """The requeue is guarded inside its own UPDATE, not by a prior read."""

    req = request(tenant)
    worker_exchange.submit(req)
    unit_exchange.claim(tenant, holder="slow", now=NOW, lease=LEASE)
    unit_exchange.mark_dispatched(tenant, req.request_id, at=NOW)

    assert unit_exchange.release_undispatched_lease(tenant, req.request_id) is False
    assert worker_exchange.read_request(
        tenant, req.request_id)["state"] is RequestState.LEASED


# --- trust, and the no-genuine-call posture ---------------------------------

def test_trust_is_a_constant(worker_exchange, unit_exchange, tenant):
    req = _served(worker_exchange, unit_exchange, tenant)
    assert worker_exchange.read_result(tenant, req.request_id)["trust"] == TRUST_LEVEL


def test_the_database_refuses_any_other_trust_value(database, tenant):
    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                f"""INSERT INTO {SCHEMA_NAME}.egress_result
                    (tenant_id, request_id, correlation_id, recorded_at, trust,
                     outcome, adapter_id, provenance_kind, genuine_call, provenance,
                     content_created_at, response_digest)
                    VALUES (%s,%s,%s,now(),'TRUSTED','REFUSED','a','RESPONSE',false,
                            '{{}}',now(),repeat('0',64))""",
                (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())))


def test_no_row_may_claim_a_genuine_call(database, tenant):
    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                f"""INSERT INTO {SCHEMA_NAME}.egress_result
                    (tenant_id, request_id, correlation_id, recorded_at, trust,
                     outcome, adapter_id, provenance_kind, genuine_call, provenance,
                     content_created_at, response_digest)
                    VALUES (%s,%s,%s,now(),'UNTRUSTED_EVIDENCE','FAILED','a',
                            'RESPONSE',true,'{{}}',now(),repeat('0',64))""",
                (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())))


def test_a_uncommissioned_credential_is_a_typed_refusal(worker_exchange,
                                                        unit_exchange, tenant):
    """§5.3: the unit composes, claims work, validates it and refuses the call —
    never a generic error, never a silent skip, never a fabricated answer."""

    req = request(tenant)
    worker_exchange.submit(req)
    done = EgressUnit(unit_exchange, LiveEgressUnavailableProvider(), holder="u",
                      lease=LEASE).run_once(tenant, now=NOW)

    assert done.outcome is ResultOutcome.REFUSED
    assert worker_exchange.read_result(
        tenant, req.request_id)["refusal_reason"] is (
        RefusalReason.CREDENTIAL_NOT_COMMISSIONED)


# --- tenant participates in identity and uniqueness -------------------------

def test_tenant_is_part_of_the_primary_key(database):
    """§4.3: the dedup key is tenant-scoped, so two tenants' requests can never
    collapse into one identity."""

    with psycopg.connect(database) as conn:
        cols = conn.execute(
            """SELECT a.attname
               FROM pg_index i
               JOIN pg_attribute a ON a.attrelid = i.indrelid
                                  AND a.attnum = ANY(i.indkey)
               WHERE i.indrelid = %s::regclass AND i.indisprimary
               ORDER BY a.attname""",
            (f"{SCHEMA_NAME}.egress_request",)).fetchall()
    assert [c[0] for c in cols] == ["request_id", "tenant_id"]


def test_the_same_request_id_may_exist_in_two_tenants(worker_exchange, tenant,
                                                      other_tenant, database):
    shared = uuid.uuid4()
    worker_exchange.submit(request(tenant, request_id=shared))

    # The other tenant's row is written through a session scoped to it.
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute("SELECT set_config('ugence.tenant_id', %s, false)",
                     (str(other_tenant),))
        other = request(other_tenant, request_id=shared)
        a = other.authorization
        conn.execute(
            f"""INSERT INTO {SCHEMA_NAME}.egress_request
                (tenant_id, request_id, correlation_id, exchange_schema_version,
                 submitted_at, not_valid_after, state, clearance_ref, clearance_digest,
                 authorized_vendor, authorized_model, policy_id, reservation_id,
                 parameters, minimized_context, content_digest, content_created_at,
                 request_digest)
                VALUES (%s,%s,%s,%s,%s,%s,'PENDING',%s,%s,%s,%s,%s,%s,'{{}}','[]',%s,%s,%s)""",
            (str(other_tenant), str(shared), str(other.correlation_id),
             other.exchange_schema_version, other.submitted_at, other.not_valid_after,
             a.clearance_ref, a.clearance_digest, a.authorized_vendor,
             a.authorized_model, a.policy_id, a.reservation_id,
             other.content_digest, other.submitted_at, other.digest()))

    assert worker_exchange.read_request(tenant, shared) is not None
    assert worker_exchange.read_request(tenant, shared)["tenant_id"] == tenant
