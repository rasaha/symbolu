"""Paired statistical significance vs the BD-A baseline.

The benchmark is BD-A (not BD-D).  The success criterion requires a *statistically significant*
improvement of the new method over BD-A while satisfying the guardrails.  Because arms share
seeds (paired design), we test the per-seed paired difference (method - BD-A) with:

  * Wilcoxon signed-rank (nonparametric; primary, appropriate for small n) -- one-sided
    (method > BD-A) and two-sided.
  * paired t-test (parametric sensitivity check).
  * a seeded paired bootstrap 95% CI of the mean difference.

Pre-registered decision: reject the null (task-only is best) only if the one-sided Wilcoxon
p < 0.05 AND the bootstrap CI excludes 0 AND the mean difference is practically meaningful.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

try:
    from scipy import stats as _sps
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _HAVE_SCIPY = False


def _wilcoxon(delta: List[float]) -> Dict[str, Optional[float]]:
    d = [x for x in delta if x != 0.0]
    if not _HAVE_SCIPY or len(d) < 1:
        return {"stat": None, "p_greater": None, "p_two_sided": None, "n_nonzero": len(d)}
    try:
        res_g = _sps.wilcoxon(d, alternative="greater", zero_method="wilcox", mode="auto")
        res_t = _sps.wilcoxon(d, alternative="two-sided", zero_method="wilcox", mode="auto")
        return {"stat": float(res_g.statistic), "p_greater": float(res_g.pvalue),
                "p_two_sided": float(res_t.pvalue), "n_nonzero": len(d)}
    except Exception as e:  # pragma: no cover
        return {"stat": None, "p_greater": None, "p_two_sided": None,
                "n_nonzero": len(d), "error": str(e)}


def _ttest(delta: List[float]) -> Dict[str, Optional[float]]:
    if not _HAVE_SCIPY or len(delta) < 2:
        return {"t": None, "p_greater": None, "p_two_sided": None}
    res = _sps.ttest_1samp(delta, 0.0, alternative="greater")
    res2 = _sps.ttest_1samp(delta, 0.0, alternative="two-sided")
    return {"t": float(res.statistic), "p_greater": float(res.pvalue),
            "p_two_sided": float(res2.pvalue)}


def _bootstrap_ci(delta: List[float], n_boot=10000, seed=12345, alpha=0.05) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(delta, dtype=float)
    n = len(arr)
    if n == 0:
        return {"lo": float("nan"), "hi": float("nan"), "mean": float("nan")}
    idx = rng.integers(0, n, size=(n_boot, n))
    means = arr[idx].mean(axis=1)
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return {"lo": lo, "hi": hi, "mean": float(arr.mean())}


def paired_comparison(method: List[float], baseline: List[float], label="method_vs_BD-A",
                      meaningful=0.02) -> Dict:
    """Full paired comparison of `method` vs `baseline` across seeds (same order)."""
    assert len(method) == len(baseline), "paired arms must share seeds"
    delta = [m - b for m, b in zip(method, baseline)]
    arr = np.asarray(delta, dtype=float)
    n = len(delta)
    n_pos = int(sum(1 for x in delta if x > 0))
    n_neg = int(sum(1 for x in delta if x < 0))
    mean_d = float(arr.mean()) if n else float("nan")
    sd = float(arr.std(ddof=1)) if n > 1 else 0.0
    dz = mean_d / sd if sd > 0 else float("nan")   # Cohen's d_z (paired effect size)
    wil = _wilcoxon(delta)
    tt = _ttest(delta)
    boot = _bootstrap_ci(delta)
    ci_excludes_0 = (boot["lo"] > 0) or (boot["hi"] < 0)
    significant = (wil["p_greater"] is not None and wil["p_greater"] < 0.05
                   and boot["lo"] > 0 and mean_d >= meaningful)
    return {
        "label": label, "n_seeds": n,
        "method_mean": float(np.mean(method)), "baseline_mean": float(np.mean(baseline)),
        "delta_per_seed": delta, "mean_delta": mean_d, "median_delta": float(np.median(arr)) if n else float("nan"),
        "sd_delta": sd, "cohens_dz": dz, "n_positive": n_pos, "n_negative": n_neg,
        "wilcoxon": wil, "ttest": tt, "bootstrap_ci95": boot,
        "ci_excludes_0": bool(ci_excludes_0),
        "significant_improvement_over_baseline": bool(significant),
        "meaningful_threshold": meaningful,
    }
