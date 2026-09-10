"""Tenant isolation, measured against a real PostgreSQL server.

Every property here is asserted twice over: once that the boundary holds, and
once — by removing the mechanism — that it was the boundary holding it. A policy
test that only ever checks the allowed path proves nothing, because a table
nobody can read passes it too.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from _fixtures import NOW, request as _make_request
from ugence_model_egress_unit.postgres import (
    OWNER_ROLE,
    SCHEMA_NAME,
    UNIT_ROLE,
    WORKER_ROLE,
    Exchange,
    UnscopableConnection,
)

pytestmark = pytest.mark.postgres

#: The two ways a session with no tenant identity is refused, both hard errors.
#:
#: A never-set custom GUC raises ``UndefinedObject``. Once any transaction in the
#: session has set it, PostgreSQL keeps the placeholder and reverts it to the
#: empty string at commit, so the next read raises ``InvalidTextRepresentation``
#: on ``''::uuid`` instead. Two code paths, and the property that matters is the
#: same for both: **an error, never a silent empty result**. The tests below
#: exercise each path deliberately rather than accepting whichever turns up.
FAIL_CLOSED = (psycopg.errors.UndefinedObject, psycopg.errors.InvalidTextRepresentation)

#: A minimal well-formed request row, for tests that must bypass ``Exchange`` to
#: reach the policy or the grant directly. Parameterised (tenant, request,
#: correlation) so each caller supplies only what it is testing.
_RAW_INSERT = f"""INSERT INTO {SCHEMA_NAME}.egress_request
    (tenant_id, request_id, correlation_id, exchange_schema_version, submitted_at,
     not_valid_after, state, clearance_ref, clearance_digest, authorized_vendor,
     authorized_model, policy_id, reservation_id, parameters, minimized_context,
     content_digest, content_created_at, request_digest)
    VALUES (%s, %s, %s, 'v1', now(), now() + interval '1 hour', 'PENDING',
            'cer-raw', repeat('0', 64), 'v', 'm', 'p', 'rsv', '{{}}', '[]',
            repeat('0', 64), now(), repeat('0', 64))"""


def _request(tenant, **kw):
    return _make_request(tenant, **kw)


# --- the required tenant identity -------------------------------------------

def test_a_session_without_tenant_identity_cannot_read_anything(database, tenant):
    """The property that makes the isolation fail *closed*.

    ``current_setting`` is called without ``missing_ok``, so an unset session
    raises. With ``missing_ok=true`` it would return NULL, ``tenant_id = NULL``
    would be false for every row, and the session would read an empty exchange —
    concluding there was no work to do. That answer is indistinguishable from a
    correct one, which is exactly what makes it dangerous.
    """

    with psycopg.connect(database) as conn:
        conn.execute(f"SET ROLE {WORKER_ROLE}")
        with pytest.raises(psycopg.errors.UndefinedObject):
            conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request").fetchone()


def test_a_session_without_tenant_identity_cannot_write_either(database, tenant):
    with psycopg.connect(database) as conn:
        conn.execute(f"SET ROLE {WORKER_ROLE}")
        with pytest.raises(psycopg.errors.UndefinedObject):
            conn.execute(
                _RAW_INSERT, (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())),
            )


# --- cross-tenant reads and writes ------------------------------------------

def test_one_tenant_cannot_read_anothers_request(worker_exchange, tenant, other_tenant):
    request = _request(tenant)
    worker_exchange.submit(request)

    assert worker_exchange.read_request(tenant, request.request_id) is not None
    assert worker_exchange.read_request(other_tenant, request.request_id) is None


def test_one_tenant_cannot_write_a_row_belonging_to_another(worker_exchange, tenant,
                                                            other_tenant):
    """``WITH CHECK`` is what stops this, and it is separate from ``USING``.

    A policy with only ``USING`` filters reads and permits an insert of a row the
    author could never read back — a write-only cross-tenant channel.
    """

    forged = _make_request(other_tenant)
    # The exchange scopes the transaction to the row's own tenant, so to test the
    # policy we have to try the mismatch the application would never make.
    exchange = Exchange(worker_exchange._connect)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with exchange._connect() as conn:
            with conn.transaction():
                exchange._scoped(conn, tenant)
                conn.execute(
                    _RAW_INSERT,
                    (str(forged.tenant_id), str(forged.request_id),
                     str(forged.correlation_id)),
                )


# --- FORCE, and the proof that it is load-bearing ---------------------------

def test_forced_row_security_binds_the_table_owner(admin_connect, worker_exchange,
                                                   tenant, other_tenant):
    """``ENABLE`` alone leaves the owner exempt; ``FORCE`` is what closes it.

    The mutation is the test. Without dropping ``FORCE`` and observing the
    cross-tenant read succeed, this would assert only that the owner sees zero
    rows — which a broken grant would also produce.
    """

    request = _request(tenant)
    worker_exchange.submit(request)

    def owner_sees(count_tenant):
        with admin_connect() as conn:
            conn.execute(f"SET ROLE {OWNER_ROLE}")
            conn.execute("SELECT set_config('ugence.tenant_id', %s, false)",
                         (str(count_tenant),))
            return conn.execute(
                f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request").fetchone()[0]

    assert owner_sees(other_tenant) == 0, "FORCE should bind the owner"

    with admin_connect() as conn:
        conn.execute(
            f"ALTER TABLE {SCHEMA_NAME}.egress_request NO FORCE ROW LEVEL SECURITY")
        conn.commit()
    try:
        assert owner_sees(other_tenant) == 1, (
            "without FORCE the owner must see across the tenant boundary — if it "
            "does not, this test is not measuring FORCE at all")
    finally:
        with admin_connect() as conn:
            conn.execute(
                f"ALTER TABLE {SCHEMA_NAME}.egress_request FORCE ROW LEVEL SECURITY")
            conn.commit()

    assert owner_sees(other_tenant) == 0


# --- the asymmetric grants ---------------------------------------------------

def test_the_worker_cannot_disposition_a_request(database, worker_exchange, tenant):
    """Only the unit writes dispositions. A worker that could would be able to
    mark its own request COMPLETED without any exchange having happened."""

    request = _request(tenant)
    worker_exchange.submit(request)

    with psycopg.connect(database) as conn:
        conn.execute(f"SET ROLE {WORKER_ROLE}")
        conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                f"UPDATE {SCHEMA_NAME}.egress_request SET state = 'COMPLETED'")


def test_the_workers_write_is_scoped_to_columns_not_to_the_table(database,
                                                                 worker_exchange,
                                                                 tenant):
    """The worker must purge and acknowledge, and must not be able to do more.

    A table-level ``UPDATE`` would have granted both at once — and with it the
    ability to set ``state``, forge a ``terminal_at``, or rewrite the digest the
    tombstone rests on. The grant is by column so the database refuses the rest,
    and this asserts both halves: the permitted columns work, the others do not.
    """

    request = _request(tenant)
    worker_exchange.submit(request)

    def as_worker(sql):
        with psycopg.connect(database, autocommit=True) as conn:
            conn.execute(f"SET ROLE {WORKER_ROLE}")
            conn.execute("SELECT set_config('ugence.tenant_id', %s, false)",
                         (str(tenant),))
            conn.execute(sql, (str(request.request_id),))

    # Permitted: the two columns a purge touches.
    as_worker(f"UPDATE {SCHEMA_NAME}.egress_request "
              f"SET minimized_context = NULL, content_purged_at = now() "
              f"WHERE request_id = %s")

    # Refused: everything else on the same table.
    for column, value in (
        ("state", "'COMPLETED'"),
        ("terminal_at", "now()"),
        ("request_digest", "repeat('f', 64)"),
        ("content_digest", "repeat('f', 64)"),
        ("authorized_model", "'something-else'"),
        ("reservation_id", "'rsv-someone-elses'"),
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_worker(f"UPDATE {SCHEMA_NAME}.egress_request "
                      f"SET {column} = {value} WHERE request_id = %s")


def test_the_worker_cannot_rewrite_an_outcome_the_unit_recorded(database,
                                                                worker_exchange,
                                                                unit_exchange, tenant):
    """The requester acknowledges and purges; it does not get to decide what came
    back. Otherwise the exchange records the requester's preferred answer."""

    from ugence_model_egress_unit import DeterministicFakeProvider, EgressUnit

    request = _request(tenant)
    worker_exchange.submit(request)
    EgressUnit(unit_exchange, DeterministicFakeProvider(), holder="unit-1"
               ).run_once(tenant, now=NOW)

    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute(f"SET ROLE {WORKER_ROLE}")
        conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
        for column, value in (
            ("outcome", "'REFUSED'"),
            ("adapter_id", "'not-the-one-that-answered'"),
            ("genuine_call", "true"),
            ("response_digest", "repeat('f', 64)"),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    f"UPDATE {SCHEMA_NAME}.egress_result SET {column} = {value} "
                    f"WHERE request_id = %s", (str(request.request_id),))


def test_the_unit_cannot_submit_a_request(database, tenant):
    """Nor can the unit invent work for itself and then answer it."""

    with psycopg.connect(database) as conn:
        conn.execute(f"SET ROLE {UNIT_ROLE}")
        conn.execute("SELECT set_config('ugence.tenant_id', %s, false)", (str(tenant),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                _RAW_INSERT, (str(tenant), str(uuid.uuid4()), str(uuid.uuid4())),
            )


def test_neither_application_role_can_alter_the_exchange(database, tenant):
    """The owner is NOLOGIN, so no credential reaches the role that could drop a
    policy. Both application roles are refused structurally."""

    for role in (WORKER_ROLE, UNIT_ROLE):
        with psycopg.connect(database) as conn:
            conn.execute(f"SET ROLE {role}")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    f"ALTER TABLE {SCHEMA_NAME}.egress_request "
                    f"DISABLE ROW LEVEL SECURITY")


def test_the_exchange_tables_are_owned_by_the_non_login_role(database):
    """Ownership is asserted directly, because it is easy to lose by accident.

    ``CREATE SCHEMA ... AUTHORIZATION`` sets the *schema's* owner and nothing
    else — tables created inside it belong to whoever ran the statement. Without
    the migration's explicit ``SET ROLE``, the migrating superuser owned these
    tables, ``FORCE ROW LEVEL SECURITY`` bound a role nobody used, and "the owner
    cannot log in" was a true statement about a role that owned nothing. This
    test is what caught that.
    """

    with psycopg.connect(database) as conn:
        owners = dict(conn.execute(
            "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = %s",
            (SCHEMA_NAME,),
        ).fetchall())

    assert owners == {
        "egress_request": OWNER_ROLE,
        "egress_result": OWNER_ROLE,
    }, owners


def test_the_owner_role_cannot_log_in(database):
    """A role nobody can authenticate as cannot be phished, leaked or reused."""

    with psycopg.connect(database) as conn:
        canlogin = conn.execute(
            "SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (OWNER_ROLE,)
        ).fetchone()[0]
    assert canlogin is False


# --- the transaction-scoped setting -----------------------------------------

def test_tenant_identity_does_not_survive_the_transaction(worker_exchange, tenant):
    """``SET LOCAL`` semantics, asserted rather than assumed.

    If the exchange used a plain ``SET``, the identity would outlive the
    transaction and the next borrower of a pooled connection would inherit it —
    a cross-tenant read that no policy can catch, because the session genuinely
    *is* that tenant by then.
    """

    request = _request(tenant)
    worker_exchange.submit(request)

    with worker_exchange._connect() as conn:
        with conn.transaction():
            worker_exchange._scoped(conn, tenant)
            assert conn.execute(
                "SELECT current_setting('ugence.tenant_id')").fetchone()[0] == str(tenant)
            assert conn.execute(
                f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request"
            ).fetchone()[0] == 1

        # Outside that transaction the identity is gone. This is the realistic
        # pooled-connection case, and the one the plain ``SET`` form would get
        # wrong: the read must fail rather than return the previous tenant's rows
        # or an empty result.
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.egress_request").fetchone()


def test_a_connection_already_in_a_transaction_is_refused(database, tenant):
    """The savepoint case, refused rather than degraded.

    ``SET LOCAL`` binds to the enclosing *transaction*. Hand the exchange a
    connection that already has one open and ``conn.transaction()`` gives a
    savepoint instead — the identity then survives the savepoint's release and
    stays live for whatever the next caller does. Nothing fails; a later read
    just quietly belongs to the wrong tenant.
    """

    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {WORKER_ROLE}")
    conn.autocommit = False
    conn.execute("SELECT 1")  # opens the implicit transaction
    try:
        exchange = Exchange(lambda: conn)
        with pytest.raises(UnscopableConnection, match="not IDLE"):
            exchange.read_request(tenant, uuid.uuid4())
    finally:
        conn.close()


def test_the_leak_this_refusal_prevents_is_real(database, tenant, other_tenant):
    """Without the guard, the identity outlives the savepoint. Measured.

    This asserts the *mechanism*, not the guard: it reaches past ``Exchange`` and
    reproduces the raw behaviour. Without it, the refusal above would be a rule
    with no demonstrated failure behind it.
    """

    conn = psycopg.connect(database, autocommit=True)
    conn.execute(f"SET ROLE {WORKER_ROLE}")
    conn.autocommit = False
    try:
        conn.execute("SELECT 1")  # implicit transaction: everything below nests
        with conn.transaction():
            conn.execute("SELECT set_config('ugence.tenant_id', %s, true)",
                         (str(tenant),))
        leaked = conn.execute("SELECT current_setting('ugence.tenant_id')").fetchone()[0]
        assert leaked == str(tenant), (
            "if this no longer leaks, PostgreSQL's SET LOCAL scoping changed and "
            "the exchange's IDLE requirement can be revisited")
    finally:
        conn.close()
