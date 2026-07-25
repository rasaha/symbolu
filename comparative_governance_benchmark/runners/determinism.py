"""Deterministic identity + clock for reproducible benchmark runs.

Benchmark-owned (imports only the stdlib) so restricted strategy modules can use
it without pulling any provider into their import graph.
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
    fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def clock() -> datetime:
        return fixed

    return clock
