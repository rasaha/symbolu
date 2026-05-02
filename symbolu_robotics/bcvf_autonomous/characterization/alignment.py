"""Outlier-attribution alignment metrics.

For families with a ``truth_label`` (the predictor that should bear
the disagreement cost), the kernel must not only fire — it must
point at the right offender. Three diagnostics:

* ``hit`` — 1 if argmax(per_predictor_cost) == truth_label, else 0.
* ``margin`` — ``cost[truth] / mean(cost[non-truth])``. Ratios > 1
  mean the truth predictor's cost stands out from the rest.
* ``rank`` — 1 if truth has the highest cost, 2 if second, ..., M
  if last.

Aggregated across cells:

* ``hit_rate`` — fraction of cells where the kernel hit.
* ``margin_mean`` — mean margin across cells (infinite margins
  filtered for percentile stability).
* ``rank_distribution`` — fraction of cells in each rank bucket.

Ported with the same shapes as ``symbolu_bcvf_llm.characterization
.alignment`` so a SOTIF reviewer who has read the LLM document can
read this one without retraining.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class AlignmentMetrics:
    """Per-cell outlier-attribution diagnostics."""

    hit: int
    margin: float
    rank: int


@dataclass
class AlignmentAggregate:
    """Aggregate across many cells."""

    hit_rate: float
    margin_mean: float
    margin_percentiles: Tuple[float, float, float]   # (25, 50, 75)
    rank_distribution: Dict[int, float]
    n_cells: int


def compute_alignment_metrics(
    per_predictor_costs: np.ndarray,
    truth_label: Optional[int],
) -> Optional[AlignmentMetrics]:
    """Per-cell alignment metrics. Returns ``None`` if no truth label.

    Args:
        per_predictor_costs: shape ``(M,)`` array of per-predictor
            costs. Caller is responsible for converting from any
            kernel-specific intermediate (e.g.
            ``BCVFPerStepBreakdown.per_step_per_predictor.sum(axis=-1)``).
        truth_label: the predictor index that should top the ranking,
            or ``None`` if the family is unattributable.
    """
    if truth_label is None:
        return None
    arr = np.asarray(per_predictor_costs, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(
            f"per_predictor_costs must be 1-D; got shape {arr.shape}"
        )
    M = arr.shape[0]
    if M == 0:
        return None
    if not (0 <= truth_label < M):
        raise IndexError(
            f"truth_label {truth_label} out of range for M={M}"
        )
    # Rank: 1 = highest cost (truth predictor at the top).
    argsort_desc = np.argsort(-arr, kind="stable")
    rank = int(np.where(argsort_desc == truth_label)[0][0]) + 1
    hit = 1 if int(argsort_desc[0]) == truth_label else 0
    non_truth = np.delete(arr, truth_label)
    denom = float(non_truth.mean()) if non_truth.size > 0 else 0.0
    if denom > 0:
        margin = float(arr[truth_label] / denom)
    else:
        # If non-truth has zero cost, the truth predictor is strictly
        # the only contributor — margin is conventionally +inf.
        margin = float("inf") if arr[truth_label] > 0 else 0.0
    return AlignmentMetrics(hit=hit, margin=margin, rank=rank)


def aggregate_alignment(
    metrics: List[Optional[AlignmentMetrics]],
) -> Optional[AlignmentAggregate]:
    """Aggregate per-cell metrics into a per-group summary.

    Returns ``None`` if no cell has a defined alignment (all
    truth_label None).
    """
    defined = [m for m in metrics if m is not None]
    if not defined:
        return None
    n = len(defined)
    M = max(m.rank for m in defined)
    hits = np.array([m.hit for m in defined])
    margins_all = np.array([m.margin for m in defined], dtype=np.float64)
    margins_finite = margins_all[np.isfinite(margins_all)]
    if margins_finite.size == 0:
        margin_mean = float("inf")
        margin_percentiles: Tuple[float, float, float] = (
            float("inf"), float("inf"), float("inf"),
        )
    else:
        margin_mean = float(margins_finite.mean())
        p25, p50, p75 = (
            float(p) for p in np.percentile(margins_finite, [25, 50, 75])
        )
        margin_percentiles = (p25, p50, p75)
    ranks = np.array([m.rank for m in defined])
    rank_distribution = {
        r: float(np.mean(ranks == r)) for r in range(1, M + 1)
    }
    return AlignmentAggregate(
        hit_rate=float(hits.mean()),
        margin_mean=margin_mean,
        margin_percentiles=margin_percentiles,
        rank_distribution=rank_distribution,
        n_cells=n,
    )
