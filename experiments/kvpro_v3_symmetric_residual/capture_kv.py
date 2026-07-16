#!/usr/bin/env python3
"""KVPro V3 Gate-1 — capture real post-RoPE Q/K/V per layer (POD-ONLY, HARDWARE-UNTESTED).

Runs a normal HF forward on a prompt and captures, per attention layer, the post-RoPE query/key
states and the value states — the exact tensors the KV cache holds. Also loads the FROZEN production
protect mask per layer. Writes a .pt the offline evals consume.

This does NOT need the int4 decode fork or the int4_protected backend — it is a fake-quant study on
raw fp KV. It DOES need: a GPU, the model weights, and the calibrated protect mask.

⚠️ The Q/K capture patches `apply_rotary_pos_emb` in the model's attention module namespace; verify it
matches your transformers version (Llama/Qwen2 style). Fails loudly if it captures nothing.
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# reuse the repo's protect-mask loader for exact frozen masks
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))


def _die(msg, code=2):
    print(f"\n[FAIL] {msg}", file=sys.stderr); sys.exit(code)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capture post-RoPE Q/K/V + frozen mask (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--prompt", default="The secret access code is 60494. " * 40)
    ap.add_argument("--max-layers", type=int, default=0, help="0 = all layers")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="captured_kv.pt")
    args = ap.parse_args(argv)

    if not args.mask or not os.path.isfile(args.mask):
        _die(f"protect mask not found (PROTECT_MASK_PATH or --mask): {args.mask!r}. "
             "Create it with CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py.")
    try:
        import torch
        import fakequant_model as FQ
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
    except Exception as e:  # noqa: BLE001
        _die(f"transformers/torch import failed: {e}")
    torch.manual_seed(args.seed)

    print(f"[capture] loading {args.model} ...")
    model, tok = FQ.load_model(args.model)          # dtype-safe (torch_dtype/dtype) + GPU

    # Patch the model's OWN rotary fn (arch-specific) to stash post-RoPE Q per layer. K/V come from the
    # cache (post-RoPE, arch-agnostic). If the patch can't fire, we save K/V without Q (recon eval still
    # works; attention-error eval — a NON-BLOCKING proxy — just skips).
    stash = {"q": []}
    mt = getattr(model.config, "model_type", "")
    rot_mod = None
    try:
        rot_mod = __import__(f"transformers.models.{mt}.modeling_{mt}", fromlist=["apply_rotary_pos_emb"])
    except Exception:  # noqa: BLE001
        rot_mod = None
    orig = getattr(rot_mod, "apply_rotary_pos_emb", None) if rot_mod is not None else None
    if orig is not None:
        def _patched(q, k, *a, **kw):
            q2, k2 = orig(q, k, *a, **kw)
            stash["q"].append(q2.detach())
            return q2, k2
        rot_mod.apply_rotary_pos_emb = _patched

    ids = tok(args.prompt, return_tensors="pt").input_ids.to("cuda")
    with torch.no_grad():
        out = model(ids, use_cache=True)
    if orig is not None:
        rot_mod.apply_rotary_pos_emb = orig

    pkv = out.past_key_values
    n_layers = FQ.num_cache_layers(pkv)
    if args.max_layers:
        n_layers = min(n_layers, args.max_layers)
    have_q = len(stash["q"]) >= n_layers
    if not have_q:
        print(f"[warn] rotary patch captured {len(stash['q'])}/{n_layers} Q (model_type={mt!r}); "
              "saving K/V WITHOUT Q — attention-error eval (non-blocking proxy) will skip.")

    mask_blob = torch.load(args.mask, map_location="cpu", weights_only=False)
    full_mask = mask_blob.get("mask", mask_blob.get("protect_mask"))     # (L, H_kv, D) int8
    if full_mask is None:
        _die(f"mask file {args.mask} has no 'mask'/'protect_mask' key.")

    layers = []
    for li in range(n_layers):
        kt, vt = FQ.layer_kv(pkv, li)               # (B, Hkv, S, D)
        entry = {"K": kt[0].transpose(0, 1).contiguous().float().cpu(),   # (S, Hkv, D)
                 "V": vt[0].transpose(0, 1).contiguous().float().cpu(),
                 "protect_mask": full_mask[li].to(torch.int8).cpu()}
        if have_q:
            Q = stash["q"][li][0].transpose(0, 1).contiguous().float().cpu()   # (S, Hq, D)
            entry["Q"] = Q[-8:] if Q.shape[0] > 8 else Q
        layers.append(entry)

    blob = {"layers": layers, "meta": {"model": args.model, "mask": args.mask, "has_Q": have_q,
            "n_layers": n_layers, "prompt_tokens": int(ids.shape[1]), "synthetic": False}}
    torch.save(blob, args.out)
    qshape = tuple(layers[0]["Q"].shape) if have_q else None
    print(f"[MEASURED] captured {n_layers} layers -> {args.out} (K {tuple(layers[0]['K'].shape)}, Q {qshape})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
