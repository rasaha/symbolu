"""Deterministic identity + clock for fully reproducible pilot runs (Task 115).

The DGM services and execution adapter accept an ``id_factory`` and ``clock``.
Seeding them per scenario makes every generated id and timestamp a deterministic
function of the scenario id, so repeated runs produce byte-identical traces (not
just identical substantive outcomes). No wall-clock or random source is used.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def make_id_factory(seed: str):
    counters: dict[str, int] = {}

    def factory(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        digest = hashlib.sha256(f"{seed}:{prefix}:{counters[prefix]}".encode()).hexdigest()[:12]
        return f"{prefix}_{digest}"

    return factory


def make_clock(seed: str):
    # a fixed, seed-independent instant keeps expiry math deterministic; the seed
    # is accepted for symmetry and future per-scenario offsets.
    fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def clock() -> datetime:
        return fixed

    return clock
