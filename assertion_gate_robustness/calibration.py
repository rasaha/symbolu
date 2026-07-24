"""Calibration utilities (Phase 8/11). Expected calibration error between a method's confidence
(here: 1 - uncertainty as a coarse proxy) and its empirical correctness. Deterministic.
"""
from __future__ import annotations

from typing import Callable, List

from assertion_gate_robustness.dataset import BaseItem, clean_bundle
from assertion_gate_robustness.gate import govern
from assertion_gate_robustness.taxonomy import to_primary


def expected_calibration_error(items: List[BaseItem], n_bins: int = 5) -> float:
    """ECE for the gate: bin by predicted confidence (1-uncertainty), compare to accuracy."""
    rows = []
    for it in items:
        d = govern(clean_bundle(it), it.claim_strength)
        conf = 1.0 - d.uncertainty
        correct = to_primary(d.disposition) == to_primary(it.gold)
        rows.append((conf, correct))
    if not rows:
        return 0.0
    ece = 0.0
    n = len(rows)
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        bucket = [r for r in rows if (lo <= r[0] < hi) or (b == n_bins - 1 and r[0] == 1.0)]
        if not bucket:
            continue
        avg_conf = sum(r[0] for r in bucket) / len(bucket)
        acc = sum(1 for r in bucket if r[1]) / len(bucket)
        ece += (len(bucket) / n) * abs(avg_conf - acc)
    return round(ece, 4)
