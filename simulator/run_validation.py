#!/usr/bin/env python3
"""
CTM+ Validation Script

Runs CTM+ against baselines on multiple synthetic workloads
and reports whether validation criteria are met.

Success criteria:
1. >10% hit rate improvement over LRU on at least one workload
2. No >5% regression on any workload
3. Move rate <2x compared to LRU

Usage:
    python run_validation.py
    python run_validation.py --events 200000
    python run_validation.py --quick
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ctm_plus import Simulator, SimulatorConfig
from ctm_plus.controllers.lru import LRUController
from ctm_plus.controllers.arc import ARCController
from ctm_plus.controllers.ctm_plus import CTMPlusController
from ctm_plus.traces import generate_synthetic_trace
from ctm_plus.core.metrics import compare_results


def run_validation(num_events: int = 100000, verbose: bool = True) -> bool:
    """
    Run full validation suite.

    Returns:
        True if validation passes, False otherwise
    """
    # Configuration
    config = SimulatorConfig(
        tier0_size=1000,
        tier1_size=100000,
    )

    sim = Simulator(config=config)

    workloads = [
        ("zipf", "Zipfian (database-like)"),
        ("hotspot", "Hotspot (80/20)"),
        ("temporal", "Temporal locality"),
        ("mixed", "Mixed phases"),
        ("uniform", "Uniform random (worst case)"),
    ]

    results = {}
    improvements = []
    regressions = []
    move_ratios = []

    print("=" * 70)
    print("CTM+ VALIDATION SUITE")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Tier-0 size: {config.tier0_size:,} pages")
    print(f"  Tier-1 size: {config.tier1_size:,} pages")
    print(f"  Events per workload: {num_events:,}")
    print()

    for pattern, description in workloads:
        print(f"\n{'─' * 70}")
        print(f"Workload: {description}")
        print(f"{'─' * 70}")

        # Generate trace
        trace = generate_synthetic_trace(
            pattern=pattern,
            num_events=num_events,
            num_pages=10000,
            seed=42,
        )

        # Create fresh controllers
        lru = LRUController(config)
        arc = ARCController(config)
        ctm = CTMPlusController(config)

        # Run simulations
        lru_result = sim.run(trace, lru, f"{pattern}_lru", verbose=verbose)
        arc_result = sim.run(trace, arc, f"{pattern}_arc", verbose=verbose)
        ctm_result = sim.run(trace, ctm, f"{pattern}_ctm", verbose=verbose)

        # Compute improvements
        comp = compare_results(lru_result.metrics, ctm_result.metrics)

        results[pattern] = {
            "lru_hit_rate": lru_result.metrics.hit_rate,
            "arc_hit_rate": arc_result.metrics.hit_rate,
            "ctm_hit_rate": ctm_result.metrics.hit_rate,
            "improvement": comp["hit_rate_improvement"],
            "improvement_pct": comp["hit_rate_improvement_pct"],
            "lru_move_rate": lru_result.metrics.move_rate,
            "ctm_move_rate": ctm_result.metrics.move_rate,
        }

        # Track metrics
        improvements.append(comp["hit_rate_improvement_pct"])
        if comp["hit_rate_improvement_pct"] < -0.05:
            regressions.append((pattern, comp["hit_rate_improvement_pct"]))

        if lru_result.metrics.move_rate > 0:
            move_ratio = ctm_result.metrics.move_rate / lru_result.metrics.move_rate
        else:
            move_ratio = 1.0
        move_ratios.append(move_ratio)

        # Print results
        print(f"\n  Results:")
        print(f"    LRU hit rate:  {lru_result.metrics.hit_rate:.2%}")
        print(f"    ARC hit rate:  {arc_result.metrics.hit_rate:.2%}")
        print(f"    CTM+ hit rate: {ctm_result.metrics.hit_rate:.2%}")
        print(f"    Improvement:   {comp['hit_rate_improvement']:+.2%} ({comp['hit_rate_improvement_pct']:+.1%})")
        print(f"    Move ratio:    {move_ratio:.2f}x")

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    max_improvement = max(improvements)
    max_regression = min(improvements) if improvements else 0
    max_move_ratio = max(move_ratios) if move_ratios else 1.0

    print(f"\nBest improvement:  {max_improvement:+.1%}")
    print(f"Worst regression:  {max_regression:+.1%}")
    print(f"Max move ratio:    {max_move_ratio:.2f}x")

    # Check criteria
    criteria_met = []

    # Criterion 1: >10% improvement on at least one workload
    crit1 = max_improvement >= 0.10
    criteria_met.append(crit1)
    status1 = "✅ PASS" if crit1 else "❌ FAIL"
    print(f"\nCriterion 1: >10% improvement on at least one workload")
    print(f"  {status1} (best: {max_improvement:+.1%})")

    # Criterion 2: No >5% regression on any workload
    crit2 = max_regression >= -0.05
    criteria_met.append(crit2)
    status2 = "✅ PASS" if crit2 else "❌ FAIL"
    print(f"\nCriterion 2: No >5% regression on any workload")
    print(f"  {status2} (worst: {max_regression:+.1%})")
    if regressions:
        for pattern, reg in regressions:
            print(f"    ⚠️  {pattern}: {reg:+.1%}")

    # Criterion 3: Move rate <2x
    crit3 = max_move_ratio <= 2.0
    criteria_met.append(crit3)
    status3 = "✅ PASS" if crit3 else "❌ FAIL"
    print(f"\nCriterion 3: Move rate <2x compared to LRU")
    print(f"  {status3} (max: {max_move_ratio:.2f}x)")

    # Final verdict
    all_pass = all(criteria_met)
    print("\n" + "=" * 70)
    if all_pass:
        print("🎉 VALIDATION PASSED - CTM+ meets all criteria")
    else:
        print("❌ VALIDATION FAILED - CTM+ does not meet all criteria")
    print("=" * 70)

    # Detailed results table
    print("\n\nDETAILED RESULTS TABLE")
    print("-" * 70)
    print(f"{'Workload':<15} {'LRU':<10} {'ARC':<10} {'CTM+':<10} {'Δ vs LRU':<12} {'Move Ratio':<10}")
    print("-" * 70)
    for pattern, r in results.items():
        print(
            f"{pattern:<15} "
            f"{r['lru_hit_rate']:<10.2%} "
            f"{r['arc_hit_rate']:<10.2%} "
            f"{r['ctm_hit_rate']:<10.2%} "
            f"{r['improvement']:+<12.2%} "
            f"{r['ctm_move_rate'] / max(r['lru_move_rate'], 0.001):<10.2f}x"
        )
    print("-" * 70)

    return all_pass


def main():
    parser = argparse.ArgumentParser(description="CTM+ Validation Suite")
    parser.add_argument(
        "--events",
        type=int,
        default=100000,
        help="Events per workload (default: 100000)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick run with 10000 events",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    if args.quick:
        num_events = 10000
    else:
        num_events = args.events

    success = run_validation(num_events=num_events, verbose=not args.quiet)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
