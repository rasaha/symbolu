"""Observable protocol + core dataclasses + correlation primitives.

Pure NumPy + stdlib. No torch.

Ported from ``symbolu_bcvf_llm.observables.base`` with autonomous
semantics: an observable consumes a predictor-trajectory tensor of
shape ``(M, H, 3)`` (M predictors, H horizon steps, SE(2) pose) and
produces a scalar witness for that planning tick. The probe harness
applies an observable across many ticks (or many episodes) and
measures how well its scalar predicts a downstream outcome
(collision, recovery, time-to-disengagement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

import numpy as np


@dataclass
class ObservableValue:
    """Output of one Observable call.

    Attributes:
        scalar: primary scalar used for correlation analyses. The
            observable documents which polarity is monotonic via
            ``higher_means_more_suspicious``.
        per_predictor: optional per-predictor decomposition (shape
            ``(M,)``) for diagnostic analysis. ``None`` if the
            observable does not decompose.
        metadata: arbitrary per-observation bookkeeping (per-step
            costs, gate activations, alignment factors, etc.).
    """

    scalar: float
    per_predictor: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Observable(Protocol):
    """A witness function that produces a scalar per planning tick."""

    name: str
    higher_means_more_suspicious: bool

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        """Return a scalar witness for this set of predictor trajectories.

        Args:
            trajectories: shape ``(M, H, 3)`` ``[x, y, theta]``. Must
                share a horizon across predictors. ``M >= 2``.
            ground_truth: optional ``(H, 3)`` ground-truth trajectory.
                Most observables ignore this; coherence-anchored
                variants use it for the alignment factor.

        MUST be pure — the trajectory tensor is not mutated.
        """
        ...


@dataclass
class ProbeDatapoint:
    """One (tick, outcome) observation for the probe harness."""

    tick_id: int
    outcome_label: bool
    observable_value: ObservableValue


@dataclass
class ProbeReport:
    """Post-probe diagnostic report for one observable."""

    observable_name: str
    higher_means_more_suspicious: bool
    n_ticks: int

    pearson_r: float
    spearman_rho: float
    auc: float

    mean_scalar_when_positive: float
    mean_scalar_when_negative: float
    std_scalar_overall: float

    classification: str
    recommendation: str
    datapoints: List[ProbeDatapoint] = field(default_factory=list, repr=False)


# --------------------------------------------------------------------------- #
# Correlation primitives (numpy-only, no scipy)
# --------------------------------------------------------------------------- #


def _pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    """Sample Pearson correlation. Returns 0 if either array is constant."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) < 2:
        return 0.0
    sx = x.std()
    sy = y.std()
    if sx == 0.0 or sy == 0.0:
        return 0.0
    return float(((x - x.mean()) * (y - y.mean())).mean() / (sx * sy))


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Average ranks for tied values (standard 'average' rank method)."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    return _pearson_r(_rankdata(x), _rankdata(y))


def _roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under ROC curve for binary labels. Returns 0.5 on degenerate input."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    n_pos = int(labels.sum())
    n_neg = int(labels.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = _rankdata(scores)
    rank_sum_pos = float(ranks[labels].sum())
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def classify_observable(
    auc: float,
    n_datapoints: int,
    min_n: int = 40,
) -> str:
    """Classify an observable by its AUC vs the outcome label.

    Bands:
      AUC ≥ 0.60 → SAFETY_CORRELATED
      0.45 ≤ AUC < 0.60 → UNCORRELATED
      AUC < 0.45 → ANTI_CORRELATED
      n_datapoints < min_n → NULL
    """
    if n_datapoints < min_n:
        return "NULL"
    if auc >= 0.60:
        return "SAFETY_CORRELATED"
    if auc < 0.45:
        return "ANTI_CORRELATED"
    return "UNCORRELATED"


_RECOMMENDATIONS = {
    "SAFETY_CORRELATED": (
        "AUC={auc:.3f} — observable predicts the outcome label. Worth "
        "wiring into the trust shaper or surfacing as an early-warning "
        "signal. Proceed to closed-loop ablation."
    ),
    "ANTI_CORRELATED": (
        "AUC={auc:.3f} < 0.45 — observable carries signal with the "
        "WRONG sign. Flip the polarity flag, reject it, or verify with "
        "a larger N before consuming."
    ),
    "UNCORRELATED": (
        "AUC={auc:.3f} near 0.5 — observable is close to noise. Not "
        "worth carrying through the trust pipeline; keep only as a "
        "diagnostic."
    ),
    "NULL": (
        "n<40 datapoints — estimate unreliable. Re-probe with a larger "
        "scenario suite before classifying."
    ),
}


def recommendation_for(classification: str, auc: float) -> str:
    template = _RECOMMENDATIONS.get(classification, _RECOMMENDATIONS["NULL"])
    return template.format(auc=auc)


# --------------------------------------------------------------------------- #
# Trajectory validation
# --------------------------------------------------------------------------- #


def validate_trajectory_tensor(trajectories: np.ndarray) -> np.ndarray:
    """Coerce to ``float64`` and validate ``(M, H, 3)`` with ``M >= 2``, ``H >= 3``."""
    arr = np.asarray(trajectories, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(
            f"trajectories must have shape (M, H, 3); got {arr.shape}"
        )
    if arr.shape[0] < 2:
        raise ValueError(
            f"observables require M >= 2 predictors; got M={arr.shape[0]}"
        )
    if arr.shape[1] < 3:
        raise ValueError(
            f"observables require H >= 3 (BCVF stencil); got H={arr.shape[1]}"
        )
    return arr
