"""The exchange: submit, claim, dispatch, record, acknowledge, purge.

Transaction boundaries, stated once
-----------------------------------
Every operation runs inside one transaction and sets the tenant identity with
``SET LOCAL``. Never a plain ``SET``: that outlives the transaction on a pooled
connection and the next borrower inherits the previous caller's tenant identity —
a cross-tenant read no policy can catch, because the session really is that
tenant. ``SET LOCAL`` is scoped to a *transaction* and not to a savepoint, so
:meth:`Exchange.require_scopable` refuses a connection that arrives mid-transaction
rather than degrading quietly.

The application checks the tenant too, on every row it reads back. Row-level
security is the boundary that holds when the application is wrong; the application
check holds if a policy is ever dropped, disabled or mis-granted. The ruling of
2026-09-10 requires both, and they fail independently, which is the only reason to
have two.

Tenant identity is part of every operation, not a column beside them: it is in the
primary key, in the claim predicate, in result correlation, in acknowledgement and
in purging. There is no wildcard and no implicit tenant.

Claiming is ``FOR UPDATE SKIP LOCKED``
--------------------------------------
Two units polling the same queue must not both claim one request. ``SKIP LOCKED``
lets each take a different row instead of serializing behind the same one. A claim
and its lease are written in the same transaction, so there is no window in which a
row is claimed but unleased.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from ..errors import (
    ExchangeError,
    RequestNotClaimable,
    ResultNotAcknowledgeable,
    TenantMismatch,
    UnscopableConnection,
)
from ..records import (
    AuthorizationBinding,
    EgressRequest,
    EgressResult,
    MinimizedUnit,
    ProvenanceKind,
    RefusalReason,
    RequestState,
    ResultOutcome,
    purge_deadline,
)
from .schema import (AUTHORIZATION_TABLE, BUDGET_TABLE, CONSUMPTION_TABLE, RESERVATION_TABLE,
                     SCHEMA_NAME, TENANT_SETTING)

__all__ = [
    "ExchangeError",
    "UnscopableConnection",
    "TenantMismatch",
    "RequestNotClaimable",
    "ResultNotAcknowledgeable",
    "ClaimedRequest",
    "PurgeSweep",
    "Exchange",
]


@dataclass(frozen=True)
class ClaimedRequest:
    """A request the caller now holds a lease on, with its content."""

    request: EgressRequest
    lease_holder: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class PurgeSweep:
    """What one retention sweep destroyed, by artifact."""

    requests: Sequence[UUID]
    results: Sequence[UUID]

    @property
    def count(self) -> int:
        return len(self.requests) + len(self.results)


def _uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _units(raw) -> Optional[tuple]:
    if raw is None:
        return None
    return tuple(
        MinimizedUnit(unit_id=u["unit_id"], text=u["text"], token_count=u["token_count"])
        for u in raw
    )


class Exchange:
    """Tenant-scoped access to the egress exchange.

    ``connect`` is a zero-argument callable returning a new psycopg connection —
    injected so a caller chooses the pool, and so the worker and the unit connect
    as different database roles against the same exchange.
    """

    def __init__(self, connect) -> None:
        self._connect = connect

    # -- transaction boundary -------------------------------------------------

    @staticmethod
    def require_scopable(conn) -> None:
        """Refuse a connection that is already inside a transaction."""

        status = conn.info.transaction_status
        if status != TransactionStatus.IDLE:
            raise UnscopableConnection(
                f"connection is {TransactionStatus(status).name}, not IDLE. Tenant "
                f"identity is established with SET LOCAL, which is scoped to a "
                f"transaction and not to a savepoint; inside an open transaction it "
                f"would outlive this operation and leak to the next caller. Hand the "
                f"exchange a connection factory that returns fresh connections."
            )

    def _scoped(self, conn, tenant_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT set_config('{TENANT_SETTING}', %s, true)", (str(tenant_id),))

    def _check_tenant(self, rows: Sequence, index: int, tenant_id: UUID) -> None:
        for row in rows:
            if _uuid(row[index]) != tenant_id:
                raise TenantMismatch(
                    f"row carries a tenant the caller did not scope to "
                    f"({RefusalReason.TENANT_SCOPE_REFUSED.value}). Row-level "
                    f"security should have made this unreachable, so the transaction "
                    f"is abandoned rather than trusted.")

    # -- worker side ----------------------------------------------------------

    def submit(self, request: EgressRequest) -> str:
        """Record a pending authorized request. Returns its request digest."""

        digest = request.digest()
        a = request.authorization
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, request.tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.egress_request
                            (tenant_id, request_id, correlation_id,
                             exchange_schema_version, submitted_at, not_valid_after,
                             state, clearance_ref, clearance_digest,
                             authorized_vendor, authorized_model, policy_id,
                             reservation_id, parameters, minimized_context,
                             content_digest, content_created_at, request_digest)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            str(request.tenant_id), str(request.request_id),
                            str(request.correlation_id),
                            request.exchange_schema_version, request.submitted_at,
                            request.not_valid_after, RequestState.PENDING.value,
                            a.clearance_ref, a.clearance_digest, a.authorized_vendor,
                            a.authorized_model, a.policy_id, a.reservation_id,
                            Jsonb(dict(request.parameters)),
                            Jsonb([u.__dict__ for u in (request.minimized_context or [])]),
                            request.content_digest,
                            request.submitted_at,  # the context's own creation clock
                            digest,
                        ),
                    )
        return digest

    def read_result(self, tenant_id: UUID, request_id: UUID) -> Optional[dict]:
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT tenant_id, request_id, correlation_id, recorded_at,
                                   trust, outcome, refusal_reason, adapter_id,
                                   provenance_kind, genuine_call, provenance, payload,
                                   content_digest, content_created_at,
                                   content_purged_at, response_digest, acknowledged_at,
                                   reservation_released
                            FROM {SCHEMA_NAME}.egress_result
                            WHERE tenant_id = %s AND request_id = %s""",
                        (str(tenant_id), str(request_id)),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 0, tenant_id)
        r = rows[0]
        return {
            "tenant_id": _uuid(r[0]), "request_id": _uuid(r[1]),
            "correlation_id": _uuid(r[2]), "recorded_at": r[3], "trust": r[4],
            "outcome": ResultOutcome(r[5]),
            "refusal_reason": RefusalReason(r[6]) if r[6] else None,
            "adapter_id": r[7], "provenance_kind": ProvenanceKind(r[8]),
            "genuine_call": r[9], "provenance": r[10], "payload": r[11],
            "content_digest": r[12], "content_created_at": r[13],
            "content_purged_at": r[14], "response_digest": r[15],
            "acknowledged_at": r[16], "reservation_released": r[17],
        }

    def acknowledge(self, tenant_id: UUID, request_id: UUID, *, at: datetime) -> None:
        """Record that the requester has durably consumed the result.

        Starts the one-hour grace. It does not *grant* retention: the 24-hour hard
        deadline is unconditional, so a worker that never acknowledges only loses
        the earlier purge it would have had.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_result
                            SET acknowledged_at = %s
                            WHERE tenant_id = %s AND request_id = %s
                              AND acknowledged_at IS NULL
                            RETURNING tenant_id""",
                        (at, str(tenant_id), str(request_id)),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        raise ResultNotAcknowledgeable(
                            f"no unacknowledged result for {request_id}: it is either "
                            f"absent, another tenant's, or already acknowledged")
                    self._check_tenant(rows, 0, tenant_id)

    # -- unit side ------------------------------------------------------------

    def claim(self, tenant_id: UUID, *, holder: str, now: datetime,
              lease: timedelta) -> Optional[ClaimedRequest]:
        """Take a lease on the oldest claimable request for this tenant."""

        expires_at = now + lease
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request AS r
                            SET state = %s, lease_holder = %s, lease_expires_at = %s
                            WHERE (r.tenant_id, r.request_id) = (
                                SELECT tenant_id, request_id
                                FROM {SCHEMA_NAME}.egress_request
                                WHERE state = %s
                                ORDER BY submitted_at
                                FOR UPDATE SKIP LOCKED
                                LIMIT 1)
                            RETURNING r.tenant_id, r.request_id, r.correlation_id,
                                      r.submitted_at, r.not_valid_after,
                                      r.clearance_ref, r.clearance_digest,
                                      r.authorized_vendor, r.authorized_model,
                                      r.policy_id, r.reservation_id, r.parameters,
                                      r.minimized_context, r.content_digest,
                                      r.exchange_schema_version""",
                        (RequestState.LEASED.value, holder, expires_at,
                         RequestState.PENDING.value),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 0, tenant_id)
        r = rows[0]
        return ClaimedRequest(
            request=EgressRequest(
                request_id=_uuid(r[1]), tenant_id=_uuid(r[0]),
                correlation_id=_uuid(r[2]), submitted_at=r[3], not_valid_after=r[4],
                authorization=AuthorizationBinding(
                    clearance_ref=r[5], clearance_digest=r[6],
                    tenant_id=_uuid(r[0]), authorized_vendor=r[7],
                    authorized_model=r[8], policy_id=r[9], reservation_id=r[10]),
                minimized_context=_units(r[12]), content_digest=r[13],
                parameters=r[11] or {}, exchange_schema_version=r[14],
            ),
            lease_holder=holder, lease_expires_at=expires_at,
        )

    def mark_dispatched(self, tenant_id: UUID, request_id: UUID, *,
                        at: datetime) -> None:
        """Record that dispatch may have occurred, before it is attempted.

        Written *before* the call, not after: a crash between the write and the
        call must leave the row looking dispatched. The whole point of §3.5 is
        that after this instant nobody may assume the call did not happen, and a
        marker written afterwards would be missing in exactly the case it exists
        for.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request
                            SET dispatched_at = COALESCE(dispatched_at, %s)
                            WHERE tenant_id = %s AND request_id = %s AND state = %s
                            RETURNING tenant_id""",
                        (at, str(tenant_id), str(request_id),
                         RequestState.LEASED.value),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        raise RequestNotClaimable(
                            f"request {request_id} is not leased, so dispatch cannot "
                            f"be recorded against it")
                    self._check_tenant(rows, 0, tenant_id)

    def record_result(self, result: EgressResult, *,
                      expect_states: Sequence[RequestState] = (RequestState.LEASED,)
                      ) -> str:
        """Write the result and move the request to its terminal state.

        Both halves in one transaction: a result without a terminal request would
        leave a row the reconciler later expires into ``OUTCOME_UNKNOWN``,
        overwriting an outcome that was in fact known.
        """

        digest = result.digest()
        terminal = {
            ResultOutcome.ANSWERED: RequestState.COMPLETED,
            ResultOutcome.REFUSED: RequestState.REFUSED,
            ResultOutcome.FAILED: RequestState.FAILED,
            ResultOutcome.OUTCOME_UNKNOWN: RequestState.OUTCOME_UNKNOWN,
        }[result.outcome]

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, result.tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request
                            SET state = %s, terminal_at = %s,
                                lease_holder = NULL, lease_expires_at = NULL
                            WHERE tenant_id = %s AND request_id = %s
                              AND state = ANY(%s)
                            RETURNING tenant_id""",
                        (terminal.value, result.recorded_at, str(result.tenant_id),
                         str(result.request_id), [s.value for s in expect_states]),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        raise RequestNotClaimable(
                            f"request {result.request_id} is not in "
                            f"{[s.value for s in expect_states]}, so a result cannot "
                            f"be recorded against it")
                    self._check_tenant(rows, 0, result.tenant_id)

                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.egress_result
                            (tenant_id, request_id, correlation_id, recorded_at, trust,
                             outcome, refusal_reason, adapter_id, provenance_kind,
                             genuine_call, provenance, payload, content_digest,
                             content_created_at, response_digest,
                             custody_lease_id, custody_authority_id, authorization_consumption_id)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            str(result.tenant_id), str(result.request_id),
                            str(result.correlation_id), result.recorded_at,
                            result.trust, result.outcome.value,
                            result.refusal_reason.value if result.refusal_reason else None,
                            result.adapter_id, result.provenance_kind.value,
                            bool(result.provenance.get("genuine_call")),
                            Jsonb(dict(result.provenance)), result.payload,
                            result.content_digest,
                            result.recorded_at,  # the payload's own creation clock
                            digest,
                            result.custody_lease_id, result.custody_authority_id,
                            result.admission.consumption_id if result.admission is not None else None,
                        ),
                    )
        return digest

    # -- LP-5: the durable, non-compensatory reservation (migration 2) --------

    def reserve_commissioning_call(self, tenant_id: UUID, request_id: UUID, *,
                                   estimated_cents: int, now: datetime) -> int:
        """Reserve one genuine call before dispatch, or raise :class:`BudgetExhausted`.

        One transaction: the budget row is created if absent, the counters are
        advanced under the table's own CHECK ceilings and the concurrency ceiling,
        and the reservation row is written. A refusal leaves nothing behind. The
        counters never come down: the trigger refuses a decrement, the unit has no
        DELETE, and ``release_in_flight`` lowers ``in_flight`` alone. Returns the
        call number, 1 to 10.
        """

        from ..limits import COMMISSIONING_LIMITS, BudgetExhausted

        if not isinstance(estimated_cents, int) or isinstance(estimated_cents, bool) or estimated_cents < 0:
            raise BudgetExhausted("an estimate must be a non-negative integer of cents")
        limits = COMMISSIONING_LIMITS
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.{BUDGET_TABLE} (tenant_id) VALUES (%s)
                            ON CONFLICT (tenant_id) DO NOTHING""", (str(tenant_id),))
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.{BUDGET_TABLE}
                            SET calls_reserved = calls_reserved + 1,
                                cents_reserved = cents_reserved + %s,
                                in_flight = in_flight + 1
                            WHERE tenant_id = %s
                              AND calls_reserved < %s
                              AND cents_reserved + %s <= %s
                              AND in_flight < %s
                            RETURNING tenant_id, calls_reserved""",
                        (estimated_cents, str(tenant_id), limits.max_genuine_calls,
                         estimated_cents, limits.budget_usd_cents, limits.concurrency))
                    rows = cur.fetchall()
                    if not rows:
                        raise BudgetExhausted(
                            f"the tenant's commissioning budget refuses this reservation "
                            f"({limits.max_genuine_calls} calls, {limits.budget_usd_cents} cents, "
                            f"concurrency {limits.concurrency})")
                    self._check_tenant(rows, 0, tenant_id)
                    call_number = int(rows[0][1])
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.{RESERVATION_TABLE}
                            (tenant_id, request_id, reserved_at, estimated_cents, call_number)
                            VALUES (%s, %s, %s, %s, %s)""",
                        (str(tenant_id), str(request_id), now, estimated_cents, call_number))
        return call_number

    def release_in_flight(self, tenant_id: UUID) -> None:
        """The call ended, in any outcome. Nothing else is given back."""

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.{BUDGET_TABLE} SET in_flight = in_flight - 1
                            WHERE tenant_id = %s AND in_flight > 0 RETURNING tenant_id""",
                        (str(tenant_id),))
                    self._check_tenant(cur.fetchall(), 0, tenant_id)

    def commissioning_budget(self, tenant_id: UUID) -> Optional[dict]:
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT tenant_id, calls_reserved, cents_reserved, in_flight
                            FROM {SCHEMA_NAME}.{BUDGET_TABLE} WHERE tenant_id = %s""",
                        (str(tenant_id),))
                    rows = cur.fetchall()
                    if not rows:
                        return None
                    self._check_tenant(rows, 0, tenant_id)
                    row = rows[0]
                    return {"tenant_id": str(row[0]), "calls_reserved": row[1],
                            "cents_reserved": row[2], "in_flight": row[3]}

    # -- retention ------------------------------------------------------------

    def purge_due(self, tenant_id: UUID, *, now: datetime) -> PurgeSweep:
        """Destroy every artifact whose retention deadline has passed.

        Two independent clocks per artifact, earlier wins: one hour after the
        worker's durable acknowledgement, and 24 hours after **that artifact's own**
        creation. The request context and the response are governed separately, so
        a consumed response is purged on its own schedule rather than waiting on
        the exchange as a unit.

        The hard deadline is unconditional and evaluated in SQL rather than by a
        caller passing a cutoff: absence of an acknowledgement never extends
        content past 24 hours, which is exactly the case a caller-supplied cutoff
        would be most likely to get wrong.
        """

        grace = "INTERVAL '1 hour'"
        hard = "INTERVAL '24 hours'"
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_result AS t
                            SET payload = NULL, content_purged_at = %s
                            WHERE t.tenant_id = %s AND t.content_purged_at IS NULL
                              AND LEAST(
                                    COALESCE(t.acknowledged_at + {grace}, 'infinity'),
                                    t.content_created_at + {hard}) <= %s
                            RETURNING t.tenant_id, t.request_id""",
                        (now, str(tenant_id), now),
                    )
                    result_rows = cur.fetchall()
                    self._check_tenant(result_rows, 0, tenant_id)

                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request AS q
                            SET minimized_context = NULL, content_purged_at = %s
                            WHERE q.tenant_id = %s AND q.content_purged_at IS NULL
                              AND LEAST(
                                    COALESCE(
                                        (SELECT s.acknowledged_at + {grace}
                                         FROM {SCHEMA_NAME}.egress_result s
                                         WHERE s.tenant_id = q.tenant_id
                                           AND s.request_id = q.request_id),
                                        'infinity'),
                                    q.content_created_at + {hard}) <= %s
                            RETURNING q.tenant_id, q.request_id""",
                        (now, str(tenant_id), now),
                    )
                    request_rows = cur.fetchall()
                    self._check_tenant(request_rows, 0, tenant_id)

        return PurgeSweep(
            requests=[_uuid(r[1]) for r in request_rows],
            results=[_uuid(r[1]) for r in result_rows],
        )

    def tombstone(self, tenant_id: UUID, request_id: UUID) -> Optional[dict]:
        """Everything that survives a purge, and nothing that does not.

        The approved retention set: identities, digests, terminal outcome,
        acknowledgement and purge times, correlation identifier, clearance
        reference, reservation identity, vendor/model binding, and non-content
        attempt provenance. Content is absent by construction — this method
        selects no column that could carry it, so a tombstone cannot leak one by
        a caller forgetting to strip it.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT q.tenant_id, q.request_id, q.correlation_id,
                                   q.exchange_schema_version, q.state,
                                   q.clearance_ref, q.clearance_digest,
                                   q.authorized_vendor, q.authorized_model,
                                   q.policy_id, q.reservation_id,
                                   q.content_digest, q.request_digest,
                                   q.submitted_at, q.terminal_at,
                                   q.content_purged_at, q.dispatched_at,
                                   s.outcome, s.response_digest, s.content_digest,
                                   s.provenance_kind, s.provenance, s.genuine_call,
                                   s.acknowledged_at, s.content_purged_at,
                                   s.reservation_released
                            FROM {SCHEMA_NAME}.egress_request q
                            LEFT JOIN {SCHEMA_NAME}.egress_result s
                              ON s.tenant_id = q.tenant_id
                             AND s.request_id = q.request_id
                            WHERE q.tenant_id = %s AND q.request_id = %s""",
                        (str(tenant_id), str(request_id)),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 0, tenant_id)
        r = rows[0]
        return {
            "tenant_id": _uuid(r[0]), "request_id": _uuid(r[1]),
            "correlation_id": _uuid(r[2]), "exchange_schema_version": r[3],
            "state": RequestState(r[4]),
            "clearance_ref": r[5], "clearance_digest": r[6],
            "authorized_vendor": r[7], "authorized_model": r[8],
            "policy_id": r[9], "reservation_id": r[10],
            "request_content_digest": r[11], "request_digest": r[12],
            "submitted_at": r[13], "terminal_at": r[14],
            "request_content_purged_at": r[15], "dispatched_at": r[16],
            "outcome": ResultOutcome(r[17]) if r[17] else None,
            "response_digest": r[18], "response_content_digest": r[19],
            "provenance_kind": ProvenanceKind(r[20]) if r[20] else None,
            "provenance": r[21], "genuine_call": r[22],
            "acknowledged_at": r[23], "response_content_purged_at": r[24],
            "reservation_released": r[25],
        }

    # -- reads used by the reconciler and the tests ---------------------------

    def read_request(self, tenant_id: UUID, request_id: UUID) -> Optional[dict]:
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT tenant_id, request_id, correlation_id, submitted_at,
                                   not_valid_after, state, authorized_vendor,
                                   authorized_model, clearance_ref, clearance_digest,
                                   policy_id, reservation_id, parameters,
                                   minimized_context, content_digest,
                                   content_created_at, content_purged_at,
                                   request_digest, lease_holder, lease_expires_at,
                                   dispatched_at, terminal_at, exchange_schema_version
                            FROM {SCHEMA_NAME}.egress_request
                            WHERE tenant_id = %s AND request_id = %s""",
                        (str(tenant_id), str(request_id)),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 0, tenant_id)
        r = rows[0]
        return {
            "tenant_id": _uuid(r[0]), "request_id": _uuid(r[1]),
            "correlation_id": _uuid(r[2]), "submitted_at": r[3],
            "not_valid_after": r[4], "state": RequestState(r[5]),
            "authorized_vendor": r[6], "authorized_model": r[7],
            "clearance_ref": r[8], "clearance_digest": r[9], "policy_id": r[10],
            "reservation_id": r[11], "parameters": r[12] or {},
            "minimized_context": _units(r[13]), "content_digest": r[14],
            "content_created_at": r[15], "content_purged_at": r[16],
            "request_digest": r[17], "lease_holder": r[18],
            "lease_expires_at": r[19], "dispatched_at": r[20], "terminal_at": r[21],
            "exchange_schema_version": r[22],
        }

    def expired_leases(self, tenant_id: UUID, *, now: datetime) -> list:
        """Expired leases, and whether dispatch may already have occurred.

        The distinction is the whole of §4.3: before dispatch an expiry may return
        the request to the queue, after possible dispatch it may not.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT tenant_id, request_id, lease_holder, dispatched_at
                            FROM {SCHEMA_NAME}.egress_request
                            WHERE tenant_id = %s AND state = %s
                              AND lease_expires_at <= %s
                            ORDER BY lease_expires_at""",
                        (str(tenant_id), RequestState.LEASED.value, now),
                    )
                    rows = cur.fetchall()
        self._check_tenant(rows, 0, tenant_id)
        return [(_uuid(r[1]), r[2], r[3]) for r in rows]

    def release_undispatched_lease(self, tenant_id: UUID, request_id: UUID) -> bool:
        """Return an undispatched expired request to the queue.

        Guarded by ``dispatched_at IS NULL`` **in the UPDATE itself**, not by a
        prior read: if a dispatch marker lands between a reconciler's read and its
        write, this must not undo it. A request that may have been dispatched is
        never made claimable again.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request
                            SET state = %s, lease_holder = NULL,
                                lease_expires_at = NULL
                            WHERE tenant_id = %s AND request_id = %s
                              AND state = %s AND dispatched_at IS NULL
                            RETURNING tenant_id""",
                        (RequestState.PENDING.value, str(tenant_id), str(request_id),
                         RequestState.LEASED.value),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        return False
                    self._check_tenant(rows, 0, tenant_id)
        return True


class ExchangeAuthorizationLedger:
    """The durable :class:`~ugence_model_egress_unit.authorization.AuthorizationLedger`:
    nonce, consumption and LP-5 capacity in the exchange's own tables, one transaction
    per attempt, consumed before dispatch and never given back (migration 3)."""

    NON_PRODUCTION = False  # this is the real ledger; it is what the live verifier uses

    def __init__(self, exchange: "Exchange") -> None:
        self._exchange = exchange

    def capacity(self, *, tenant_id: UUID) -> tuple:
        from ..limits import COMMISSIONING_LIMITS
        budget = self._exchange.commissioning_budget(tenant_id) or {"calls_reserved": 0, "cents_reserved": 0}
        return (COMMISSIONING_LIMITS.max_genuine_calls - budget["calls_reserved"],
                COMMISSIONING_LIMITS.budget_usd_cents - budget["cents_reserved"])

    def consume(self, authorization, *, tenant_id: UUID, request_id: UUID, request_digest: str,
                estimated_cents: int, now: datetime) -> tuple:
        import psycopg
        from ..authorization import AuthorizationRefusal as R, AuthorizationRefused
        from ..limits import COMMISSIONING_LIMITS, BudgetExhausted

        digest = authorization.digest()
        ex = self._exchange
        with ex._connect() as conn:
            ex.require_scopable(conn)
            with conn.transaction():
                ex._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(f"SELECT authorization_digest FROM {SCHEMA_NAME}.{AUTHORIZATION_TABLE} WHERE nonce = %s",
                                (authorization.nonce,))
                    held = cur.fetchone()
                    if held is not None and held[0] != digest:
                        raise AuthorizationRefused(R.NONCE_REPLAYED, "this nonce already backs a different authorization")
                    if held is None:
                        cur.execute(
                            f"""INSERT INTO {SCHEMA_NAME}.{AUTHORIZATION_TABLE}
                                (nonce, authorization_digest, max_calls, calls_consumed, expires_at, first_consumed_at)
                                VALUES (%s, %s, %s, 0, %s, %s)""",
                            (authorization.nonce, digest, authorization.max_calls, authorization.expires_at, now))
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.{AUTHORIZATION_TABLE}
                            SET calls_consumed = calls_consumed + 1
                            WHERE nonce = %s AND authorization_digest = %s
                              AND calls_consumed < max_calls AND expires_at > %s
                            RETURNING calls_consumed""",
                        (authorization.nonce, digest, now))
                    row = cur.fetchone()
                    if row is None:
                        cur.execute(f"SELECT calls_consumed, max_calls, expires_at FROM {SCHEMA_NAME}.{AUTHORIZATION_TABLE} WHERE nonce = %s",
                                    (authorization.nonce,))
                        state = cur.fetchone()
                        if state is not None and state[2] <= now:
                            raise AuthorizationRefused(R.EXPIRED)
                        raise AuthorizationRefused(R.CALLS_EXHAUSTED, f"{authorization.max_calls} authorized calls consumed")
                    call_number = int(row[0])
                    try:
                        cur.execute(
                            f"""INSERT INTO {SCHEMA_NAME}.{CONSUMPTION_TABLE}
                                (tenant_id, authorization_digest, request_id, request_digest, call_number, consumed_at)
                                VALUES (%s, %s, %s, %s, %s, %s) RETURNING consumption_id""",
                            (str(tenant_id), digest, str(request_id), request_digest, call_number, now))
                    except psycopg.errors.UniqueViolation:
                        raise AuthorizationRefused(R.ALREADY_CONSUMED, "this request was already consumed under this authorization")
                    consumption_id = str(cur.fetchone()[0])
                    # LP-5's durable reservation, in the same transaction: a refusal here
                    # rolls the consumption back too, so nothing is consumed without capacity.
                    limits = COMMISSIONING_LIMITS
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.{BUDGET_TABLE} (tenant_id) VALUES (%s)
                            ON CONFLICT (tenant_id) DO NOTHING""", (str(tenant_id),))
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.{BUDGET_TABLE}
                            SET calls_reserved = calls_reserved + 1, cents_reserved = cents_reserved + %s,
                                in_flight = in_flight + 1
                            WHERE tenant_id = %s AND calls_reserved < %s AND cents_reserved + %s <= %s AND in_flight < %s
                            RETURNING calls_reserved""",
                        (estimated_cents, str(tenant_id), limits.max_genuine_calls, estimated_cents,
                         limits.budget_usd_cents, limits.concurrency))
                    reserved = cur.fetchone()
                    if reserved is None:
                        raise AuthorizationRefused(R.CAPACITY_EXHAUSTED, "the durable reservation ledger has no remaining capacity")
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.{RESERVATION_TABLE}
                            (tenant_id, request_id, reserved_at, estimated_cents, call_number)
                            VALUES (%s, %s, %s, %s, %s)""",
                        (str(tenant_id), str(request_id), now, estimated_cents, int(reserved[0])))
        return consumption_id, call_number

    def authorization_state(self, nonce: str) -> Optional[dict]:
        ex = self._exchange
        with ex._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT nonce, authorization_digest, max_calls, calls_consumed, expires_at FROM {SCHEMA_NAME}.{AUTHORIZATION_TABLE} WHERE nonce = %s", (nonce,))
                row = cur.fetchone()
        if row is None:
            return None
        return {"nonce": row[0], "authorization_digest": row[1], "max_calls": row[2], "calls_consumed": row[3], "expires_at": row[4]}

