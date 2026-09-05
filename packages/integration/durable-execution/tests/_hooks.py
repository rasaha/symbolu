"""Governance hooks used by the matrix, and the table they record into.

The crash rows compare what happened *before* a SIGKILL with what happens *after*
recovery in a different process, so a hook that only remembers in memory is useless to
them. These hooks persist every evaluation to Postgres on their own connection, which
also mirrors reality: a governance evaluator is a separate concern from the runtime's
transaction and its record must survive the runtime rolling back.

None of these hooks mints authority. The permissive one is a test hook and is labelled
as such wherever it is used, exactly as Agent Runtime labels its own
``AllowAllGovernanceHook`` ("UNSAFE explicit testing/simulation hook").
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

import sqlalchemy as sa

from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
)
from ugence_agent_runtime.models.proposal import TransitionProposal

EVAL_LOG_DDL = """
CREATE TABLE IF NOT EXISTS governance_evaluations (
    id           bigserial PRIMARY KEY,
    instance_id  text NOT NULL,
    task_id      text NOT NULL,
    fingerprint  text NOT NULL,
    disposition  text NOT NULL,
    process_tag  text NOT NULL
)
"""


class RecordingHook:
    """Records every evaluation durably, then returns a configured disposition.

    ``valid_until_offset`` (when set) is added to ``evaluation_time`` to produce the
    clearance's expiry, so a test can mint a clearance that is already expired, expires
    exactly now, or expires far in the future.
    """

    def __init__(
        self,
        url: str,
        *,
        disposition: GovernanceDisposition = GovernanceDisposition.CLEAR,
        process_tag: str = "p1",
        valid_until_offset: Optional[float] = None,
        valid_until_absolute: Optional[float] = None,
    ) -> None:
        self._engine = sa.create_engine(url)
        self._disposition = disposition
        self._tag = process_tag
        self._offset = valid_until_offset
        self._absolute = valid_until_absolute
        with self._engine.begin() as c:
            c.execute(sa.text(EVAL_LOG_DDL))

    def evaluate(
        self, proposal: TransitionProposal, evaluation_time: float
    ) -> GovernanceEvaluation:
        with self._engine.begin() as c:
            c.execute(
                sa.text(
                    "INSERT INTO governance_evaluations "
                    "(instance_id, task_id, fingerprint, disposition, process_tag) "
                    "VALUES (:i, :t, :f, :d, :p)"
                ),
                {
                    "i": proposal.instance_id,
                    "t": proposal.task_id,
                    "f": proposal.fingerprint,
                    "d": self._disposition.value,
                    "p": self._tag,
                },
            )
        valid_until = self._absolute
        if valid_until is None and self._offset is not None:
            valid_until = evaluation_time + self._offset
        return GovernanceEvaluation(
            disposition=self._disposition,
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=("MATRIX_TEST_HOOK",),
            evaluation_reference=f"matrix:{proposal.fingerprint[:12]}",
            correlation_reference=proposal.correlation_id,
            valid_until=valid_until,
        )


def evaluations(url: str, instance_id: str):
    """Every recorded evaluation for an instance, in insertion order."""
    engine = sa.create_engine(url)
    with engine.begin() as c:
        rows = c.execute(
            sa.text(
                "SELECT fingerprint, disposition, process_tag FROM governance_evaluations "
                "WHERE instance_id = :i ORDER BY id ASC"
            ),
            {"i": instance_id},
        ).all()
    return [tuple(r) for r in rows]


def provider_calls(url: str):
    """Every recorded provider invocation, in insertion order."""
    engine = sa.create_engine(url)
    with engine.begin() as c:
        rows = c.execute(
            sa.text("SELECT idempotency_key FROM provider_calls ORDER BY id ASC")
        ).all()
    return [r[0] for r in rows]


# --------------------------------------------------------------------------- #
# last-mile authority rechecks (ADR §6.5 / §8 row 6)
# --------------------------------------------------------------------------- #
def revoking_recheck(*_a: Any, **_k: Any) -> Tuple[bool, Tuple[str, ...]]:
    """Authority was revoked between CLEAR and the effect. Fail closed."""
    return False, ("ENVELOPE_REVOKED", "EPOCH_ADVANCED")


def raising_recheck(*_a: Any, **_k: Any):
    """A misbehaving recheck. Must be normalized to a fail-closed rejection, never a
    permit."""
    raise RuntimeError("recheck exploded")


def malformed_recheck(*_a: Any, **_k: Any):
    """Returns something that is not ``(bool, reasons)``. A truthy malformed result must
    never be mistaken for permission."""
    return "yes, definitely permitted"
