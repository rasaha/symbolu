"""Neutral, in-memory runtime counters derived from a trace.

Metrics are computed from the deterministic event stream, so they never read a
clock or perform I/O. They summarize coordination facts only.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict

from .tracing import RunTrace


def event_counts(trace: RunTrace) -> Dict[str, int]:
    return dict(Counter(trace.types()))
