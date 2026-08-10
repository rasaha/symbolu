"""H22-C — the portfolio (orchestration-level) audit trace.

This trace answers a different question from the per-workflow runtime trace:

    runtime trace  → *what happened inside one workflow's execution?*
    portfolio trace → *why did the team coordinator make this orchestration decision?*

It is a separate, append-only log ordered by a portfolio-level **logical sequence number**
(1, 2, 3, …), never by wall-clock — deterministic ordering comes from the sequence alone.
Events reference workflows and execution artifacts **by id / digest** (``instance_id``,
``execution_state_digest``, ``workflow_checkpoint_digest``); they never embed workflow
execution payload or Canonical Execution State, so the portfolio trace never duplicates the
runtime trace.

Trace history is audit data, distinct from the durable orchestration *checkpoint*: the
checkpoint stores only the latest sequence as an anchor (so a recovered portfolio keeps
issuing strictly increasing sequence numbers), while the full historical event list lives
here. Restoring the position after recovery is :meth:`PortfolioTrace.restore`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PortfolioEventType(str, Enum):
    """The minimal orchestration event vocabulary needed to reconstruct why the coordinator
    acted. Deliberately small — per-workflow execution detail stays in the runtime trace."""

    PORTFOLIO_CREATED = "PORTFOLIO_CREATED"
    WORKFLOW_REGISTERED = "WORKFLOW_REGISTERED"
    DEPENDENCY_ADDED = "DEPENDENCY_ADDED"
    #: One scheduling round granted a bounded quantum to a selected workflow.
    QUANTUM_GRANTED = "QUANTUM_GRANTED"
    #: A scheduling round found no eligible workflow (quiescent) — non-terminal work remains.
    NO_ELIGIBLE_WORKFLOW = "NO_ELIGIBLE_WORKFLOW"
    #: The portfolio observed a workflow's terminal failure and applied its failure policy.
    WORKFLOW_FAILURE_OBSERVED = "WORKFLOW_FAILURE_OBSERVED"
    #: An operator/application requested a cancellation with a given scope.
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    #: The portfolio cooperatively cancelled one workflow via the runtime cancellation API.
    WORKFLOW_CANCELLED_BY_PORTFOLIO = "WORKFLOW_CANCELLED_BY_PORTFOLIO"
    #: A durable portfolio checkpoint was committed (records its digest + trace anchor).
    PORTFOLIO_CHECKPOINT_COMMITTED = "PORTFOLIO_CHECKPOINT_COMMITTED"
    #: The portfolio was reconstructed from a durable checkpoint (no execution occurred).
    PORTFOLIO_RECOVERED = "PORTFOLIO_RECOVERED"
    #: The whole portfolio reached a terminal orchestration state.
    PORTFOLIO_CANCELLED = "PORTFOLIO_CANCELLED"
    PORTFOLIO_FAILED = "PORTFOLIO_FAILED"
    PORTFOLIO_COMPLETED = "PORTFOLIO_COMPLETED"


PORTFOLIO_EVENT_TYPES: Tuple[str, ...] = tuple(e.value for e in PortfolioEventType)


@dataclass(frozen=True)
class PortfolioTraceEntry:
    """One append-only, immutable orchestration event.

    ``sequence`` is the authoritative logical order (monotonic, gap-free per portfolio).
    ``detail`` carries structured references only (ids / digests / small scalars) — never an
    opaque mutable object or an execution payload."""

    portfolio_id: str
    sequence: int
    event_type: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "detail": dict(self.detail),
        }


class PortfolioTrace:
    """An append-only portfolio trace with a monotonic logical sequence.

    The sequence starts at 1 and increases by exactly 1 per event; history is never mutated
    (there is no update/delete). After recovery, :meth:`restore` re-seats the next sequence to
    ``anchor + 1`` so the reconstructed portfolio continues issuing strictly increasing
    numbers even though the pre-crash in-memory history is gone (only the anchor is durable)."""

    def __init__(self, portfolio_id: str) -> None:
        if not portfolio_id or not isinstance(portfolio_id, str):
            raise ValueError("PortfolioTrace.portfolio_id required")
        self._portfolio_id = portfolio_id
        self._entries: List[PortfolioTraceEntry] = []
        self._next = 1

    @property
    def portfolio_id(self) -> str:
        return self._portfolio_id

    @property
    def entries(self) -> Tuple[PortfolioTraceEntry, ...]:
        return tuple(self._entries)

    @property
    def last_sequence(self) -> int:
        """The highest sequence emitted so far (0 before the first event)."""
        return self._next - 1

    def emit(self, event_type: PortfolioEventType, **detail: Any) -> PortfolioTraceEntry:
        """Append one event and return it. The sequence is assigned here (never by the
        caller), so ordering is authoritative and deterministic."""
        if not isinstance(event_type, PortfolioEventType):
            raise TypeError("event_type must be a PortfolioEventType")
        entry = PortfolioTraceEntry(
            portfolio_id=self._portfolio_id,
            sequence=self._next,
            event_type=event_type.value,
            detail=dict(detail),
        )
        self._entries.append(entry)
        self._next += 1
        return entry

    @classmethod
    def restore(cls, portfolio_id: str, anchor_sequence: int) -> "PortfolioTrace":
        """Rebuild an empty trace whose next event continues at ``anchor_sequence + 1``.

        The historical entries are not restored (audit history is not carried in the
        checkpoint); only the sequence position is, so post-recovery events never collide with
        or precede pre-crash ones."""
        if anchor_sequence < 0:
            raise ValueError("anchor_sequence must be >= 0")
        t = cls(portfolio_id)
        t._next = anchor_sequence + 1
        return t
