#!/usr/bin/env python3
"""Phase D — cross-channel / head / layer structure + template clustering.

Tests whether metadata can be represented as `template ID + small local correction`
WITHOUT assuming a low-rank matrix: cross-channel correlation within heads, similarity
of per-channel profiles across heads and layers, and k-means clustering of head
profiles for k ∈ {2,4,8,16} with WORST-case reconstruction error. Scale is clustered
in log space (multiplicative); xmin in linear space.

  python analyze_clustering.py --manifest meta.pt --kind scale --out-json scale_cluster.json
  python analyze_clustering.py --synthetic clustered --kind scale     # CPU self-check
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

_KS = (2, 4, 8, 16)


def _profile(M: torch.Tensor, positive: bool) -> torch.Tensor:
    """Per-channel profile (D,): log-mean over blocks for scale, mean for xmin."""
    return M.clamp_min(1e-8).log().mean(0) if positive else M.mean(0)


def _kmeans(X: torch.Tensor, k: int, iters: int = 30, seed: int = 0):
    N = X.shape[0]; k = min(k, N)
    g = torch.Generator().manual_seed(seed)
    C = X[torch.randperm(N, generator=g)[:k]].clone()
    a = torch.zeros(N, dtype=torch.long)
    for _ in range(iters):
        a = torch.cdist(X, C).argmin(1)
        newC = C.clone()
        for j in range(k):
            m = a == j
            if m.any():
                newC[j] = X[m].mean(0)
        if torch.allclose(newC, C):
            break
        C = newC
    return a, C


def _mean_abs_offdiag_corr(M: torch.Tensor) -> float:
    """Mean |correlation| across channels (columns) within a head's (B,D) matrix."""
    if M.shape[0] < 3:
        return float("nan")
    X = M - M.mean(0, keepdim=True)
    s = X.std(0, unbiased=False).clamp_min(1e-12)
    C = (X.transpose(0, 1) @ X) / (M.shape[0] * s[:, None] * s[None, :])
    D = C.shape[0]
    off = (C.abs().sum() - C.diagonal().abs().sum()) / (D * D - D)
    return float(off)


def run(manifest: dict, kind: str) -> dict:
    positive = (kind == "scale")
    profiles, prof_loc, chan_corr = [], [], []
    layer_profiles: Dict[int, List[torch.Tensor]] = {}
    for meta, M in EC.iter_heads(manifest, kind):          # M: (B, D)
        p = _profile(M, positive)
        profiles.append(p); prof_loc.append(meta)
        layer_profiles.setdefault(meta["layer"], []).append(p)
        c = _mean_abs_offdiag_corr(M)
        if c == c:
            chan_corr.append(c)
    P = torch.stack(profiles)                              # (n_heads_total, D)

    # cross-head profile cosine similarity (mean pairwise)
    Pn = torch.nn.functional.normalize(P, dim=1)
    cos = Pn @ Pn.transpose(0, 1)
    n = P.shape[0]
    head_cos = float((cos.sum() - cos.diagonal().sum()) / max(n * n - n, 1))
    # cross-layer profile cosine
    lp = torch.stack([torch.stack(v).mean(0) for _, v in sorted(layer_profiles.items())])
    lpn = torch.nn.functional.normalize(lp, dim=1)
    lcos = lpn @ lpn.transpose(0, 1)
    m = lp.shape[0]
    layer_cos = float((lcos.sum() - lcos.diagonal().sum()) / max(m * m - m, 1)) if m > 1 else 1.0

    # k-means of head profiles: template coverage + worst-head reconstruction error
    clusters = {}
    for k in _KS:
        if k > n:
            continue
        a, C = _kmeans(P, k)
        recon = C[a]
        # "template ID + small LOCAL CORRECTION": allow one per-head scalar (the level),
        # so the residual measures whether the profile SHAPE clusters (the real question).
        recon_corr = recon + (P - recon).mean(dim=1, keepdim=True)
        per_head_err = ((P - recon_corr).norm(dim=1) / P.norm(dim=1).clamp_min(1e-12)).tolist()
        wi = max(range(len(per_head_err)), key=lambda i: per_head_err[i])
        clusters[f"k{k}"] = {
            "rel_frob_template_only": round(EC.rel_frob(P, recon), 5),
            "rel_frob_template_plus_scalar": round(EC.rel_frob(P, recon_corr), 5),
            "worst_head_rel_err": round(max(per_head_err), 5),
            "worst_loc": {kk: prof_loc[wi].get(kk) for kk in ("layer", "head")},
            "assignments": a.tolist(),
        }
    return {
        "model": manifest.get("model"), "kind": kind, "n_head_profiles": n,
        "mean_abs_channel_corr": EC.agg_worst(chan_corr, prof_loc, worst="min"),
        "cross_head_profile_cosine": round(head_cos, 4),
        "cross_layer_profile_cosine": round(layer_cos, 4),
        "template_clustering": clusters,
        "note": ("high cross-head cosine + low template rel_frob at small k => few reusable templates "
                 "(template ID + local correction). Note: templates cover the per-channel PROFILE; the "
                 "per-block gain is separate (see compare_structure_methods)."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata clustering / templates")
    ap.add_argument("--manifest"); ap.add_argument("--kind", choices=["scale", "xmin"], required=True)
    ap.add_argument("--out-json")
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    a = ap.parse_args(argv)
    man = (synthetic.explore_manifest_synthetic(structure=a.synthetic) if a.synthetic
           else EC.load_explore(a.manifest))
    rep = run(man, a.kind)
    print(f"[{a.kind}] cross-head cosine={rep['cross_head_profile_cosine']} "
          f"cross-layer cosine={rep['cross_layer_profile_cosine']} "
          f"chan-corr med={rep['mean_abs_channel_corr']['median']}")
    for k, c in rep["template_clustering"].items():
        print(f"  {k}: template+scalar rel_frob={c['rel_frob_template_plus_scalar']} "
              f"(template-only {c['rel_frob_template_only']}) worst_head={c['worst_head_rel_err']}")
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
