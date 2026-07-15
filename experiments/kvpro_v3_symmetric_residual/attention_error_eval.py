"""KVPro V3 Gate-1 — attention-error eval (Phase C, decisive half).

The DECISIVE offline signal: how much each candidate perturbs the attention chain
(QKᵀ logits -> softmax -> weighted-V output), on captured real Q/K/V. Emits per-layer + summary
JSON, including each candidate's attention-output error RELATIVE to the accepted affine baseline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quantizers as Q                      # noqa: E402
import metrics as M                         # noqa: E402
from reconstruction_eval import load_capture, make_synthetic   # noqa: E402

_ATT_KEYS = ("logit_mse", "softmax_kl_mean", "softmax_kl_max", "attn_out_mse", "attn_out_maxabs")


def run(cap, BS=32, v_group_size=32):
    cands = Q.candidate_names()
    per_layer = []
    for li, L in enumerate(cap["layers"]):
        if "Q" not in L:
            raise ValueError(f"layer {li} has no Q — capture must include query states for attention error")
        K, V, mask, Qq = L["K"].float(), L["V"].float(), L["protect_mask"], L["Q"].float()
        row = {"layer": li}
        affine_m = None
        for c in cands:
            Kh, Vh = Q.reconstruct(K, V, mask, c, BS=BS, v_group_size=v_group_size)
            am = M.attention_metrics(Qq, K, V, Kh, Vh)
            if c == "affine":
                affine_m = am
            row[c] = am
        # relative-to-affine for every candidate (how much worse than the shipped baseline)
        for c in cands:
            row[c].update(M.relative_to_affine(row[c], affine_m, _ATT_KEYS))
        per_layer.append(row)

    summary = {}
    for c in cands:
        summary[c] = {
            "attn_out_cos_min": min(r[c]["attn_out_cos"] for r in per_layer),
            "attn_out_mse_max": max(r[c]["attn_out_mse"] for r in per_layer),
            "attn_out_mse_vs_affine_max": max(r[c].get("attn_out_mse_vs_affine", 1.0) for r in per_layer),
            "softmax_kl_mean_max": max(r[c]["softmax_kl_mean"] for r in per_layer),
            "softmax_kl_max_max": max(r[c]["softmax_kl_max"] for r in per_layer),
        }
    return {"summary": summary, "per_layer": per_layer}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Gate-1 attention-error eval")
    ap.add_argument("--capture", default=None)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default="attention_error_metrics.json")
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--v-group-size", type=int, default=32)
    args = ap.parse_args(argv)

    if args.capture:
        cap = load_capture(args.capture); source = f"capture:{args.capture}"; measured = True
    elif args.synthetic:
        cap = make_synthetic(); source = "synthetic-fixture"; measured = False
    else:
        print("[FAIL] provide --capture <real.pt> or --synthetic", file=sys.stderr)
        return 2

    res = run(cap, BS=args.bs, v_group_size=args.v_group_size)
    res["source"] = source
    res["label"] = "MEASURED" if measured else "NOT_A_VERDICT_SYNTHETIC"
    with open(args.out, "w") as fh:
        json.dump(res, fh, indent=2)
    print(f"[{'MEASURED' if measured else 'SYNTHETIC'}] attention error -> {args.out}")
    for c, s in res["summary"].items():
        print(f"  {c:7} attn_out_cos_min={s['attn_out_cos_min']:.6f} "
              f"attn_out_mse_x_affine={s['attn_out_mse_vs_affine_max']:.3f} "
              f"kl_max={s['softmax_kl_max_max']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
