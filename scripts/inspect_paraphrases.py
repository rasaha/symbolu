#!/usr/bin/env python
"""Fast standalone paraphrase inspector.

Loads a HuggingFace causal LM + tokenizer, pulls N TruthfulQA-MC
questions, and generates paraphrases for each using the current
``make_paraphrased_prompt`` pipeline (including the §10.V1.6 cleaning
+ validation). Dumps the raw + cleaned + validation-status triple per
question so you can see exactly what the rewriter is producing.

Purpose: a ~1-2 minute sanity check on the paraphrase pipeline
without paying the full benchmark harness cost (torch.compile warmup,
trust decoder's 45-forward-passes-per-question speculation loop,
multi-decoder scoring, etc.). Runs ~100× faster than the full
benchmark at the same N.

Typical usage on RunPod:

    python scripts/inspect_paraphrases.py \\
        --model mistralai/Mistral-7B-Instruct-v0.3 \\
        --num-questions 10 \\
        --seed 1

Prints two paraphrases per question (rewrite-seed pair from --seed),
side-by-side with the original.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from typing import List

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from symbolu_bcvf_llm.sources.paraphrase import (  # noqa: E402
    DEFAULT_REWRITE_INSTRUCTION,
    V1_REWRITE_INSTRUCTION,
    make_paraphrased_prompt,
)


def _load_questions(
    num_questions: int, split: str = "validation"
) -> List[dict]:
    """Load first N TruthfulQA-MC rows (without the full benchmark harness)."""
    from datasets import load_dataset

    ds = load_dataset("truthful_qa", "multiple_choice", split=split)
    ds = ds.select(range(min(num_questions, len(ds))))
    return [{"question": row["question"], "row_id": i}
            for i, row in enumerate(ds)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Fast paraphrase inspector — no benchmark, no trust decoder."
    )
    parser.add_argument(
        "--model", default="mistralai/Mistral-7B-Instruct-v0.3",
        help="HuggingFace causal LM",
    )
    parser.add_argument(
        "--num-questions", type=int, default=10,
        help="how many TruthfulQA-MC questions to paraphrase",
    )
    parser.add_argument(
        "--seed", type=int, default=1,
        help="evaluation seed — determines rewrite-seed pair via (2N-1, 2N)",
    )
    parser.add_argument(
        "--split", default="validation",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=64,
        help="max tokens per paraphrase generate() call",
    )
    parser.add_argument(
        "--use-v1-template", action="store_true",
        help="use the V1 (pre-fix) rewrite template for A/B comparison",
    )
    parser.add_argument(
        "--no-clean", action="store_true",
        help="skip the §10.V1.6 post-processing; show raw model output",
    )
    parser.add_argument(
        "--compile", action="store_true",
        help="enable torch.compile (default OFF; has ~60s warmup that "
             "only pays back on large N)",
    )
    args = parser.parse_args(argv)

    try:
        import torch
        import transformers  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        print("pip install torch transformers datasets", file=sys.stderr)
        return 1

    print(f"Loading {args.model} ...", flush=True)
    t_load = time.perf_counter()
    torch.set_float32_matmul_precision("high")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype)
    if torch.cuda.is_available():
        model = model.to("cuda")
    model.eval()
    if args.compile:
        print("torch.compile(dynamic=True) ...", flush=True)
        model = torch.compile(model, dynamic=True)
    print(f"Loaded in {time.perf_counter() - t_load:.1f} s", flush=True)

    print(f"Loading TruthfulQA-MC {args.split} split ...", flush=True)
    questions = _load_questions(args.num_questions, split=args.split)
    print(f"Loaded {len(questions)} questions", flush=True)

    # Evaluation seed → rewrite seed pair (matches TruthfulQABenchmark).
    base = max(int(args.seed), 1)
    rewrite_pair = (2 * base - 1, 2 * base)
    print(f"§1.10 rewrite seed pair for --seed {args.seed}: {rewrite_pair}")

    template = V1_REWRITE_INSTRUCTION if args.use_v1_template else DEFAULT_REWRITE_INSTRUCTION
    clean = not args.no_clean
    print(f"Template: {'V1 (pre-fix)' if args.use_v1_template else 'DEFAULT (post-§10.V1.6)'}")
    print(f"Post-processing: {'OFF (raw model output)' if args.no_clean else 'ON (clean + validate)'}")
    print()
    print("=" * 78)

    # Wrap a single question's prompt just as TruthfulQABenchmark does.
    def prompt_for(q):
        return f"Q: {q['question']}\nA:"

    for q in questions:
        prompt = prompt_for(q)
        print(f"\n[Q{q['row_id']}] Original prompt:")
        print(f"  {prompt!r}")
        for seed in rewrite_pair:
            t0 = time.perf_counter()
            rewrite = make_paraphrased_prompt(
                model, tokenizer, prompt,
                rewrite_seed=seed,
                max_new_tokens=args.max_new_tokens,
                instruction_template=template,
                clean_output=clean,
            )
            elapsed = time.perf_counter() - t0
            fellback = (rewrite == prompt) and clean
            status = "⚠ FALLBACK → original" if fellback else "✓ clean rewrite"
            print(f"\n  Rewrite seed={seed}  ({elapsed*1000:.0f} ms)  {status}")
            print(f"    {rewrite!r}")
        print("-" * 78)

    print()
    print(f"Done. Inspected {len(questions)} questions × 2 paraphrases = "
          f"{len(questions) * 2} rewrites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
