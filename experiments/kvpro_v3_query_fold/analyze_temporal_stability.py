#!/usr/bin/env python3
"""Phase C — temporal / block stability of the K scale / xmin metadata.

For every (layer, head, channel) block-series, reports lag-1/2/4 autocorrelation,
mean/normalized block-to-block change, fraction of transitions within relative-change
bands, change-point frequency, and run-lengths of ~constant values — then classifies
the metadata as slowly-drifting / piecewise-constant / abrupt-noisy. Full blocks and
the partial trailing block are reported separately. Worst-case, not just averages.

  python analyze_temporal_stability.py --manifest meta.pt --kind scale --out-json scale_temporal.json
  python analyze_temporal_stability.py --synthetic piecewise --kind scale    # CPU self-check
"""
from __future__ import annotations

import argparse
import json
from statistics import median
from typing import Dict, List

import torch

try:
    from . import explore_common as EC, synthetic
except ImportError:  # pragma: no cover
    import explore_common as EC  # type: ignore
    import synthetic             # type: ignore

_REL_BANDS = (0.02, 0.05, 0.10, 0.25)


def _autocorr(s: torch.Tensor, lag: int) -> float:
    if s.numel() <= lag:
        return float("nan")
    a, b = s[:-lag], s[lag:]
    a = a - a.mean(); b = b - b.mean()
    den = (a.norm() * b.norm()).item()
    return (a * b).sum().item() / den if den > 1e-12 else float("nan")


def _run_lengths(s: torch.Tensor, rel_tol: float = 0.02) -> List[int]:
    """Lengths of runs where the value stays within rel_tol of the run's start."""
    runs, start = [], 0
    for i in range(1, s.numel()):
        base = abs(s[start].item()) + 1e-12
        if abs(s[i].item() - s[start].item()) / base > rel_tol:
            runs.append(i - start); start = i
    runs.append(s.numel() - start)
    return runs


def series_stats(s: torch.Tensor) -> Dict[str, float]:
    d = (s[1:] - s[:-1]).abs()
    base = s[:-1].abs().clamp_min(1e-12)
    rel = d / base
    sd = s.std(unbiased=False).item() + 1e-12
    runs = _run_lengths(s)
    return {
        "lag1": _autocorr(s, 1), "lag2": _autocorr(s, 2), "lag4": _autocorr(s, 4),
        "mean_abs_change": d.mean().item() if d.numel() else 0.0,
        "norm_change": (d.mean().item() / sd) if d.numel() else 0.0,
        **{f"frac_within_{int(b*100)}pct": float((rel <= b).to(torch.float64).mean()) if rel.numel() else 1.0
           for b in _REL_BANDS},
        "changepoint_freq": float(((d / sd) > 2.0).to(torch.float64).mean()) if d.numel() else 0.0,
        "mean_run_len": sum(runs) / len(runs), "max_run_len": max(runs),
    }


def _classify(lag1_med, frac5_med, run_frac):
    if lag1_med is None:
        return "unknown"
    if run_frac >= 0.6 or frac5_med >= 0.7:
        return "piecewise_constant_or_slow"
    if lag1_med >= 0.7:
        return "slowly_drifting"
    if lag1_med <= 0.2:
        return "abrupt_noisy"
    return "mixed"


def run(manifest: dict, kind: str) -> dict:
    lag1, lag2, lag4, norm_ch, frac5, cp, run_frac = [], [], [], [], [], [], []
    loc = []
    tail_dev = []       # partial-tail (last block) relative deviation from the prior block
    n_blocks = manifest["geom"]["n_blocks"]
    for meta, M in EC.iter_heads(manifest, kind):          # M: (B, D)
        B = M.shape[0]
        full = M[:-1] if B >= 3 else M                     # exclude partial trailing block
        for d in range(M.shape[1]):
            st = series_stats(full[:, d])
            if st["lag1"] == st["lag1"]:                   # not NaN
                lag1.append(st["lag1"]); lag2.append(st["lag2"]); lag4.append(st["lag4"])
                norm_ch.append(st["norm_change"]); frac5.append(st["frac_within_5pct"])
                cp.append(st["changepoint_freq"]); run_frac.append(st["max_run_len"] / max(full.shape[0], 1))
                loc.append(meta)
        if B >= 2:                                         # partial-tail vs prior full block
            base = M[-2].abs().clamp_min(1e-12)
            tail_dev.append(float(((M[-1] - M[-2]).abs() / base).median()))
    lag1_med = median(lag1) if lag1 else None
    cls = _classify(lag1_med, median(frac5) if frac5 else None, median(run_frac) if run_frac else 0.0)
    return {
        "model": manifest.get("model"), "kind": kind, "n_series": len(loc), "n_blocks": n_blocks,
        "lag1": EC.agg_worst(lag1, loc, worst="min"), "lag2": EC.agg_worst(lag2, loc, worst="min"),
        "lag4": EC.agg_worst(lag4, loc, worst="min"),
        "norm_block_change": EC.agg_worst(norm_ch, loc, worst="max"),
        "frac_within_5pct": EC.agg_worst(frac5, loc, worst="min"),
        "changepoint_freq": EC.agg_worst(cp, loc, worst="max"),
        "max_run_frac": EC.agg_worst(run_frac, loc, worst="min"),
        "partial_tail_median_rel_dev": round(median(tail_dev), 4) if tail_dev else None,
        "classification": cls,
        "note": ("high lag1 + long runs => temporally stable (delta/piecewise coding viable); low lag1 "
                 "+ high changepoint_freq => abrupt, no temporal win. Partial tail reported separately."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata temporal stability")
    ap.add_argument("--manifest"); ap.add_argument("--kind", choices=["scale", "xmin"], required=True)
    ap.add_argument("--out-json")
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    a = ap.parse_args(argv)
    man = (synthetic.explore_manifest_synthetic(structure=a.synthetic) if a.synthetic
           else EC.load_explore(a.manifest))
    rep = run(man, a.kind)
    print(f"[{a.kind}] class={rep['classification']} | lag1 med={rep['lag1']['median']} "
          f"worst={rep['lag1']['worst']} | max_run_frac med={rep['max_run_frac']['median']} | "
          f"changepoint worst={rep['changepoint_freq']['worst']} | tail_dev={rep['partial_tail_median_rel_dev']}")
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
