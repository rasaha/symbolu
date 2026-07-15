#!/usr/bin/env python3
"""KVPro V3 Gate-1 — MMLU / knowledge driver (POD-ONLY for generation; builder CPU-testable).

REUSES the repo MMLU harness (`bench_phase6n_mmlu_quality.build_prompt` / `parse_answer` / `_load_mmlu`
/ `_BUILTIN_QA`, tol `DEFAULT_TOL_PCT`=1.0). Small deterministic subset for the first gate; `--num-questions`
large + `--real` pulls the full prior battery via `datasets`. Runs fake-quant per candidate; emits
knowledge_results.json with exact-answer agreement handled downstream by results.py/gates.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "CTM_plus", "Bench", "scripts"))
import bench_phase6n_mmlu_quality as mm    # noqa: E402  (pure build_prompt/parse_answer/score/_load_mmlu)

CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]


def build_question_set(num_questions=8, real=False):
    """CPU-testable when real=False (uses the repo's built-in deterministic set). real=True pulls MMLU."""
    if real:
        return mm._load_mmlu(num_questions)                # raises clearly if `datasets` missing
    qs = list(mm._BUILTIN_QA)
    # tile deterministically up to num_questions (no randomness) for a slightly larger quick gate
    out = []
    while len(out) < num_questions:
        out.extend(qs)
    return out[:num_questions]


def main(argv=None):
    ap = argparse.ArgumentParser(description="MMLU/knowledge (fake-quant, pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--num-questions", type=int, default=8)
    ap.add_argument("--real", action="store_true", help="pull real MMLU via `datasets` (full prior battery)")
    ap.add_argument("--max-new-tokens", type=int, default=5)
    ap.add_argument("--out", default="knowledge_results.json")
    args = ap.parse_args(argv)
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr); return 2

    questions = build_question_set(args.num_questions, real=args.real)
    if not questions:
        print("[FAIL] no questions (dataset missing?)", file=sys.stderr); return 2

    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    masks = FQ.load_masks(args.mask)

    items = []
    for i, q in enumerate(questions):
        prompt = mm.build_prompt(q["q"], q["choices"])
        row = {"seed": 0, "gold": int(q["answer"]), "cells": {}}
        for cell in CELLS:
            out = FQ.generate(model, tok, prompt, cell, masks, max_new_tokens=args.max_new_tokens)
            row["cells"][cell] = {"pred": mm.parse_answer(out), "output": out[:40]}
        items.append(row)
        preds = ",".join(f"{c}:{row['cells'][c]['pred']}" for c in CELLS)
        print(f"  q {i+1}/{len(questions)} gold={q['answer']} preds={{{preds}}}")
    blob = {"model": args.model, "label": "MEASURED", "cells": CELLS,
            "dataset": "mmlu-real" if args.real else "builtin-deterministic", "items": items}
    json.dump(blob, open(args.out, "w"), indent=2)
    print(f"[MEASURED] knowledge -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
