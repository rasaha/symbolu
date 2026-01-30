#!/usr/bin/env python3
"""
Command-line interface for CTM+ simulator.

Usage:
    # Run with synthetic trace
    python -m ctm_plus.cli --pattern zipf --events 100000

    # Run with trace file
    python -m ctm_plus.cli --trace path/to/trace.csv

    # Compare controllers
    python -m ctm_plus.cli --pattern hotspot --compare

    # Generate trace file
    python -m ctm_plus.cli --generate --pattern mixed --output trace.csv
"""

import argparse
import json
import sys
from pathlib import Path

from .simulator import Simulator, run_comparison
from .core.config import SimulatorConfig, CTMPlusConfig
from .core.metrics import print_comparison
from .controllers.lru import LRUController, LRU2Controller
from .controllers.arc import ARCController
from .controllers.ctm_plus import CTMPlusController
from .traces.loader import (
    load_trace,
    generate_synthetic_trace,
    save_trace_csv,
)


def main():
    parser = argparse.ArgumentParser(
        description="CTM+ Simulator - Validate Coherence-Tier Memory algorithms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with Zipfian workload
  python -m ctm_plus.cli --pattern zipf --events 50000

  # Full comparison on hotspot workload
  python -m ctm_plus.cli --pattern hotspot --events 200000 --compare

  # Run on your own trace
  python -m ctm_plus.cli --trace my_trace.csv --tier0 2000 --tier1 200000

  # Generate trace for external use
  python -m ctm_plus.cli --generate --pattern mixed --events 1000000 --output large_trace.csv
        """,
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--trace",
        type=str,
        help="Path to trace file (CSV, MSR, or binary format)",
    )
    input_group.add_argument(
        "--pattern",
        type=str,
        choices=["uniform", "zipf", "sequential", "hotspot", "temporal", "mixed", "clustered", "correlated"],
        help="Synthetic workload pattern (clustered/correlated test CTM+'s cluster-awareness)",
    )
    input_group.add_argument(
        "--generate",
        action="store_true",
        help="Generate trace file only (use with --pattern and --output)",
    )

    # Trace generation options
    parser.add_argument(
        "--events",
        type=int,
        default=100000,
        help="Number of events for synthetic trace (default: 100000)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=10000,
        help="Number of unique pages in synthetic trace (default: 10000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for generated trace",
    )

    # Tier configuration
    parser.add_argument(
        "--tier0",
        type=int,
        default=1000,
        help="Tier-0 (fast) size in pages (default: 1000)",
    )
    parser.add_argument(
        "--tier1",
        type=int,
        default=100000,
        help="Tier-1 (slow) size in pages (default: 100000)",
    )

    # Controller selection
    parser.add_argument(
        "--controller",
        type=str,
        choices=["lru", "lru2", "arc", "ctm+", "all"],
        default="all",
        help="Controller to use (default: all)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare all controllers (same as --controller all)",
    )

    # CTM+ configuration
    parser.add_argument(
        "--ctm-preset",
        type=str,
        choices=["default", "aggressive", "conservative"],
        default="default",
        help="CTM+ configuration preset",
    )

    # Output options
    parser.add_argument(
        "--json",
        type=str,
        help="Output results to JSON file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )

    args = parser.parse_args()

    # Handle trace generation only
    if args.generate:
        if not args.pattern:
            parser.error("--generate requires --pattern")
        if not args.output:
            parser.error("--generate requires --output")

        print(f"Generating {args.pattern} trace with {args.events:,} events...")
        trace = generate_synthetic_trace(
            pattern=args.pattern,
            num_events=args.events,
            num_pages=args.pages,
            seed=args.seed,
        )
        save_trace_csv(trace, args.output)
        print(f"Saved to {args.output}")
        return 0

    # Load or generate trace
    if args.trace:
        print(f"Loading trace from {args.trace}...")
        trace = load_trace(args.trace)
        trace_name = Path(args.trace).stem
    else:
        print(f"Generating {args.pattern} trace with {args.events:,} events...")
        trace = generate_synthetic_trace(
            pattern=args.pattern,
            num_events=args.events,
            num_pages=args.pages,
            seed=args.seed,
        )
        trace_name = f"synthetic_{args.pattern}"

    print(f"Loaded {len(trace):,} events")

    # Create simulator config
    config = SimulatorConfig(
        tier0_size=args.tier0,
        tier1_size=args.tier1,
    )

    # Get CTM+ config
    ctm_configs = {
        "default": CTMPlusConfig.default(),
        "aggressive": CTMPlusConfig.aggressive(),
        "conservative": CTMPlusConfig.conservative(),
    }
    ctm_config = ctm_configs[args.ctm_preset]

    # Determine controllers to run
    if args.compare or args.controller == "all":
        controllers = [
            LRUController(config),
            ARCController(config),
            CTMPlusController(config, ctm_config),
        ]
    else:
        controller_map = {
            "lru": LRUController(config),
            "lru2": LRU2Controller(config),
            "arc": ARCController(config),
            "ctm+": CTMPlusController(config, ctm_config),
        }
        controllers = [controller_map[args.controller]]

    # Run simulation
    sim = Simulator(config=config)
    results = sim.compare(
        trace=trace,
        controllers=controllers,
        trace_name=trace_name,
        verbose=not args.quiet,
    )

    # Print comparison if multiple controllers
    if len(results) > 1:
        baseline = results[0]  # LRU
        for result in results[1:]:
            print_comparison(baseline.metrics, result.metrics)

    # Save JSON output
    if args.json:
        output = {
            "trace_name": trace_name,
            "num_events": len(trace),
            "config": {
                "tier0_size": args.tier0,
                "tier1_size": args.tier1,
            },
            "results": [
                {
                    "controller": r.metrics.controller_name,
                    "metrics": r.metrics.to_dict(),
                    "elapsed_time_sec": r.elapsed_time_sec,
                    "events_per_sec": r.events_per_sec,
                    "controller_stats": r.controller_stats,
                }
                for r in results
            ],
        }

        with open(args.json, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\nResults saved to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
