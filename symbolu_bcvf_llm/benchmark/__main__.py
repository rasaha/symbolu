"""CLI entry: ``python -m symbolu_bcvf_llm.benchmark``.

Runs the three §1.10 decoders against the selected benchmark,
writes per-question results as CSV, and synthesizes a Markdown
summary with the §6.5 / §1.10 classification verdict.

V1 defaults to `--benchmark mock` so the harness is runnable
offline without torch / transformers / datasets. `--benchmark
truthfulqa` requires the ML stack and is hard-gated on §0.6
rule 1.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List

import numpy as np

from .dataset import MockBenchmark
from .harness import BenchmarkRunBundle, run_benchmark
from .metrics import (
    classify_phase_six_result,
    latency_stats,
    mcnemar_paired,
)


def _write_csv(bundle: BenchmarkRunBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for decoder_name, result in bundle.results.items():
        for i in range(result.num_questions):
            rows.append({
                "benchmark": bundle.benchmark_name,
                "seed": bundle.seed,
                "decoder": decoder_name,
                "question_id": i,
                "predicted": int(result.per_question_predicted[i]),
                "correct": bool(result.per_question_correct[i]),
                "latency_s": float(result.per_question_latency_s[i]),
                "scores": json.dumps(result.per_question_scores[i]),
            })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "benchmark", "seed", "decoder", "question_id",
                "predicted", "correct", "latency_s", "scores",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(bundle: BenchmarkRunBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# Phase 6 Summary — §1.10 three-decoder comparison\n")
    lines.append(
        f"**Benchmark:** `{bundle.benchmark_name}`   "
        f"**Seed:** `{bundle.seed}`   "
        f"**N:** `{next(iter(bundle.results.values())).num_questions}`\n"
    )
    lines.append("\n## Per-decoder results\n")
    lines.append("| Decoder | Accuracy | Mean latency (s) | Median latency (s) |")
    lines.append("|---|---|---|---|")
    for decoder_name, r in bundle.results.items():
        ls = latency_stats(r.per_question_latency_s)
        lines.append(
            f"| {decoder_name} | {r.accuracy:.2%} | "
            f"{ls.mean_s * 1e3:.2f} ms | {ls.median_s * 1e3:.2f} ms |"
        )

    lines.append("\n## §1.10 classification (single seed)\n")
    if (
        "bcvf_trust" in bundle.results
        and "conventional_blend" in bundle.results
    ):
        trust = bundle.results["bcvf_trust"]
        blend = bundle.results["conventional_blend"]
        verdict = classify_phase_six_result(
            trust_correct=trust.per_question_correct,
            blend_correct=blend.per_question_correct,
            trust_latencies=trust.per_question_latency_s,
            blend_latencies=blend.per_question_latency_s,
        )
        lines.append(f"**Classification:** `{verdict.classification}`\n")
        lines.append(f"- BCVF-trust accuracy: {verdict.accuracy_trust:.2%}")
        lines.append(f"- Conventional-blend accuracy: {verdict.accuracy_blend:.2%}")
        lines.append(f"- Δ (trust − blend): {verdict.delta_pp:+.2f} pp")
        lines.append(f"- Latency ratio: {verdict.latency_ratio:.2f}×")
        lines.append(
            f"- McNemar paired: b={verdict.mcnemar.b}, c={verdict.mcnemar.c}, "
            f"p={verdict.mcnemar.p_value_exact:.3f}"
        )
        lines.append(f"\n**Notes:** {verdict.notes}\n")

    lines.append("\n## Paired comparisons (McNemar)\n")
    lines.append("| A | B | b (A✓ B✗) | c (A✗ B✓) | p (exact two-sided) |")
    lines.append("|---|---|---|---|---|")
    decoders = list(bundle.results.keys())
    for i, a_name in enumerate(decoders):
        for b_name in decoders[i + 1 :]:
            mcn = mcnemar_paired(
                bundle.results[a_name].per_question_correct,
                bundle.results[b_name].per_question_correct,
            )
            lines.append(
                f"| {a_name} | {b_name} | {mcn.b} | {mcn.c} | "
                f"{mcn.p_value_exact:.3f} |"
            )
    path.write_text("\n".join(lines) + "\n")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="§6 Phase 4 — three-decoder benchmark sweep"
    )
    parser.add_argument(
        "--benchmark",
        choices=("mock", "truthfulqa"),
        default="mock",
        help="which benchmark to run",
    )
    parser.add_argument(
        "--num-questions",
        type=int,
        default=None,
        help="cap number of questions (both mock + truthfulqa)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "docs" / "experiments",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="filename suffix for results (e.g. '_seed42')",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="meta-llama/Meta-Llama-3.1-8B-Instruct",
        help="HuggingFace model name (truthfulqa only). "
             "Defaults to §1.3's Llama 3.1 8B Instruct.",
    )
    parser.add_argument(
        "--no-paraphrase",
        action="store_true",
        help="truthfulqa only: use three identical prompts instead of "
             "paraphrasing. Useful for smoke-testing the HuggingFaceSource "
             "plumbing without the paraphrase round-trip.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="smoke run: N=2 questions, --no-paraphrase, suffix '_smoke'. "
             "Meant for first-time verification that the ML stack and the "
             "harness run end-to-end before committing to a full sweep.",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        help="truthfulqa split (validation is the usual choice).",
    )
    args = parser.parse_args(argv)

    # Smoke mode rewrites the other args for convenience.
    if args.smoke:
        args.num_questions = 2 if args.num_questions is None else min(
            args.num_questions, 2
        )
        args.no_paraphrase = True
        if not args.suffix:
            args.suffix = "_smoke"

    if args.benchmark == "mock":
        n = args.num_questions if args.num_questions is not None else 48
        bench = MockBenchmark(num_questions=n, seed=args.seed)
    else:  # pragma: no cover — real benchmark path not exercised here
        from .dataset import TruthfulQABenchmark
        bench = TruthfulQABenchmark(
            model_name=args.model,
            split=args.split,
            max_questions=args.num_questions,
            use_paraphrase=not args.no_paraphrase,
        )

    print(
        f"Running {args.benchmark} benchmark, "
        f"N={len(bench.questions)}, seed={args.seed}"
        + (f", model={args.model}" if args.benchmark == "truthfulqa" else "")
        + (", NO-PARAPHRASE" if args.no_paraphrase else "")
        + " ..."
    )

    def progress(i, n, decoder):
        if i == n:
            print(f"  {decoder}: {i}/{n}")

    bundle = run_benchmark(
        benchmark=bench,
        seed=args.seed,
        progress_callback=progress,
    )

    csv_path = args.out_dir / f"phase_6_{args.benchmark}_results{args.suffix}.csv"
    md_path = args.out_dir / f"phase_6_{args.benchmark}_summary{args.suffix}.md"
    _write_csv(bundle, csv_path)
    _write_summary(bundle, md_path)

    for decoder, r in bundle.results.items():
        print(f"  {decoder}: accuracy = {r.accuracy:.2%}")

    print(f"\nResults: {csv_path}")
    print(f"Summary: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
