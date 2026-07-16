#!/usr/bin/env python3
"""Phase F — neutral comparison of candidate metadata representations.

Ten methods, no method privileged. For each: reconstruction error (median + WORST
layer/head/block), metadata values kept per block, bytes saved, whether it REDUCES
PER-ELEMENT HOT-PATH WORK (folds the affine off the per-element path) vs merely
compresses storage, and static / block-varying / prompt-dependent classification.

Crucial honesty (task constraint): a method that saves metadata bytes but still
reconstructs per element (piecewise / codebook / delta / sparse) does NOT reduce
hot-path work — it is flagged `reduces_per_element_work=False`.

  python compare_structure_methods.py --manifest meta.pt --kind scale --out-json scale_methods.json
  python compare_structure_methods.py --synthetic low_rank --kind scale     # CPU self-check
"""
from __future__ import annotations

import argparse
import csv
import json
from statistics import median
from typing import Dict, List

import torch

try:
    from . import explore_common as EC, factorize, synthetic
    from .analyze_clustering import _kmeans
except ImportError:  # pragma: no cover
    import explore_common as EC  # type: ignore
    import factorize             # type: ignore
    import synthetic             # type: ignore
    from analyze_clustering import _kmeans  # type: ignore

_SCLAMP = 1e-8


def _worst_block_err(M, Mh):
    e = ((M - Mh).norm(dim=1) / M.norm(dim=1).clamp_min(1e-12))
    return float(e.max())


# ---- per-head reconstruction methods: return (M_hat, block_meta, chan_meta, reduces_work, cls) ----
def _rank1_linear(M, pos):
    f = factorize.low_rank_svd(M, 1); return f["fitted"], 1, M.shape[1], True, "block_varying"

def _rank1_log(M, pos):
    if pos:
        f = factorize.rank1_log_multiplicative(M); return f["fitted"], 1, M.shape[1], True, "block_varying"
    f = factorize.two_way_additive(M); return f["fitted"], 1, M.shape[1], True, "block_varying"

def _svd(M, pos, R):
    f = factorize.low_rank_svd(M, R); return f["fitted"], R, R * M.shape[1], True, "block_varying"

def _piecewise(M, pos, rel_tol=0.05):
    B, D = M.shape; seg_val = M[0].clone(); Mh = torch.empty_like(M); n_seg = 1; start = 0
    Mh[0] = M[0]
    for b in range(1, B):
        if (M[b] - M[start]).norm() / M[start].norm().clamp_min(1e-12) > rel_tol:
            start = b; n_seg += 1
        Mh[b] = M[start]
    # metadata: one D-vector per segment -> amortized D*n_seg/B values per block; per-element reconstruct stays
    return Mh, round(D * n_seg / B, 2), 0, False, "block_varying_compress"

def _kmeans_vq(M, pos, k=4):
    B, D = M.shape; k = min(k, B)
    a, C = _kmeans(M, k); Mh = C[a]
    return Mh, 0, k * D, False, "block_varying_compress"      # codeword id/block (~0) + k*D codebook

def _per_head_template(M, pos):
    if pos:
        prof = M.clamp_min(_SCLAMP).log().mean(0); gain = (M.clamp_min(_SCLAMP).log() - prof).mean(1)
        Mh = torch.exp(prof[None, :] + gain[:, None])
    else:
        prof = M.mean(0); gain = (M - prof).mean(1); Mh = prof[None, :] + gain[:, None]
    return Mh, 1, M.shape[1], True, "static_template_plus_block_scalar"

def _channel_baseline_sparse(M, pos, keep=0.1):
    base = M.mean(0); resid = M - base
    thr = torch.quantile(resid.abs().reshape(-1), 1 - keep)
    Mh = base[None, :] + torch.where(resid.abs() >= thr, resid, torch.zeros_like(resid))
    return Mh, round(keep * M.shape[1], 1), M.shape[1], False, "block_varying_compress"

def _codebook(M, pos, k=16):
    # low-entropy codebook: uniform k-level quantization over the value range (O(N),
    # not per-head k-means). Same "can k codes represent these values" question, fast.
    import math
    lo, hi = M.min(), M.max()
    if (hi - lo).abs() < 1e-30:
        return M.clone(), round(M.shape[1] * math.log2(max(k, 2)) / 16.0, 2), k, False, "block_varying_compress"
    edges = torch.linspace(float(lo), float(hi), k + 1, dtype=M.dtype)
    idx = torch.bucketize(M, edges[1:-1].contiguous())
    centers = 0.5 * (edges[:-1] + edges[1:])
    Mh = centers[idx.clamp(max=k - 1)]
    return Mh, round(M.shape[1] * math.log2(max(k, 2)) / 16.0, 2), k, False, "block_varying_compress"

def _delta_prev(M, pos):
    # lossless reconstruction; "savings" only if deltas are low-entropy (temporal). Per-element stays.
    Mh = M.clone(); d = (M[1:] - M[:-1]).abs()
    small = float((d < 0.05 * M[:-1].abs().clamp_min(1e-12)).to(torch.float64).mean()) if d.numel() else 1.0
    bm = round(M.shape[1] * (1 - 0.5 * small), 2)             # heuristic: low-entropy deltas compress
    return Mh, bm, M.shape[1], False, "block_varying_compress"

_METHODS = {
    "rank1_multiplicative": lambda M, p: _rank1_linear(M, p),
    "rank1_log_additive":   lambda M, p: _rank1_log(M, p),
    "svd_R2":               lambda M, p: _svd(M, p, 2),
    "svd_R4":               lambda M, p: _svd(M, p, 4),
    "piecewise_const":      lambda M, p: _piecewise(M, p),
    "kmeans_vq":            lambda M, p: _kmeans_vq(M, p),
    "per_head_template":    lambda M, p: _per_head_template(M, p),
    "channel_baseline_sparse": lambda M, p: _channel_baseline_sparse(M, p),
    "codebook":             lambda M, p: _codebook(M, p),
    "delta_prev":           lambda M, p: _delta_prev(M, p),
}


def run(manifest: dict, kind: str) -> dict:
    pos = (kind == "scale"); D = manifest["geom"]["D"]
    acc: Dict[str, dict] = {m: {"rf": [], "wb": [], "loc": [], "bm": None, "cm": None,
                                "rw": None, "cls": None} for m in _METHODS}
    # per-head methods
    n = 0
    for meta, M in EC.iter_heads(manifest, kind):
        for name, fn in _METHODS.items():
            Mh, bm, cm, rw, cls = fn(M, pos)
            a = acc[name]
            a["rf"].append(EC.rel_frob(M, Mh)); a["wb"].append(_worst_block_err(M, Mh))
            a["loc"].append(meta); a["bm"], a["cm"], a["rw"], a["cls"] = bm, cm, rw, cls
        n += 1
        if n % 200 == 0:
            print(f"  [methods/{kind}] {n} heads...", flush=True)
    # per-layer template (needs cross-head): layer profile shared across its heads
    pl = _per_layer_template(manifest, kind, pos)

    out = {"model": manifest.get("model"), "kind": kind, "D": D, "methods": {}}
    for name, a in acc.items():
        wi = max(range(len(a["rf"])), key=lambda i: a["rf"][i])
        bytes_saved = round(100.0 * (D - a["bm"]) / D, 2) if isinstance(a["bm"], (int, float)) else None
        out["methods"][name] = {
            "rel_frob_median": round(median(a["rf"]), 5), "rel_frob_worst": round(a["rf"][wi], 5),
            "worst_loc": {k: a["loc"][wi].get(k) for k in ("layer", "head")},
            "worst_block_rel_err": round(max(a["wb"]), 5),
            "block_meta_values": a["bm"], "channel_meta_values": a["cm"],
            "metadata_bytes_saved_pct": bytes_saved,
            "reduces_per_element_work": a["rw"], "classification": a["cls"],
        }
    out["methods"]["per_layer_template"] = pl
    return out


def _per_layer_template(manifest, kind, pos):
    key = "s_prod" if kind == "scale" else "xmin_prod"
    rf, wb, D = [], [], manifest["geom"]["D"]
    # layer template = mean per-channel profile over that layer's heads (first capture)
    for cap in manifest["captures"][:1]:
        for lyr in cap["layers"]:
            M = lyr[key].to(torch.float64)                    # (B,H,D)
            prof = (M.clamp_min(_SCLAMP).log().mean((0, 1)) if pos else M.mean((0, 1)))  # (D,)
            for h in range(M.shape[1]):
                Mh = M[:, h, :]
                if pos:
                    gain = (Mh.clamp_min(_SCLAMP).log() - prof).mean(1)
                    rec = torch.exp(prof[None, :] + gain[:, None])
                else:
                    gain = (Mh - prof).mean(1); rec = prof[None, :] + gain[:, None]
                rf.append(EC.rel_frob(Mh, rec)); wb.append(_worst_block_err(Mh, rec))
    return {"rel_frob_median": round(median(rf), 5), "rel_frob_worst": round(max(rf), 5),
            "worst_block_rel_err": round(max(wb), 5), "block_meta_values": 1,
            "channel_meta_values": D, "metadata_bytes_saved_pct": round(100.0 * (D - 1) / D, 2),
            "reduces_per_element_work": True,
            "classification": "static_template_shared_across_heads_plus_block_scalar"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata structure-method comparison")
    ap.add_argument("--manifest"); ap.add_argument("--kind", choices=["scale", "xmin"], required=True)
    ap.add_argument("--out-json"); ap.add_argument("--out-csv")
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    a = ap.parse_args(argv)
    man = (synthetic.explore_manifest_synthetic(structure=a.synthetic) if a.synthetic
           else EC.load_explore(a.manifest))
    rep = run(man, a.kind)
    print(f"[{a.kind}] method comparison ({rep['model']})")
    for name, m in sorted(rep["methods"].items(), key=lambda kv: kv[1]["rel_frob_median"]):
        print(f"  {name:24} rf_med={m['rel_frob_median']:.4f} worst={m['rel_frob_worst']:.4f} "
              f"bytes_saved={m['metadata_bytes_saved_pct']}% reduces_work={m['reduces_per_element_work']} "
              f"[{m['classification']}]")
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    if a.out_csv:
        with open(a.out_csv, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["method", "rel_frob_median", "rel_frob_worst",
                "worst_block_rel_err", "block_meta_values", "metadata_bytes_saved_pct",
                "reduces_per_element_work", "classification"])
            for name, m in rep["methods"].items():
                w.writerow([name, m["rel_frob_median"], m["rel_frob_worst"], m["worst_block_rel_err"],
                            m["block_meta_values"], m["metadata_bytes_saved_pct"],
                            m["reduces_per_element_work"], m["classification"]])
        print(f"  -> {a.out_csv}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
