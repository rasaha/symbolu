"""Trace sinks (human-readable + no-op). Never governance-bearing."""
from __future__ import annotations
from typing import List
from .trace import RunTrace


def format_trace(trace: RunTrace) -> str:
    lines = [f"run {trace.run_id}"]
    for e in trace.events:
        lines.append(f"  [{e.seq:02d}] {e.type} {e.detail}")
    return "\n".join(lines)
