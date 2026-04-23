"""Observable protocol + core dataclasses + classification logic.

Pure NumPy + stdlib. No torch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

import numpy as np

from symbolu_bcvf_llm.sources.base import Source


@dataclass
class ObservableValue:
    """Output of one Observable call.

    Attributes:
        scalar: primary scalar used for correlation analyses. Higher
            should MEAN something monotonic (either "more suspicious"
            or "more confident" — the observable documents which).
        per_source: optional per-source decomposition (shape (M,)) for
            diagnostic analysis. None if the observable doesn't decompose.
        metadata: arbitrary per-observation bookkeeping (kernel stats,
            gate activations, etc.).
    """

    scalar: float
    per_source: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Observable(Protocol):
    """A witness function that produces a scalar per (question, choice)."""

    name: str
    higher_means_more_suspicious: bool

    def observe(
        self,
        sources: Sequence[Source],
        prompt_tokens: Sequence[int],
        choice_tokens: Sequence[int],
    ) -> ObservableValue:
        """Return a scalar witness for this (sources, question, choice).

        MUST be pure — doesn't mutate source state.
        """
        ...


@dataclass
class ProbeDatapoint:
    """One (question, choice) observation for the probe harness."""

    question_id: int
    choice_id: int
    is_correct: bool
    observable_value: ObservableValue


@dataclass
class ProbeReport:
    """Post-probe diagnostic report for one observable."""

    observable_name: str
    higher_means_more_suspicious: bool
    n_questions: int
    n_datapoints: int

    pearson_r: float            # signed correlation between scalar and correctness
    spearman_rho: float         # rank-based signed correlation
    auc: float                  # P(observable(correct) > observable(wrong))

    mean_scalar_when_correct: float
    mean_scalar_when_wrong: float
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
        avg_rank = (i + j) / 2 + 1  # ranks are 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation via Pearson on rank-transformed inputs."""
    return _pearson_r(_rankdata(x), _rankdata(y))


def _roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under ROC curve for binary labels. Returns 0.5 on degenerate input.

    Tie-aware rank-sum formulation: O(n log n) via the existing rank
    primitive, which already averages tied ranks (ties → 0.5 contribution).
    """
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
    """Classify an observable by its AUC vs correctness.

    Bands:
      AUC ≥ 0.60 → TRUTH_CORRELATED
      0.45 ≤ AUC < 0.60 → UNCORRELATED
      AUC < 0.45 → ANTI_CORRELATED
      n_datapoints < min_n → NULL (estimate is unreliable)
    """
    if n_datapoints < min_n:
        return "NULL"
    if auc >= 0.60:
        return "TRUTH_CORRELATED"
    if auc < 0.45:
        return "ANTI_CORRELATED"
    return "UNCORRELATED"


_RECOMMENDATIONS = {
    "TRUTH_CORRELATED": (
        "AUC={auc:.3f} — observable has signal. Worth building a Rahu "
        "attractor around. Proceed to bounded benchmark."
    ),
    "ANTI_CORRELATED": (
        "AUC={auc:.3f} < 0.45 — observable has signal with the WRONG "
        "sign. A conventional trust-shaped attractor on this would "
        "ACTIVELY HURT accuracy. Options: flip the observable's sign, "
        "reject it, or verify with a larger N."
    ),
    "UNCORRELATED": (
        "AUC={auc:.3f} near 0.5 — observable is close to noise. A "
        "Rahu built on this converges to conventional-blend at best. "
        "Not worth the inference cost."
    ),
    "NULL": (
        "n<40 datapoints — estimate unreliable. Re-probe with a larger "
        "benchmark subset before classifying."
    ),
}


def recommendation_for(classification: str, auc: float) -> str:
    """Human-readable next-step recommendation per classification."""
    template = _RECOMMENDATIONS.get(classification, _RECOMMENDATIONS["NULL"])
    return template.format(auc=auc)
