"""Minimal in-process metrics (counters + latency samples).

Tracks the SLO-relevant signals (spec §31): ActionGate decision counts and the
critical **unauthorized-action-escape** counter, which the conformance suite
asserts stays at zero. A production deployment swaps this for a real metrics
backend; the interface is intentionally tiny.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Metrics"]


@dataclass
class Metrics:
    counters: dict[str, int] = field(default_factory=dict)
    latency_ms: dict[str, list[float]] = field(default_factory=dict)

    def incr(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def observe_latency(self, name: str, millis: float) -> None:
        self.latency_ms.setdefault(name, []).append(millis)

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)
