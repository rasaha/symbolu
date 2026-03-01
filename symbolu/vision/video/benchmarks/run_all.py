"""
FSCS-V Benchmark Runner.

Runs all benchmarks for unresolved patent integration gaps and
produces a summary report.

Usage:
    python -m symbolu.vision.video.benchmarks.run_all [--device cpu|cuda] [--quick]

The --quick flag runs with smaller sizes for faster iteration.
"""

import argparse
import sys
import time
import traceback
from typing import List, Tuple

import torch


def run_single_benchmark(name: str, module_name: str, device: str, quick: bool) -> Tuple[str, bool, float]:
    """Run a single benchmark and return (name, passed, elapsed_ms)."""
    try:
        mod = __import__(
            f"symbolu.vision.video.benchmarks.{module_name}",
            fromlist=["run_benchmark", "print_results"],
        )

        kwargs = {"device": device}

        # Quick mode: reduce sizes
        if quick:
            if hasattr(mod, "run_benchmark"):
                import inspect
                sig = inspect.signature(mod.run_benchmark)
                if "n_samples" in sig.parameters:
                    kwargs["n_samples"] = 100
                if "n_videos" in sig.parameters:
                    kwargs["n_videos"] = 4
                if "distill_steps" in sig.parameters:
                    kwargs["distill_steps"] = 200  # Proxy encoder needs enough steps
                if "height" in sig.parameters and module_name != "bench_scale":
                    kwargs["height"] = 16
                if "width" in sig.parameters and module_name != "bench_scale":
                    kwargs["width"] = 16

        t0 = time.time()
        result = mod.run_benchmark(**kwargs)
        passed = mod.print_results(result)
        elapsed = (time.time() - t0) * 1000
        return name, passed, elapsed

    except Exception as e:
        print(f"\n  ERROR in {name}: {e}")
        traceback.print_exc()
        return name, False, 0.0


def main():
    parser = argparse.ArgumentParser(description="FSCS-V Benchmark Suite")
    parser.add_argument(
        "--device", type=str, default=None,
        help="Device to use (cpu or cuda). Default: auto-detect.",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Run with smaller sizes for faster iteration.",
    )
    parser.add_argument(
        "--bench", type=str, default=None,
        help="Run only this benchmark (e.g., 'rectification', 'l2_phase_lock').",
    )
    args = parser.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    benchmarks = [
        ("Issue 1: Rectification", "bench_rectification"),
        ("Issue 6: L2 Phase-Lock", "bench_l2_phase_lock"),
        ("Issue 7: Gradient Safety", "bench_gradient_safety"),
        ("Issue 8: Three-Band Ablation", "bench_three_band_ablation"),
        ("Issue 4: Proxy Encoder", "bench_proxy_encoder"),
        ("Next Step 3: FVD/Quality", "bench_fvd"),
        ("Next Step 4: Identity Lock", "bench_identity_lock"),
        ("Next Step 5: Scale Test", "bench_scale"),
    ]

    if args.bench:
        benchmarks = [
            (name, mod) for name, mod in benchmarks
            if args.bench.lower() in mod.lower() or args.bench.lower() in name.lower()
        ]
        if not benchmarks:
            print(f"No benchmark matching '{args.bench}'")
            sys.exit(1)

    print()
    print("=" * 70)
    print("  FSCS-V BENCHMARK SUITE")
    print(f"  Device: {device} | Quick: {args.quick} | Benchmarks: {len(benchmarks)}")
    print("=" * 70)
    print()

    results: List[Tuple[str, bool, float]] = []
    total_start = time.time()

    for name, module_name in benchmarks:
        print(f"\n{'~' * 70}")
        print(f"  Running: {name}")
        print(f"{'~' * 70}\n")
        result = run_single_benchmark(name, module_name, device, args.quick)
        results.append(result)

    total_elapsed = (time.time() - total_start) * 1000

    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()

    def check(v): return "\u2705" if v else "\u274c"

    passed_count = 0
    for name, passed, elapsed in results:
        status = check(passed)
        passed_count += passed
        print(f"  {status} {name:<40} ({elapsed:.0f}ms)")

    print()
    print(f"  Results: {passed_count}/{len(results)} passed")
    print(f"  Total time: {total_elapsed:.0f}ms")
    print()

    # Issue resolution status
    print("  Unresolved Issue Status:")
    issue_map = {
        "Issue 1": "Rectification Gap",
        "Issue 4": "Proxy Encoder",
        "Issue 6": "L2 Phase-Lock",
        "Issue 7": "Gradient Safety",
        "Issue 8": "Three-Band",
    }
    for name, passed, _ in results:
        for issue_id, issue_name in issue_map.items():
            if issue_id in name:
                status = "VALIDATED" if passed else "NEEDS WORK"
                print(f"    {issue_id} ({issue_name}): {status}")

    print()
    all_passed = passed_count == len(results)
    print(f"  OVERALL: {'ALL PASS' if all_passed else 'SOME FAILURES'}")
    print()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
