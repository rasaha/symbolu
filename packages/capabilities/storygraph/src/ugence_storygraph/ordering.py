"""Ordering & clock-status model (§6).

Actor-supplied `timestamp` / `sequence_id` alone are not trusted to order events.
Each event may carry several ordering signals, resolved by a fixed deterministic
priority. When they disagree the analyzer surfaces the disagreement rather than
silently normalizing events into a convenient attack sequence.

Signals (any subset may be present):

* ``event_time``               — actor/source event time (epoch seconds)
* ``source_sequence``          — source-system monotonic sequence
* ``ingestion_time``           — analyzer ingestion counter (always present)
* ``receipt_sequence``         — ActionGate receipt sequence
* ``correlation_local_sequence`` — monotonic within a correlation
* ``clock_skew``               — declared/derived skew indicator

Pairwise resolution returns ``A_BEFORE_B`` / ``B_BEFORE_A`` / ``AMBIGUOUS`` /
``CONFLICTING``. An assembly-level status aggregates the pairwise results into
``ORDERED`` / ``PARTIALLY_ORDERED`` / ``AMBIGUOUS_ORDER`` / ``CONFLICTING_ORDER``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .timeutil import parse_epoch

# pairwise
A_BEFORE_B = "A_BEFORE_B"
B_BEFORE_A = "B_BEFORE_A"
AMBIGUOUS = "AMBIGUOUS"
CONFLICTING = "CONFLICTING"

# assembly-level
ORDERED = "ORDERED"
PARTIALLY_ORDERED = "PARTIALLY_ORDERED"
AMBIGUOUS_ORDER = "AMBIGUOUS_ORDER"
CONFLICTING_ORDER = "CONFLICTING_ORDER"


@dataclass(frozen=True)
class OrderSignals:
    correlation_id: str
    ingestion_time: int
    event_time: float | None = None
    source_sequence: int | None = None
    receipt_sequence: int | None = None
    correlation_local_sequence: int | None = None
    clock_skew: str = ""

    def to_dict(self) -> dict:
        return {
            "correlation_id": self.correlation_id,
            "ingestion_time": self.ingestion_time,
            "event_time": self.event_time,
            "source_sequence": self.source_sequence,
            "receipt_sequence": self.receipt_sequence,
            "correlation_local_sequence": self.correlation_local_sequence,
            "clock_skew": self.clock_skew,
        }


def extract_order_signals(event: dict, ingestion_time: int) -> OrderSignals:
    """Deterministically pull ordering signals from an event."""
    o = event.get("ordering", {}) or {}
    corr = str(event.get("correlation_id", ""))

    def _int(*keys):
        for k in keys:
            v = o.get(k, event.get(k))
            if v is not None:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return None
        return None

    et = parse_epoch(o.get("event_time") or event.get("timestamp") or event.get("at"))
    # a trailing integer in sequence_id is a weak correlation-local sequence
    cls = _int("correlation_local_sequence")
    if cls is None:
        seq = str(event.get("sequence_id", ""))
        digits = "".join(ch for ch in seq.rsplit(":", 1)[-1] if ch.isdigit())
        cls = int(digits) if digits else None
    return OrderSignals(
        correlation_id=corr,
        ingestion_time=ingestion_time,
        event_time=et,
        source_sequence=_int("source_sequence", "source_seq"),
        receipt_sequence=_int("receipt_sequence", "actiongate_receipt_sequence"),
        correlation_local_sequence=cls,
        clock_skew=str(o.get("clock_skew", event.get("clock_skew", ""))),
    )


def _cmp(a_val, b_val) -> int | None:
    if a_val is None or b_val is None:
        return None
    if a_val < b_val:
        return -1
    if a_val > b_val:
        return 1
    return 0


def resolve_pair(a: OrderSignals, b: OrderSignals) -> str:
    """Resolve the order of two events from their signals.

    Strong signals (source_sequence / correlation_local_sequence) are only
    comparable within the *same* correlation. Cross-correlation ordering relies on
    event_time / receipt_sequence. If a strong signal and a time signal disagree,
    the result is ``CONFLICTING`` (surfaced, not silently resolved).
    """
    same_corr = a.correlation_id and a.correlation_id == b.correlation_id
    votes: list[int] = []

    if same_corr:
        for attr in ("source_sequence", "correlation_local_sequence"):
            c = _cmp(getattr(a, attr), getattr(b, attr))
            if c is not None and c != 0:
                votes.append(c)
    c_time = _cmp(a.event_time, b.event_time)
    if c_time is not None and c_time != 0:
        votes.append(c_time)
    c_receipt = _cmp(a.receipt_sequence, b.receipt_sequence)
    if c_receipt is not None and c_receipt != 0:
        votes.append(c_receipt)

    if votes:
        if all(v < 0 for v in votes):
            return A_BEFORE_B
        if all(v > 0 for v in votes):
            return B_BEFORE_A
        return CONFLICTING  # strong signals disagree

    # no discriminating strong/time signal: fall back to ingestion order, but mark
    # ambiguous (the true source order is unknown).
    return AMBIGUOUS


def assembly_status(signals: list[OrderSignals]) -> str:
    """Aggregate pairwise resolutions over the contributing events."""
    if len(signals) <= 1:
        return ORDERED
    saw_conflict = False
    saw_ambiguous = False
    resolved = 0
    total = 0
    for i in range(len(signals)):
        for j in range(i + 1, len(signals)):
            total += 1
            r = resolve_pair(signals[i], signals[j])
            if r == CONFLICTING:
                saw_conflict = True
            elif r == AMBIGUOUS:
                saw_ambiguous = True
            else:
                resolved += 1
    if saw_conflict:
        return CONFLICTING_ORDER
    if saw_ambiguous and resolved == 0:
        return AMBIGUOUS_ORDER
    if saw_ambiguous:
        return PARTIALLY_ORDERED
    return ORDERED


def satisfies_strict_ordering(status: str, permit_ambiguous: bool) -> bool:
    """Whether a strict-ordering recipe may be treated as satisfied."""
    if status in (ORDERED, PARTIALLY_ORDERED):
        return True
    return permit_ambiguous
