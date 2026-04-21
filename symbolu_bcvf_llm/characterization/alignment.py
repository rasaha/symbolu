"""§3.6 alignment diagnostic: hit / margin / rank.

Computed only for cells whose ``TraceBundle.truth_label is not None``
(§3.2.4 ``accelerating`` → truth_label=1; §3.2.6 ``outlier`` →
truth_label=0; §3.2.7 ``eos_truncation`` inherits from outer family).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class AlignmentMetrics:
    hit: int               # 1 if argmax(per_source_costs) == truth_label
    margin: float          # cost[truth] / mean(cost[non-truth])
    rank: int              # 1 = highest cost; 2 = second; 3 = lowest (M=3)


@dataclass
class AlignmentAggregate:
    hit_rate: float
    margin_mean: float
    margin_percentiles: Tuple[float, float, float]   # (25, 50, 75)
    rank_distribution: Dict[int, float]              # {1: frac, 2: frac, 3: frac}
    n_cells: int


def compute_alignment_metrics(
    per_source_costs: Dict[int, float],
    truth_label: Optional[int],
) -> Optional[AlignmentMetrics]:
    """Per-cell alignment metrics; returns None if truth_label is None."""
    if truth_label is None:
        return None
    M = len(per_source_costs)
    if M == 0:
        return None
    ordered = [per_source_costs[i] for i in range(M)]
    # rank: 1 means truth has the largest cost.
    argsort_desc = sorted(range(M), key=lambda i: -ordered[i])
    rank = argsort_desc.index(truth_label) + 1
    hit = 1 if argsort_desc[0] == truth_label else 0
    non_truth = [ordered[i] for i in range(M) if i != truth_label]
    denom = float(np.mean(non_truth)) if non_truth else 0.0
    margin = float(ordered[truth_label] / denom) if denom > 0 else float("inf")
    return AlignmentMetrics(hit=hit, margin=margin, rank=rank)


def aggregate_alignment(
    metrics: List[Optional[AlignmentMetrics]],
) -> Optional[AlignmentAggregate]:
    """Aggregate per-cell metrics into a per-group summary. Returns
    None if no cell has a defined alignment (truth_label all None)."""
    defined = [m for m in metrics if m is not None]
    if not defined:
        return None
    hits = np.array([m.hit for m in defined])
    # Filter infinite margins (division-by-zero) for percentile stability.
    margins_all = np.array([m.margin for m in defined], dtype=np.float64)
    margins_finite = margins_all[np.isfinite(margins_all)]
    if margins_finite.size == 0:
        margin_mean = float("inf")
        margin_percentiles = (float("inf"),) * 3
    else:
        margin_mean = float(margins_finite.mean())
        margin_percentiles = tuple(
            float(p) for p in np.percentile(margins_finite, [25, 50, 75])
        )
    ranks = np.array([m.rank for m in defined])
    rank_distribution = {
        r: float(np.mean(ranks == r)) for r in (1, 2, 3)
    }
    return AlignmentAggregate(
        hit_rate=float(hits.mean()),
        margin_mean=margin_mean,
        margin_percentiles=margin_percentiles,
        rank_distribution=rank_distribution,
        n_cells=len(defined),
    )
