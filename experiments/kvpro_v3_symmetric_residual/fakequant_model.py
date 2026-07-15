"""Shared fake-quant generation backend (POD-ONLY, HARDWARE-UNTESTED).

Loads an HF model and runs generation / teacher-forced forwards with the KV cache fake-quantized per
candidate (fp/affine/S1..S4), reusing `quantizers.reconstruct`. Needs GPU + model. NOT importable-safe
to *run*, but the module imports without torch so the pure prompt-set builders in the drivers can be
CPU-tested. All torch/transformers imports are lazy (inside functions).
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))
import quantizers as Q          # noqa: E402  (pure, no torch at import for reconstruct? it needs torch at call)


def load_model(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not torch.cuda.is_available():
        raise SystemExit("[FAIL] no CUDA GPU — fake-quant generation needs a GPU + model weights.")
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cuda").eval()
    return model, tok


def build_fakequant_cache(candidate, masks, BS=32, v_group_size=32):
    """DynamicCache subclass that fake-quantizes K/V on every update (B=1 eval).
    candidate 'fp' is a pass-through. masks: (L, H_kv, D)."""
    import torch  # noqa: F401
    from transformers.cache_utils import DynamicCache

    class FakeQuantCache(DynamicCache):
        def update(self, key, value, layer_idx, cache_kwargs=None):
            k, v = super().update(key, value, layer_idx, cache_kwargs)
            if candidate == "fp":
                return k, v
            mask = masks[layer_idx].to(k.device)
            Kf = k[0].transpose(0, 1).float()      # (S, Hkv, D)
            Vf = v[0].transpose(0, 1).float()
            Kh, Vh = Q.reconstruct(Kf, Vf, mask, candidate, BS=BS, v_group_size=v_group_size)
            k[0] = Kh.transpose(0, 1).to(k.dtype)
            v[0] = Vh.transpose(0, 1).to(v.dtype)
            return k, v
    return FakeQuantCache()


def generate(model, tok, prompt, candidate, masks, max_new_tokens=24):
    import torch
    ids = tok(prompt, return_tensors="pt").input_ids.to("cuda")
    cache = build_fakequant_cache(candidate, masks)
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens=max_new_tokens, do_sample=False,
                             past_key_values=cache, use_cache=True, pad_token_id=tok.pad_token_id)
    return tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)


def teacher_forced_argmax(model, tok, text, candidate, masks):
    """Return (pred_next_token_ids, target_ids) for teacher-forced next-token agreement."""
    import torch
    ids = tok(text, return_tensors="pt").input_ids.to("cuda")
    cache = build_fakequant_cache(candidate, masks)
    with torch.no_grad():
        out = model(ids, use_cache=True, past_key_values=cache)
    return out.logits[0, :-1].argmax(-1).cpu(), ids[0, 1:].cpu()


def load_masks(mask_path):
    import torch
    blob = torch.load(mask_path, map_location="cpu", weights_only=False)
    m = blob.get("mask", blob.get("protect_mask"))
    if m is None:
        raise SystemExit(f"[FAIL] mask file {mask_path} has no 'mask'/'protect_mask' key.")
    return m


CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]
