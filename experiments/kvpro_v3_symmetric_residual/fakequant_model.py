"""Shared fake-quant generation backend (POD-ONLY, HARDWARE-UNTESTED).

Loads an HF model and runs generation / teacher-forced forwards with the KV cache fake-quantized per
candidate (fp/affine/S1..S4), reusing `quantizers.reconstruct`. Needs GPU + model. The module imports
without torch so the pure prompt-set builders in the drivers stay CPU-testable; torch/transformers
imports are lazy (inside functions).

Cache API: transformers moved DynamicCache to a `.layers[i].keys/.values` layout (no subscripting);
`layer_kv` reads it across that + the legacy `key_cache[i]` / `pkv[i]` variants.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))
import quantizers as Q          # noqa: E402
import protected_int8 as P8      # noqa: E402  (P8 protected-INT8 candidates; orthogonal to S1-S4)

CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]


def layer_kv(pkv, i):
    """(key, value) tensors (B,H,S,D) for layer i, across transformers cache API variants."""
    layers = getattr(pkv, "layers", None)
    if layers is not None:                          # transformers 5.x: list of cache layers
        L = layers[i]
        for kn, vn in (("keys", "values"), ("key_cache", "value_cache"), ("key_states", "value_states")):
            k, v = getattr(L, kn, None), getattr(L, vn, None)
            if k is not None and v is not None:
                return k, v
    kc, vc = getattr(pkv, "key_cache", None), getattr(pkv, "value_cache", None)
    if kc is not None and vc is not None:           # older: parallel lists on the cache
        return kc[i], vc[i]
    return pkv[i][0], pkv[i][1]                      # legacy tuple-subscript


def num_cache_layers(pkv):
    layers = getattr(pkv, "layers", None)
    if layers is not None:
        return len(layers)
    kc = getattr(pkv, "key_cache", None)
    return len(kc) if kc is not None else len(pkv)


def load_model(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not torch.cuda.is_available():
        raise SystemExit("[FAIL] no CUDA GPU — fake-quant generation needs a GPU + model weights.")
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    try:                                            # transformers 5.x renamed torch_dtype -> dtype
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.bfloat16, device_map="cuda")
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cuda")
    return model.eval(), tok


def build_fakequant_cache(candidate, masks, BS=32, v_group_size=32):
    """DynamicCache subclass whose update() returns the candidate's reconstructed K/V, so attention
    attends over fake-quantized KV. 'fp' is pass-through. Returns fresh tensors (no reliance on cache
    storage internals); protected channels stay exact via quantizers.reconstruct."""
    import torch
    from transformers.cache_utils import DynamicCache

    class FakeQuantCache(DynamicCache):
        def update(self, key, value, layer_idx, cache_kwargs=None):
            k, v = super().update(key, value, layer_idx, cache_kwargs)
            if candidate == "fp":
                return k, v
            mask = masks[layer_idx].to(k.device)
            kwargs = {"BS": BS, "v_group_size": v_group_size}
            if candidate == "P8prod":                       # production-faithful: static calibrated min/max
                if _PROT_KMIN is None or _PROT_KMAX is None:
                    raise SystemExit("[FAIL] P8prod needs k_min/k_max in the mask artifact (Phase-6N "
                                     "calibrated). Rebuild the mask with minmax, or use P8aff/P8sym.")
                kwargs["k_min"] = _PROT_KMIN[layer_idx].to(k.device)
                kwargs["k_max"] = _PROT_KMAX[layer_idx].to(k.device)
            recon = P8.reconstruct_p8 if candidate.startswith("P8") else Q.reconstruct
            kh, vh = [], []
            for b in range(k.shape[0]):
                Kh, Vh = recon(k[b].transpose(0, 1).float(), v[b].transpose(0, 1).float(),
                               mask, candidate, **kwargs)
                kh.append(Kh.transpose(0, 1)); vh.append(Vh.transpose(0, 1))
            return torch.stack(kh).to(k.dtype), torch.stack(vh).to(v.dtype)
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


_PROT_KMIN = None      # (L, H_kv, D) calibrated k_min for P8prod; set by load_masks, None if absent
_PROT_KMAX = None


def load_masks(mask_path):
    import torch
    global _PROT_KMIN, _PROT_KMAX
    blob = torch.load(mask_path, map_location="cpu", weights_only=False)
    m = blob.get("mask", blob.get("protect_mask"))
    if m is None:
        raise SystemExit(f"[FAIL] mask file {mask_path} has no 'mask'/'protect_mask' key.")
    _PROT_KMIN, _PROT_KMAX = blob.get("k_min"), blob.get("k_max")   # Phase-6N calibrated minmax (P8prod)
    return m
