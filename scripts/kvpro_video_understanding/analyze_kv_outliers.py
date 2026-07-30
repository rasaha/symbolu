"""KVPro × video-understanding — feasibility ANALYZER (CPU-runnable).

Decides whether KVPro's channel-protected INT4 KV compression is likely to transfer from text tokens
to VISUAL tokens in a VLM (e.g. Qwen2.5-VL). Runs on captured K/V tensors (see capture_vlm_kv.py);
needs no GPU/model — this is the cheap, decisive part of the feasibility gate.

KVPro's quality trick works only if a small set of channels carries outsized magnitude/importance
(the "protected" channels). This script asks, per token type (visual vs text):
  1. STRUCTURE  — do a few channels dominate? (top-p% energy share, kurtosis)
  2. PROTECTION — does keeping the top-p% channels exact meaningfully cut INT4 reconstruction error?
  3. TRANSFER   — do the visual outlier channels overlap the text ones? (can one static mask cover both?)

Pre-registered GO/NO-GO gates are fixed in DEFAULT_GATES below (see the plan doc). Self-contained INT4
math mirrors the production per-channel affine intent; the feasibility signal (does protection help
visual KV) is representation-granularity-agnostic.

Input: a .pt dict with keys {"k": (S,H,D) float, "token_type": (S,) int (1=visual, 0=text), "layer": int}
       or a directory of such per-layer files. Output: JSON verdict + per-metric CSV.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

import torch

PROTECT_FRAC = 0.04          # KVPro's 4% channel budget
_ASYM = 15.0                 # unsigned int4
_CLAMP = 1e-8

DEFAULT_GATES = {
    "structure_concentration_ratio_min": 3.0,   # top-4% channels hold >=3x their "fair share" of energy
    "protection_benefit_min": 1.30,             # int4-only err / int4+protect err  >= 1.30 on visual KV
    "mask_transfer_iou_min": 0.50,              # visual vs text top-channel overlap >= 0.50 (else combined mask)
    "combined_mask_budget_x_max": 2.0,          # a union mask may cost <= 2x the 4% budget and still be OK
}


def channel_rms(x):                 # x: (S,H,D) -> (H,D)
    return x.float().pow(2).mean(dim=0).sqrt()


def concentration_ratio(mags, frac):
    """(energy share of top-frac channels) / frac.  ~1 = uniform; >>1 = concentrated outliers."""
    flat = mags.flatten().pow(2)
    k = max(1, int(round(frac * flat.numel())))
    top = torch.topk(flat, k).values.sum()
    share = (top / (flat.sum() + 1e-12)).item()
    return share / frac, share


def kurtosis(mags):
    v = mags.flatten().float()
    m = v.mean(); s = v.std() + 1e-12
    return ((v - m).pow(4).mean() / s.pow(4)).item()


def top_channel_mask(mags, frac):
    """Per-head top-frac channels -> bool (H,D)."""
    H, D = mags.shape
    k = max(1, int(round(frac * D)))
    mask = torch.zeros_like(mags, dtype=torch.bool)
    idx = torch.topk(mags, k, dim=1).indices          # (H,k)
    mask.scatter_(1, idx, True)
    return mask


def int4_affine_per_channel(x):     # simplified INT4: per-(h,d) affine over tokens
    xf = x.float()
    mn = xf.amin(dim=0, keepdim=True); mx = xf.amax(dim=0, keepdim=True)
    scale = ((mx - mn) / _ASYM).clamp(min=_CLAMP)
    q = ((xf - mn) / scale).round().clamp(0, _ASYM)
    return q * scale + mn


def rel_l2(ref, test, restrict=None):
    a, b = ref.float(), test.float()
    if restrict is not None:
        m = restrict.view(1, *restrict.shape).expand_as(a)
        a, b = a[m], b[m]
    return (torch.linalg.vector_norm(b - a) / (torch.linalg.vector_norm(a) + 1e-12)).item()


def analyze_subset(x, frac):
    """x: (S,H,D) for one token type. Returns metrics dict + top-channel mask."""
    if x.shape[0] < 2:
        return None, None
    mags = channel_rms(x)
    cratio, share = concentration_ratio(mags, frac)
    mask = top_channel_mask(mags, frac)
    x_int4 = int4_affine_per_channel(x)
    x_prot = torch.where(mask.view(1, *mask.shape).expand_as(x), x.float(), x_int4)
    e_int4 = rel_l2(x, x_int4)
    e_prot = rel_l2(x, x_prot)
    benefit = e_int4 / (e_prot + 1e-12)
    return ({
        "n_tokens": int(x.shape[0]),
        "concentration_ratio": round(cratio, 3),
        "top_channel_energy_share": round(share, 4),
        "kurtosis": round(kurtosis(mags), 2),
        "int4_rel_l2": round(e_int4, 5),
        "int4_protect_rel_l2": round(e_prot, 5),
        "protection_benefit_x": round(benefit, 3),
    }, mask)


def iou(a, b):
    inter = (a & b).sum().item(); union = (a | b).sum().item()
    return inter / union if union else 0.0


def load_layers(path):
    files = sorted(glob.glob(os.path.join(path, "*.pt"))) if os.path.isdir(path) else [path]
    for f in files:
        blob = torch.load(f, map_location="cpu", weights_only=False)
        yield os.path.basename(f), blob


def run(path, gates, out_json, out_csv):
    rows, agg = [], {"visual": [], "text": []}
    for name, blob in load_layers(path):
        k = blob["k"].float()
        tt = blob["token_type"].to(torch.int64)
        vis = k[tt == 1]; txt = k[tt == 0]
        mv, mask_v = analyze_subset(vis, PROTECT_FRAC)
        mt, mask_t = analyze_subset(txt, PROTECT_FRAC)
        row = {"source": name, "layer": blob.get("layer", -1)}
        if mv: row.update({f"visual_{k2}": v for k2, v in mv.items()})
        if mt: row.update({f"text_{k2}": v for k2, v in mt.items()})
        if mask_v is not None and mask_t is not None:
            row["mask_iou_visual_vs_text"] = round(iou(mask_v, mask_t), 3)
            union = mask_v | mask_t
            row["combined_mask_budget_x"] = round(union.float().mean().item() / PROTECT_FRAC, 3)
        rows.append(row)
        if mv: agg["visual"].append(mv);
        if mt: agg["text"].append(mt)

    def mean(key, cell):
        vals = [m[key] for m in agg[cell] if key in m]
        return sum(vals) / len(vals) if vals else float("nan")

    ious = [r["mask_iou_visual_vs_text"] for r in rows if "mask_iou_visual_vs_text" in r]
    comb = [r["combined_mask_budget_x"] for r in rows if "combined_mask_budget_x" in r]
    summary = {
        "protect_frac": PROTECT_FRAC, "layers_analyzed": len(rows),
        "visual_concentration_ratio_mean": round(mean("concentration_ratio", "visual"), 3),
        "text_concentration_ratio_mean": round(mean("concentration_ratio", "text"), 3),
        "visual_protection_benefit_mean": round(mean("protection_benefit_x", "visual"), 3),
        "text_protection_benefit_mean": round(mean("protection_benefit_x", "text"), 3),
        "mask_iou_mean": round(sum(ious) / len(ious), 3) if ious else None,
        "combined_mask_budget_x_mean": round(sum(comb) / len(comb), 3) if comb else None,
    }
    # ---- pre-registered gates ----
    g1 = summary["visual_concentration_ratio_mean"] >= gates["structure_concentration_ratio_min"]
    g2 = summary["visual_protection_benefit_mean"] >= gates["protection_benefit_min"]
    g3_iou = (summary["mask_iou_mean"] or 0) >= gates["mask_transfer_iou_min"]
    g3_comb = (summary["combined_mask_budget_x_mean"] or 99) <= gates["combined_mask_budget_x_max"]
    g3 = g3_iou or g3_comb
    if g1 and g2 and g3:
        verdict = "GO" if g3_iou else "GO_WITH_COMBINED_MASK"
    elif g1 and g2 and not g3:
        verdict = "GO_BUT_MASK_DOES_NOT_TRANSFER (visual needs its own mask)"
    elif g1 and not g2:
        verdict = "NO_GO_PROTECTION (outliers exist but protection doesn't cut error like text)"
    else:
        verdict = "NO_GO_STRUCTURE (visual KV lacks the concentrated-outlier structure protection needs)"
    summary["gates"] = {"structure": bool(g1), "protection": bool(g2),
                        "mask_transfer_iou": bool(g3_iou), "mask_transfer_combined": bool(g3_comb)}
    summary["gate_thresholds"] = gates
    summary["VERDICT"] = verdict

    if out_csv and rows:
        with open(out_csv, "w", newline="") as f:
            keys = sorted({k for r in rows for k in r})
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    if out_json:
        json.dump(summary, open(out_json, "w"), indent=2)
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro video-understanding feasibility analyzer (CPU)")
    ap.add_argument("--kv", required=True, help=".pt file or directory of captured per-layer KV")
    ap.add_argument("--out-json", default="artifacts/kvpro_video/feasibility_verdict.json")
    ap.add_argument("--out-csv", default="artifacts/kvpro_video/kv_outlier_metrics.csv")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    run(args.kv, DEFAULT_GATES, args.out_json, args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
