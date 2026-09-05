"""The three Agent Runtime persistence Protocols, backed by Postgres (ADR §5).

Agent Runtime defines the Protocols; this module implements them and adds nothing to
their surface. ``CheckpointStore.put``/``latest``, ``RuntimeEventStore.append``/``events``
and ``RuntimeStateStore.save``/``load`` are exactly as the runtime declares them.

**Every store writes on a session it is GIVEN, not one it opens.** The session provider
is a zero-argument callable returning the SQLAlchemy ``Session`` currently active for
the durable step (for DBOS, ``datasource.sql_session``). That indirection is the whole
mechanism behind OD-1: because the runtime's writes go through the same session DBOS
records its step output on, the step record and all three store writes commit in one
Postgres transaction, or none of them do.

A store that opened its own connection would silently break that property while still
passing every functional test, so the session provider is not optional and there is no
fallback path that opens one.
"""
from __future__ import annotations

import json
from typing import Any, Callable, List, Optional

import sqlalchemy as sa

from ..errors import CheckpointIntegrityError
from .schema import SCHEMA_NAME

__all__ = [
    "PostgresCheckpointStore",
    "PostgresRuntimeEventStore",
    "PostgresRuntimeStateStore",
    "SessionProvider",
]

SessionProvider = Callable[[], Any]


def _next_seq(session: Any, table: str, instance_id: str) -> int:
    row = session.execute(
        sa.text(
            f"SELECT COALESCE(MAX(seq), 0) + 1 FROM {SCHEMA_NAME}.{table} "
            "WHERE instance_id = :i"
        ),
        {"i": instance_id},
    ).scalar_one()
    return int(row)


def _verify(checkpoint: Any, instance_id: str, where: str) -> None:
    """Fail closed on any integrity failure. Never repair, never skip (ADR §8 row 7).

    Three checks, because the runtime's checkpoint carries three separable integrity
    claims: the base ``digest`` over coordination state, the ``extension_digest`` over
    the canonical-execution-state extension (which the base digest deliberately does
    not cover), and each persisted execution state's own binding to this checkpoint.
    """
    if not checkpoint.verify():
        raise CheckpointIntegrityError(
            f"{where}: checkpoint for {instance_id!r} failed base digest verification"
        )
    if checkpoint.has_extension_data() and not checkpoint.verify_extension():
        raise CheckpointIntegrityError(
            f"{where}: checkpoint for {instance_id!r} failed extension digest verification"
        )
    ok, reason = checkpoint.validate_execution_states()
    if not ok:
        raise CheckpointIntegrityError(
            f"{where}: checkpoint for {instance_id!r} failed execution-state validation: {reason}"
        )


class PostgresCheckpointStore:
    """Append-only checkpoint history. ``put`` inserts; it never updates."""

    def __init__(self, session_provider: SessionProvider) -> None:
        self._session = session_provider

    def put(self, checkpoint: Any) -> None:
        _verify(checkpoint, checkpoint.instance_id, "put")
        s = self._session()
        seq = _next_seq(s, "checkpoints", checkpoint.instance_id)
        s.execute(
            sa.text(
                f"INSERT INTO {SCHEMA_NAME}.checkpoints "
                "(instance_id, seq, digest, ext_digest, body) "
                "VALUES (:i, :s, :d, :e, CAST(:b AS jsonb))"
            ),
            {
                "i": checkpoint.instance_id,
                "s": seq,
                "d": checkpoint.digest,
                "e": checkpoint.extension_digest,
                "b": json.dumps(checkpoint.to_dict(), sort_keys=True),
            },
        )

    def latest(self, instance_id: str) -> Optional[Any]:
        from ugence_agent_runtime.persistence.checkpoints import Checkpoint

        row = self._session().execute(
            sa.text(
                f"SELECT body FROM {SCHEMA_NAME}.checkpoints WHERE instance_id = :i "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"i": instance_id},
        ).first()
        if row is None:
            return None
        ckpt = Checkpoint.from_dict(row[0])
        _verify(ckpt, instance_id, "latest")
        return ckpt

    def history(self, instance_id: str) -> List[Any]:
        """All checkpoints in ``seq`` order. Not part of the runtime Protocol; used by
        the matrix tests to assert the chain has no gap."""
        from ugence_agent_runtime.persistence.checkpoints import Checkpoint

        rows = self._session().execute(
            sa.text(
                f"SELECT body FROM {SCHEMA_NAME}.checkpoints WHERE instance_id = :i "
                "ORDER BY seq ASC"
            ),
            {"i": instance_id},
        ).all()
        return [Checkpoint.from_dict(r[0]) for r in rows]


class PostgresRuntimeEventStore:
    """Append-only runtime event log.

    ``attempt_token`` and ``engine_id`` are recorded so a duplicate delivery is
    *detectable*, and no read path branches on them so it is never *suppressed*. The
    log records what the runtime did, including that it re-did it.
    """

    def __init__(self, session_provider: SessionProvider, engine_id: str = "") -> None:
        self._session = session_provider
        self._engine_id = engine_id
        self.attempt_token: Optional[str] = None

    def append(self, instance_id: str, event: Any) -> None:
        s = self._session()
        seq = _next_seq(s, "runtime_events", instance_id)
        body = event.to_dict() if hasattr(event, "to_dict") else {"repr": repr(event)}
        s.execute(
            sa.text(
                f"INSERT INTO {SCHEMA_NAME}.runtime_events "
                "(instance_id, seq, event_type, body, attempt_token, engine_id) "
                "VALUES (:i, :s, :t, CAST(:b AS jsonb), :a, :e)"
            ),
            {
                "i": instance_id,
                "s": seq,
                "t": str(getattr(event, "event_type", "") or body.get("event_type", "")),
                "b": json.dumps(body, sort_keys=True, default=str),
                "a": self.attempt_token,
                "e": self._engine_id,
            },
        )

    def events(self, instance_id: str) -> List[Any]:
        from ugence_agent_runtime.models.events import RuntimeEvent

        rows = self._session().execute(
            sa.text(
                f"SELECT body FROM {SCHEMA_NAME}.runtime_events WHERE instance_id = :i "
                "ORDER BY seq ASC"
            ),
            {"i": instance_id},
        ).all()
        out: List[Any] = []
        for (body,) in rows:
            try:
                out.append(RuntimeEvent(**body))
            except Exception:
                # A stored event whose shape this build cannot construct is surfaced as
                # the raw mapping rather than dropped. Losing an audit event silently
                # would be worse than returning it untyped.
                out.append(body)
        return out

    def attempt_tokens(self, instance_id: str) -> List[Optional[str]]:
        """Distinct attempt tokens recorded against this instance, in first-seen order.
        Used by the matrix tests to assert a duplicate delivery was recorded."""
        rows = self._session().execute(
            sa.text(
                f"SELECT DISTINCT attempt_token FROM {SCHEMA_NAME}.runtime_events "
                "WHERE instance_id = :i AND attempt_token IS NOT NULL"
            ),
            {"i": instance_id},
        ).all()
        return [r[0] for r in rows]


class PostgresRuntimeStateStore:
    """The single resume point: one row per instance, updated in place.

    ``claim`` takes ``SELECT ... FOR UPDATE`` on that row. Holding it is what makes one
    worker per instance a database property rather than a convention.
    """

    def __init__(
        self,
        session_provider: SessionProvider,
        engine_id: str = "",
        definition_digest: str = "",
    ) -> None:
        self._session = session_provider
        self._engine_id = engine_id
        self._definition_digest = definition_digest

    def save(self, checkpoint: Any) -> None:
        _verify(checkpoint, checkpoint.instance_id, "save")
        self._session().execute(
            sa.text(
                f"INSERT INTO {SCHEMA_NAME}.runtime_state "
                "(instance_id, workflow_id, definition_digest, correlation_id, engine_id, "
                " checkpoint, updated_seq) "
                "VALUES (:i, :w, :d, :c, :e, CAST(:b AS jsonb), 1) "
                "ON CONFLICT (instance_id) DO UPDATE SET "
                "  checkpoint = EXCLUDED.checkpoint, "
                f"  updated_seq = {SCHEMA_NAME}.runtime_state.updated_seq + 1"
            ),
            {
                "i": checkpoint.instance_id,
                "w": checkpoint.workflow_id,
                "d": self._definition_digest,
                "c": checkpoint.correlation_id,
                "e": self._engine_id,
                "b": json.dumps(checkpoint.to_dict(), sort_keys=True),
            },
        )

    def load(self, instance_id: str) -> Optional[Any]:
        from ugence_agent_runtime.persistence.checkpoints import Checkpoint

        row = self._session().execute(
            sa.text(
                f"SELECT checkpoint FROM {SCHEMA_NAME}.runtime_state WHERE instance_id = :i"
            ),
            {"i": instance_id},
        ).first()
        if row is None:
            return None
        ckpt = Checkpoint.from_dict(row[0])
        _verify(ckpt, instance_id, "load")
        return ckpt

    def definition_digest(self, instance_id: str) -> Optional[str]:
        row = self._session().execute(
            sa.text(
                f"SELECT definition_digest FROM {SCHEMA_NAME}.runtime_state "
                "WHERE instance_id = :i"
            ),
            {"i": instance_id},
        ).first()
        return None if row is None else row[0]

    def claim(self, instance_id: str, worker_id: str, now: float) -> bool:
        """Take an exclusive, non-blocking claim on the instance. False if held.

        A transaction-scoped **advisory lock**, not ``SELECT ... FOR UPDATE NOWAIT``.
        Both refuse rather than queue — which is the property that matters, since a
        second concurrent delivery must be observably refused, not queued behind the
        first and then executed — but ``NOWAIT`` signals refusal by raising, and in
        PostgreSQL a raised error *aborts the whole transaction*. The loser's step would
        then fail on its next statement instead of returning a clean "did not progress".

        ``pg_try_advisory_xact_lock`` returns a boolean instead, and releases at the end
        of the transaction, which is exactly the intended scope: one worker drives this
        instance for the duration of one durable step.
        """
        s = self._session()
        acquired = s.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(hashtext(:i))"),
            {"i": instance_id},
        ).scalar_one()
        if not acquired:
            return False
        row = s.execute(
            sa.text(
                f"SELECT instance_id FROM {SCHEMA_NAME}.runtime_state WHERE instance_id = :i"
            ),
            {"i": instance_id},
        ).first()
        if row is None:
            return False
        s.execute(
            sa.text(
                f"INSERT INTO {SCHEMA_NAME}.worker_claims (instance_id, worker_id, claimed_at) "
                "VALUES (:i, :w, :t) "
                "ON CONFLICT (instance_id) DO UPDATE SET worker_id = EXCLUDED.worker_id, "
                "claimed_at = EXCLUDED.claimed_at"
            ),
            {"i": instance_id, "w": worker_id, "t": now},
        )
        return True
