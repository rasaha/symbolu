"""Migration 3 (ADR §0.6): the durable consumption ledger, on real PostgreSQL.

Consumption happens before dispatch in one transaction with the LP-5 reservation; a
nonce backs one digest ever; a request is consumed once; the call ceiling holds in the
table; nothing is given back; a genuine result row must reference its consumption; the
fresh install and the upgrade from migration 2 both land here.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

import ugence_model_egress_unit.version as version
from ugence_model_egress_unit import (
    NOT_GIVEN,
    AuthorizationRefusal as R,
    AuthorizationRefused,
    CommissioningRecordView,
    EgressRequest,
    EgressResult,
    LiveSyntheticValidationAuthorization,
    MinimizedUnit,
    ScopeExpectation,
    admit_genuine_call,
    designation_record_digest,
    reference_clearance,
)
from ugence_model_egress_unit.postgres import (
    AUTHORIZATION_TABLE,
    CONSUMPTION_TABLE,
    SCHEMA_NAME,
    UNIT_ROLE,
    WORKER_ROLE,
    Exchange,
    ExchangeAuthorizationLedger,
    MIGRATIONS,
    migrate,
)

NOW = datetime(2026, 9, 12, 1, 0, tzinfo=timezone.utc)
MODEL = "gpt-5.4-mini-2026-03-17"
OWNER = "Rakesh Mohan — Founder, Ugence Labs"
DESIGNATION = {"schema": "model-egress-unit.live-provider-designation.v1", "fixture": "test-designation"}
SCOPE = ScopeExpectation(openai_organization_id="org-a1b2c3d4e5", openai_project_id="proj_f6g7h8i9j0",
                         openai_service_account_id="svc-acct-meu-validation-01", model=MODEL)
PLAN = "a" * 64


def _request(tenant, text="synthetic probe") -> EgressRequest:
    return EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, correlation_id=uuid.uuid4(), submitted_at=NOW,
        not_valid_after=NOW + timedelta(hours=1),
        authorization=reference_clearance(tenant_id=tenant, vendor="openai", model=MODEL),
        minimized_context=[MinimizedUnit("u-1", text, 8)], parameters={"max_output_tokens": 64})


def _auth(requests, **overrides) -> LiveSyntheticValidationAuthorization:
    base = dict(
        authorization_id="lsva-2026-09-12-001", nonce="nonce-" + uuid.uuid4().hex, authorizing_owner=OWNER,
        authority_reference="acceptance://owner/live-synthetic-validation/2026-09-12",
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(hours=2), environment="NON_PRODUCTION",
        openai_organization_id=SCOPE.openai_organization_id, openai_project_id=SCOPE.openai_project_id,
        openai_service_account_id=SCOPE.openai_service_account_id, provider="openai", model=MODEL,
        endpoint="https://api.openai.com/v1/responses", designation_record_digest=designation_record_digest(DESIGNATION),
        validation_plan_digest=PLAN, authorized_request_digests=tuple(r.digest() for r in requests),
        synthetic_non_sensitive_only=True, max_calls=len(requests), max_input_tokens=8_192, max_output_tokens=1_024,
        budget_usd_cents=2_500, concurrency=1, max_retries=1)
    base.update(overrides)
    return LiveSyntheticValidationAuthorization(**base)


def _record(auth, status="PENDING_VALIDATION") -> CommissioningRecordView:
    return CommissioningRecordView(status=status, authorization_digest=auth.digest(), revoked_digests=(),
                                   authorizing_owner=OWNER, designation_digest=designation_record_digest(DESIGNATION))


def _admit(auth, request, ledger, now=NOW, cents=250):
    return admit_genuine_call(auth, record=_record(auth), request=request, expected=SCOPE, plan_digest=PLAN,
                              now=now, ledger=ledger, estimated_cents=cents)


def test_the_ledger_is_the_real_one_and_the_migration_is_the_third():
    assert ExchangeAuthorizationLedger.NON_PRODUCTION is False
    assert [m.version for m in MIGRATIONS] == [1, 2, 3]


def test_consumption_is_durable_before_dispatch_in_one_transaction_with_the_reservation(database, tenant, unit_exchange):
    ledger = ExchangeAuthorizationLedger(unit_exchange)
    r1, r2 = _request(tenant), _request(tenant, "second")
    auth = _auth([r1, r2])
    assert ledger.capacity(tenant_id=tenant) == (10, 2500)
    admission = _admit(auth, r1, ledger)
    assert admission.verify() and admission.call_number == 1 and uuid.UUID(admission.consumption_id)
    assert ledger.capacity(tenant_id=tenant) == (9, 2250)
    assert unit_exchange.commissioning_budget(tenant)["in_flight"] == 1   # reserved, in flight, before any dispatch
    state = ledger.authorization_state(auth.nonce)
    assert state["calls_consumed"] == 1 and state["max_calls"] == 2 and state["authorization_digest"] == auth.digest()
    # an ambiguous dispatch keeps the consumption: only in_flight comes down
    unit_exchange.release_in_flight(tenant)
    assert ledger.capacity(tenant_id=tenant) == (9, 2250) and ledger.authorization_state(auth.nonce)["calls_consumed"] == 1
    # the same request again: refused, nothing consumed
    with pytest.raises(AuthorizationRefused) as info:
        _admit(auth, r1, ledger)
    assert info.value.reason is R.ALREADY_CONSUMED
    assert ledger.authorization_state(auth.nonce)["calls_consumed"] == 1 and ledger.capacity(tenant_id=tenant) == (9, 2250)
    second = _admit(auth, r2, ledger)
    assert second.call_number == 2
    # the sequence is consumed: a third request under the same authorization is refused
    r3 = _request(tenant, "third")
    with pytest.raises(AuthorizationRefused) as info:
        _admit(_auth([r1, r2, r3], nonce=auth.nonce), r3, ledger)  # same nonce, different digest → replay
    assert info.value.reason is R.NONCE_REPLAYED


def test_calls_exhausted_and_expiry_hold_in_the_table_and_nothing_rewinds(database, tenant, unit_exchange, worker_exchange):
    ledger = ExchangeAuthorizationLedger(unit_exchange)
    r1 = _request(tenant)
    auth = _auth([r1], max_calls=1)
    _admit(auth, r1, ledger)
    unit_exchange.release_in_flight(tenant)
    r_other = _request(tenant, "another")
    auth_same = dataclasses.replace(auth, authorized_request_digests=(r1.digest(), r_other.digest()), max_calls=2)
    # a different (edited) authorization on the same nonce is a replay, whatever it authorizes
    with pytest.raises(AuthorizationRefused) as info:
        _admit(auth_same, r_other, ledger)
    assert info.value.reason is R.NONCE_REPLAYED
    # expiry is enforced by the durable row too, not only by the pure check
    expired = _auth([r_other], issued_at=NOW - timedelta(hours=3), expires_at=NOW - timedelta(hours=1))
    with pytest.raises(AuthorizationRefused) as info:
        _admit(expired, r_other, ledger)
    assert info.value.reason is R.EXPIRED
    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {UNIT_ROLE}")
    conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
    with pytest.raises(psycopg.errors.CheckViolation):     # never rewound
        conn.execute(f"UPDATE {SCHEMA_NAME}.{AUTHORIZATION_TABLE} SET calls_consumed = 0")
    with pytest.raises(psycopg.errors.CheckViolation):     # the table's own ceiling
        conn.execute(f"UPDATE {SCHEMA_NAME}.{AUTHORIZATION_TABLE} SET calls_consumed = 2")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"UPDATE {SCHEMA_NAME}.{AUTHORIZATION_TABLE} SET expires_at = now() + interval '1 year'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"DELETE FROM {SCHEMA_NAME}.{CONSUMPTION_TABLE}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"DELETE FROM {SCHEMA_NAME}.{AUTHORIZATION_TABLE}")
    conn.close()
    # the worker may read the ledger and may not consume
    assert ExchangeAuthorizationLedger(worker_exchange).authorization_state(auth.nonce)["calls_consumed"] == 1
    rw = _request(tenant, "w")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _admit(_auth([rw]), rw, ExchangeAuthorizationLedger(worker_exchange))


def test_capacity_exhaustion_rolls_the_consumption_back(database, tenant, unit_exchange):
    ledger = ExchangeAuthorizationLedger(unit_exchange)
    for n in range(10):
        unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=100, now=NOW)
        unit_exchange.release_in_flight(tenant)
    r = _request(tenant)
    auth = _auth([r])
    with pytest.raises(AuthorizationRefused) as info:
        _admit(auth, r, ledger)
    assert info.value.reason is R.CAPACITY_EXHAUSTED
    assert ledger.authorization_state(auth.nonce) is None      # nothing consumed without capacity


def test_a_genuine_result_row_needs_the_consumption_and_the_application_needs_the_admission(database, tenant, worker_exchange, unit_exchange, monkeypatch):
    ledger = ExchangeAuthorizationLedger(unit_exchange)
    r = _request(tenant)
    worker_exchange.submit(r)
    claimed = unit_exchange.claim(tenant, holder="unit-1", now=NOW, lease=timedelta(minutes=5))
    auth = _auth([r])
    admission = _admit(auth, claimed.request, ledger)
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "PENDING_VALIDATION")
    result = EgressResult.answered_genuine(
        request_id=r.request_id, tenant_id=tenant, correlation_id=r.correlation_id, recorded_at=NOW + timedelta(seconds=1),
        adapter_id="test-adapter", payload="[test] answer", model_ref=MODEL, custody_lease_id="lease-x",
        custody_authority_id="custody-x", admission=admission)
    unit_exchange.mark_dispatched(tenant, r.request_id, at=NOW)
    unit_exchange.record_result(result)
    row = worker_exchange.read_result(tenant, r.request_id)
    assert row["provenance"]["genuine_call"] is True
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
        cid = conn.execute(f"SELECT authorization_consumption_id FROM {SCHEMA_NAME}.egress_result WHERE request_id = %s",
                           (str(r.request_id),)).fetchone()[0]
        assert str(cid) == admission.consumption_id
    # the same admission cannot back a second result: the request is terminal and the
    # consumption is one row; a forged token for another request fails verification
    other = _request(tenant, "other")
    forged = dataclasses.replace(admission, request_id=other.request_id)
    assert not forged.verify()


def test_fresh_install_and_upgrade_from_migration_two_both_land_on_three(admin_dsn):
    import psycopg as pg
    from conftest import _swap_dbname
    name = f"meu_m3_{uuid.uuid4().hex[:12]}"
    with pg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    target = _swap_dbname(admin_dsn, name)
    try:
        with pg.connect(target, autocommit=True) as conn:
            assert [m.version for m in migrate(conn, MIGRATIONS[:2])] == [1, 2]   # the upgrade path
            names_before = {r[0] for r in conn.execute(
                f"SELECT conname FROM pg_constraint WHERE conrelid = '{SCHEMA_NAME}.egress_result'::regclass")}
            assert "egress_result_genuine_call_requires_custody" in names_before
            assert [m.version for m in migrate(conn)] == [3]
            assert migrate(conn) == []
            names = {r[0] for r in conn.execute(
                f"SELECT conname FROM pg_constraint WHERE conrelid = '{SCHEMA_NAME}.egress_result'::regclass")}
            assert "egress_result_genuine_call_requires_custody_and_admission" in names
            assert "egress_result_genuine_call_requires_custody" not in names
    finally:
        with pg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))
            conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
