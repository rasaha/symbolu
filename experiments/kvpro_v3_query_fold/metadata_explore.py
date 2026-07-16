#!/usr/bin/env python3
"""Phase A — multi-prompt / multi-seed production K metadata capture (POD-ONLY).

Runs the model on several representative prompts × seeds, derives the PRODUCTION
per-block per-channel K scale / xmin via the faithful `quant_ref`, and writes a
metadata-ONLY explore manifest (no K/Q/V — this gate studies the metadata itself).
The model is loaded ONCE and reused across prompts/seeds. No external INT4 fork; no
attention or quality here.

  python metadata_explore.py --model Qwen/Qwen2.5-7B-Instruct --mask <m.pt> --out qwen_meta.pt
  python metadata_explore.py --synthetic low_rank --out synth_meta.pt      # no GPU
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIB = os.path.join(_HERE, "..", "kvpro_v3_symmetric_residual")
for p in (_HERE, _SIB, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy")):
    sys.path.insert(0, p)

import quant_ref  # noqa: E402

# A few varied, long, deterministic prompts so metadata spans many BS=32 blocks and
# stability across DIFFERENT inputs can be evaluated (Phase E).
_PROMPTS = [
    ("In a distant archive the records were catalogued. The secret access code is 60494. " * 40),
    ("A treatise on rivers, tides, and the slow work of erosion across centuries follows. " * 40),
    ("Dialogue: the engineer explained the protocol step by step to the new apprentice. " * 40),
    ("Numbers and dates: in 1742 the library was founded; by 1801 it held twelve thousand books. " * 40),
]


def _die(msg, code=2):
    print(f"\n[FAIL] {msg}", file=sys.stderr); sys.exit(code)


def build_explore(model_name, mask_path, prompts, seeds, max_layers, BS):
    import torch
    import fakequant_model as FQ
    print(f"[explore] loading {model_name} once ...")
    model, tok = FQ.load_model(model_name)
    blob = torch.load(mask_path, map_location="cpu", weights_only=False)
    full_mask = blob.get("mask", blob.get("protect_mask"))
    if full_mask is None:
        _die(f"mask {mask_path} has no 'mask'/'protect_mask'.")

    caps, geom = [], None
    for pi, prompt in enumerate(prompts):
        for seed in seeds:
            torch.manual_seed(seed)
            ids = tok(prompt, return_tensors="pt").input_ids.to("cuda")
            with torch.no_grad():
                out = model(ids, use_cache=True)
            pkv = out.past_key_values
            n_layers = FQ.num_cache_layers(pkv)
            if max_layers:
                n_layers = min(n_layers, max_layers)
            layers = []
            for li in range(n_layers):
                kt, _ = FQ.layer_kv(pkv, li)                        # (B,H_kv,S,D)
                K = kt[0].transpose(0, 1).contiguous().to(torch.bfloat16).float().cpu()  # (S,H_kv,D)
                s, x, _ = quant_ref.production_k_metadata(K, BS)
                layers.append({"layer": li, "s_prod": s, "xmin_prod": x,
                               "protect_mask": full_mask[li].to(torch.int8)})
            caps.append({"prompt_id": pi, "seed": int(seed), "layers": layers})
            H_kv, D = layers[0]["s_prod"].shape[1], layers[0]["s_prod"].shape[2]
            geom = {"n_layers": n_layers, "H_kv": H_kv, "D": D, "n_blocks": layers[0]["s_prod"].shape[0]}
            print(f"  prompt {pi} seed {seed}: {n_layers} layers, {geom['n_blocks']} blocks")
    n_protect = int(caps[0]["layers"][0]["protect_mask"].sum(-1).max())
    return {"model": model_name, "mask_path": mask_path, "BS": BS, "n_protect": n_protect,
            "geom": geom, "n_prompts": len(prompts), "seeds": list(seeds), "captures": caps}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata exploration capture")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--n-prompts", type=int, default=4, help="use the first N built-in prompts")
    ap.add_argument("--max-layers", type=int, default=0)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    ap.add_argument("--out", default="metadata_explore.pt")
    a = ap.parse_args(argv)
    import torch
    if a.synthetic:
        import synthetic
        man = synthetic.explore_manifest_synthetic(structure=a.synthetic, n_captures=3, n_layers=3)
        torch.save(man, a.out)
        print(f"[SYNTHETIC {a.synthetic}] -> {a.out} ({len(man['captures'])} captures)")
        return 0
    if not a.mask or not os.path.isfile(a.mask):
        _die(f"mask not found (PROTECT_MASK_PATH or --mask): {a.mask!r}")
    seeds = tuple(int(s) for s in a.seeds.split(","))
    man = build_explore(a.model, a.mask, _PROMPTS[:a.n_prompts], seeds, a.max_layers, a.bs)
    torch.save(man, a.out)
    g = man["geom"]
    print(f"[MEASURED] {len(man['captures'])} captures -> {a.out} "
          f"| L={g['n_layers']} H_kv={g['H_kv']} D={g['D']} blocks={g['n_blocks']} n_protect={man['n_protect']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
