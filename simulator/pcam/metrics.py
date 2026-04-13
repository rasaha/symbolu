"""
PCAM minimal metrics wrapper — Phase 1.

A tiny, dependency-free helper around ``KVCachePolicy.get_stats()``.
Lets a consumer take snapshots and compute deltas without pulling in
Prometheus, OpenTelemetry, or any framework-specific exporter.

Scope is intentionally narrow:

- ``PolicyMetrics(policy)`` wraps a live policy.
- ``snapshot()`` returns the current stats dict (a fresh copy).
- ``delta(prev)`` computes per-key numeric deltas vs a previous
  snapshot. Non-numeric or absent keys are silently dropped from the
  delta.

What this is NOT:

- Not an exporter — callers convert the dict to whatever format they
  need.
- Not a histogram — get_stats currently exposes counters and gauges
  only; histograms belong to a later phase.
- Not a sampling client — no decimation, no rate-limiting.

If you need any of those, build them on top of this. Do not extend
this module to host them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .kv_policy import KVCachePolicy


__all__ = ["PolicyMetrics"]


class PolicyMetrics:
    """
    Thin observability wrapper around ``KVCachePolicy.get_stats()``.

    Holds a reference to the wrapped policy and produces dict
    snapshots / deltas on demand. Does not modify policy state.
    """

    def __init__(self, policy: "KVCachePolicy") -> None:
        self._policy = policy

    def snapshot(self) -> Dict[str, Any]:
        """Return a fresh shallow copy of the policy's current stats."""
        return dict(self._policy.get_stats())

    def delta(self, prev: Dict[str, Any]) -> Dict[str, Any]:
        """
        Per-key numeric delta of the current snapshot vs ``prev``.

        Only keys whose values are numeric in BOTH snapshots survive
        the delta — string fields, missing keys, and type mismatches
        are silently dropped. Negative deltas are returned as-is so
        callers can detect counter resets.
        """
        current = self.snapshot()
        out: Dict[str, Any] = {}
        for key, new_val in current.items():
            if key not in prev:
                continue
            old_val = prev[key]
            if isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                out[key] = new_val - old_val
        return out
