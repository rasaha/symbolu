#!/usr/bin/env python3
"""KVPro V3 Gate-1 — STANDARD needle driver (POD-ONLY for generation; builder is CPU-testable).

REUSES the repo's needle protocol (`verify_phase5b_5_needle._make_needle` / `_build_prompt`,
needle-in-the-middle, the same context-length buckets) and scores by "needle code appears in output".
Runs it through fake-quant per candidate {fp, affine, S1..S4}. Emits needle_results.json.
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
import verify_phase5b_5_needle as vn      # noqa: E402  (repo protocol; pure builders)

CONTEXT_LENS = [200, 600, 1200]           # the repo's 3 filler-token buckets
CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]


def build_prompt_set(seeds=(0, 1), context_lens=CONTEXT_LENS, num_needles=5):
    """CPU-testable: reuse the repo needle builders to produce the exact same prompt set."""
    items = []
    for seed in seeds:
        rng = random.Random(seed)
        for clen in context_lens:
            for _ in range(num_needles):
                needle = vn._make_needle(rng)
                prompt = vn._build_prompt(needle, clen, rng)
                items.append({"seed": seed, "context_len": clen, "needle": needle, "prompt": prompt})
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="standard needle (fake-quant, pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--num-needles", type=int, default=5)
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--out", default="needle_results.json")
    ap.add_argument("--cells", default=",".join(CELLS), help="comma cells; P8 study: fp,affine,P8sym,P8aff")
    args = ap.parse_args(argv)
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr); return 2
    cells = args.cells.split(",")

    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    masks = FQ.load_masks(args.mask)
    seeds = tuple(int(s) for s in args.seeds.split(","))
    pset = build_prompt_set(seeds=seeds, num_needles=args.num_needles)

    items = []
    for i, it in enumerate(pset):
        row = {"seed": it["seed"], "context_len": it["context_len"], "needle": it["needle"], "cells": {}}
        for cell in cells:
            out = FQ.generate(model, tok, it["prompt"], cell, masks, max_new_tokens=args.max_new_tokens)
            row["cells"][cell] = {"hit": it["needle"].lower() in out.lower(), "output": out[:120]}
        items.append(row)
        print(f"  needle {i+1}/{len(pset)} seed={it['seed']} ctx={it['context_len']} "
              f"hits={{{','.join(c for c in cells if row['cells'][c]['hit'])}}}")
    blob = {"model": args.model, "label": "MEASURED", "cells": cells, "items": items}
    json.dump(blob, open(args.out, "w"), indent=2)
    print(f"[MEASURED] standard needle -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
