#!/usr/bin/env python3
"""KVPro V3 Gate-1 — protect-mask calibration via TRANSFORMERS (no vLLM needed).

Reproduces the PRODUCTION criterion (CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py):
  per-(layer, h_kv, d) MAX-ABS of the cached (post-RoPE) K, accumulated over a calibration corpus;
  protect the top-`round(D * protect_fraction)` channels per (layer, h_kv).
Writes the SAME artifact schema (`mask` (L,H_kv,D) int8 + k_min/k_max + geometry) the drivers /
capture load. Uses `past_key_values` (architecture-agnostic; matches the K the drivers fake-quant) so
no rotary monkey-patch is required.

POD-ONLY (needs GPU + model). The pure mask-builder `build_mask_from_maxabs` is CPU-tested.
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_CORPUS = [
    "The Cook-Levin theorem established that boolean satisfiability is NP-complete.",
    "Photosynthesis converts carbon dioxide and water into glucose and oxygen using light.",
    "In distributed systems, consensus protocols like Raft elect a leader to order a log.",
    "The gross domestic product measures the market value of goods produced in a period.",
    "Mitochondria generate ATP through oxidative phosphorylation across the inner membrane.",
    "A binary search halves the interval each step, giving logarithmic time on sorted data.",
    "The Treaty of Westphalia in 1648 shaped the modern notion of state sovereignty.",
    "Gradient descent updates parameters against the gradient of a differentiable loss.",
    "Enzymes lower activation energy by stabilizing the transition state of a reaction.",
    "TCP provides reliable, ordered, error-checked delivery over an unreliable network.",
    "Supply and demand curves intersect at the equilibrium price in a competitive market.",
    "The second law of thermodynamics states entropy of an isolated system never decreases.",
]


def build_mask_from_maxabs(maxabs_by_layer, protect_fraction: float):
    """Pure (CPU-testable): {layer_idx: (H_kv,D) max-abs tensor} -> ((L,H_kv,D) int8 mask, n_protect).
    Exactly mirrors production _build_mask_from_accumulator: top-k per (h_kv) by max-abs."""
    import torch
    order = sorted(maxabs_by_layer)
    H_kv, D = maxabs_by_layer[order[0]].shape
    n_protect = max(1, int(round(D * protect_fraction)))
    mask = torch.zeros((len(order), H_kv, D), dtype=torch.int8)
    for li, key in enumerate(order):
        mag = maxabs_by_layer[key]
        if tuple(mag.shape) != (H_kv, D):
            raise RuntimeError(f"inconsistent shape at layer {key}: {tuple(mag.shape)} != {(H_kv, D)}")
        _, idx = mag.topk(n_protect, dim=-1)              # (H_kv, n_protect)
        mask[li].scatter_(-1, idx.cpu(), 1)
    return mask, n_protect


def widen_minmax(k_min, k_max, margin: float = 1.1):
    """Pure (CPU-testable): Phase-6N deployment margin — push each per-channel bound OUTWARD by
    (margin-1)*range so live values slightly past calibration do not clip under prot-int8. Byte-identical
    to production calibrate_phase5b_protect_mask._widen_minmax:  pad=(margin-1)*(k_max-k_min);
    return k_min-pad, k_max+pad. The writer/P8prod consume the stored (already-widened) bounds as-is."""
    if margin < 1.0:
        raise ValueError(f"minmax margin must be >= 1.0; got {margin}")
    pad = (margin - 1.0) * (k_max - k_min)
    return k_min - pad, k_max + pad


def main(argv=None):
    ap = argparse.ArgumentParser(description="protect-mask calibration via transformers (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--output", required=True)
    ap.add_argument("--protect-fraction", type=float, default=0.04)
    ap.add_argument("--num-prompts", type=int, default=0, help="0 = use the whole built-in corpus")
    ap.add_argument("--minmax-margin", type=float, default=1.1,
                    help="Phase-6N prot-int8 deployment margin (widen k_min/k_max outward); matches production")
    args = ap.parse_args(argv)

    import torch
    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    corpus = _CORPUS if not args.num_prompts else (_CORPUS * (args.num_prompts // len(_CORPUS) + 1))[:args.num_prompts]

    maxabs, kmin, kmax = {}, {}, {}
    n_layers = None
    for pi, text in enumerate(corpus):
        ids = tok(text, return_tensors="pt").input_ids.to("cuda")
        with torch.no_grad():
            out = model(ids, use_cache=True)
        pkv = out.past_key_values
        n_layers = model.config.num_hidden_layers
        for li in range(n_layers):
            kt, _ = FQ.layer_kv(pkv, li)                  # (B, H_kv, S, D)
            k = kt[0].float()                             # (H_kv, S, D)
            ma = k.abs().amax(dim=1).cpu()                # (H_kv, D)
            mn = k.amin(dim=1).cpu(); mx = k.amax(dim=1).cpu()
            maxabs[li] = ma if li not in maxabs else torch.maximum(maxabs[li], ma)
            kmin[li] = mn if li not in kmin else torch.minimum(kmin[li], mn)
            kmax[li] = mx if li not in kmax else torch.maximum(kmax[li], mx)
        print(f"  calibrated on prompt {pi+1}/{len(corpus)}")

    mask, n_protect = build_mask_from_maxabs(maxabs, args.protect_fraction)
    L, H_kv, D = mask.shape
    # widen raw min/max by the Phase-6N margin so k_min/k_max are PRODUCTION-FAITHFUL (P8prod uses them as-is)
    kmin_raw = torch.stack([kmin[i] for i in sorted(kmin)])
    kmax_raw = torch.stack([kmax[i] for i in sorted(kmax)])
    kmin_w, kmax_w = widen_minmax(kmin_raw, kmax_raw, args.minmax_margin)
    artifact = {
        "mask": mask, "protect_fraction": args.protect_fraction, "n_protect": n_protect,
        "num_layers": L, "num_kv_heads": H_kv, "head_dim": D, "model": args.model,
        "k_min": kmin_w, "k_max": kmax_w, "minmax_margin": args.minmax_margin,
        "calibrated_by": "hf_maxabs_topk (transformers; matches production max-abs criterion + minmax margin)",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    torch.save(artifact, args.output)
    per_head = mask.sum(-1).float()
    print(f"[MEASURED] mask saved: {args.output}  shape=({L},{H_kv},{D}) n_protect={n_protect} "
          f"(per-head protected: min/mean/max = {int(per_head.min())}/{per_head.mean():.1f}/{int(per_head.max())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
