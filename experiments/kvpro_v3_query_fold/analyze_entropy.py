#!/usr/bin/env python3
"""Phase B — distribution + entropy analysis of the K scale / xmin metadata.

Reports mean/std/CV, min/max/median, percentiles, skew/kurtosis, histogram, unique
values after bf16 storage, effective entropy (bits), dynamic range, proportion near
zero, and proportion in dominant bins — at GLOBAL, per-LAYER, per-HEAD, per-CHANNEL
(series), and per-BLOCK levels. Worst-case reported, not just averages.

  python analyze_entropy.py --manifest meta.pt --kind scale --out-json scale_entropy.json
  python analyze_entropy.py --synthetic random --kind scale     # CPU self-check
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


def entropy_bits(x: torch.Tensor) -> float:
    """Shannon entropy (bits) over the bf16-stored value distribution."""
    xb = x.to(torch.bfloat16).to(torch.float64).reshape(-1)
    vals, counts = torch.unique(xb, return_counts=True)
    p = counts.to(torch.float64) / counts.sum()
    return float(-(p * torch.log2(p.clamp_min(1e-30))).sum())


def dist_stats(x: torch.Tensor, positive: bool) -> Dict[str, float]:
    xf = x.to(torch.float64).reshape(-1)
    n = xf.numel()
    mu = xf.mean().item(); sd = xf.std(unbiased=False).item()
    xc = xf - mu
    sk = float((xc ** 3).mean() / (sd ** 3 + 1e-30))
    ku = float((xc ** 4).mean() / (sd ** 4 + 1e-30))     # non-excess
    qs = torch.quantile(xf, torch.tensor([0.05, 0.25, 0.5, 0.75, 0.95], dtype=torch.float64)).tolist()
    xb = x.to(torch.bfloat16).to(torch.float64)
    n_uniq = int(torch.unique(xb).numel())
    hist = torch.histc(xf.float(), bins=32).tolist()
    dom = sum(sorted(hist, reverse=True)[:3]) / max(sum(hist), 1e-30)   # top-3 bins mass
    if positive:
        mn = xf.min().clamp_min(1e-30).item(); mx = xf.max().item()
        dyn = float(torch.log2(torch.tensor(mx / mn))) if mn > 0 else float("inf")
        near0 = float((xf < 1e-6).to(torch.float64).mean())            # near the scale clamp floor
    else:
        dyn = (xf.max() - xf.min()).item() / (sd + 1e-30)
        near0 = float((xf.abs() < 0.05 * (sd + 1e-30)).to(torch.float64).mean())
    return {"n": n, "mean": mu, "std": sd, "cv": abs(sd / mu) if abs(mu) > 1e-30 else float("inf"),
            "min": xf.min().item(), "max": xf.max().item(), "median": qs[2],
            "p05": qs[0], "p25": qs[1], "p75": qs[3], "p95": qs[4], "skew": sk, "kurtosis": ku,
            "n_unique_bf16": n_uniq, "entropy_bits": round(entropy_bits(x), 4),
            "dynamic_range": round(dyn, 4) if dyn != float("inf") else None,
            "prop_near_zero": round(near0, 4), "prop_dominant_bins": round(dom, 4),
            "hist32": [round(h, 2) for h in hist]}


def run(manifest: dict, kind: str) -> dict:
    positive = (kind == "scale")
    all_vals: List[torch.Tensor] = []
    per_layer: Dict[int, List[torch.Tensor]] = {}
    head_entropy, head_cv, chan_entropy, block_cv = [], [], [], []
    head_loc, chan_loc = [], []
    for meta, M in EC.iter_heads(manifest, kind):           # M: (B, D)
        all_vals.append(M.reshape(-1))
        per_layer.setdefault(meta["layer"], []).append(M.reshape(-1))
        head_entropy.append(entropy_bits(M)); head_cv.append(dist_stats(M, positive)["cv"])
        head_loc.append(meta)
        # per-channel series entropy (across blocks) — median over channels for this head
        ce = [entropy_bits(M[:, d]) for d in range(M.shape[1])]
        chan_entropy.append(median(ce)); chan_loc.append(meta)
        # per-block CV (across channels within a block) — median over blocks
        block_cv.append(median([dist_stats(M[b], positive)["cv"] for b in range(M.shape[0])]))
    g = dist_stats(torch.cat(all_vals), positive)
    layers = {int(li): dist_stats(torch.cat(v), positive) for li, v in sorted(per_layer.items())}
    return {
        "model": manifest.get("model"), "kind": kind, "n_layer_head": len(head_loc),
        "global": g,
        "per_layer_entropy_bits": {li: s["entropy_bits"] for li, s in layers.items()},
        "per_layer_cv": {li: round(s["cv"], 4) for li, s in layers.items()},
        "head_entropy_bits": EC.agg_worst(head_entropy, head_loc, worst="max"),
        "head_cv": EC.agg_worst([c for c in head_cv if c != float("inf")], head_loc, worst="max"),
        "channel_series_entropy_bits": EC.agg_worst(chan_entropy, chan_loc, worst="max"),
        "per_block_cv_median": round(median(block_cv), 4) if block_cv else None,
        "note": ("low entropy_bits + few n_unique_bf16 => codebook-compressible; high per-block CV "
                 "means channels differ a lot within a block (poor per-block scalar)."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata entropy/distribution")
    ap.add_argument("--manifest"); ap.add_argument("--kind", choices=["scale", "xmin"], required=True)
    ap.add_argument("--out-json")
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    a = ap.parse_args(argv)
    man = (synthetic.explore_manifest_synthetic(structure=a.synthetic) if a.synthetic
           else EC.load_explore(a.manifest))
    rep = run(man, a.kind)
    g = rep["global"]
    print(f"[{a.kind}] global: entropy={g['entropy_bits']}bits uniq={g['n_unique_bf16']} cv={g['cv']:.3f} "
          f"dyn={g['dynamic_range']} near0={g['prop_near_zero']} dom_bins={g['prop_dominant_bins']}")
    print(f"  head entropy median={rep['head_entropy_bits']['median']} worst={rep['head_entropy_bits']['worst']} "
          f"| per-block CV median={rep['per_block_cv_median']}")
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
