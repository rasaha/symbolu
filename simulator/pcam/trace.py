"""
Offline PCAM trace replay (Phase 2).

A small primitive for driving a ``KVCachePolicy`` through a deterministic
sequence of events. Useful for:

- Reproducing a serving incident in dev
- Comparing the same trace under different config (parameter sweeps)
- Sanity-checking a new tier-hint threshold
- Hand-feeding the parity harness or future benchmarks with synthetic
  scenarios

This module is **not** a benchmark framework. It is intentionally
narrow: a small event schema, a single ``replay`` function, and a
result dataclass that captures the per-event outputs of the policy.
Any benchmark suite belongs to Phase 3 and should build on top of
this primitive rather than absorbing it.

Schema
------
A trace is a sequence of ``TraceEvent`` records. Each event has a
``kind`` (one of the ``EventKind`` enum values) and an ``args`` dict
that mirrors the corresponding ``KVCachePolicy`` method's keyword
arguments. Events are JSON-friendly: ``TraceEvent.from_dict`` builds
an event from a plain dict, so a trace can be loaded from a JSON file
without any custom serializer.

Supported event kinds
---------------------
- ``register_sequence`` — args: ``seq_id``
- ``set_phase`` — args: ``seq_id``, ``phase`` (``"PREFILL"`` or
  ``"DECODE"``, or an ``InferencePhase`` instance)
- ``ensure_block`` — args: ``block_id``, ``sequence_id``, ``positions``
- ``on_block_attention`` — args: ``block_id``, ``attention_sum``,
  ``sequence_id``
- ``select_victims`` — args: ``count``
- ``complete_sequence`` — args: ``seq_id``
- ``tier_hints`` — args: ``block_ids``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Sequence

from .kv_policy import InferencePhase, KVCachePolicy, TierHint


__all__ = ["EventKind", "TraceEvent", "ReplayResult", "replay"]


class EventKind(str, Enum):
    REGISTER_SEQUENCE = "register_sequence"
    SET_PHASE = "set_phase"
    ENSURE_BLOCK = "ensure_block"
    ON_BLOCK_ATTENTION = "on_block_attention"
    SELECT_VICTIMS = "select_victims"
    COMPLETE_SEQUENCE = "complete_sequence"
    TIER_HINTS = "tier_hints"


@dataclass
class TraceEvent:
    """A single PCAM-relevant event."""

    kind: EventKind
    args: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceEvent":
        """
        Build a ``TraceEvent`` from a plain dict (e.g. one element of a
        JSON-loaded trace). The dict must have a ``kind`` key whose
        value is a string matching an ``EventKind`` member; ``args`` is
        optional and defaults to an empty dict.
        """
        if "kind" not in data:
            raise TypeError("TraceEvent.from_dict: missing 'kind' key")
        return cls(kind=EventKind(data["kind"]), args=dict(data.get("args", {})))

    def to_dict(self) -> Dict[str, Any]:
        """Round-trips with ``from_dict``."""
        return {"kind": self.kind.value, "args": dict(self.args)}


@dataclass
class ReplayResult:
    """
    Structured result of a trace replay.

    - ``final_stats``: ``policy.get_stats()`` after the last event
    - ``victim_lists``: per ``select_victims`` event, the list of
      block IDs the policy returned (in order)
    - ``tier_hint_results``: per ``tier_hints`` event, the dict of
      ``{block_id: TierHint}`` the policy returned
    - ``completed_sequences``: per ``complete_sequence`` event, the
      list of block IDs that were freed
    - ``event_count``: number of events replayed
    """

    final_stats: Dict[str, Any]
    victim_lists: List[List[int]]
    tier_hint_results: List[Dict[int, TierHint]]
    completed_sequences: List[List[int]]
    event_count: int


def _coerce_phase(value: Any) -> InferencePhase:
    """Accept either an ``InferencePhase`` instance or its string name."""
    if isinstance(value, InferencePhase):
        return value
    if isinstance(value, str):
        try:
            return InferencePhase[value]
        except KeyError as exc:
            raise ValueError(
                f"unknown InferencePhase name: {value!r}"
            ) from exc
    raise TypeError(
        f"set_phase event 'phase' must be InferencePhase or str, got {type(value).__name__}"
    )


def replay(
    policy: KVCachePolicy,
    events: Sequence[TraceEvent],
) -> ReplayResult:
    """
    Drive a ``KVCachePolicy`` through ``events`` and capture the per-event
    outputs of ``select_victims``, ``tier_hints``, and ``complete_sequence``.

    The policy is mutated in place. The caller is responsible for passing
    a fresh policy if isolation is desired.

    Raises ``ValueError`` on an unknown ``EventKind`` so a malformed
    trace fails loudly instead of silently dropping events.
    """
    victim_lists: List[List[int]] = []
    tier_hint_results: List[Dict[int, TierHint]] = []
    completed: List[List[int]] = []

    for event in events:
        kind = event.kind
        args = event.args

        if kind is EventKind.REGISTER_SEQUENCE:
            policy.register_sequence(args["seq_id"])

        elif kind is EventKind.SET_PHASE:
            policy.set_phase(args["seq_id"], _coerce_phase(args["phase"]))

        elif kind is EventKind.ENSURE_BLOCK:
            policy.ensure_block(
                args["block_id"],
                args["sequence_id"],
                list(args["positions"]),
            )

        elif kind is EventKind.ON_BLOCK_ATTENTION:
            policy.on_block_attention(
                args["block_id"],
                float(args["attention_sum"]),
                args["sequence_id"],
            )

        elif kind is EventKind.SELECT_VICTIMS:
            victims = policy.select_victims(int(args["count"]))
            victim_lists.append(list(victims))

        elif kind is EventKind.COMPLETE_SEQUENCE:
            freed = policy.complete_sequence(args["seq_id"])
            completed.append(list(freed))

        elif kind is EventKind.TIER_HINTS:
            hints = policy.tier_hints(list(args["block_ids"]))
            tier_hint_results.append(hints)

        else:  # pragma: no cover — defensive, EventKind is closed
            raise ValueError(f"unknown event kind: {kind!r}")

    return ReplayResult(
        final_stats=policy.get_stats(),
        victim_lists=victim_lists,
        tier_hint_results=tier_hint_results,
        completed_sequences=completed,
        event_count=len(events),
    )
