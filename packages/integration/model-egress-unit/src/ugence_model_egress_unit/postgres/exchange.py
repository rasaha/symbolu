"""The exchange itself: submit, claim, record, acknowledge, purge.

Transaction boundaries, stated once
-----------------------------------
Every operation runs inside one transaction and sets the tenant identity with
``SET LOCAL``. ``SET LOCAL`` — never plain ``SET`` — because a plain ``SET``
outlives the transaction on a pooled connection, and the next borrower of that
connection would inherit the previous caller's tenant identity. That is a
cross-tenant read that no policy can catch, because as far as PostgreSQL is
concerned the session really is that tenant. The transaction-scoped form makes
the identity expire with the work it was established for.

The application checks the tenant too, on every row it reads back. Row-level
security is the boundary that holds when the application is wrong; the
application check is the one that holds if a policy is ever dropped, disabled or
mis-granted. Neither is redundant: they fail independently, which is the only
reason to have two.

Claiming is ``FOR UPDATE SKIP LOCKED``
--------------------------------------
Two units polling the same queue must not both claim one request. ``SKIP LOCKED``
lets each take a different row instead of serializing behind the same one, and
the lease it writes is what the reconciler later expires. A claim and its lease
are written in the same transaction, so there is no window in which a row is
claimed but unleased.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID

from psycopg.pq import TransactionStatus

from ..errors import (
    ExchangeError,
    RequestNotClaimable,
    ResultNotAcknowledgeable,
    TenantMismatch,
    UnscopableConnection,
)
from ..records import (
    EgressRequest,
    EgressResult,
    RefusalReason,
    RequestState,
    ResultOutcome,
)
from .schema import SCHEMA_NAME, TENANT_SETTING

__all__ = [
    "ExchangeError",
    "UnscopableConnection",
    "TenantMismatch",
    "RequestNotClaimable",
    "ResultNotAcknowledgeable",
    "ClaimedRequest",
    "Exchange",
]


@dataclass(frozen=True)
class ClaimedRequest:
    """A request the caller now holds a lease on, with its content."""

    request: EgressRequest
    lease_holder: str
    lease_expires_at: datetime


def _uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


class Exchange:
    """Tenant-scoped access to the egress exchange.

    ``connect`` is a zero-argument callable returning a new psycopg connection —
    injected rather than constructed here so a caller chooses the pool, and so
    the worker and the unit can connect as different database roles against the
    same exchange.
    """

    def __init__(self, connect) -> None:
        self._connect = connect

    # -- transaction boundary -------------------------------------------------

    @staticmethod
    def require_scopable(conn) -> None:
        """Refuse a connection that is already inside a transaction.

        See :class:`UnscopableConnection`. This is checked rather than documented
        because the degradation is silent: everything keeps working, and the only
        symptom is that a later caller reads another tenant's rows.
        """

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
        """Establish tenant identity for the enclosing transaction only.

        ``SET LOCAL`` reverts at commit or rollback — provided the enclosing
        transaction is a real one. :meth:`require_scopable` is what guarantees
        that; see the module docstring for why the unscoped form would be a
        cross-tenant leak rather than a style preference.
        """

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT set_config('{TENANT_SETTING}', %s, true)", (str(tenant_id),))

    def _check_tenant(self, rows: Sequence, index: int, tenant_id: UUID) -> None:
        for row in rows:
            if _uuid(row[index]) != tenant_id:
                raise TenantMismatch(
                    f"row carries tenant {row[index]} while the caller scoped to "
                    f"{tenant_id}. Row-level security should have made this "
                    f"unreachable, so the transaction is abandoned rather than "
                    f"trusted.")

    # -- worker side ----------------------------------------------------------

    def submit(self, request: EgressRequest) -> str:
        """Record a pending request. Returns its request digest."""

        digest = request.digest()
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, request.tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.egress_request
                            (request_id, tenant_id, submitted_at, state, model_id,
                             purpose, parameters, content, content_sha256,
                             request_digest)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            str(request.request_id),
                            str(request.tenant_id),
                            request.submitted_at,
                            RequestState.PENDING.value,
                            request.model_id,
                            request.purpose,
                            json.dumps(dict(request.parameters), sort_keys=True),
                            request.content,
                            request.content_sha256,
                            digest,
                        ),
                    )
        return digest

    def read_result(self, tenant_id: UUID, request_id: UUID) -> Optional[dict]:
        """The recorded result for a request, or ``None`` if there is not one yet."""

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT request_id, tenant_id, recorded_at, outcome,
                                   provider_id, refusal_reason, content,
                                   content_sha256, response_digest,
                                   acknowledged_at, content_purged_at
                            FROM {SCHEMA_NAME}.egress_result
                            WHERE request_id = %s""",
                        (str(request_id),),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 1, tenant_id)
        row = rows[0]
        return {
            "request_id": _uuid(row[0]),
            "tenant_id": _uuid(row[1]),
            "recorded_at": row[2],
            "outcome": ResultOutcome(row[3]),
            "provider_id": row[4],
            "refusal_reason": RefusalReason(row[5]) if row[5] else None,
            "content": row[6],
            "content_sha256": row[7],
            "response_digest": row[8],
            "acknowledged_at": row[9],
            "content_purged_at": row[10],
        }

    def acknowledge(self, tenant_id: UUID, request_id: UUID, *, at: datetime) -> None:
        """Record that the requester has read the result.

        Purge is gated on this. Without it, a sweep would be free to destroy an
        answer before anybody had seen it — and the tombstone would be indis-
        tinguishable from one left after a normal read.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_result
                            SET acknowledged_at = %s
                            WHERE request_id = %s AND acknowledged_at IS NULL
                            RETURNING tenant_id""",
                        (at, str(request_id)),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        raise ResultNotAcknowledgeable(
                            f"no unacknowledged result for {request_id}: it is "
                            f"either absent or already acknowledged")
                    self._check_tenant(rows, 0, tenant_id)

    # -- unit side ------------------------------------------------------------

    def claim(
        self,
        tenant_id: UUID,
        *,
        holder: str,
        now: datetime,
        lease: timedelta,
    ) -> Optional[ClaimedRequest]:
        """Take a lease on the oldest pending request, or ``None`` if there is none.

        ``FOR UPDATE SKIP LOCKED`` so concurrent units take different rows rather
        than queueing behind one another.
        """

        expires_at = now + lease
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request AS r
                            SET state = %s, lease_holder = %s, lease_expires_at = %s
                            WHERE r.request_id = (
                                SELECT request_id FROM {SCHEMA_NAME}.egress_request
                                WHERE state = %s
                                ORDER BY submitted_at
                                FOR UPDATE SKIP LOCKED
                                LIMIT 1)
                            RETURNING r.request_id, r.tenant_id, r.submitted_at,
                                      r.model_id, r.purpose, r.parameters, r.content,
                                      r.content_sha256""",
                        (
                            RequestState.LEASED.value,
                            holder,
                            expires_at,
                            RequestState.PENDING.value,
                        ),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 1, tenant_id)
        row = rows[0]
        return ClaimedRequest(
            request=EgressRequest(
                request_id=_uuid(row[0]),
                tenant_id=_uuid(row[1]),
                submitted_at=row[2],
                model_id=row[3],
                purpose=row[4],
                content=row[6],
                content_sha256=row[7],
                parameters=row[5] or {},
            ),
            lease_holder=holder,
            lease_expires_at=expires_at,
        )

    def record_result(
        self,
        result: EgressResult,
        *,
        expect_states: Sequence[RequestState] = (RequestState.LEASED,),
    ) -> str:
        """Write the result and move the request to its terminal state.

        Both halves in one transaction: a result without a terminal request would
        leave a row the reconciler would later expire into ``OUTCOME_UNKNOWN``,
        overwriting an outcome that was in fact known.
        """

        digest = result.digest()
        terminal = {
            ResultOutcome.ANSWERED: RequestState.COMPLETED,
            ResultOutcome.REFUSED: RequestState.REFUSED,
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
                            WHERE request_id = %s AND state = ANY(%s)
                            RETURNING tenant_id""",
                        (
                            terminal.value,
                            result.recorded_at,
                            str(result.request_id),
                            [s.value for s in expect_states],
                        ),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        raise RequestNotClaimable(
                            f"request {result.request_id} is not in "
                            f"{[s.value for s in expect_states]}, so a result "
                            f"cannot be recorded against it")
                    self._check_tenant(rows, 0, result.tenant_id)

                    cur.execute(
                        f"""INSERT INTO {SCHEMA_NAME}.egress_result
                            (request_id, tenant_id, recorded_at, outcome, provider_id,
                             refusal_reason, content, content_sha256, response_digest)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            str(result.request_id),
                            str(result.tenant_id),
                            result.recorded_at,
                            result.outcome.value,
                            result.provider_id,
                            result.refusal_reason.value if result.refusal_reason else None,
                            result.content,
                            result.content_sha256,
                            digest,
                        ),
                    )
        return digest

    # -- purge ----------------------------------------------------------------

    def purge_content(self, tenant_id: UUID, request_id: UUID, *, at: datetime) -> bool:
        """Destroy the content on both sides, leaving a digest-only tombstone.

        Refuses unless the result has been acknowledged: purging an answer nobody
        read destroys it rather than retiring it.

        What survives is deliberate. ``content_sha256`` and the request and
        response digests stay, so the row can still answer "was it this?" for a
        reader holding a candidate — and cannot answer "what was it?" for anyone.
        Every other field survives too, which is what keeps the request digest
        recomputable from the tombstone: a purge that removed a digested field
        would leave a digest nobody could check.
        """

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_result
                            SET content = NULL, content_purged_at = %s
                            WHERE request_id = %s
                              AND acknowledged_at IS NOT NULL
                              AND content_purged_at IS NULL
                            RETURNING tenant_id""",
                        (at, str(request_id)),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        return False
                    self._check_tenant(rows, 0, tenant_id)

                    cur.execute(
                        f"""UPDATE {SCHEMA_NAME}.egress_request
                            SET content = NULL, content_purged_at = %s
                            WHERE request_id = %s AND content_purged_at IS NULL
                            RETURNING tenant_id""",
                        (at, str(request_id)),
                    )
                    self._check_tenant(cur.fetchall(), 0, tenant_id)
        return True

    # -- reads used by the reconciler and the tests ---------------------------

    def read_request(self, tenant_id: UUID, request_id: UUID) -> Optional[dict]:
        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT request_id, tenant_id, submitted_at, state, model_id,
                                   purpose, parameters, content, content_sha256,
                                   request_digest, lease_holder, lease_expires_at,
                                   terminal_at, content_purged_at
                            FROM {SCHEMA_NAME}.egress_request WHERE request_id = %s""",
                        (str(request_id),),
                    )
                    rows = cur.fetchall()
        if not rows:
            return None
        self._check_tenant(rows, 1, tenant_id)
        row = rows[0]
        return {
            "request_id": _uuid(row[0]),
            "tenant_id": _uuid(row[1]),
            "submitted_at": row[2],
            "state": RequestState(row[3]),
            "model_id": row[4],
            "purpose": row[5],
            "parameters": row[6] or {},
            "content": row[7],
            "content_sha256": row[8],
            "request_digest": row[9],
            "lease_holder": row[10],
            "lease_expires_at": row[11],
            "terminal_at": row[12],
            "content_purged_at": row[13],
        }

    def expired_leases(self, tenant_id: UUID, *, now: datetime) -> list:
        """Requests whose lease has run out. The reconciler's input."""

        with self._connect() as conn:
            self.require_scopable(conn)
            with conn.transaction():
                self._scoped(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""SELECT request_id, tenant_id, lease_holder
                            FROM {SCHEMA_NAME}.egress_request
                            WHERE state = %s AND lease_expires_at <= %s
                            ORDER BY lease_expires_at""",
                        (RequestState.LEASED.value, now),
                    )
                    rows = cur.fetchall()
        self._check_tenant(rows, 1, tenant_id)
        return [(_uuid(r[0]), r[2]) for r in rows]
