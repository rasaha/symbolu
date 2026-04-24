#!/usr/bin/env python
"""Probe source-level variance directly — bypass the full observable
probe and just call ``make_sources(q)`` then ``sources[0].lookahead()``
for N questions.

Purpose: the §11 probe reports source_0_entropy = 1.3821 with
Pearson r = +0.000 across 120 datapoints (zero variance). Either the
HuggingFaceSource is returning a constant distribution regardless of
prompt, or the observable/probe loop has a bug downstream of source
construction. This script isolates source output:

    for each question (up to N):
        sources = benchmark.make_sources(question)
        probs, _mask = sources[0].lookahead()
        print(entropy, top1_prob, top1_token, vocab_size, argmax_distribution)

If entropy varies across questions → the source is fine; dig into
the observable or probe loop.

If entropy is constant → the source is broken; the 5 distinct
prompts are producing the same output distribution, which narrows
the bug to HuggingFaceSource.__init__ / _initialize_lookahead or
to make_sources itself.

Usage:

    HF_HUB_DISABLE_XET=1 python scripts/diag_source_variance.py \\
        --num-questions 5 \\
        --model Qwen/Qwen2.5-7B-Instruct \\
        --draft-model Qwen/Qwen2.5-3B-Instruct

About 1 forward pass per question per source pair (target + draft),
so ~10 forward passes total at N=5. Much faster than a full probe.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=5)
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
    )
    parser.add_argument(
        "--draft-model", default="Qwen/Qwen2.5-3B-Instruct",
    )
    parser.add_argument("--no-compile", action="store_true", default=True)
    parser.add_argument("--num-candidates", type=int, default=4)
    parser.add_argument("--candidate-length", type=int, default=16)
    parser.add_argument("--draft-temperature", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    from symbolu_bcvf_llm.benchmark.speculative import (
        SpeculativeDecodingBenchmark,
    )

    print(f"Building benchmark (N={args.num_questions}) ...", flush=True)
    bench = SpeculativeDecodingBenchmark(
        target_model_name=args.model,
        draft_model_name=args.draft_model,
        source_dataset="pminervini/HaluEval",
        source_subset="qa",
        split="data",
        max_questions=args.num_questions,
        num_candidates=args.num_candidates,
        candidate_length=args.candidate_length,
        draft_temperature=args.draft_temperature,
        draft_seed=args.seed,
        compile_model=not args.no_compile,
    )
    print(f"shared_vocab={bench._shared_vocab}\n", flush=True)

    rows = []
    questions = list(bench.questions)[: args.num_questions]
    for q_idx, q in enumerate(questions):
        prompt = q.metadata.get("prompt_text", "<no prompt>")
        prompt_preview = prompt.replace("\n", " ")[:80]
        sources = bench.make_sources(q)
        # source 0 = target, source 1 = draft
        for src_idx, src in enumerate(sources):
            probs, mask = src.lookahead()
            # probs: (L, V). Observable uses probs[0].
            p0 = probs[0].astype(np.float64)
            p0_safe = np.clip(p0, 1e-30, None)
            entropy = float(-np.sum(p0 * np.log(p0_safe)))
            top1_token = int(np.argmax(p0))
            top1_prob = float(p0.max())
            # Top-5 mass to detect degenerate distributions.
            top5_idx = np.argsort(p0)[-5:][::-1]
            top5_mass = float(p0[top5_idx].sum())
            rows.append({
                "q_idx": q_idx,
                "src_idx": src_idx,
                "vocab_size": int(p0.shape[0]),
                "entropy": entropy,
                "top1_token": top1_token,
                "top1_prob": top1_prob,
                "top5_mass": top5_mass,
                "prompt_preview": prompt_preview,
            })

    print(f"{'q':>3} {'src':>3} {'vocab':>7} {'entropy':>10} "
          f"{'top1_p':>8} {'top1_tok':>9} {'top5_mass':>10}  prompt")
    print("-" * 120)
    for r in rows:
        print(f"{r['q_idx']:>3} {r['src_idx']:>3} {r['vocab_size']:>7} "
              f"{r['entropy']:>10.4f} {r['top1_prob']:>8.4f} "
              f"{r['top1_token']:>9} {r['top5_mass']:>10.4f}  "
              f"{r['prompt_preview']}")

    entropies_tgt = [r['entropy'] for r in rows if r['src_idx'] == 0]
    entropies_drf = [r['entropy'] for r in rows if r['src_idx'] == 1]
    print("\nTarget (source 0) entropy:")
    print(f"  values : {[f'{e:.4f}' for e in entropies_tgt]}")
    print(f"  stddev : {np.std(entropies_tgt):.6f}")
    print(f"  range  : [{min(entropies_tgt):.4f}, {max(entropies_tgt):.4f}]")
    print("Draft  (source 1) entropy:")
    print(f"  values : {[f'{e:.4f}' for e in entropies_drf]}")
    print(f"  stddev : {np.std(entropies_drf):.6f}")
    print(f"  range  : [{min(entropies_drf):.4f}, {max(entropies_drf):.4f}]")

    print("\nVERDICT:")
    if np.std(entropies_tgt) < 1e-6:
        print("  target entropy has ZERO variance across distinct prompts.")
        print("  → HuggingFaceSource is returning a constant distribution.")
        print("  → Bug is upstream of the observable: check _initialize_lookahead")
        print("    or the prompt-to-logits path in HuggingFaceSource.__init__.")
    else:
        print("  target entropy VARIES across prompts (as expected).")
        print("  → HuggingFaceSource is working correctly.")
        print("  → The 1.3821-constant report is a downstream bug: probe loop,")
        print("    observable aggregation, or the report's mean-computation path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
