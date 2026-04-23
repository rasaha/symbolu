#!/usr/bin/env python
"""§11 CLI: probe candidate Ketu observables against a benchmark.

Runs one or more observables over a benchmark, measures AUC vs
correctness, classifies each, and writes a Markdown report.

Verdict-agnostic — works on PASS / NULL / REGRESSION-era data.
The point is to diagnose whether the observable is worth building
a Rahu attractor around BEFORE the expensive decoder run.

Typical usage (no torch, no GPU — MockBenchmark only):

    python scripts/probe_observables.py --benchmark mock --num-questions 48

Against a real model (truthfulqa):

    python scripts/probe_observables.py \\
        --benchmark truthfulqa \\
        --num-questions 100 \\
        --model mistralai/Mistral-7B-Instruct-v0.3 \\
        --no-compile

Output: `docs/experiments/probe_observables__<suffix>.md`.
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

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark  # noqa: E402
from symbolu_bcvf_llm.observables import (  # noqa: E402
    BCVFPerStepMaxObservable,
    BCVFSourceZeroCostObservable,
    BCVFSourceZeroPerStepMaxObservable,
    BCVFTotalCostObservable,
    Source0EntropyObservable,
    SourceAgreementObservable,
    probe_observables_parallel,
)


def build_observables():
    return [
        BCVFTotalCostObservable(),
        BCVFSourceZeroCostObservable(),
        Source0EntropyObservable(),
        SourceAgreementObservable(),
        BCVFPerStepMaxObservable(),
        BCVFSourceZeroPerStepMaxObservable(),
    ]


def render_report(reports, benchmark_name: str, n_questions: int) -> str:
    lines: List[str] = []
    lines.append("# §11 Ketu Observable Probe Report\n")
    lines.append(f"- **Benchmark:** `{benchmark_name}`")
    lines.append(f"- **Questions probed:** {n_questions}")
    lines.append(f"- **Observables tested:** {len(reports)}\n")

    lines.append("## Verdict summary\n")
    lines.append(
        "| Observable | AUC | Classification | Mean(correct) | Mean(wrong) |"
    )
    lines.append("|---|---|---|---|---|")
    for name, r in reports.items():
        lines.append(
            f"| `{name}` | {r.auc:.3f} | **{r.classification}** | "
            f"{r.mean_scalar_when_correct:.4f} | {r.mean_scalar_when_wrong:.4f} |"
        )

    lines.append("\n## Per-observable detail\n")
    for name, r in reports.items():
        lines.append(f"### `{name}`\n")
        lines.append(
            f"- **AUC:** {r.auc:.3f}  (higher AUC = observable predicts correctness better)"
        )
        lines.append(f"- **Pearson r:** {r.pearson_r:+.3f}")
        lines.append(f"- **Spearman ρ:** {r.spearman_rho:+.3f}")
        lines.append(
            f"- **Polarity:** "
            + ("higher = more suspicious" if r.higher_means_more_suspicious
               else "higher = more trusted")
        )
        lines.append(
            f"- **Mean scalar when correct:** {r.mean_scalar_when_correct:.4f}"
        )
        lines.append(
            f"- **Mean scalar when wrong:** {r.mean_scalar_when_wrong:.4f}"
        )
        lines.append(
            f"- **N datapoints:** {r.n_datapoints} "
            f"(from {r.n_questions} questions)"
        )
        lines.append(f"- **Classification:** **`{r.classification}`**")
        lines.append(f"\n**Recommendation:** {r.recommendation}\n")

    lines.append("\n## Discipline — what this report means\n")
    lines.append(
        "§11 Observable Discipline (per §10.V1's falsification lesson): "
        "before building a Rahu attractor on top of any Ketu observable, "
        "the observable must be probed on a held-out benchmark subset "
        "to confirm it is truth-correlated. The AUC bands used here:\n"
    )
    lines.append("- `AUC ≥ 0.60` → **TRUTH_CORRELATED** — worth a Rahu attractor.")
    lines.append("- `0.45 ≤ AUC < 0.60` → **UNCORRELATED** — a Rahu built on "
                 "this converges to conventional blend at best.")
    lines.append("- `AUC < 0.45` → **ANTI_CORRELATED** — signal is present "
                 "with the WRONG sign. A Rahu on this would actively hurt "
                 "accuracy (V1's failure mode).")
    lines.append("- `n<40` → **NULL** — too few datapoints; expand N.\n")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="§11 probe candidate Ketu observables vs benchmark ground truth."
    )
    parser.add_argument(
        "--benchmark",
        choices=("mock", "truthfulqa", "halueval"),
        default="mock",
    )
    parser.add_argument(
        "--num-questions", type=int, default=48,
        help="number of benchmark questions to probe (default 48)",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
    )
    parser.add_argument("--suffix", type=str, default="")
    # truthfulqa-only
    parser.add_argument(
        "--model", type=str,
        default="mistralai/Mistral-7B-Instruct-v0.3",
    )
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--no-paraphrase", action="store_true")
    parser.add_argument(
        "--paraphraser-model", type=str, default=None,
        help=(
            "HF model name to use for paraphrase generation. Defaults "
            "to the same model as --model (V1 same-model configuration). "
            "Set to a different model for §10.V1.3 Experiment A "
            "cross-model source ensemble."
        ),
    )
    parser.add_argument(
        "--paraphrase-cache-file", type=pathlib.Path, default=None,
        help=(
            "Persist paraphrases to this JSON so subsequent runs reuse "
            "them. Cache is invalidated if (model, paraphraser, split, "
            "pipeline version) change."
        ),
    )
    args = parser.parse_args(argv)

    if args.benchmark == "mock":
        bench = MockBenchmark(num_questions=args.num_questions, seed=args.seed)
    else:
        if args.benchmark == "truthfulqa":
            from symbolu_bcvf_llm.benchmark.dataset import TruthfulQABenchmark
            bench_cls = TruthfulQABenchmark
        else:  # halueval
            from symbolu_bcvf_llm.benchmark.dataset import HaluEvalBenchmark
            bench_cls = HaluEvalBenchmark
        bench = bench_cls(
            model_name=args.model,
            max_questions=args.num_questions,
            compile_model=not args.no_compile,
            use_paraphrase=not args.no_paraphrase,
            evaluation_seed=args.seed,
            paraphraser_model_name=args.paraphraser_model,
            paraphrase_cache_file=args.paraphrase_cache_file,
        )

    observables = build_observables()
    total_q = len(list(bench.questions))
    n_q = min(args.num_questions, total_q) if args.num_questions else total_q
    print(
        f"Probing {len(observables)} observables against "
        f"{args.benchmark} N={n_q}...",
        flush=True,
    )

    t0 = time.perf_counter()
    reports = probe_observables_parallel(
        observables, bench,
        max_questions=args.num_questions,
        retain_datapoints=False,
    )
    elapsed = time.perf_counter() - t0
    print(f"Probed in {elapsed:.1f} s")

    # Terminal summary
    print()
    print(f"{'Observable':<36} {'AUC':>6}   {'Classification':<22} {'N':>5}")
    print("-" * 76)
    for name, r in reports.items():
        print(
            f"{name:<36} {r.auc:>6.3f}   "
            f"{r.classification:<22} {r.n_datapoints:>5}"
        )
    print()

    out_path = args.out_dir / f"probe_observables_{args.benchmark}{args.suffix}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(
        reports,
        benchmark_name=args.benchmark,
        n_questions=int(next(iter(reports.values())).n_questions),
    ))
    print(f"Markdown report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
