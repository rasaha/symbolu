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


def _layer_key(pkv, i):
    """Post-RoPE K for layer i across transformers Cache / legacy-tuple past_key_values."""
    kc = getattr(pkv, "key_cache", None)
    if kc is not None:
        return kc[i]
    return pkv[i][0]


def main(argv=None):
    ap = argparse.ArgumentParser(description="protect-mask calibration via transformers (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--output", required=True)
    ap.add_argument("--protect-fraction", type=float, default=0.04)
    ap.add_argument("--num-prompts", type=int, default=0, help="0 = use the whole built-in corpus")
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
            k = _layer_key(pkv, li)[0].float()            # (H_kv, S, D)
            ma = k.abs().amax(dim=1).cpu()                # (H_kv, D)
            mn = k.amin(dim=1).cpu(); mx = k.amax(dim=1).cpu()
            maxabs[li] = ma if li not in maxabs else torch.maximum(maxabs[li], ma)
            kmin[li] = mn if li not in kmin else torch.minimum(kmin[li], mn)
            kmax[li] = mx if li not in kmax else torch.maximum(kmax[li], mx)
        print(f"  calibrated on prompt {pi+1}/{len(corpus)}")

    mask, n_protect = build_mask_from_maxabs(maxabs, args.protect_fraction)
    L, H_kv, D = mask.shape
    artifact = {
        "mask": mask, "protect_fraction": args.protect_fraction, "n_protect": n_protect,
        "num_layers": L, "num_kv_heads": H_kv, "head_dim": D, "model": args.model,
        "k_min": torch.stack([kmin[i] for i in sorted(kmin)]),
        "k_max": torch.stack([kmax[i] for i in sorted(kmax)]),
        "calibrated_by": "hf_maxabs_topk (transformers; matches production max-abs criterion)",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    torch.save(artifact, args.output)
    per_head = mask.sum(-1).float()
    print(f"[MEASURED] mask saved: {args.output}  shape=({L},{H_kv},{D}) n_protect={n_protect} "
          f"(per-head protected: min/mean/max = {int(per_head.min())}/{per_head.mean():.1f}/{int(per_head.max())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
