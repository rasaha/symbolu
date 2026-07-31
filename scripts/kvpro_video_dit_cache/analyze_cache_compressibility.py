"""Video-DiT reused-feature-cache compression — STAGE A ANALYZER (CPU-runnable).

Reads captured cross-step cache tensors (see capture_dit_cache.py / the plan's tensor-capture spec) and
answers the REPRESENTATION-feasibility question: do these persistent cross-step cache objects have
compressible structure, and does PROTECTED low-bit encoding add measurable value over UNIFORM low-bit?

Runs entirely on CPU, no GPU/model. Emits a per-cache-object metrics table + a provisional verdict that
can reach AT MOST 'CONTINUE — representation feasibility only' (systems gates G1-bound-ness/G4/G6 need
GPU — see verdict.py). Cache-object types are analyzed SEPARATELY and never averaged together (plan §7).

Evidence tier for every number here: **Measured — CPU tensor analysis**. Tensor reconstruction fidelity
is a PROXY for output-video quality, not a substitute — Stage B (GPU + generation) settles quality and
all systems gates.

Input: a directory of captured .pt files, each a dict:
  { "cache_object": str in dit_cache_lib.CACHE_OBJECTS, "layer": int, "step_indices": [int,...],
    "tensor": float (T,N,C), "dtype": "bf16"|"fp16"|"fp32", "meta": {...} }
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import torch

import dit_cache_lib as L
import verdict as V

PROTECT_FRAC = 0.04
INT8_BITS, INT4_BITS = 8, 4
BLOCK = 32
LOWRANK_FRAC = 0.05


def analyze_object(tensor: torch.Tensor, meta: dict) -> dict:
    """All Stage-A representation metrics for ONE captured cache object (T,N,C)."""
    x = tensor.float()
    if x.ndim == 2:
        x = x.unsqueeze(0)
    T, N, C = x.shape
    base_bits = {"bf16": 16, "fp16": 16, "fp32": 32}.get(meta.get("dtype", "bf16"), 16)

    ch_mask = L.top_channel_mask(x, PROTECT_FRAC)

    # ---- distribution / structure ----
    ch_conc = L.concentration_ratio(L.channel_rms(x), PROTECT_FRAC)
    tok_conc = L.concentration_ratio(L.token_rms(x), PROTECT_FRAC)
    row = {
        "cache_object": meta.get("cache_object", "?"),
        "layer": meta.get("layer", -1),
        "T": T, "N": N, "C": C,
        "bytes_per_snapshot": round(N * C * base_bits / 8, 1),
        "persistent_residency_bytes": round(T * N * C * base_bits / 8, 1),
        "channel_concentration_ratio": round(ch_conc, 3),
        "token_concentration_ratio": round(tok_conc, 3),
        "channel_kurtosis": round(L.kurtosis(L.channel_rms(x)), 2),
        "dynamic_range_db": round(L.dynamic_range_db(x), 1),
        "entropy_bits": round(L.entropy_bits(x), 3),
    }
    row.update(L.temporal_redundancy(x))
    row.update(L.spatial_redundancy(x))

    # ---- uniform vs per-channel vs per-block quant error (INT8 & INT4) ----
    for bits, tag in ((INT8_BITS, "int8"), (INT4_BITS, "int4")):
        x_ptensor = L.quantize_uniform(x, bits, "per_tensor")
        x_pchan = L.quantize_uniform(x, bits, "per_channel")
        x_pblock = L.quantize_uniform(x, bits, "per_block", block_size=BLOCK)
        row[f"{tag}_per_tensor_rel_l2"] = round(L.rel_l2(x, x_ptensor), 5)
        row[f"{tag}_per_channel_rel_l2"] = round(L.rel_l2(x, x_pchan), 5)
        row[f"{tag}_per_block_rel_l2"] = round(L.rel_l2(x, x_pblock), 5)

    # ---- protected vs uniform (the G5 question), at INT4 per-block ----
    x_uniform4 = L.quantize_uniform(x, INT4_BITS, "per_block", block_size=BLOCK)
    x_prot4 = L.protected_quantize(x, INT4_BITS, ch_mask, granularity="per_block", block_size=BLOCK)
    e_uniform4 = L.rel_l2(x, x_uniform4)
    e_prot4 = L.rel_l2(x, x_prot4)
    row["int4_uniform_rel_l2"] = round(e_uniform4, 5)
    row["int4_protected_rel_l2"] = round(e_prot4, 5)
    row["uniform_vs_protected_err_ratio"] = round(e_uniform4 / (e_prot4 + 1e-12), 3)
    row["protected_cosine"] = round(L.cosine_sim(x, x_prot4), 6)

    # ---- quant + low-rank residual ----
    x_lr = L.lowrank_residual_reconstruct(x, x_uniform4, rank=max(1, int(round(LOWRANK_FRAC * min(N, C)))))
    row["int4_lowrank_residual_rel_l2"] = round(L.rel_l2(x, x_lr), 5)

    # ---- byte accounting (net density after overheads) ----
    ba = L.byte_account(x, INT4_BITS, "per_block", protect_frac=PROTECT_FRAC, block_size=BLOCK, baseline_bits=base_bits)
    row["net_density_x"] = ba["net_density_x"]
    row["scale_meta_bytes"] = ba["scale_meta_bytes"]

    # ---- error accumulation over repeated reuse (protected int4) ----
    enc = lambda t: L.protected_quantize(t, INT4_BITS, ch_mask, granularity="per_block", block_size=BLOCK)  # noqa: E731
    acc = L.error_accumulation(x, enc, reuse_len=min(8, max(2, T)))
    row["reuse_error_growth_x"] = acc["error_growth_x"]
    row["reuse_error_bounded"] = acc["bounded"]

    # ---- gate admission/rejection over snapshots (illustrative frozen-style rule) ----
    rule = {"max_rel_l2": V.FROZEN_GATES["g3_max_cache_rel_l2"], "min_cosine": V.FROZEN_GATES["g3_min_cache_cosine"]}
    admits = 0
    for t in range(T):
        hat = L.protected_quantize(x[t], INT4_BITS, ch_mask, granularity="per_block", block_size=BLOCK)
        if L.gate_admit(x[t], hat, rule)["admit"]:
            admits += 1
    row["gate_admission_rate"] = round(admits / T, 3)
    row["gate_rejection_rate"] = round(1 - admits / T, 3)
    return row


def load_objects(path: str):
    files = sorted(glob.glob(os.path.join(path, "*.pt"))) if os.path.isdir(path) else [path]
    for f in files:
        blob = torch.load(f, map_location="cpu", weights_only=False)
        yield os.path.basename(f), blob


def run(path: str, out_json: str, out_csv: str) -> dict:
    rows = []
    for name, blob in load_objects(path):
        meta = {k: blob.get(k) for k in ("cache_object", "layer", "dtype", "step_indices", "meta")}
        meta.setdefault("dtype", blob.get("dtype", "bf16"))
        r = analyze_object(blob["tensor"], meta)
        r["source"] = name
        rows.append(r)

    # ---- aggregate the DOMINANT cache object for the provisional verdict (never average across types) ----
    by_obj = {}
    for r in rows:
        by_obj.setdefault(r["cache_object"], []).append(r)

    def obj_summary(rs):
        n = len(rs)
        return {
            "layers": n,
            "persistent_residency_bytes": round(sum(r["persistent_residency_bytes"] for r in rs), 1),
            "channel_concentration_ratio_mean": round(sum(r["channel_concentration_ratio"] for r in rs) / n, 3),
            "net_density_x_mean": round(sum(r["net_density_x"] for r in rs) / n, 3),
            "int4_protected_rel_l2_mean": round(sum(r["int4_protected_rel_l2"] for r in rs) / n, 5),
            "protected_cosine_mean": round(sum(r["protected_cosine"] for r in rs) / n, 6),
            "uniform_vs_protected_err_ratio_mean": round(sum(r["uniform_vs_protected_err_ratio"] for r in rs) / n, 3),
        }

    obj_summaries = {obj: obj_summary(rs) for obj, rs in by_obj.items()}
    dominant = max(obj_summaries, key=lambda o: obj_summaries[o]["persistent_residency_bytes"]) if obj_summaries else None

    provisional = None
    if dominant:
        s = obj_summaries[dominant]
        evidence = {
            "cache_bytes": s["persistent_residency_bytes"],           # capacity side only (Modeled at this scale)
            "net_density_x": s["net_density_x_mean"],                 # Measured — CPU
            "cache_rel_l2": s["int4_protected_rel_l2_mean"],          # Measured — CPU (tensor proxy)
            "cache_cosine": s["protected_cosine_mean"],               # Measured — CPU (tensor proxy)
            "uniform_vs_protected_err_ratio": s["uniform_vs_protected_err_ratio_mean"],  # Measured — CPU
            # NO systems fields -> verdict caps at 'representation feasibility only' by construction.
        }
        provisional = V.decide(evidence)  # uses FROZEN_GATES defaults; caller re-freezes after calibration

    summary = {
        "int_math": L.INT_MATH,
        "protect_frac": PROTECT_FRAC,
        "block_size": BLOCK,
        "objects_analyzed": sorted(by_obj),
        "dominant_cache_object_by_residency": dominant,
        "per_object_summary": obj_summaries,
        "provisional_verdict": provisional,
        "evidence_tier": "Measured — CPU tensor analysis (representation only; systems gates REQUIRE GPU)",
        "caveat": ("CPU analysis cannot establish whether the workload is capacity-, bandwidth-, "
                   "communication-, or compute-bound; tensor fidelity is a proxy for output-video quality."),
    }
    if out_csv and rows:
        with open(out_csv, "w", newline="") as f:
            keys = sorted({k for r in rows for k in r})
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        json.dump(summary, open(out_json, "w"), indent=2)
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage A: video-DiT cache-compressibility analyzer (CPU)")
    ap.add_argument("--cache", required=True, help=".pt file or directory of captured cross-step cache tensors")
    ap.add_argument("--out-json", default="artifacts/video_dit_cache/stageA_verdict.json")
    ap.add_argument("--out-csv", default="artifacts/video_dit_cache/stageA_metrics.csv")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    run(args.cache, args.out_json, args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
