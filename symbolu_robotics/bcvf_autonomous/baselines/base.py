"""Arbitrator protocol + result dataclass shared by every baseline.

An arbitrator consumes a ``(M, H, 3)`` predictor trajectory tensor
and produces a ``(H, 3)`` consensus trajectory + a ``(M,)``
per-predictor attribution score (higher = more suspicious).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

import numpy as np


@dataclass
class ArbitrationResult:
    """Output of one ``Arbitrator.arbitrate`` call."""

    consensus: np.ndarray            # (H, 3)
    attribution: np.ndarray          # (M,) higher = more suspicious
    per_tick_us: float = 0.0         # microseconds per tick (median)
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Arbitrator(Protocol):
    """Common interface for the baseline shootout."""

    name: str

    def arbitrate(self, trajectories: np.ndarray) -> ArbitrationResult:
        """Take ``(M, H, 3)`` predictor trajectories; return consensus + attribution."""
        ...


def validate_trajectories(trajectories: np.ndarray) -> np.ndarray:
    arr = np.asarray(trajectories, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(
            f"trajectories must have shape (M, H, 3); got {arr.shape}"
        )
    if arr.shape[0] < 2:
        raise ValueError(
            f"shootout requires M >= 2 predictors; got M={arr.shape[0]}"
        )
    if arr.shape[1] < 3:
        raise ValueError(
            f"shootout requires H >= 3; got H={arr.shape[1]}"
        )
    return arr
