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
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import transformers.models.llama.modeling_llama as llama_mod
    except Exception as e:  # noqa: BLE001
        _die(f"transformers/torch import failed: {e}")
    if not torch.cuda.is_available():
        _die("no CUDA GPU — capture needs a GPU + model weights.")
    torch.manual_seed(args.seed)

    # --- patch rotary to stash post-RoPE q,k per call (Llama/Qwen2 share this fn) --- #
    stash = {"qk": []}
    orig = llama_mod.apply_rotary_pos_emb

    def patched(q, k, cos, sin, *a, **kw):
        q2, k2 = orig(q, k, cos, sin, *a, **kw)
        stash["qk"].append((q2.detach(), k2.detach()))
        return q2, k2
    llama_mod.apply_rotary_pos_emb = patched

    print(f"[capture] loading {args.model} ...")
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16,
                                                 device_map="cuda")
    model.eval()
    ids = tok(args.prompt, return_tensors="pt").input_ids.to("cuda")
    with torch.no_grad():
        out = model(ids, use_cache=True)
    llama_mod.apply_rotary_pos_emb = orig

    if not stash["qk"]:
        _die("captured 0 rotary calls — the patch did not fire; adjust for your transformers version "
             "(the model may not use transformers.models.llama.modeling_llama.apply_rotary_pos_emb).")

    pkv = out.past_key_values                      # per-layer (key, value); value = post-proj V
    n_layers = len(stash["qk"])
    if args.max_layers:
        n_layers = min(n_layers, args.max_layers)
    mask_blob = torch.load(args.mask, map_location="cpu", weights_only=False)
    full_mask = mask_blob.get("mask", mask_blob.get("protect_mask"))     # (L, H_kv, D) int8
    if full_mask is None:
        _die(f"mask file {args.mask} has no 'mask'/'protect_mask' key.")

    layers = []
    for li in range(n_layers):
        q, k = stash["qk"][li]                      # (B, Hq, S, D), (B, Hkv, S, D)
        v = pkv[li][1] if not hasattr(pkv, "layers") else pkv.layers[li].values   # (B, Hkv, S, D)
        # to (S, H, D), drop batch 0
        K = k[0].transpose(0, 1).contiguous().float().cpu()      # (S, Hkv, D)
        V = v[0].transpose(0, 1).contiguous().float().cpu()
        Q = q[0].transpose(0, 1).contiguous().float().cpu()      # (S, Hq, D)
        layers.append({"K": K, "V": V, "Q": Q[-8:] if Q.shape[0] > 8 else Q,   # a few decode queries
                       "protect_mask": full_mask[li].to(torch.int8).cpu()})

    blob = {"layers": layers, "meta": {"model": args.model, "mask": args.mask,
            "n_layers": n_layers, "prompt_tokens": int(ids.shape[1]), "synthetic": False}}
    torch.save(blob, args.out)
    print(f"[MEASURED] captured {n_layers} layers -> {args.out} "
          f"(K/V/Q shapes: {tuple(layers[0]['K'].shape)}/{tuple(layers[0]['Q'].shape)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
