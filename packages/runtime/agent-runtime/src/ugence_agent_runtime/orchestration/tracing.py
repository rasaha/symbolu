"""H22-C — the portfolio (orchestration-level) audit trace and its durable event store.

This trace answers a different question from the per-workflow runtime trace:

    runtime trace  → *what happened inside one workflow's execution?*
    portfolio trace → *why did the team coordinator make this orchestration decision?*

It is an append-only log ordered by a portfolio-level **logical sequence number** (1, 2, 3,
…), never by wall-clock — deterministic ordering comes from the sequence alone. Events
reference workflows and execution artifacts **by id / digest** (``instance_id``,
``execution_state_digest``, ``workflow_checkpoint_digest``); they never embed workflow
execution payload or Canonical Execution State, so the portfolio trace never duplicates the
runtime trace.

## Durability

`PortfolioTrace` is a thin stateful *writer/view*. When constructed with a
:class:`PortfolioEventStore` it appends every event to that durable, append-only, portfolio-
scoped store, so **pre-crash audit history survives recovery** — not just the last sequence
number. Without a store it degrades to an in-process log (only the checkpoint's sequence
anchor is then durable). The core ships only an in-memory reference store; a production
backend is supplied externally (no SQL/Redis/filesystem/cloud backend here).

The event store is **not** part of an atomic distributed transaction with the portfolio
checkpoint store: they are two independent stores. Recovery reconciles them deterministically
by continuing the sequence at ``max(checkpoint anchor, event-store last sequence) + 1`` — see
:mod:`.recovery` — which is crash-safe across both the "checkpoint saved, commit-event not yet
appended" and the "commit-event appended, then crash" windows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


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


class PortfolioTraceSequenceError(Exception):
    """Raised when an event would violate the append-only monotonic sequence contract."""


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

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioTraceEntry":
        return cls(
            portfolio_id=d["portfolio_id"],
            sequence=int(d["sequence"]),
            event_type=d["event_type"],
            detail=dict(d.get("detail", {})),
        )


@runtime_checkable
class PortfolioEventStore(Protocol):
    """Neutral, append-only, portfolio-scoped durable store for orchestration trace events.

    Records are immutable and ordered by a deterministic contiguous logical sequence
    (1, 2, 3, …). ``append`` must reject a duplicate or out-of-order sequence
    (:class:`PortfolioTraceSequenceError`); ``events`` returns history in sequence order;
    ``last_sequence`` returns the highest stored sequence (0 if none). The core ships only
    :class:`InMemoryPortfolioEventStore`; no SQL/Redis/filesystem/cloud backend is included."""

    def append(self, entry: PortfolioTraceEntry) -> None:
        ...

    def events(self, portfolio_id: str) -> List[PortfolioTraceEntry]:
        ...

    def last_sequence(self, portfolio_id: str) -> int:
        ...


class InMemoryPortfolioEventStore:
    """Deterministic, dependency-free append-only reference event store (NOT durable backend).

    Portfolio-scoped and append-only: it stores immutable serialized records and enforces a
    contiguous monotonic sequence per portfolio (the first event must be sequence 1, each
    subsequent event exactly one greater). A duplicate or out-of-order sequence is rejected
    fail-closed. History is never mutated in place."""

    def __init__(self) -> None:
        self._events: Dict[str, List[dict]] = {}

    def append(self, entry: PortfolioTraceEntry) -> None:
        history = self._events.setdefault(entry.portfolio_id, [])
        expected = (history[-1]["sequence"] + 1) if history else 1
        if entry.sequence != expected:
            raise PortfolioTraceSequenceError(
                f"non-contiguous portfolio event for {entry.portfolio_id!r}: got sequence "
                f"{entry.sequence}, expected {expected} (append-only, no gaps/duplicates)"
            )
        history.append(entry.to_dict())  # immutable serialized record

    def events(self, portfolio_id: str) -> List[PortfolioTraceEntry]:
        return [PortfolioTraceEntry.from_dict(d) for d in self._events.get(portfolio_id, [])]

    def last_sequence(self, portfolio_id: str) -> int:
        history = self._events.get(portfolio_id)
        return history[-1]["sequence"] if history else 0


class PortfolioTrace:
    """An append-only portfolio trace with a monotonic logical sequence — a thin writer/view.

    The sequence starts at 1 and increases by exactly 1 per event; history is never mutated.
    When bound to a :class:`PortfolioEventStore`, every event is also appended to that durable
    store, so :meth:`history` returns the full pre-crash audit history after recovery; without
    a store, :meth:`history` returns only this process's events. After recovery, :meth:`restore`
    re-seats the next sequence past both the checkpoint anchor and any durable events so the
    reconstructed trace never collides with or precedes a pre-crash event."""

    def __init__(
        self,
        portfolio_id: str,
        *,
        event_store: Optional[PortfolioEventStore] = None,
        start_sequence: int = 0,
    ) -> None:
        if not portfolio_id or not isinstance(portfolio_id, str):
            raise ValueError("PortfolioTrace.portfolio_id required")
        if start_sequence < 0:
            raise ValueError("start_sequence must be >= 0")
        self._portfolio_id = portfolio_id
        self._event_store = event_store
        self._entries: List[PortfolioTraceEntry] = []
        self._next = start_sequence + 1

    @property
    def portfolio_id(self) -> str:
        return self._portfolio_id

    @property
    def event_store(self) -> Optional[PortfolioEventStore]:
        return self._event_store

    @property
    def entries(self) -> Tuple[PortfolioTraceEntry, ...]:
        """Events appended by THIS process/session (in order)."""
        return tuple(self._entries)

    def history(self) -> Tuple[PortfolioTraceEntry, ...]:
        """Full durable history in sequence order when an event store is bound; otherwise this
        process's events. This is what preserves pre-crash audit history after recovery."""
        if self._event_store is not None:
            return tuple(self._event_store.events(self._portfolio_id))
        return tuple(self._entries)

    @property
    def last_sequence(self) -> int:
        """The highest sequence emitted so far (0 before the first event)."""
        return self._next - 1

    def emit(self, event_type: PortfolioEventType, **detail: Any) -> PortfolioTraceEntry:
        """Append one event and return it. The sequence is assigned here (never by the
        caller). When an event store is bound the event is appended durably first (fail-closed
        on any sequence violation), then to the in-process view."""
        if not isinstance(event_type, PortfolioEventType):
            raise TypeError("event_type must be a PortfolioEventType")
        entry = PortfolioTraceEntry(
            portfolio_id=self._portfolio_id,
            sequence=self._next,
            event_type=event_type.value,
            detail=dict(detail),
        )
        if self._event_store is not None:
            self._event_store.append(entry)  # durable, append-only, sequence-checked
        self._entries.append(entry)
        self._next += 1
        return entry

    @classmethod
    def restore(
        cls,
        portfolio_id: str,
        anchor_sequence: int,
        *,
        event_store: Optional[PortfolioEventStore] = None,
    ) -> "PortfolioTrace":
        """Rebuild a trace whose next event continues past both the checkpoint ``anchor_sequence``
        and any durable events already in ``event_store``.

        The next sequence is ``max(anchor_sequence, event_store.last_sequence(portfolio_id)) + 1``.
        This is crash-safe across both windows: (A) checkpoint saved but the
        ``PORTFOLIO_CHECKPOINT_COMMITTED`` event was not yet appended — the anchor and the
        store agree, no gap; and (B) the commit event WAS appended before the crash — the
        store's last sequence exceeds the anchor, so recovery continues *after* it and never
        reuses that sequence. With a bound store, pre-crash history is preserved (queryable via
        :meth:`history`); without one, only the anchor is available."""
        if anchor_sequence < 0:
            raise ValueError("anchor_sequence must be >= 0")
        last = anchor_sequence
        if event_store is not None:
            last = max(last, event_store.last_sequence(portfolio_id))
        return cls(portfolio_id, event_store=event_store, start_sequence=last)
