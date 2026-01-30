#!/usr/bin/env python3
"""
Ablation study for CTM+ components.

Tests different combinations of:
- enable_smart_victim: Use CTM+ victim selection vs LRU
- enable_bcvf_gate: Use BCVF promotion gate vs always promote

Usage:
    python3 simulator/run_ablation.py [--temporal-only]
"""

import sys
import argparse
from dataclasses import dataclass
from typing import List, Tuple

from ctm_plus import Simulator, SimulatorConfig
from ctm_plus.core.config import CTMPlusConfig
from ctm_plus.controllers.ctm_plus import CTMPlusController
from ctm_plus.controllers.arc import ARCController
from ctm_plus.traces import generate_synthetic_trace


@dataclass
class AblationConfig:
    name: str
    smart_victim: bool
    bcvf_gate: bool


CONFIGS = [
    AblationConfig("baseline", True, True),
    AblationConfig("no_bcvf", True, False),
    AblationConfig("no_smart_victim", False, True),
    AblationConfig("lru_fallback", False, False),
]


def run_ablation(temporal_only: bool = False, num_events: int = 50000):
    """Run ablation study."""

    tier0_size = 1000
    tier1_size = 100000

    # Select workloads
    if temporal_only:
        workloads = [("temporal", {"pattern": "temporal", "num_pages": 10000})]
    else:
        workloads = [
            ("zipfian", {"pattern": "zipf", "num_pages": 10000}),
            ("temporal", {"pattern": "temporal", "num_pages": 10000}),
        ]

    sim = Simulator(tier0_size=tier0_size, tier1_size=tier1_size)
    config = sim.config

    # Get ARC baseline first
    print("=" * 70)
    print("CTM+ ABLATION STUDY")
    print("=" * 70)
    print(f"\nConfiguration: {num_events:,} events, Tier0={tier0_size}, Tier1={tier1_size}")
    print()

    results = {}

    for workload_name, workload_params in workloads:
        print(f"\n{'─' * 70}")
        print(f"Workload: {workload_name}")
        print(f"{'─' * 70}")

        trace = generate_synthetic_trace(num_events=num_events, **workload_params)

        # ARC baseline
        arc = ARCController(config)
        arc_result = sim.run(trace, arc, f"{workload_name}_arc", verbose=False)
        arc_hit = arc_result.metrics.hit_rate
        print(f"  ARC baseline: {arc_hit:.2%}")

        results[workload_name] = {"arc": arc_hit}

        # Test each ablation config
        for cfg in CONFIGS:
            ctm_config = CTMPlusConfig(
                enable_smart_victim=cfg.smart_victim,
                enable_bcvf_gate=cfg.bcvf_gate,
            )
            ctm = CTMPlusController(config, ctm_config=ctm_config)

            # Regenerate trace for fair comparison
            trace = generate_synthetic_trace(num_events=num_events, **workload_params)

            result = sim.run(trace, ctm, f"{workload_name}_{cfg.name}", verbose=False)
            hit_rate = result.metrics.hit_rate
            delta = hit_rate - arc_hit

            results[workload_name][cfg.name] = hit_rate

            flags = []
            if not cfg.bcvf_gate:
                flags.append("!BCVF")
            if not cfg.smart_victim:
                flags.append("!SMART")
            flag_str = f" [{', '.join(flags)}]" if flags else ""

            sign = "+" if delta >= 0 else ""
            print(f"  {cfg.name:25s}: {hit_rate:.2%} ({sign}{delta:.2%} vs ARC){flag_str}")

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY: Best configuration per workload")
    print("=" * 70)

    for workload_name in results:
        arc_hit = results[workload_name]["arc"]
        best_cfg = None
        best_delta = float("-inf")

        for cfg in CONFIGS:
            hit = results[workload_name][cfg.name]
            delta = hit - arc_hit
            if delta > best_delta:
                best_delta = delta
                best_cfg = cfg.name

        sign = "+" if best_delta >= 0 else ""
        print(f"  {workload_name}: {best_cfg} ({sign}{best_delta:.2%} vs ARC)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CTM+ Ablation Study")
    parser.add_argument("--temporal-only", action="store_true", help="Only test temporal workload")
    parser.add_argument("--events", type=int, default=50000, help="Events per workload")
    args = parser.parse_args()

    run_ablation(temporal_only=args.temporal_only, num_events=args.events)
