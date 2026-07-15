"""Lifecycle status constants + a helper to classify a terminal run status.

Re-exports the status constants from ``state`` so callers have one import surface.
"""
from __future__ import annotations
from .state import (RUNNING, COMPLETED, STOPPED, CANCELLED, AWAITING_HUMAN, BUDGET_STOP)

TERMINAL = frozenset({COMPLETED, STOPPED, CANCELLED, AWAITING_HUMAN, BUDGET_STOP})


def is_terminal(status: str) -> bool:
    return status in TERMINAL
