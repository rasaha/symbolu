"""CLI entry: ``python -m symbolu_bcvf_llm.benchmark``.

Runs the three §1.10 decoders against the selected benchmark,
writes per-question results as CSV, and synthesizes a Markdown
summary with the §6.5 / §1.10 classification verdict.

V1 defaults to `--benchmark mock` so the harness is runnable
offline without torch / transformers / datasets. `--benchmark
truthfulqa` requires the ML stack and is hard-gated on §0.6
rule 1.

Every run writes four artifacts alongside the existing CSV +
summary, under `--out-dir` with suffix `<suffix>`:

  phase_6_<bench>_results<suffix>.csv     per-question rows
  phase_6_<bench>_summary<suffix>.md      §1.10 verdict summary
  phase_6_<bench>_run<suffix>.log         full DEBUG log file
  phase_6_<bench>_manifest<suffix>.json   env + args + git + outcome
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from symbolu_bcvf_llm.logging_util import (
    capture_environment,
    capture_git_state,
    configure_logging,
    format_exception,
    log_environment,
    write_manifest,
)

from .dataset import MockBenchmark
from .harness import BenchmarkRunBundle, run_benchmark
from .metrics import (
    classify_phase_six_result,
    latency_stats,
    mcnemar_paired,
)


CSV_FIELDNAMES = [
    "benchmark", "seed", "decoder", "question_id",
    "predicted", "correct", "latency_s", "scores",
]


def _result_to_rows(
    bench_name: str, seed: int, decoder: str, result
) -> List[Dict[str, Any]]:
    rows = []
    for i in range(result.num_questions):
        rows.append({
            "benchmark": bench_name,
            "seed": seed,
            "decoder": decoder,
            "question_id": i,
            "predicted": int(result.per_question_predicted[i]),
            "correct": bool(result.per_question_correct[i]),
            "latency_s": float(result.per_question_latency_s[i]),
            "scores": json.dumps(result.per_question_scores[i]),
        })
    return rows


def _write_csv_rows(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_csv(bundle: BenchmarkRunBundle, path: Path) -> None:
    """Write all decoders' results as a single CSV (end-of-run)."""
    rows: List[Dict[str, Any]] = []
    for decoder_name, result in bundle.results.items():
        rows.extend(
            _result_to_rows(bundle.benchmark_name, bundle.seed, decoder_name, result)
        )
    _write_csv_rows(rows, path)


def _write_per_decoder_csv(
    benchmark_name: str,
    seed: int,
    decoder: str,
    result,
    path: Path,
) -> None:
    """Crash-safe incremental CSV — one file per decoder, written as
    soon as that decoder completes."""
    rows = _result_to_rows(benchmark_name, seed, decoder, result)
    _write_csv_rows(rows, path)


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="§6 Phase 4 — three-decoder benchmark sweep"
    )
    parser.add_argument(
        "--benchmark", choices=("mock", "truthfulqa"), default="mock",
        help="which benchmark to run",
    )
    parser.add_argument(
        "--num-questions", type=int, default=None,
        help="cap number of questions (both mock + truthfulqa)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out-dir", type=Path,
        default=Path(__file__).resolve().parents[2] / "docs" / "experiments",
    )
    parser.add_argument(
        "--suffix", type=str, default="",
        help="filename suffix for results (e.g. '_seed42')",
    )
    parser.add_argument(
        "--model", type=str,
        default="meta-llama/Meta-Llama-3.1-8B-Instruct",
        help="HuggingFace model name (truthfulqa only). "
             "Defaults to §1.3's Llama 3.1 8B Instruct.",
    )
    parser.add_argument(
        "--no-paraphrase", action="store_true",
        help="truthfulqa only: use three identical prompts instead of "
             "paraphrasing. Useful for smoke-testing the HuggingFaceSource "
             "plumbing without the paraphrase round-trip.",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="smoke run: N=2 questions, --no-paraphrase, suffix '_smoke'. "
             "Meant for first-time verification that the ML stack and the "
             "harness run end-to-end before committing to a full sweep.",
    )
    parser.add_argument(
        "--split", type=str, default="validation",
        help="truthfulqa split (validation is the usual choice).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="DEBUG level on the console handler (file log is always DEBUG).",
    )
    parser.add_argument(
        "--no-compile", action="store_true",
        help="truthfulqa only: disable `torch.compile` on the model. "
             "Default is ON (2-3× forward-pass speedup on Ampere+); "
             "disable if compile throws an unrecoverable error.",
    )
    parser.add_argument(
        "--no-compile-dynamic", action="store_true",
        help="use static shapes in torch.compile (default is dynamic=True "
             "because teacher-forcing produces variable sequence lengths; "
             "static compile would recompile on every shape change).",
    )
    parser.add_argument(
        "--no-fast-scoring", action="store_true",
        help="§6.2 Phase 2 escape hatch: force every decoder to use the "
             "slow lookahead/commit scoring loop. Default is fast-scoring "
             "ON (~15× speedup on vanilla + blend via single-forward-pass "
             "teacher-forcing; trust stays speculation-based regardless).",
    )
    parser.add_argument(
        "--paraphrase-cache-file", type=Path, default=None,
        help="disk-persistent paraphrase cache path (truthfulqa only). "
             "If unset, defaults to <out-dir>/paraphrase_cache_<model>_<split>.json. "
             "Set to '' or 'none' to disable disk persistence (in-memory "
             "cache only — back to pre-cache behaviour).",
    )
    parser.add_argument(
        "--no-paraphrase-cache-file", action="store_true",
        help="disable disk-persistent paraphrase cache entirely.",
    )
    parser.add_argument(
        "--clear-paraphrase-cache", action="store_true",
        help="truthfulqa only: delete the disk paraphrase cache file "
             "before the run (if it exists). Forces fresh paraphrase "
             "generation. Useful as a belt-and-suspenders over the "
             "automatic pipeline-version check that normally rejects "
             "stale caches.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Smoke mode rewrites the other args for convenience.
    if args.smoke:
        args.num_questions = 2 if args.num_questions is None else min(
            args.num_questions, 2
        )
        args.no_paraphrase = True
        if not args.suffix:
            args.suffix = "_smoke"

    # Output paths resolved up-front so the log file is created
    # before any heavy work (model load, dataset download) that can
    # fail with informative tracebacks.
    out_dir = Path(args.out_dir)
    run_tag = f"phase_6_{args.benchmark}{args.suffix}"
    csv_path = out_dir / f"{run_tag.replace('phase_6_', 'phase_6_') }_results".replace(
        "_results", "_results"
    )  # keep original layout
    csv_path = out_dir / f"phase_6_{args.benchmark}_results{args.suffix}.csv"
    md_path = out_dir / f"phase_6_{args.benchmark}_summary{args.suffix}.md"
    log_path = out_dir / f"phase_6_{args.benchmark}_run{args.suffix}.log"
    manifest_path = (
        out_dir / f"phase_6_{args.benchmark}_manifest{args.suffix}.json"
    )

    logger = configure_logging(log_path=log_path, verbose=args.verbose)
    logger.info("=" * 72)
    logger.info("§6 Phase 4 benchmark run starting")
    logger.info("=" * 72)
    logger.info("args = %s", {k: str(v) for k, v in vars(args).items()})
    env_info = log_environment(logger)

    manifest: Dict[str, Any] = {
        "script": "symbolu_bcvf_llm.benchmark",
        "args": {k: str(v) for k, v in vars(args).items()},
        "output_paths": {
            "results_csv": str(csv_path),
            "summary_md": str(md_path),
            "run_log": str(log_path),
            "manifest_json": str(manifest_path),
        },
        **env_info,
        "outcome": "PENDING",
    }
    write_manifest(manifest_path, manifest)

    t_start = time.perf_counter()

    try:
        if args.benchmark == "mock":
            n = args.num_questions if args.num_questions is not None else 48
            logger.info("Instantiating MockBenchmark(num_questions=%d)", n)
            bench = MockBenchmark(num_questions=n, seed=args.seed)
        else:  # pragma: no cover — real benchmark path not exercised here
            logger.info(
                "Instantiating TruthfulQABenchmark(model=%s, split=%s, "
                "max_questions=%s, use_paraphrase=%s)",
                args.model, args.split, args.num_questions,
                not args.no_paraphrase,
            )
            t_load = time.perf_counter()
            from .dataset import TruthfulQABenchmark

            # Resolve default paraphrase-cache path: per model + split
            # so two models' caches never collide. Disabled by
            # --no-paraphrase-cache-file.
            if args.no_paraphrase_cache_file:
                cache_file = None
            elif args.paraphrase_cache_file is not None:
                cache_file = args.paraphrase_cache_file
            else:
                model_slug = args.model.replace("/", "_").replace(":", "_")
                cache_file = (
                    args.out_dir
                    / f"paraphrase_cache_{model_slug}__{args.split}.json"
                )
            if cache_file is not None:
                if args.clear_paraphrase_cache and cache_file.exists():
                    logger.info(
                        "--clear-paraphrase-cache: deleting %s "
                        "(explicit user request)",
                        cache_file,
                    )
                    try:
                        cache_file.unlink()
                    except OSError as exc:
                        logger.warning(
                            "Failed to delete cache file: %s", exc
                        )
                logger.info("Paraphrase cache file: %s (exists=%s)",
                            cache_file, cache_file.exists())

            bench = TruthfulQABenchmark(
                model_name=args.model,
                split=args.split,
                max_questions=args.num_questions,
                use_paraphrase=not args.no_paraphrase,
                compile_model=not args.no_compile,
                compile_dynamic=not args.no_compile_dynamic,
                paraphrase_cache_file=cache_file,
                evaluation_seed=args.seed,
            )
            logger.info(
                "Model + dataset loaded in %.1f s", time.perf_counter() - t_load
            )
            logger.info("torch.compile status: %s", bench.compile_status)
            logger.info(
                "§1.10 rewrite seed pair for --seed %d: %s",
                args.seed, bench.rewrite_seed_pair,
            )
            _stats0 = bench.paraphrase_cache_stats
            if _stats0.get("loaded_from_disk", 0) > 0:
                logger.info(
                    "Paraphrase cache warm-start: %d entries loaded from %s",
                    _stats0["loaded_from_disk"], _stats0.get("persisted_to"),
                )
            elif _stats0.get("persisted_to"):
                discard_reason = _stats0.get("discarded_reason")
                if discard_reason:
                    # Cache file existed but was rejected — auto-detect
                    # handled the "rm stale cache" step for the user.
                    logger.info(
                        "Paraphrase cache auto-discarded on load: %s",
                        discard_reason,
                    )
                logger.info(
                    "Paraphrase cache cold-start; will persist to %s as it fills.",
                    _stats0.get("persisted_to"),
                )
            manifest["model"] = {
                "name": args.model,
                "vocab_size": bench.vocab_size,
                "L": bench.L,
                "eos_token_id": bench.eos_token_id,
                "use_paraphrase": not args.no_paraphrase,
                "compile_status": bench.compile_status,
                "rewrite_seed_pair": list(bench.rewrite_seed_pair),
                "evaluation_seed": args.seed,
            }
            write_manifest(manifest_path, manifest)

        n_questions = len(bench.questions)
        logger.info(
            "Running benchmark '%s' with N=%d questions at seed=%d",
            args.benchmark, n_questions, args.seed,
        )

        # Periodic INFO-level progress so long runs (N=817 can take
        # hours per seed) visibly heartbeat. Fires at every 5% milestone
        # and at the final completion; DEBUG fires on every question.
        progress_t0 = {"t": time.perf_counter()}

        def progress(i: int, n: int, decoder: str) -> None:
            logger.debug("  %s: %d/%d", decoder, i, n)
            step = max(1, n // 20)  # 5% granularity
            if i == n or i % step == 0:
                elapsed = time.perf_counter() - progress_t0["t"]
                rate = i / elapsed if elapsed > 0 else 0.0
                eta_s = (n - i) / rate if rate > 0 else float("inf")
                logger.info(
                    "  %s: %d/%d  (%.1f q/min, ETA %s)",
                    decoder, i, n,
                    rate * 60,
                    (
                        f"{eta_s / 60:.1f} min"
                        if eta_s < 3600 else f"{eta_s / 3600:.1f} h"
                    ) if eta_s != float("inf") else "?",
                )
                progress_t0["t"] = time.perf_counter() if i == n else progress_t0["t"]

        # Per-decoder incremental save — crashes mid-run after this point
        # preserve the decoder CSVs that have already completed.
        per_decoder_paths: Dict[str, Path] = {}

        def on_decoder_complete(decoder_name: str, result) -> None:
            p = (
                args.out_dir
                / f"phase_6_{args.benchmark}_results{args.suffix}__{decoder_name}.csv"
            )
            _write_per_decoder_csv(
                bench.name, args.seed, decoder_name, result, p
            )
            per_decoder_paths[decoder_name] = p
            from .metrics import latency_stats as _ls
            ls = _ls(result.per_question_latency_s)
            logger.info(
                "  %-20s CHECKPOINT: accuracy=%.2f%%  "
                "mean_latency=%.3f s  csv=%s",
                decoder_name, result.accuracy * 100, ls.mean_s, p.name,
            )
            # Snapshot the manifest so the partial state is on disk.
            manifest.setdefault("per_decoder_checkpoints", {})
            manifest["per_decoder_checkpoints"][decoder_name] = {
                "accuracy": float(result.accuracy),
                "mean_latency_s": float(ls.mean_s),
                "csv": str(p),
            }
            write_manifest(manifest_path, manifest)

        bundle = run_benchmark(
            benchmark=bench,
            seed=args.seed,
            progress_callback=progress,
            fast_scoring=not args.no_fast_scoring,
            per_decoder_complete_callback=on_decoder_complete,
        )

        _write_csv(bundle, csv_path)
        _write_summary(bundle, md_path)

        for decoder, r in bundle.results.items():
            ls = latency_stats(r.per_question_latency_s)
            logger.info(
                "  %-20s accuracy=%.2f%%  mean_latency=%.3f s  median=%.3f s  p95=%.3f s",
                decoder, r.accuracy * 100, ls.mean_s, ls.median_s, ls.p95_s,
            )

        # Paraphrase-cache diagnostics (TruthfulQABenchmark only).
        cache_stats = getattr(bench, "paraphrase_cache_stats", None)
        if cache_stats is not None:
            logger.info(
                "  paraphrase cache: hits=%d misses=%d entries=%d (hit_rate=%.1f%%)",
                cache_stats["hits"], cache_stats["misses"],
                cache_stats["entries"],
                100.0 * cache_stats["hits"]
                / max(cache_stats["hits"] + cache_stats["misses"], 1),
            )
            manifest["paraphrase_cache_stats"] = cache_stats

        # Compute verdict once so it lands in both the summary and
        # the manifest.
        verdict: Dict[str, Any] = {}
        if (
            "bcvf_trust" in bundle.results
            and "conventional_blend" in bundle.results
        ):
            trust = bundle.results["bcvf_trust"]
            blend = bundle.results["conventional_blend"]
            v = classify_phase_six_result(
                trust_correct=trust.per_question_correct,
                blend_correct=blend.per_question_correct,
                trust_latencies=trust.per_question_latency_s,
                blend_latencies=blend.per_question_latency_s,
            )
            verdict = {
                "classification": v.classification,
                "accuracy_trust": v.accuracy_trust,
                "accuracy_blend": v.accuracy_blend,
                "delta_pp": v.delta_pp,
                "latency_ratio": v.latency_ratio,
                "mcnemar": asdict(v.mcnemar),
                "notes": v.notes,
            }
            logger.info(
                "§1.10 classification: %s  Δ=%+0.2f pp  latency_ratio=%.2f×",
                v.classification, v.delta_pp, v.latency_ratio,
            )

        manifest["per_decoder"] = {
            name: {
                "accuracy": float(r.accuracy),
                "num_questions": int(r.num_questions),
                "mean_latency_s": float(
                    np.mean(r.per_question_latency_s)
                ) if r.num_questions else 0.0,
            }
            for name, r in bundle.results.items()
        }
        manifest["verdict"] = verdict
        manifest["duration_s"] = round(time.perf_counter() - t_start, 3)
        manifest["outcome"] = "OK"
        write_manifest(manifest_path, manifest)

        logger.info("Results: %s", csv_path)
        logger.info("Summary: %s", md_path)
        logger.info("Run log: %s", log_path)
        logger.info("Manifest: %s", manifest_path)
        logger.info("Finished in %.1f s", manifest["duration_s"])
        return 0

    except Exception as exc:
        logger.error(
            "FATAL: run aborted by exception after %.1f s",
            time.perf_counter() - t_start,
        )
        logger.error("%s", traceback.format_exc())
        manifest["outcome"] = "EXCEPTION"
        manifest["exception"] = format_exception(exc)
        manifest["duration_s"] = round(time.perf_counter() - t_start, 3)
        try:
            write_manifest(manifest_path, manifest)
        except Exception:  # pragma: no cover — manifest write failure
            logger.exception("also failed to write manifest")
        logger.error("Manifest with failure state: %s", manifest_path)
        logger.error("Run log: %s", log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
