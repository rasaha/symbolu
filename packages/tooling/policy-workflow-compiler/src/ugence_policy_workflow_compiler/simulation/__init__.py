"""Deterministic offline simulation of a compiled governed workflow (PWC-P3C).

It simulates; it never executes. There is no I/O, no provider import, no port and
no field in its output that could carry a grant — the four properties that keep a
simulator from becoming a runtime, each enforced by a test rather than a promise.
"""

from __future__ import annotations

from .models import NodeObservation, NodeOutcome, OracleComparison, SimulationRun
from .runner import simulate, simulate_all

__all__ = [
    "NodeOutcome",
    "NodeObservation",
    "OracleComparison",
    "SimulationRun",
    "simulate",
    "simulate_all",
]
