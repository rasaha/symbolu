#!/usr/bin/env python3
"""
Replay an annotated FSCS/Mistral KV-cache trace through CTM+/PCAM
in baseline vs enhanced mode and compare policy quality.

Usage:

    # Capture first (requires GPU + Mistral weights):
    python3 benchmarks/pcam_fscs_trace_capture.py \
        --output results/pcam_traces/fscs_annotated.jsonl

    # Then replay (no GPU needed):
    python3 benchmarks/pcam_fscs_replay_compare.py \
        --trace results/pcam_traces/fscs_annotated.jsonl \
        --output results/pcam_traces/comparison.json

The output JSON contains:
    - baseline metrics (four-signal scoring, no FSCS signals)
    - enhanced metrics (six-signal scoring with boundary, band, instability)
    - delta between the two
    - per-victim-set comparison showing which blocks each mode evicts
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam.kv_policy import KVCachePolicy
from simulator.pcam.trace import EventKind, TraceEvent, ReplayResult, replay


def load_trace(path: str) -> List[TraceEvent]:
    """Load a JSONL trace file into a list of TraceEvents."""
    events: List[TraceEvent] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(TraceEvent.from_dict(json.loads(line)))
    return events


def count_blocks_in_trace(events: List[TraceEvent]) -> int:
    """Count unique block_ids in ensure_block events."""
    return len({
        e.args["block_id"]
        for e in events
        if e.kind is EventKind.ENSURE_BLOCK
    })


def replay_with_config(
    events: List[TraceEvent],
    max_blocks: int,
    boundary_weight: float = 0.0,
    instability_weight: float = 0.0,
    label: str = "",
) -> Dict[str, Any]:
    """
    Replay a trace through a fresh KVCachePolicy with the given
    signal weights. Returns a metrics dict.

    Band class is always consumed from the trace events (it's in the
    ensure_block args). Boundary and instability weights control
    whether those signals affect scoring.
    """
    import random

    policy = KVCachePolicy(
        max_blocks=max_blocks,
        block_size=16,
        sink_tokens=4,
    )
    policy.set_rng(random.Random(42))

    if boundary_weight > 0:
        policy.set_boundary_weight(boundary_weight)
    if instability_weight > 0:
        policy.set_instability_weight(instability_weight)

    result = replay(policy, events)

    # Compute metrics
    total_victims = sum(len(v) for v in result.victim_lists)
    total_eviction_rounds = len(result.victim_lists)

    # Score distribution of evicted blocks (if available)
    # The replay already mutated the policy, so we can't re-score
    # evicted blocks. Instead we report the victim counts and
    # the final policy stats.
    stats = result.final_stats

    metrics = {
        "label": label,
        "boundary_weight": boundary_weight,
        "instability_weight": instability_weight,
        "total_events": result.event_count,
        "total_eviction_rounds": total_eviction_rounds,
        "total_victims_evicted": total_victims,
        "policy_stats": stats,
        "victim_lists": result.victim_lists,
    }

    print(f"  [{label}] {result.event_count} events, "
          f"{total_eviction_rounds} eviction rounds, "
          f"{total_victims} victims evicted", flush=True)

    return metrics


def compare(baseline: Dict, enhanced: Dict) -> Dict[str, Any]:
    """Compute deltas between baseline and enhanced metrics."""
    delta: Dict[str, Any] = {}

    b_victims = baseline["total_victims_evicted"]
    e_victims = enhanced["total_victims_evicted"]
    delta["victims_evicted_baseline"] = b_victims
    delta["victims_evicted_enhanced"] = e_victims

    # Compare which blocks were evicted differently
    b_sets = [set(v) for v in baseline["victim_lists"]]
    e_sets = [set(v) for v in enhanced["victim_lists"]]

    different_rounds = 0
    total_different_victims = 0
    for b_set, e_set in zip(b_sets, e_sets):
        if b_set != e_set:
            different_rounds += 1
            total_different_victims += len(b_set.symmetric_difference(e_set))

    delta["eviction_rounds_total"] = len(b_sets)
    delta["eviction_rounds_different"] = different_rounds
    delta["eviction_rounds_same"] = len(b_sets) - different_rounds
    delta["total_different_victim_choices"] = total_different_victims

    if len(b_sets) > 0:
        delta["pct_rounds_changed"] = round(
            100.0 * different_rounds / len(b_sets), 2
        )
    else:
        delta["pct_rounds_changed"] = 0.0

    return delta


def main() -> int:
    p = argparse.ArgumentParser(
        description="Replay annotated FSCS trace: baseline vs enhanced"
    )
    p.add_argument("--trace", required=True,
                   help="Path to JSONL trace from pcam_fscs_trace_capture.py")
    p.add_argument("--max-blocks", type=int, default=None,
                   help="Max KV-cache blocks for the policy. Default: "
                        "auto from trace (total unique blocks / 2).")
    p.add_argument("--boundary-weight", type=float, default=0.10)
    p.add_argument("--instability-weight", type=float, default=0.15)
    p.add_argument("--output", default="results/pcam_traces/comparison.json")
    args = p.parse_args()

    print(f"Loading trace: {args.trace}", flush=True)
    events = load_trace(args.trace)
    num_blocks = count_blocks_in_trace(events)
    print(f"  {len(events)} events, {num_blocks} unique blocks", flush=True)

    # Auto-size the cache to create eviction pressure
    max_blocks = args.max_blocks or max(16, num_blocks // 2)
    print(f"  max_blocks={max_blocks} (eviction pressure: "
          f"~{num_blocks - max_blocks} blocks must be evicted)", flush=True)

    print("\n--- Baseline (four-signal, no FSCS signals) ---", flush=True)
    baseline = replay_with_config(
        events, max_blocks,
        boundary_weight=0.0,
        instability_weight=0.0,
        label="baseline",
    )

    print("\n--- Enhanced (six-signal, FSCS signals enabled) ---", flush=True)
    enhanced = replay_with_config(
        events, max_blocks,
        boundary_weight=args.boundary_weight,
        instability_weight=args.instability_weight,
        label="enhanced",
    )

    print("\n--- Comparison ---", flush=True)
    delta = compare(baseline, enhanced)

    result = {
        "trace": args.trace,
        "max_blocks": max_blocks,
        "num_blocks_in_trace": num_blocks,
        "config": {
            "boundary_weight": args.boundary_weight,
            "instability_weight": args.instability_weight,
            "band_class": "from trace (global=1.3, mid=1.0, local=0.8)",
        },
        "baseline": {k: v for k, v in baseline.items() if k != "victim_lists"},
        "enhanced": {k: v for k, v in enhanced.items() if k != "victim_lists"},
        "delta": delta,
    }

    # Print summary
    print(f"\n  Eviction rounds total:     {delta['eviction_rounds_total']}")
    print(f"  Eviction rounds changed:   {delta['eviction_rounds_different']} "
          f"({delta['pct_rounds_changed']}%)")
    print(f"  Total different victims:   {delta['total_different_victim_choices']}")

    if delta["eviction_rounds_different"] > 0:
        print(f"\n  *** The FSCS-derived signals CHANGED eviction decisions "
              f"in {delta['pct_rounds_changed']}% of eviction rounds. ***")
    else:
        print(f"\n  The FSCS-derived signals did NOT change any eviction "
              f"decisions. This may indicate the signals are too weak "
              f"relative to the four base signals, or the trace does not "
              f"have enough eviction pressure.")

    # Write result
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Result written: {args.output}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
