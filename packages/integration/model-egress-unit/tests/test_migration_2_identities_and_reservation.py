"""Migration 2 against a real PostgreSQL: the migrator identity, tenant-bound runtime
identities, the LP-2b custody constraint and the durable LP-5 reservation.

Every boundary is measured both ways: the allowed path works, and the forbidden one
is refused by the database, not by the code's good behaviour.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import psycopg
import pytest

from _fixtures import NOW, request as _make_request
from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    COMMISSIONING_STATUS,
    BudgetExhausted,
    DeterministicFakeProvider,
    EgressResult,
    ResultOutcome,
)
from ugence_model_egress_unit.postgres import (
    BINDING_TABLE,
    BUDGET_TABLE,
    MIGRATIONS,
    MIGRATOR_ROLE,
    OWNER_ROLE,
    RESERVATION_TABLE,
    SCHEMA_NAME,
    UNIT_ROLE,
    WORKER_ROLE,
    Exchange,
    applied_versions,
    bind_identity,
    identity_name,
    identity_report,
    identity_statements,
    migrate,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def blank(admin_dsn):
    """A database with no migrations applied (``database`` is already migrated)."""

    name = f"meu_blank2_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    head, _, _tail = admin_dsn.rpartition("/")
    try:
        yield f"{head}/{name}"
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _as(dsn, role):
    def connect():
        conn = psycopg.connect(dsn, autocommit=True)
        conn.execute(f"SET ROLE {role}")
        conn.autocommit = False
        return conn
    return connect


def _submit_and_answer(worker: Exchange, unit: Exchange, tenant):
    req = _make_request(tenant)
    worker.submit(req)
    claimed = unit.claim(tenant, holder="unit-1", now=NOW, lease=timedelta(minutes=5))
    result = DeterministicFakeProvider().execute(claimed.request, now=NOW + timedelta(seconds=1))
    unit.record_result(result)
    return req, result


# --- fresh install and upgrade path ------------------------------------------------

def test_a_fresh_install_applies_both_migrations_and_migration_one_is_byte_identical(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        applied = migrate(conn)
        assert [m.version for m in applied] == [1, 2]
        assert applied_versions(conn) == {1: MIGRATIONS[0].digest, 2: MIGRATIONS[1].digest}
        assert migrate(conn) == []
    # the digest of migration 1 is the one #1743 shipped: nothing edited an applied step
    assert MIGRATIONS[0].name == "exchange_roles_tables_and_rls"


def test_the_upgrade_path_keeps_existing_rows_and_digests_valid(blank, tenant):
    """Rows written under migration 1 (by the 0.1.x/0.2.x code, which knew no custody
    columns) read back unchanged after migration 2, their digests still recompute, and
    the upgraded exchange keeps working."""
    with psycopg.connect(blank, autocommit=True) as conn:
        assert [m.version for m in migrate(conn, MIGRATIONS[:1])] == [1]
        for role in (WORKER_ROLE, UNIT_ROLE):
            conn.execute(f"GRANT CONNECT ON DATABASE \"{conn.info.dbname}\" TO {role}")
    # a pre-upgrade request and result, written the migration-1 way (no custody columns)
    req = _make_request(tenant)
    Exchange(_as(blank, WORKER_ROLE)).submit(req)
    result = DeterministicFakeProvider().execute(req, now=NOW + timedelta(seconds=1))
    with psycopg.connect(blank) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('ugence.tenant_id', %s, true)", (str(tenant),))
            conn.execute(
                f"""UPDATE {SCHEMA_NAME}.egress_request SET state = 'COMPLETED', terminal_at = %s
                    WHERE request_id = %s""", (result.recorded_at, str(req.request_id)))
            conn.execute(
                f"""INSERT INTO {SCHEMA_NAME}.egress_result
                    (tenant_id, request_id, correlation_id, recorded_at, trust, outcome, refusal_reason,
                     adapter_id, provenance_kind, genuine_call, provenance, payload, content_digest,
                     content_created_at, response_digest)
                    VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,false,%s,%s,%s,%s,%s)""",
                (str(tenant), str(req.request_id), str(req.correlation_id), result.recorded_at,
                 result.trust, result.outcome.value, result.adapter_id, result.provenance_kind.value,
                 psycopg.types.json.Jsonb(dict(result.provenance)), result.payload, result.content_digest,
                 result.recorded_at, result.digest()))
    worker = Exchange(_as(blank, WORKER_ROLE))
    before = worker.read_result(tenant, req.request_id)
    assert before is not None and before["response_digest"] == result.digest()
    with psycopg.connect(blank, autocommit=True) as conn:
        assert [m.version for m in migrate(conn)] == [2]
        with conn.cursor() as cur:
            cur.execute("SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass",
                        (f"{SCHEMA_NAME}.egress_result",))
            names = {r[0] for r in cur.fetchall()}
        assert "egress_result_no_genuine_call" not in names
        assert "egress_result_genuine_call_requires_custody" in names
    after = worker.read_result(tenant, req.request_id)
    assert after == before, "an existing row reads back unchanged after the upgrade"
    assert after["response_digest"] == result.digest(), "its digest still recomputes"
    # and the upgraded exchange keeps working, custody columns included
    _submit_and_answer(worker, Exchange(_as(blank, UNIT_ROLE)), tenant)


def test_the_upgrade_is_all_or_nothing(blank):
    """A migration 2 that fails halfway leaves the database on version 1."""
    from ugence_model_egress_unit.postgres.migrations import Migration
    broken = Migration(version=2, name="broken", sql=MIGRATIONS[1].sql + "\nSELECT 1/0;")
    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn, MIGRATIONS[:1])
        with pytest.raises(psycopg.errors.DivisionByZero):
            migrate(conn, (MIGRATIONS[0], broken))
        assert applied_versions(conn) == {1: MIGRATIONS[0].digest}
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"{SCHEMA_NAME}.{BUDGET_TABLE}",))
            assert cur.fetchone()[0] is None, "nothing of the failed step survives"


# --- the migrator identity and what the runtime roles cannot do -------------------

def test_the_migrator_holds_nothing_until_it_assumes_the_owner(database, tenant):
    with psycopg.connect(database, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rolcanlogin, rolinherit, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s",
                        (MIGRATOR_ROLE,))
            assert cur.fetchone() == (False, False, False, False)
    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {MIGRATOR_ROLE}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request")
    conn.execute(f"SET ROLE {OWNER_ROLE}")  # a member may assume the owner during a migration
    conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{BINDING_TABLE}")
    conn.close()


@pytest.mark.parametrize("group", [WORKER_ROLE, UNIT_ROLE])
def test_a_runtime_identity_cannot_ddl_disable_rls_drop_a_policy_or_assume_a_privileged_role(database, group):
    """A genuine login identity, not SET ROLE from a superuser: SET ROLE is judged
    against the *session* user's memberships, so a superuser session can assume any
    role and would make the last three refusals below untestable."""
    probe = f"meu_probe_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(database, autocommit=True) as admin:
        admin.execute(f"CREATE ROLE {probe} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE IN ROLE {group}")
        admin.execute(f'GRANT CONNECT ON DATABASE "{admin.info.dbname}" TO {probe}')
    head, _, tail = database.rpartition("/")
    scheme, _, rest = head.partition("://")
    _user, at, hostport = rest.rpartition("@")
    probe_dsn = f"{scheme}://{probe}@{hostport}/{tail}"
    conn = psycopg.connect(probe_dsn, autocommit=True)
    try:
        _probe_forbidden_statements(conn, probe)
    finally:
        conn.close()
        with psycopg.connect(database, autocommit=True) as admin:
            admin.execute(f'REVOKE ALL ON DATABASE "{admin.info.dbname}" FROM {probe}')
            admin.execute(f"DROP OWNED BY {probe}")
            admin.execute(f"DROP ROLE {probe}")


def _probe_forbidden_statements(conn, probe):
    assert conn.execute("SELECT session_user").fetchone()[0] == probe
    conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(uuid.uuid4()),))
    forbidden = [
        f"CREATE TABLE {SCHEMA_NAME}.smuggled (x int)",
        f"ALTER TABLE {SCHEMA_NAME}.egress_request DISABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {SCHEMA_NAME}.egress_request NO FORCE ROW LEVEL SECURITY",
        f"DROP POLICY tenant_isolation ON {SCHEMA_NAME}.egress_request",
        f"DROP POLICY identity_binding ON {SCHEMA_NAME}.egress_request",
        f"ALTER TABLE {SCHEMA_NAME}.egress_result DROP CONSTRAINT egress_result_genuine_call_requires_custody",
        f"INSERT INTO {SCHEMA_NAME}.{BINDING_TABLE} (role_name, tenant_id) VALUES ('x', gen_random_uuid())",
        f"DELETE FROM {SCHEMA_NAME}.{BUDGET_TABLE}",
        f"DROP TRIGGER commissioning_budget_no_refund ON {SCHEMA_NAME}.{BUDGET_TABLE}",
        f"SET ROLE {OWNER_ROLE}",
        f"SET ROLE {MIGRATOR_ROLE}",
        "CREATE ROLE smuggled",
        "INSERT INTO public.meu_schema_version (version, name, digest) VALUES (99, 'x', repeat('0', 64))",
        "ALTER ROLE CURRENT_USER BYPASSRLS",
    ]
    for sql in forbidden:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql)
    # and the identity still works through its group's grants
    conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request")


# --- tenant-bound runtime identities ----------------------------------------------

def test_a_bound_identity_is_refused_every_other_tenant_whatever_its_session_claims(database, tenant, other_tenant):
    worker_id, unit_id = identity_name("worker", tenant), identity_name("unit", tenant)
    with psycopg.connect(database, autocommit=True) as conn:
        for side, name in (("worker", worker_id), ("unit", unit_id)):
            for stmt in identity_statements(side, tenant, login=False):
                conn.execute(stmt)
    bound_worker, bound_unit = Exchange(_as(database, worker_id)), Exchange(_as(database, unit_id))
    generic_worker = Exchange(_as(database, WORKER_ROLE))
    # its own tenant: everything works, through the inherited grants
    req, _ = _submit_and_answer(bound_worker, bound_unit, tenant)
    assert bound_worker.read_result(tenant, req.request_id) is not None
    # another tenant, with the session scoped to that tenant: the binding policy refuses
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        bound_worker.submit(_make_request(other_tenant))
    foreign = _make_request(other_tenant)
    generic_worker.submit(foreign)  # the unbound reference role can, as before
    assert bound_worker.read_request(other_tenant, foreign.request_id) is None
    assert bound_unit.claim(other_tenant, holder="u", now=NOW, lease=timedelta(minutes=1)) is None
    assert generic_worker.read_request(other_tenant, foreign.request_id) is not None


def test_a_binding_cannot_be_written_by_a_runtime_role_and_the_report_names_unbound_logins(database, tenant):
    stray = f"stray_login_{uuid.uuid4().hex[:8]}"  # roles are cluster-wide; other databases may hold their own
    with psycopg.connect(database, autocommit=True) as conn:
        assert [r for r in identity_report(conn) if r["role"] == stray] == []
        conn.execute(f"CREATE ROLE {stray} LOGIN NOSUPERUSER NOBYPASSRLS IN ROLE {WORKER_ROLE}")
        try:
            report = [r for r in identity_report(conn) if r["role"] == stray]
            assert report == [{"role": stray, "group": WORKER_ROLE, "tenant_id": None, "bound": False}]
            bind_identity(conn, stray, tenant)
            (row,) = [r for r in identity_report(conn) if r["role"] == stray]
            assert row["bound"] is True and row["tenant_id"] == str(tenant)
        finally:
            conn.execute(f"DROP OWNED BY {stray}")
            conn.execute(f"DROP ROLE {stray}")
    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {UNIT_ROLE}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"UPDATE {SCHEMA_NAME}.{BINDING_TABLE} SET tenant_id = gen_random_uuid()")
    conn.close()


# --- LP-2b: the custody constraint, both halves ----------------------------------

def test_the_database_admits_a_genuine_row_only_with_custody_and_the_application_admits_none(database, tenant, worker_exchange, unit_exchange):
    req, _ = _submit_and_answer(worker_exchange, unit_exchange, tenant)
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute(f"SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(f"UPDATE {SCHEMA_NAME}.egress_result SET genuine_call = true WHERE request_id = %s",
                         (str(req.request_id),))
        conn.execute(f"""UPDATE {SCHEMA_NAME}.egress_result SET genuine_call = true,
                         custody_lease_id = 'lease-x', custody_authority_id = 'custody-x'
                         WHERE request_id = %s""", (str(req.request_id),))
        conn.execute(f"""UPDATE {SCHEMA_NAME}.egress_result SET genuine_call = false,
                         custody_lease_id = NULL, custody_authority_id = NULL WHERE request_id = %s""",
                     (str(req.request_id),))
    # the application half: no result may claim a genuine call while commissioning is not MET
    assert COMMISSIONING_STATUS != "MET"
    fake = DeterministicFakeProvider().execute(_make_request(tenant), now=NOW)
    with pytest.raises(ValueError, match="while commissioning is"):
        EgressResult(request_id=fake.request_id, tenant_id=fake.tenant_id, correlation_id=fake.correlation_id,
                     recorded_at=fake.recorded_at, outcome=ResultOutcome.ANSWERED, adapter_id="x",
                     provenance={**dict(fake.provenance), "genuine_call": True}, payload="p",
                     content_digest=fake.content_digest, custody_lease_id="l", custody_authority_id="c")


# --- LP-5: the durable reservation ------------------------------------------------

def test_the_reservation_is_taken_before_dispatch_and_never_refunded(database, tenant, unit_exchange, worker_exchange):
    rid = uuid.uuid4()
    assert unit_exchange.reserve_commissioning_call(tenant, rid, estimated_cents=200, now=NOW) == 1
    assert unit_exchange.commissioning_budget(tenant) == {"tenant_id": str(tenant), "calls_reserved": 1,
                                                          "cents_reserved": 200, "in_flight": 1}
    with pytest.raises(BudgetExhausted):  # concurrency 1
        unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=1, now=NOW)
    unit_exchange.release_in_flight(tenant)
    assert unit_exchange.commissioning_budget(tenant)["in_flight"] == 0
    with pytest.raises(BudgetExhausted):  # over budget, refused, nothing recorded
        unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=2301, now=NOW)
    assert unit_exchange.commissioning_budget(tenant)["calls_reserved"] == 1
    for n in range(9):
        assert unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=100, now=NOW) == n + 2
        unit_exchange.release_in_flight(tenant)
    with pytest.raises(BudgetExhausted):  # the eleventh
        unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=0, now=NOW)
    # nothing refunds: not the unit, not by a direct decrement, not by delete
    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {UNIT_ROLE}")
    conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(f"UPDATE {SCHEMA_NAME}.{BUDGET_TABLE} SET calls_reserved = calls_reserved - 1")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(f"UPDATE {SCHEMA_NAME}.{BUDGET_TABLE} SET cents_reserved = 0")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"DELETE FROM {SCHEMA_NAME}.{RESERVATION_TABLE}")
    with pytest.raises(psycopg.errors.CheckViolation):  # the table's own ceiling, even bypassing the method
        conn.execute(f"UPDATE {SCHEMA_NAME}.{BUDGET_TABLE} SET calls_reserved = 11")
    conn.close()
    # the worker may read the budget and may not reserve
    assert worker_exchange.commissioning_budget(tenant)["calls_reserved"] == 10
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        worker_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=0, now=NOW)
    assert COMMISSIONING_LIMITS.max_genuine_calls == 10


def test_a_reservation_is_tenant_scoped(database, tenant, other_tenant, unit_exchange):
    unit_exchange.reserve_commissioning_call(tenant, uuid.uuid4(), estimated_cents=5, now=NOW)
    assert unit_exchange.commissioning_budget(other_tenant) is None
    assert unit_exchange.reserve_commissioning_call(other_tenant, uuid.uuid4(), estimated_cents=5, now=NOW) == 1
