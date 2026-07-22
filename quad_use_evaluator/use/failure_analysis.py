"""Failure-case analysis: where USE and standard confidence agree/disagree on failure detection.

On the pooled dataset, compare the best-USE OOF predictor against the best confidence baseline
(token probability) and categorise queries into: both catch, both miss, USE-only catch,
confidence-only catch, false alarms of each. Reports counts and mean signal values to support
mechanistic interpretation.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from . import predict, metrics
from .experiment import all_use_names, base_names


def analyze(pool: Dict[str, np.ndarray], seed=0) -> Dict:
    y = pool["label_failure"].astype(int)
    if len(np.unique(y)) < 2:
        return {"skipped": "single class"}
    use_probs = predict.oof_probabilities(pool, all_use_names(pool), y, seed=seed)
    base_probs = predict.oof_probabilities(pool, base_names(), y, seed=seed)
    # thresholds at each predictor's median (balanced operating point)
    ut, bt = np.median(use_probs), np.median(base_probs)
    use_flag = use_probs >= ut
    base_flag = base_probs >= bt
    fail = y == 1
    ok = y == 0

    def frac(mask):
        return {"count": int(mask.sum()), "frac": float(mask.mean())}

    cats = {
        "both_catch_failure": frac(fail & use_flag & base_flag),
        "both_miss_failure": frac(fail & ~use_flag & ~base_flag),
        "use_only_catches": frac(fail & use_flag & ~base_flag),
        "confidence_only_catches": frac(fail & ~use_flag & base_flag),
        "use_false_alarm": frac(ok & use_flag & ~base_flag),
        "confidence_false_alarm": frac(ok & base_flag & ~use_flag),
    }
    # detection rates
    det = {"use_recall_on_failures": float(use_flag[fail].mean()),
           "confidence_recall_on_failures": float(base_flag[fail].mean()),
           "use_precision": float(fail[use_flag].mean()) if use_flag.any() else float("nan"),
           "confidence_precision": float(fail[base_flag].mean()) if base_flag.any() else float("nan")}
    return {"categories": cats, "detection": det,
            "use_auroc": metrics.auroc(y, use_probs),
            "confidence_auroc": metrics.auroc(y, base_probs),
            "n": int(len(y)), "n_failure": int(fail.sum())}
