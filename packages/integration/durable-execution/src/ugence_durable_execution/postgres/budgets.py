"""Budget ledger (ADR §8 row 8), on the shared Postgres per owner ruling OD-2.

Agent Runtime's own resource coordination is portfolio-local — its limitations
document says so in as many words — so concurrent instances contending for one budget
is precisely the case a single-process runtime cannot settle. This ledger settles it in
the database:

* the ceiling is a ``CHECK`` constraint, so over-consumption is refused by Postgres,
  not by in-process bookkeeping that a second worker cannot see;
* consumption is keyed by the runtime's **own** idempotency key, so a retry carrying
  the same key settles once however many times it is delivered.

The ledger reserves and records. It never grants, never invokes, and a refusal is a
refusal: the caller does not invoke.
"""
from __future__ import annotations

from typing import Any, Callable

import sqlalchemy as sa

from ..errors import BudgetExhausted
from .schema import SCHEMA_NAME

__all__ = ["PostgresBudgetLedger"]


class PostgresBudgetLedger:
    """Reserve-once budget consumption, shared across processes."""

    def __init__(self, session_provider: Callable[[], Any]) -> None:
        self._session = session_provider

    def define(self, budget_id: str, ceiling: int) -> None:
        self._session().execute(
            sa.text(
                f"INSERT INTO {SCHEMA_NAME}.budgets (budget_id, ceiling) VALUES (:b, :c) "
                "ON CONFLICT (budget_id) DO NOTHING"
            ),
            {"b": budget_id, "c": ceiling},
        )

    def reserve(
        self,
        *,
        budget_id: str,
        idempotency_key: str,
        instance_id: str,
        units: int = 1,
    ) -> bool:
        """Consume ``units`` once for ``idempotency_key``.

        Returns True when this call consumed, False when the same key had already
        consumed (an idempotent replay — not an error, and not a second consumption).
        Raises :class:`BudgetExhausted` when the ceiling would be exceeded; the caller
        must not invoke.

        The order matters: the consumption row is inserted first, so a duplicate key
        collides and short-circuits *before* the ceiling is touched. Incrementing first
        would let a replay consume a second unit against the ceiling and then discover
        the duplicate too late to undo it.
        """
        s = self._session()
        # Everything below runs under a SAVEPOINT so that a refusal leaves the
        # enclosing transaction usable: PostgreSQL aborts the whole transaction on any
        # error, so without the savepoint a refused reservation would also poison the
        # durable step that asked for it. Rolling the savepoint back also discards the
        # consumption row, so a refused key is not remembered as "already consumed".
        nested = s.begin_nested()
        try:
            inserted = s.execute(
                sa.text(
                    f"INSERT INTO {SCHEMA_NAME}.budget_consumption "
                    "(budget_id, idempotency_key, instance_id, units) "
                    "VALUES (:b, :k, :i, :u) "
                    "ON CONFLICT (budget_id, idempotency_key) DO NOTHING "
                    "RETURNING idempotency_key"
                ),
                {"b": budget_id, "k": idempotency_key, "i": instance_id, "u": units},
            ).first()
            if inserted is None:
                nested.commit()
                return False  # already consumed under this key; settle once, not twice
            # Conditional so the ordinary path never trips the CHECK constraint; the
            # constraint remains the backstop, and a violation is still caught below
            # inside the savepoint.
            updated = s.execute(
                sa.text(
                    f"UPDATE {SCHEMA_NAME}.budgets SET consumed = consumed + :u "
                    "WHERE budget_id = :b AND consumed + :u <= ceiling "
                    "RETURNING consumed"
                ),
                {"u": units, "b": budget_id},
            ).first()
            if updated is None:
                raise BudgetExhausted(
                    f"budget {budget_id!r} would exceed its ceiling; refusing to consume "
                    f"{units} for {idempotency_key!r} (instance {instance_id!r})"
                )
            s.flush()
        except sa.exc.IntegrityError as exc:
            nested.rollback()
            raise BudgetExhausted(
                f"budget {budget_id!r} would exceed its ceiling; refusing to consume "
                f"{units} for {idempotency_key!r} (instance {instance_id!r})"
            ) from exc
        except BudgetExhausted:
            nested.rollback()
            raise
        nested.commit()
        return True

    def consumed(self, budget_id: str) -> int:
        return int(
            self._session()
            .execute(
                sa.text(f"SELECT consumed FROM {SCHEMA_NAME}.budgets WHERE budget_id = :b"),
                {"b": budget_id},
            )
            .scalar_one()
        )
