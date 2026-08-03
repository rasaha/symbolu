"""Deterministic selection policy — OPTIMIZATION only, never safety.

The policy decides the *order* in which already-eligible (unprotected, non-duplicate)
units are considered for extractive removal, and when a token budget is reached. It
can NEVER remove protection, bypass the oracle, change the equivalence requirement,
or turn a failed check into success — those are safety concerns owned by
:mod:`ugence_context_minimization.oracle` and the protected-span invariant.

Identical input + policy + oracle evaluations ⇒ identical output. The policy is
versioned and fingerprinted so a change is visible in every result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional

from .protocols import TokenCounter

# Default structural prior for removal ordering: lower rank ⇒ considered for removal
# first. No query is available to the neutral core, so this is a source-type prior:
# pure filler and transient log/chat spans go before durable facts. Callers with a
# different corpus can supply their own priority map.
_DEFAULT_SOURCE_PRIORITY: Mapping[str, int] = {
    "log_event": 0,
    "chat_turn": 1,
    "sentence": 2,
    "clause": 3,
    "retrieved_passage": 3,
    "list_item": 3,
    "state_fact": 4,
}
_DEFAULT_FILLER_HINTS: tuple[str, ...] = (
    "weekly", "sprint", "historical", "log:", "previously", "earlier",
    "planning", "on-call", "maintenance window",
)
_DEFAULT_UNKNOWN_RANK = 5


@dataclass(frozen=True)
class MinimizationPolicy:
    """A frozen, fingerprintable extractive-ordering policy."""

    source_type_priority: Mapping[str, int] = field(
        default_factory=lambda: dict(_DEFAULT_SOURCE_PRIORITY)
    )
    filler_hints: tuple[str, ...] = _DEFAULT_FILLER_HINTS
    unknown_rank: int = _DEFAULT_UNKNOWN_RANK
    version: str = "cm-policy/1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_type_priority",
            MappingProxyType({str(k): int(v) for k, v in self.source_type_priority.items()}),
        )
        object.__setattr__(self, "filler_hints", tuple(self.filler_hints))

    def removal_key(self, unit, counter: Optional[TokenCounter]) -> tuple:
        """Sort key for removal ordering (smaller ⇒ removed earlier).

        Deterministic tuple: (filler-hint first, source-type rank, larger spans
        first to reach a budget faster, then unit id as the final tie-break so the
        order is total and stable).
        """
        base = self.source_type_priority.get(unit.source_type, self.unknown_rank)
        text = (unit.text or "").lower()
        hint = -1 if any(w in text for w in self.filler_hints) else 0
        return (hint, base, -unit.counted_tokens(counter), unit.id)

    def fingerprint(self) -> str:
        payload = {
            "version": self.version,
            "source_type_priority": dict(sorted(self.source_type_priority.items())),
            "filler_hints": list(self.filler_hints),
            "unknown_rank": self.unknown_rank,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(b"ugence-cm-policy/1\x00" + blob.encode("utf-8")).hexdigest()
        return f"{self.version}:{digest[:16]}"


DEFAULT_POLICY = MinimizationPolicy()
