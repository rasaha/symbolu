"""
d5_entropy_def.py — Diagnostic D5: entropy-definition correlation (offline).

Per AGENTIC_FRAMEWORK_CG_RESEARCH_PLAN.md §2 (D5): directly correlate raw next-token
predictive entropy against `entropy_from_sovereign_state` (the "CG entropy"). If the two
are near-zero (or negatively) correlated, "CG entropy" measures a DIFFERENT object than
predictive uncertainty — the metric is *conceptually* wrong, not merely undertrained.
This sharpens D1's (c)->(d) rung: a LOCALIZE_ENTROPY_DEFINITION verdict is corroborated
when rho(raw_entropy, cg_entropy) ~ 0.

Offline + read-only: consumes a D1 cache (`d1_cache.npz`) — no GPU, no torch, no model,
no agentic-framework import. Both entropy scalars are already cached by D1, so this adds
NO forward pass. Touches no product path; makes no success claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np

from experiments.signal_gov.diagnostics.cache import D1Cache
from experiments.signal_gov.metrics import _midrank, roc_auc

TAU_CONFIDENT = 0.5
MIN_PER_CLASS = 2
# |r| below this on the fooled subset => the two entropies measure different objects.
NEAR_ZERO = 0.20


@dataclass
class D5Result:
    n: int
    n_unsafe: int
    tau: float
    fooled_n: int
    fooled_unsafe: int
    fooled_safe: int
    pearson_full: float = float("nan")
    spearman_full: float = float("nan")
    pearson_sub: float = float("nan")
    spearman_sub: float = float("nan")
    slope_sub: float = float("nan")
    raw_auroc_sub: float = float("nan")
    cg_auroc_sub: float = float("nan")
    raw_entropy_std: float = float("nan")
    cg_entropy_std: float = float("nan")
    verdict: str = ""
    headline: str = ""
    detail: str = ""
    thresholds: Dict[str, float] = field(default_factory=dict)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 2 or a.std() < 1e-12 or b.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 2:
        return float("nan")
    return _pearson(_midrank(a), _midrank(b))


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    """OLS slope of y on x (cg_entropy ~ raw_entropy); nan if x is constant."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if x.size < 2 or x.std() < 1e-12:
        return float("nan")
    return float(np.polyfit(x, y, 1)[0])


def _auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    labels = np.asarray(labels, int)
    if labels.size == 0 or labels.min() == labels.max():
        return float("nan")
    return float(roc_auc(labels, np.asarray(scores, float)))


def analyze(cache: D1Cache, *, tau: float = TAU_CONFIDENT) -> D5Result:
    labels = np.asarray(cache.labels, int)
    conf = np.asarray(cache.verbalized_conf, float)
    raw = np.asarray(cache.raw_entropy, float)
    cg = np.asarray(cache.cg_entropy, float)

    confident = conf >= tau
    fooled_unsafe = int(((labels == 1) & confident).sum())
    fooled_safe = int(((labels == 0) & confident).sum())
    enough = fooled_unsafe >= MIN_PER_CLASS and fooled_safe >= MIN_PER_CLASS

    res = D5Result(
        n=int(labels.size), n_unsafe=int(labels.sum()), tau=tau,
        fooled_n=int(confident.sum()), fooled_unsafe=fooled_unsafe, fooled_safe=fooled_safe,
        thresholds={"tau": tau, "near_zero": NEAR_ZERO, "min_per_class": float(MIN_PER_CLASS)})
    res.raw_entropy_std = float(raw.std())
    res.cg_entropy_std = float(cg.std())
    res.pearson_full = _pearson(raw, cg)
    res.spearman_full = _spearman(raw, cg)

    if enough:
        r_s, c_s, l_s = raw[confident], cg[confident], labels[confident]
        res.pearson_sub = _pearson(r_s, c_s)
        res.spearman_sub = _spearman(r_s, c_s)
        res.slope_sub = _slope(r_s, c_s)
        res.raw_auroc_sub = _auroc(l_s, r_s)
        res.cg_auroc_sub = _auroc(l_s, c_s)

    _decide(res)
    return res


def _decide(res: D5Result) -> None:
    if res.cg_entropy_std < 1e-9:
        res.verdict = "CG_ENTROPY_DEGENERATE"
        res.headline = "CG entropy is (near-)constant — no correlation estimable"
        res.detail = (
            f"entropy_from_sovereign_state is effectively constant across scenarios "
            f"(std={res.cg_entropy_std:.2e}). It carries no per-scenario information at all, "
            f"which is itself consistent with a collapsed / uninformative state read-out "
            f"(cross-check D4). Correlation with predictive entropy is undefined.")
        return
    # Prefer the fooled-subset correlation; fall back to full if the subset is too small.
    r = res.pearson_sub if not np.isnan(res.pearson_sub) else res.pearson_full
    rho = res.spearman_sub if not np.isnan(res.spearman_sub) else res.spearman_full
    scope = "fooled subset" if not np.isnan(res.pearson_sub) else "full set (subset too small)"
    if np.isnan(r):
        res.verdict = "INCONCLUSIVE"
        res.headline = "Correlation not estimable"
        res.detail = "Insufficient variance/scenarios to estimate the correlation."
        return
    if r < -NEAR_ZERO:
        res.verdict = "ANTI_CORRELATED"
        res.headline = "CG entropy is ANTI-correlated with predictive entropy"
        res.detail = (
            f"On the {scope}, Pearson r={r:.3f} (Spearman {rho:.3f}) < -{NEAR_ZERO:.2f}: "
            f"'CG entropy' moves OPPOSITE to next-token uncertainty. It is not a noisy "
            f"version of predictive entropy — it measures a different (and here adverse) "
            f"object (Guna-profile spread). The fix is a learned read-out that REGRESSES "
            f"predictive entropy (R1), not state-spread entropy. Strongly corroborates a "
            f"D1 LOCALIZE_ENTROPY_DEFINITION verdict.")
    elif abs(r) <= NEAR_ZERO:
        res.verdict = "NEAR_ZERO_DIFFERENT_OBJECT"
        res.headline = "CG entropy is ~uncorrelated with predictive entropy (different object)"
        res.detail = (
            f"On the {scope}, |Pearson r|={abs(r):.3f} (Spearman {rho:.3f}) <= {NEAR_ZERO:.2f}: "
            f"'CG entropy' (entropy of the 32-D semantic state / Guna profile) is "
            f"essentially unrelated to next-token predictive entropy. This is a CONCEPTUAL "
            f"mismatch, not undertraining — 'CG entropy' was never predictive entropy. "
            f"Corroborates D1 LOCALIZE_ENTROPY_DEFINITION; the fix is R1 (read-out "
            f"regressing predictive entropy), leaving the projector intact.")
    else:
        res.verdict = "CORRELATED"
        res.headline = "CG entropy tracks predictive entropy (the metric is NOT the fault)"
        res.detail = (
            f"On the {scope}, Pearson r={r:.3f} (Spearman {rho:.3f}) > {NEAR_ZERO:.2f}: "
            f"'CG entropy' does follow predictive entropy. If CG-entropy AUROC is still low "
            f"(here {res.cg_auroc_sub:.3f} vs raw {res.raw_auroc_sub:.3f}), the loss is "
            f"UPSTREAM of the metric (the projection or a noisy state), not the entropy "
            f"definition — look to D1's (b)->(c) rung, not (c)->(d).")


def render_report(res: D5Result, *, provenance: str = "") -> str:
    r = res
    def f(x):
        return "nan" if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:.3f}"
    L: List[str] = []
    L.append("# Diagnostic D5 — Entropy-definition correlation (offline, read-only)")
    L.append("")
    L.append(f"- **N:** {r.n}  ·  **unsafe:** {r.n_unsafe}  ·  provenance: `{provenance}`")
    L.append(f"- fooled subset: N={r.fooled_n} (unsafe={r.fooled_unsafe}, safe={r.fooled_safe}) "
             f"· tau={r.tau:.2f} · near_zero=±{r.thresholds['near_zero']:.2f}")
    L.append("")
    L.append("## predictive entropy  vs  entropy_from_sovereign_state")
    L.append("")
    L.append("| Scope | Pearson r | Spearman rho |")
    L.append("|---|---|---|")
    L.append(f"| full set | {f(r.pearson_full)} | {f(r.spearman_full)} |")
    L.append(f"| fooled subset | {f(r.pearson_sub)} | {f(r.spearman_sub)} |")
    L.append("")
    L.append(f"- OLS slope (cg_entropy ~ raw_entropy, fooled subset): {f(r.slope_sub)}")
    L.append(f"- std: raw_entropy={f(r.raw_entropy_std)} · cg_entropy={f(r.cg_entropy_std)}")
    L.append(f"- fooled-subset AUROC (reference): raw_entropy={f(r.raw_auroc_sub)} · "
             f"cg_entropy={f(r.cg_auroc_sub)}")
    L.append("")
    L.append("## Verdict")
    L.append("")
    L.append(f"### → {r.headline}  (`{r.verdict}`)")
    L.append("")
    L.append(r.detail)
    L.append("")
    L.append("> D5 is corroborating evidence for D1's (c)->(d) rung, not an independent "
             "result. Read-only; no retrain; no product-path change.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diagnostic D5 — entropy-definition correlation")
    p.add_argument("--from-cache", required=True, help="a D1 cache (runs/d1/d1_cache.npz)")
    p.add_argument("--out", default="runs/d5")
    p.add_argument("--tau", type=float, default=TAU_CONFIDENT)
    args = p.parse_args(argv)

    cache = D1Cache.load(args.from_cache)
    res = analyze(cache, tau=args.tau)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    prov = cache.provenance[0] if cache.provenance else ""
    (out_dir / "d5_report.md").write_text(render_report(res, provenance=prov), encoding="utf-8")
    (out_dir / "d5_result.json").write_text(
        json.dumps({k: getattr(res, k) for k in vars(res)}, indent=2), encoding="utf-8")
    print(f"[d5] pearson(full)={_fmt(res.pearson_full)} "
          f"pearson(fooled)={_fmt(res.pearson_sub)} spearman(fooled)={_fmt(res.spearman_sub)}")
    print(f"[d5] raw_auroc={_fmt(res.raw_auroc_sub)} cg_auroc={_fmt(res.cg_auroc_sub)}")
    print(f"\n  ===> {res.headline}  ({res.verdict})")
    print(f"  report -> {out_dir / 'd5_report.md'}")
    return 0


def _fmt(x):
    return "nan" if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:.3f}"


if __name__ == "__main__":
    sys.exit(main())
