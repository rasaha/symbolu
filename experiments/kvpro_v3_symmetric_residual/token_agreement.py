#!/usr/bin/env python3
"""KVPro V3 Gate-1 — token-agreement (POD-ONLY). Two precisely-defined, SEPARATE metrics:

  teacher_forced_agree     : argmax next-token over a fixed text, per position, == fp's argmax.
  autoregressive_agree     : greedily generate N tokens from a prompt; position-wise == fp's tokens.

These are NOT mixed. Emits token_agreement.json. This is a SECONDARY signal — the gate does not GO on
token agreement (or ppl) alone; it requires needle + hard-needle + MMLU.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def main(argv=None):
    ap = argparse.ArgumentParser(description="token agreement (fake-quant, pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--text", default="The field report logged a measurement, a checksum, and a "
                                      "timestamp before the shift change. " * 12)
    ap.add_argument("--gen-prompt", default="Continue this log entry factually:")
    ap.add_argument("--gen-tokens", type=int, default=32)
    ap.add_argument("--out", default="token_agreement.json")
    args = ap.parse_args(argv)
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr); return 2

    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    masks = FQ.load_masks(args.mask)

    # teacher-forced reference (fp)
    fp_tf, _ = FQ.teacher_forced_argmax(model, tok, args.text, "fp", masks)
    # autoregressive reference (fp)
    fp_gen = tok(FQ.generate(model, tok, args.gen_prompt, "fp", masks, max_new_tokens=args.gen_tokens),
                 return_tensors="pt").input_ids[0]

    cells = {}
    for cell in FQ.CELLS:
        tf, _ = FQ.teacher_forced_argmax(model, tok, args.text, cell, masks)
        tf_agree = float((tf == fp_tf).float().mean() * 100.0)
        gen = tok(FQ.generate(model, tok, args.gen_prompt, cell, masks, max_new_tokens=args.gen_tokens),
                  return_tensors="pt").input_ids[0]
        n = min(len(gen), len(fp_gen))
        ar_agree = float((gen[:n] == fp_gen[:n]).float().mean() * 100.0) if n else 0.0
        cells[cell] = {"teacher_forced_agree": round(tf_agree, 3),
                       "autoregressive_agree": round(ar_agree, 3)}
        print(f"  {cell:7} teacher_forced={cells[cell]['teacher_forced_agree']} "
              f"autoregressive={cells[cell]['autoregressive_agree']}")
    blob = {"model": args.model, "label": "MEASURED", "cells": cells,
            "note": "teacher-forced and autoregressive are separate; secondary signal, not a GO gate."}
    json.dump(blob, open(args.out, "w"), indent=2)
    print(f"[MEASURED] token agreement -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
