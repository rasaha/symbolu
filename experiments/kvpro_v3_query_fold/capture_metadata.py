#!/usr/bin/env python3
"""Phase B — capture real metadata + K/Q/V tensors (POD-ONLY, HARDWARE-UNTESTED).

Runs a normal HF forward on a deterministic prompt, captures per attention layer the
post-RoPE Q / K / V, loads the FROZEN 4% protect mask, and derives the PRODUCTION K
metadata (per-block per-channel scale / xmin / int4 codes) via the faithful
`quant_ref`. Writes the query-fold manifest the analyzers + evaluator consume.

Does NOT need the int4 decode fork or the int4_protected backend — this is a
fake-quant structural study on raw fp KV. It DOES need: a GPU, the model weights, and
the calibrated protect mask. Reuses the sibling study's rotary-patch capture + FQ
loader so the post-RoPE hook is identical to the validated one.

  python capture_metadata.py --model Qwen/Qwen2.5-7B-Instruct --mask <mask.pt> --out qwen_cap.pt
  python capture_metadata.py --synthetic --out synth_cap.pt      # no GPU (pipeline smoke)
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIB = os.path.join(_HERE, "..", "kvpro_v3_symmetric_residual")
sys.path.insert(0, _HERE)
sys.path.insert(0, _SIB)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy"))

import quant_ref  # noqa: E402


def _die(msg, code=2):
    print(f"\n[FAIL] {msg}", file=sys.stderr); sys.exit(code)


# A long, deterministic prompt so the sequence spans MANY BS=32 blocks (the
# decomposition needs enough blocks to be meaningful).
_PROMPT = ("In a distant archive, the following records were catalogued. "
           "The secret access code is 60494. ") * 60


def _build_manifest_from_capture(model_name, mask_path, prompt, seed, max_layers, BS):
    import torch
    import fakequant_model as FQ                      # sibling helper (validated loader)
    torch.manual_seed(seed)
    print(f"[capture] loading {model_name} ...")
    model, tok = FQ.load_model(model_name)

    stash = {"q": []}
    mt = getattr(model.config, "model_type", "")
    try:
        rot_mod = __import__(f"transformers.models.{mt}.modeling_{mt}",
                             fromlist=["apply_rotary_pos_emb"])
    except Exception:  # noqa: BLE001
        rot_mod = None
    orig = getattr(rot_mod, "apply_rotary_pos_emb", None) if rot_mod is not None else None
    if orig is not None:
        def _patched(q, k, *a, **kw):
            q2, k2 = orig(q, k, *a, **kw)
            stash["q"].append(q2.detach())
            return q2, k2
        rot_mod.apply_rotary_pos_emb = _patched

    ids = tok(prompt, return_tensors="pt").input_ids.to("cuda")
    with torch.no_grad():
        out = model(ids, use_cache=True)
    if orig is not None:
        rot_mod.apply_rotary_pos_emb = orig

    pkv = out.past_key_values
    n_layers = FQ.num_cache_layers(pkv)
    if max_layers:
        n_layers = min(n_layers, max_layers)
    if len(stash["q"]) < n_layers:
        _die(f"rotary patch captured only {len(stash['q'])}/{n_layers} Q (model_type={mt!r}); "
             "the attention gate needs Q. Check the transformers version.")

    blob = torch.load(mask_path, map_location="cpu", weights_only=False)
    full_mask = blob.get("mask", blob.get("protect_mask"))          # (L, H_kv, D) int8
    if full_mask is None:
        _die(f"mask {mask_path} has no 'mask'/'protect_mask' key.")

    layers = []
    S = int(ids.shape[1])
    for li in range(n_layers):
        kt, vt = FQ.layer_kv(pkv, li)                                # (B, H_kv, S, D)
        K = kt[0].transpose(0, 1).contiguous().float().cpu()         # (S, H_kv, D)
        V = vt[0].transpose(0, 1).contiguous().float().cpu()
        Q = stash["q"][li][0].transpose(0, 1).contiguous().float().cpu()  # (S, H_q, D)
        Q = Q[-8:] if Q.shape[0] > 8 else Q                          # last 8 as decode queries
        Kb = K.to(torch.bfloat16)                                    # store-precision, then derive
        s_prod, xmin_prod, codes = quant_ref.production_k_metadata(Kb.float(), BS)
        layers.append({"layer": li, "K": Kb, "V": V.to(torch.bfloat16), "Q": Q.to(torch.bfloat16),
                       "s_prod": s_prod, "xmin_prod": xmin_prod, "codes": codes,
                       "protect_mask": full_mask[li].to(torch.int8)})
    H_kv, D = layers[0]["K"].shape[1], layers[0]["K"].shape[2]
    n_protect = int(layers[0]["protect_mask"].sum(-1).max())
    return {"model": model_name, "mask_path": mask_path, "BS": BS, "n_protect": n_protect,
            "geom": {"n_layers": n_layers, "H_kv": H_kv, "H_q": layers[0]["Q"].shape[1],
                     "D": D, "S": S, "n_blocks": (S + BS - 1) // BS}, "seed": seed,
            "prompt_tokens": S, "synthetic": False, "layers": layers}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 query-fold Phase B capture")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--prompt", default=_PROMPT)
    ap.add_argument("--max-layers", type=int, default=0, help="0 = all layers")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--synthetic", action="store_true", help="write a synthetic manifest (no GPU)")
    ap.add_argument("--out", default="query_fold_capture.pt")
    a = ap.parse_args(argv)

    import torch
    if a.synthetic:
        import synthetic
        man = synthetic.synthetic_capture(n_layers=4, S=8 * 32, H=4, H_q=8, D=128, n_protect=5)
        man["model"] = "SYNTHETIC"
        torch.save(man, a.out)
        print(f"[SYNTHETIC] wrote pipeline-smoke manifest -> {a.out} "
              f"({man['geom']['n_layers']} layers, S={man['geom']['S']})")
        return 0

    if not a.mask or not os.path.isfile(a.mask):
        _die(f"protect mask not found (PROTECT_MASK_PATH or --mask): {a.mask!r}")
    man = _build_manifest_from_capture(a.model, a.mask, a.prompt, a.seed, a.max_layers, a.bs)
    torch.save(man, a.out)
    g = man["geom"]
    print(f"[MEASURED] {g['n_layers']} layers -> {a.out} | K(S={g['S']},H_kv={g['H_kv']},D={g['D']}) "
          f"n_blocks={g['n_blocks']} n_protect={man['n_protect']} H_q={g['H_q']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
