"""Telemetry + prospective RegistryUpdater (Phase 8, invariants 11/12).

Telemetry observes outcomes AFTER decisions. RegistryUpdater applies observations to a
registry version STRICTLY GREATER than the in-flight trace's pinned version, so feedback
can never affect the trace that produced it (no circularity). An attempt to write to the
current or a past version is rejected as RUNTIME.CIRCULAR_DEPENDENCY_DETECTED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control_plane.failure_codes import Failure


@dataclass
class Observation:
    trace_id: str
    target: str                       # e.g. provider/model
    outcome: str                      # ok | provider_failed | denied | rejected
    observed_at: float
    observed_cost_usd: float = 0.0
    observed_latency_ms: Optional[float] = None


@dataclass
class RegistryUpdater:
    """Prospective-only. `current_version` is the version pinned for in-flight traces."""
    current_version: str = "reg_v1"
    pending: List[Observation] = field(default_factory=list)

    def enqueue(self, obs: Observation, target_registry_version: str) -> Optional[Failure]:
        # target must be strictly future; equal/past => would rewrite the in-flight basis
        if not _is_future(target_registry_version, self.current_version):
            return Failure.CIRCULAR_DEPENDENCY_DETECTED
        self.pending.append(obs)
        return None


def _is_future(target: str, current: str) -> bool:
    def n(v: str) -> int:
        digits = "".join(ch for ch in v if ch.isdigit())
        return int(digits) if digits else 0
    return n(target) > n(current)


class Telemetry:
    def __init__(self, updater: Optional[RegistryUpdater] = None):
        self.updater = updater or RegistryUpdater()
        self.observations: List[Observation] = []

    def record_outcome(self, trace_id: str, target: str, outcome: str, now: float,
                       cost: float = 0.0, latency: Optional[float] = None) -> Observation:
        obs = Observation(trace_id, target, outcome, now, cost, latency)
        self.observations.append(obs)
        return obs

    def feed_forward(self, obs: Observation) -> Optional[Failure]:
        """Push an observation to a strictly-future registry version (invariant 12)."""
        nxt = _next_version(self.updater.current_version)
        return self.updater.enqueue(obs, nxt)


def _next_version(v: str) -> str:
    digits = "".join(ch for ch in v if ch.isdigit())
    prefix = v[: len(v) - len(digits)] if digits else v + "_v"
    return f"{prefix}{(int(digits) if digits else 0) + 1}"
