"""§11 Observable protocol + core dataclasses + classification logic.

A Ketu observable is a witness function. Given a question + candidate
choice + the sources' behavior on that choice, it produces a scalar
(and optionally per-source decomposition). The scalar is then
correlated with ground-truth correctness over the benchmark to
determine whether the observable is worth building a Rahu attractor
around.

This module is pure NumPy + stdlib. No torch. Tests run on CPU in <1 s.
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

import math

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
    """A Ketu — a witness function that produces a scalar per (Q, choice)."""

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
    n_choices: int
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

    The observable's `higher_means_more_suspicious` flag is NOT applied
    here — this function computes AUC as 'probability that a label=1
    example scores HIGHER than a label=0 example'. The probe harness
    inverts labels before calling when the observable is suspicion-
    polarity so the final reported AUC is consistently "higher AUC =
    observable predicts correctness better."
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    pos = scores[labels]
    neg = scores[~labels]
    n_pos, n_neg = len(pos), len(neg)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    # Tie-aware rank-sum AUC — O((n_pos + n_neg)^2) is fine at benchmark sizes.
    greater = 0.0
    for p in pos:
        greater += float((p > neg).sum()) + 0.5 * float((p == neg).sum())
    return greater / (n_pos * n_neg)


def classify_observable(
    auc: float,
    n_datapoints: int,
    min_n: int = 40,
) -> str:
    """Classify an observable by its AUC vs correctness.

    Uses thresholds calibrated for the §11 Observable Discipline:
      AUC ≥ 0.60 → TRUTH_CORRELATED
      0.45 ≤ AUC < 0.60 → UNCORRELATED (marginal signal at best)
      AUC < 0.45 → ANTI_CORRELATED (has signal with wrong sign)

    If fewer than `min_n` datapoints are available, returns NULL
    because the AUC estimate itself is unreliable.
    """
    if n_datapoints < min_n:
        return "NULL"
    if auc >= 0.60:
        return "TRUTH_CORRELATED"
    if auc < 0.45:
        return "ANTI_CORRELATED"
    return "UNCORRELATED"


def recommendation_for(classification: str, auc: float) -> str:
    """Human-readable next-step recommendation per classification."""
    if classification == "TRUTH_CORRELATED":
        return (
            f"AUC={auc:.3f} — observable has signal. Worth building a "
            "Rahu attractor around. Proceed to §10.V1.3 Experiment A-style "
            "attractor design + bounded benchmark."
        )
    if classification == "ANTI_CORRELATED":
        return (
            f"AUC={auc:.3f} < 0.45 — observable has signal with the WRONG "
            "sign. Building a conventional trust-shaped attractor on this "
            "would ACTIVELY HURT accuracy (the V1 failure mode). Options: "
            "(1) flip the observable's sign (invert the direction); "
            "(2) reject this observable and try another; (3) verify this "
            "is real by re-probing with a larger N."
        )
    if classification == "UNCORRELATED":
        return (
            f"AUC={auc:.3f} near 0.5 — observable is close to noise. "
            "A Rahu built on this produces trust ≈ uniform most of the "
            "time — converges to conventional-blend at best. Not worth "
            "the inference cost."
        )
    return (
        f"n<40 datapoints — estimate unreliable. Re-probe with a larger "
        "benchmark subset before classifying."
    )
