#!/usr/bin/env python3
"""Phase F — attention-level evaluator.

For captured real Q/K/V, reconstruct K under each candidate (V is production affine
for all; protected K channels exact), then compare each candidate against full
precision AND against the current-affine arm. Emits per-candidate metrics + the
baseline-RELATIVE deltas the attention gate uses.

  python evaluate_attention.py --manifest capture.pt --out-json attention_metrics.json
  python evaluate_attention.py --synthetic factorable      # CPU self-check
"""
from __future__ import annotations

import argparse
import json
from statistics import mean
from typing import Dict, List

try:
    from . import attn_metrics, candidates, quant_ref, synthetic
except ImportError:  # pragma: no cover
    import attn_metrics    # type: ignore
    import candidates      # type: ignore
    import quant_ref       # type: ignore
    import synthetic       # type: ignore

# keys used by the (baseline-relative) attention gate
_REL_KEYS = ("attn_out_cos", "softmax_kl", "topk_overlap")


def run(manifest: dict, topk: int = 10, v_group_size: int = 32, BS: int = 32) -> dict:
    per_layer: Dict[str, List[dict]] = {}
    for lyr in manifest["layers"]:
        K = lyr["K"].float(); V = lyr["V"].float(); Q = lyr["Q"].float()
        mask = lyr["protect_mask"]
        V_hat = quant_ref.production_v(V, v_group_size)          # identical across candidates
        for cand in candidates.candidate_names():
            K_hat = candidates.reconstruct_k(K, lyr["s_prod"], lyr["xmin_prod"], mask, cand, BS)
            m = attn_metrics.metrics(Q, K, V, K_hat, V_hat, mask, topk)
            per_layer.setdefault(cand, []).append({"layer": lyr["layer"], **m})

    agg: Dict[str, dict] = {}
    for cand, rows in per_layer.items():
        keys = [k for k in rows[0] if k != "layer"]
        agg[cand] = {k: round(mean([r[k] for r in rows if k in r]), 6) for k in keys}

    aff = agg.get("affine", {})
    rel: Dict[str, dict] = {}
    for cand, m in agg.items():
        if cand == "affine":
            continue
        rel[cand] = {
            "attn_out_cos_minus_affine": round(m.get("attn_out_cos", 0) - aff.get("attn_out_cos", 0), 6),
            "softmax_kl_ratio_to_affine": round(m.get("softmax_kl", 0) / max(aff.get("softmax_kl", 0), 1e-12), 4),
            "topk_overlap_minus_affine": round(m.get("topk_overlap", 0) - aff.get("topk_overlap", 0), 6),
        }
    return {"model_name": manifest.get("model"), "topk": topk,
            "per_candidate": agg, "relative_to_affine": rel,
            "n_layers": len(manifest["layers"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 query-fold attention evaluator")
    ap.add_argument("--manifest")
    ap.add_argument("--out-json")
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--synthetic", choices=["factorable", "random"])
    a = ap.parse_args(argv)
    if a.synthetic:
        man = synthetic.synthetic_capture(n_layers=2, factorable=(a.synthetic == "factorable"))
    elif a.manifest:
        import torch
        man = torch.load(a.manifest, map_location="cpu", weights_only=False)
    else:
        ap.error("--manifest PATH or --synthetic required")
    rep = run(man, topk=a.topk)
    for cand, m in rep["per_candidate"].items():
        tag = "(ref)" if cand == "affine" else ""
        print(f"  {cand:7}{tag:5} k_cos={m['k_recon_cos']:.4f} logit_mse={m['qk_logit_mse']:.4f} "
              f"kl={m['softmax_kl']:.4f} topk={m['topk_overlap']:.3f} out_cos={m['attn_out_cos']:.4f}")
    for cand, r in rep["relative_to_affine"].items():
        print(f"    {cand} vs affine: Δout_cos={r['attn_out_cos_minus_affine']:+.4f} "
              f"kl_ratio={r['softmax_kl_ratio_to_affine']:.2f} Δtopk={r['topk_overlap_minus_affine']:+.4f}")
    if a.out_json:
        with open(a.out_json, "w") as fh:
            json.dump(rep, fh, indent=2)
        print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
