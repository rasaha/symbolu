"""
probes.py — a small, honest linear probe for the signal-survival ladder (D1).

The D1 diagnostic asks: how far does the working signal (raw next-token predictive
entropy, AUROC ~0.857 on the fooled subset) survive down the pipeline

    logits  ->  final hidden state  ->  32-D sovereign state  ->  CG-state entropy

A *linear probe* on the hidden state and on the 32-D state is the instrument that
localizes WHERE the signal is lost (a big AUROC drop across one rung = that rung
destroys the signal). For that instrument to be honest at the tiny N of the probe
set (~20 scenarios, 4096-D hidden), it must satisfy two things:

  1. **No in-sample evaluation.** A linear classifier on D>>N features separates any
     labelling perfectly in-sample (AUROC 1.0, meaningless). We report only
     OUT-OF-FOLD scores via leave-one-GROUP-out cross-validation.
  2. **No twin leakage.** The probe set is built from surface-matched safe/unsafe
     TWINS (same task, same `policy_context['twin']`). Leaving out a single item
     would leave its twin in the training fold and let the probe memorise the pair.
     We hold out BOTH members of a twin together (leave-one-pair-out).

The probe itself is L2-regularised least-squares (ridge) in its DUAL (linear-kernel)
form, so it is O(N^3) regardless of the hidden width and never has a convergence
knob — deterministic and reviewer-checkable. Ridge-regression scores are a monotone
linear read-out; their ROC ranking is what we report. To remove the regularisation
strength as a degree of freedom, callers evaluate a fixed alpha grid and summarise by
the MEDIAN out-of-fold AUROC (all per-alpha values are reported, so the headline is
not alpha-cherry-picked).

Pure numpy. No torch, no sklearn. Read-only: nothing here is trained into a model.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np

from experiments.signal_gov.metrics import roc_auc

# Pre-registered alpha grid for the linear probe (ridge penalty on standardised
# features). The headline probe AUROC is the MEDIAN over this grid; per-alpha values
# are reported so the verdict is visibly robust to the regularisation choice.
DEFAULT_ALPHAS: Tuple[float, ...] = (0.1, 1.0, 10.0, 100.0)


def _ridge_dual_fit_predict(
    x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, alpha: float
) -> np.ndarray:
    """Ridge regression in dual (linear-kernel) form; returns scores for x_test.

    Features are standardised with TRAIN-fold statistics only (no test leakage).
    Solving in the dual (N x N) makes this independent of the feature width D, so a
    4096-D hidden state is no more expensive than the 32-D state.
    """
    mu = x_train.mean(axis=0)
    sd = x_train.std(axis=0)
    sd = np.where(sd < 1e-8, 1.0, sd)
    xtr = (x_train - mu) / sd
    xte = (x_test - mu) / sd

    y_mean = float(y_train.mean())
    yc = y_train - y_mean

    k_train = xtr @ xtr.T                      # [n, n] linear kernel
    n = k_train.shape[0]
    dual = np.linalg.solve(k_train + alpha * np.eye(n), yc)   # [n]
    k_test = xte @ xtr.T                        # [m, n]
    return k_test @ dual + y_mean


def _groups_array(groups: Sequence[str], n: int) -> np.ndarray:
    if groups is None:
        return np.arange(n).astype(str)        # degenerate: each item its own group
    g = np.asarray(list(groups), dtype=object)
    if g.shape[0] != n:
        raise ValueError(f"groups length {g.shape[0]} != n {n}")
    return g


def linear_probe_oof_scores(
    x: np.ndarray, y: Sequence[int], groups: Sequence[str], alpha: float
) -> np.ndarray:
    """Leave-one-GROUP-out out-of-fold ridge scores, one per row of `x`.

    Each held-out group (a safe/unsafe twin pair) is scored by a probe fit on all
    OTHER groups, so no item is ever scored by a probe that saw it or its twin.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = x.shape[0]
    g = _groups_array(groups, n)
    oof = np.full(n, np.nan, dtype=float)
    for grp in np.unique(g):
        test_mask = g == grp
        train_mask = ~test_mask
        if train_mask.sum() < 2 or len(np.unique(y[train_mask])) < 2:
            # Cannot fit a discriminative probe on this fold — leave NaN.
            continue
        oof[test_mask] = _ridge_dual_fit_predict(
            x[train_mask], y[train_mask], x[test_mask], alpha
        )
    return oof


def probe_auroc_over_alphas(
    x: np.ndarray,
    y: Sequence[int],
    groups: Sequence[str],
    eval_mask: Sequence[bool] | None = None,
    alphas: Sequence[float] = DEFAULT_ALPHAS,
) -> Dict[str, object]:
    """Group-LOO probe AUROC on the `eval_mask` subset, per alpha + median summary.

    Returns:
        {
          "per_alpha":  {alpha: auroc_on_eval_subset, ...},
          "median":     median over per_alpha (the headline probe AUROC),
          "oof_median_alpha": the alpha whose AUROC is the median (for traceability),
        }
    `eval_mask` selects the subset the AUROC is computed on (the fooled subset for D1);
    the probe is always FIT on the full set minus the held-out group, so the eval
    subset still benefits from honest out-of-fold scoring.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int)
    n = x.shape[0]
    mask = np.ones(n, dtype=bool) if eval_mask is None else np.asarray(eval_mask, dtype=bool)

    per_alpha: Dict[float, float] = {}
    for a in alphas:
        oof = linear_probe_oof_scores(x, y, groups, alpha=float(a))
        valid = mask & ~np.isnan(oof)
        sub_y = y[valid]
        if sub_y.size == 0 or sub_y.min() == sub_y.max():
            per_alpha[float(a)] = float("nan")
        else:
            per_alpha[float(a)] = float(roc_auc(sub_y, oof[valid]))

    vals = [v for v in per_alpha.values() if not np.isnan(v)]
    median = float(np.median(vals)) if vals else float("nan")
    # Report the alpha closest to the median value (deterministic tie-break: smallest).
    median_alpha = float("nan")
    if vals:
        median_alpha = min(
            (a for a, v in per_alpha.items() if not np.isnan(v)),
            key=lambda a: (abs(per_alpha[a] - median), a),
        )
    return {
        "per_alpha": {f"{a:g}": per_alpha[a] for a in per_alpha},
        "median": median,
        "median_alpha": median_alpha,
    }
