#!/usr/bin/env python3
"""KVPro V3 Gate-1 — HARD-needle driver (MANDATORY gate; POD-ONLY for generation).

REUSES the exact repo hard-needle protocol that established KVPro's prior 0.964 result:
`phase6k12_hard_needle.build_item` (modes multi/distractor/conflict/qa) + `classify`
(HIT/NEAR_V/MISS_K/COLLAPSE/FORMAT) + strict_accuracy = HIT/total. Runs it through fake-quant per
candidate. Emits hard_needle_results.json. Qwen2.5-7B (the marginal model) MUST be evaluated first.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "Bench", "scripts"))
import phase6k12_hard_needle as hn        # noqa: E402  (repo protocol; build_item/classify/MODES pure)

CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]


def build_item_set(seeds=(0, 1), items_per_mode=6, target_tokens=6000):
    """CPU-testable: reuse the repo hard-needle item builder for the exact same needle set."""
    items = []
    for seed in seeds:
        rng = random.Random(seed)
        for mode in hn.MODES:
            for _ in range(items_per_mode):
                prompt, expected, distractors, tag = hn.build_item(mode, target_tokens, rng)
                items.append({"seed": seed, "mode": mode, "prompt": prompt,
                              "expected": expected, "distractors": distractors})
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="hard-needle (fake-quant, pod-only) — MANDATORY gate")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--items-per-mode", type=int, default=6)
    ap.add_argument("--target-tokens", type=int, default=6000)
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--out", default="hard_needle_results.json")
    args = ap.parse_args(argv)
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr); return 2

    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    masks = FQ.load_masks(args.mask)
    seeds = tuple(int(s) for s in args.seeds.split(","))
    iset = build_item_set(seeds=seeds, items_per_mode=args.items_per_mode, target_tokens=args.target_tokens)

    items = []
    for i, it in enumerate(iset):
        row = {"seed": it["seed"], "mode": it["mode"], "cells": {}}
        for cell in CELLS:
            out = FQ.generate(model, tok, it["prompt"], cell, masks, max_new_tokens=args.max_new_tokens)
            label = hn.classify(out, it["expected"], it["distractors"], it["mode"])
            row["cells"][cell] = {"label": label, "output": out[:120]}
        items.append(row)
        print(f"  hard {i+1}/{len(iset)} seed={it['seed']} mode={it['mode']} "
              f"HIT={{{','.join(c for c in CELLS if row['cells'][c]['label']=='HIT')}}}")
    blob = {"model": args.model, "label": "MEASURED", "cells": CELLS, "items": items}
    json.dump(blob, open(args.out, "w"), indent=2)
    print(f"[MEASURED] hard needle -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
