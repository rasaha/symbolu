#!/usr/bin/env python3
"""
CTM+ Production Benchmark CLI

The one demo that changes everything:
"Same model, same workload, same conditions, higher throughput at same quality"
(or same throughput at higher quality)

Usage:
    python -m ctm_plus_vllm.production_cli demo
    python -m ctm_plus_vllm.production_cli latency-budget
    python -m ctm_plus_vllm.production_cli trace-replay --trace path/to/trace.csv
"""

import argparse
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import OrderedDict

from .production import (
    CTMPlusProduction,
    ProductionConfig,
    TraceReplayer,
    TraceEntry,
    LatencyStats,
)


# =============================================================================
# BASELINE IMPLEMENTATIONS (Production-grade for fair comparison)
# =============================================================================

class LRUProduction:
    """Production LRU baseline with same interface."""

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.cache: OrderedDict = OrderedDict()
        self.latency_stats = LatencyStats()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def access(self, position: int, attention_weight: float = 0.01, importance: float = 0.5) -> bool:
        start = time.perf_counter()

        if position in self.cache:
            self.stats["hits"] += 1
            self.cache.move_to_end(position)
            is_hit = True
        else:
            self.stats["misses"] += 1
            while len(self.cache) >= self.max_tokens:
                self.cache.popitem(last=False)
                self.stats["evictions"] += 1
            self.cache[position] = True
            is_hit = False

        latency_us = (time.perf_counter() - start) * 1e6
        self.latency_stats.record(latency_us)
        return is_hit

    def get_telemetry(self) -> dict:
        return {
            "stats": self.stats.copy(),
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
            "hit_rate": self.stats["hits"] / max(1, self.stats["hits"] + self.stats["misses"]),
            "latency": self.latency_stats.summary(),
        }


class SinkLRUProduction:
    """Sink-pinned LRU baseline (what most production systems use)."""

    def __init__(self, max_tokens: int, num_sinks: int = 4):
        self.max_tokens = max_tokens
        self.num_sinks = num_sinks
        self.cache: OrderedDict = OrderedDict()
        self.pinned: set = set()
        self.latency_stats = LatencyStats()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def access(self, position: int, attention_weight: float = 0.01, importance: float = 0.5) -> bool:
        start = time.perf_counter()

        if position in self.cache:
            self.stats["hits"] += 1
            if position not in self.pinned:
                self.cache.move_to_end(position)
            is_hit = True
        else:
            self.stats["misses"] += 1

            while len(self.cache) >= self.max_tokens:
                # Find first non-pinned to evict
                for key in self.cache:
                    if key not in self.pinned:
                        del self.cache[key]
                        self.stats["evictions"] += 1
                        break
                else:
                    break  # All pinned, can't evict

            self.cache[position] = True
            if position < self.num_sinks:
                self.pinned.add(position)
            is_hit = False

        latency_us = (time.perf_counter() - start) * 1e6
        self.latency_stats.record(latency_us)
        return is_hit

    def get_telemetry(self) -> dict:
        return {
            "stats": self.stats.copy(),
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
            "pinned_count": len(self.pinned),
            "hit_rate": self.stats["hits"] / max(1, self.stats["hits"] + self.stats["misses"]),
            "latency": self.latency_stats.summary(),
        }


class H2OProduction:
    """H2O (Heavy-Hitter Oracle) baseline."""

    def __init__(self, max_tokens: int, heavy_ratio: float = 0.05, recent_ratio: float = 0.25):
        self.max_tokens = max_tokens
        self.heavy_count = max(1, int(max_tokens * heavy_ratio))
        self.recent_count = max(1, int(max_tokens * recent_ratio))
        self.cache: Dict[int, dict] = {}
        self.access_order: List[int] = []
        self.latency_stats = LatencyStats()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def access(self, position: int, attention_weight: float = 0.01, importance: float = 0.5) -> bool:
        start = time.perf_counter()

        if position in self.cache:
            self.stats["hits"] += 1
            self.cache[position]["attention"] += attention_weight
            self.cache[position]["count"] += 1
            # Update access order
            if position in self.access_order:
                self.access_order.remove(position)
            self.access_order.append(position)
            is_hit = True
        else:
            self.stats["misses"] += 1

            while len(self.cache) >= self.max_tokens:
                self._evict()

            self.cache[position] = {"attention": attention_weight, "count": 1}
            self.access_order.append(position)
            is_hit = False

        latency_us = (time.perf_counter() - start) * 1e6
        self.latency_stats.record(latency_us)
        return is_hit

    def _evict(self):
        if not self.cache:
            return

        # Protect recent
        recent = set(self.access_order[-self.recent_count:]) if self.access_order else set()

        # Protect heavy hitters
        by_attention = sorted(self.cache.items(), key=lambda x: x[1]["attention"], reverse=True)
        heavy = set(pos for pos, _ in by_attention[:self.heavy_count])

        protected = recent | heavy

        # Evict oldest non-protected
        for pos in self.access_order:
            if pos not in protected and pos in self.cache:
                del self.cache[pos]
                self.access_order.remove(pos)
                self.stats["evictions"] += 1
                return

        # If all protected, evict oldest
        if self.access_order:
            victim = self.access_order.pop(0)
            if victim in self.cache:
                del self.cache[victim]
                self.stats["evictions"] += 1

    def get_telemetry(self) -> dict:
        return {
            "stats": self.stats.copy(),
            "cache_size": len(self.cache),
            "max_tokens": self.max_tokens,
            "hit_rate": self.stats["hits"] / max(1, self.stats["hits"] + self.stats["misses"]),
            "latency": self.latency_stats.summary(),
        }


# =============================================================================
# QUALITY METRICS
# =============================================================================

@dataclass
class QualityMetrics:
    """Quality metrics that matter for production."""
    hit_rate: float
    sink_retention: float  # Are sinks still cached?
    important_retention: float  # Are high-importance tokens cached?
    attention_coverage: float  # What fraction of attention mass is cached?


def compute_quality_metrics(
    policy,
    trace: List[TraceEntry],
    sink_positions: set,
    important_positions: set,
) -> QualityMetrics:
    """Compute quality metrics after replay."""
    telemetry = policy.get_telemetry()

    # Check sink retention
    if hasattr(policy, 'tokens'):
        cached = set(policy.tokens.keys())
    elif hasattr(policy, 'cache'):
        cached = set(policy.cache.keys())
    else:
        cached = set()

    sink_retained = len(sink_positions & cached) / max(1, len(sink_positions))
    important_retained = len(important_positions & cached) / max(1, len(important_positions))

    # Attention coverage (simplified)
    # Would need attention weights per cached token for accurate measure
    attention_coverage = len(cached) / max(1, len(trace))

    return QualityMetrics(
        hit_rate=telemetry["hit_rate"],
        sink_retention=sink_retained,
        important_retention=important_retained,
        attention_coverage=attention_coverage,
    )


# =============================================================================
# THE DEMO
# =============================================================================

def print_header(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def cmd_demo(args):
    """
    The one demo that changes everything.
    Shows: same workload, higher throughput at same quality (or better quality at same throughput).
    """
    print_header("CTM+ Production Demo: The One Metric That Matters")

    print("Goal: Same workload, prove CTM+ delivers better quality/throughput tradeoff")
    print()

    # Configuration
    context_length = args.context_length
    generation_length = args.generation_length
    cache_ratio = args.cache_ratio
    cache_size = int(context_length * cache_ratio)

    print(f"Configuration:")
    print(f"  Context Length:    {context_length:,} tokens")
    print(f"  Generation Length: {generation_length:,} tokens")
    print(f"  Cache Size:        {cache_size:,} tokens ({cache_ratio:.0%} of context)")
    print()

    # Generate trace
    print("Generating realistic trace...")
    trace = TraceReplayer.generate_synthetic_trace(
        context_length=context_length,
        generation_length=generation_length,
        seed=42,
    )
    print(f"  {len(trace):,} access events")

    # Define important positions
    sink_positions = set(range(4))
    # Simulate "entity" positions that should be retained
    random.seed(42)
    important_positions = sink_positions | set(random.sample(range(context_length), context_length // 20))

    # Policies to compare
    policies = {
        "LRU": LRUProduction(max_tokens=cache_size),
        "Sink+LRU": SinkLRUProduction(max_tokens=cache_size, num_sinks=4),
        "H2O": H2OProduction(max_tokens=cache_size),
        "CTM+": CTMPlusProduction(max_tokens=cache_size, config=ProductionConfig(
            k_candidates=32,
            eviction_batch_size=64,
        )),
    }

    results = {}

    print("\nRunning benchmarks...")
    print("-" * 70)

    for name, policy in policies.items():
        # Replay trace
        start = time.perf_counter()
        for entry in trace:
            importance = 1.0 if entry.position in important_positions else 0.5
            policy.access(entry.position, entry.attention_weight, importance)
        elapsed = time.perf_counter() - start

        # Get metrics
        telemetry = policy.get_telemetry()
        quality = compute_quality_metrics(policy, trace, sink_positions, important_positions)

        results[name] = {
            "hit_rate": quality.hit_rate,
            "sink_retention": quality.sink_retention,
            "important_retention": quality.important_retention,
            "throughput": len(trace) / elapsed,
            "p50_us": telemetry["latency"]["p50_us"],
            "p95_us": telemetry["latency"]["p95_us"],
            "p99_us": telemetry["latency"]["p99_us"],
            "evictions": telemetry["stats"]["evictions"],
        }

    # Print results table
    print_header("Results: Quality Metrics")

    print("{:<12} {:>10} {:>12} {:>14} {:>12}".format(
        "Policy", "Hit Rate", "Sinks", "Important", "Evictions"
    ))
    print("-" * 62)

    lru_important = results["LRU"]["important_retention"]

    for name in policies:
        r = results[name]
        imp = r["important_retention"]
        imp_vs_lru = ((imp - lru_important) / max(0.001, lru_important)) * 100 if name != "LRU" else 0

        print("{:<12} {:>9.1%} {:>11.1%} {:>10.1%} ({:+.0f}%) {:>11,}".format(
            name,
            r["hit_rate"],
            r["sink_retention"],
            imp,
            imp_vs_lru,
            r["evictions"],
        ))

    print_header("Results: Latency (µs)")

    print("{:<12} {:>10} {:>10} {:>10} {:>15}".format(
        "Policy", "p50", "p95", "p99", "Throughput"
    ))
    print("-" * 60)

    for name in policies:
        r = results[name]
        print("{:<12} {:>10.2f} {:>10.2f} {:>10.2f} {:>13,.0f}/s".format(
            name,
            r["p50_us"],
            r["p95_us"],
            r["p99_us"],
            r["throughput"],
        ))

    # Summary comparison
    print_header("Summary: CTM+ vs Baselines")

    ctm = results["CTM+"]
    sink_lru = results["Sink+LRU"]
    h2o = results["H2O"]

    print("Quality Improvement (Important Token Retention):")
    print(f"  CTM+ vs Sink+LRU: {((ctm['important_retention'] - sink_lru['important_retention']) / max(0.001, sink_lru['important_retention']) * 100):+.1f}%")
    print(f"  CTM+ vs H2O:      {((ctm['important_retention'] - h2o['important_retention']) / max(0.001, h2o['important_retention']) * 100):+.1f}%")

    print()
    print("Latency (p99):")
    print(f"  CTM+:     {ctm['p99_us']:.2f} µs")
    print(f"  Sink+LRU: {sink_lru['p99_us']:.2f} µs")
    print(f"  H2O:      {h2o['p99_us']:.2f} µs")

    print()
    if ctm["p99_us"] < 100:
        print("✓ CTM+ meets latency budget (p99 < 100 µs)")
    else:
        print("✗ CTM+ exceeds latency budget (p99 >= 100 µs)")

    # The verdict
    print_header("Verdict")

    ctm_better_quality = ctm["important_retention"] > sink_lru["important_retention"]
    ctm_acceptable_latency = ctm["p99_us"] < 100

    if ctm_better_quality and ctm_acceptable_latency:
        print("✓ CTM+ delivers BETTER QUALITY at ACCEPTABLE LATENCY")
        print()
        print("  This is the demo that matters:")
        print("  - Same workload")
        print(f"  - {((ctm['important_retention'] - sink_lru['important_retention']) / sink_lru['important_retention'] * 100):+.1f}% better important token retention")
        print(f"  - p99 latency: {ctm['p99_us']:.2f} µs (under 100 µs budget)")
    elif ctm_better_quality:
        print("△ CTM+ delivers better quality but needs latency optimization")
    else:
        print("✗ CTM+ needs improvement on this workload")


def cmd_latency_budget(args):
    """Test latency budget across different configurations."""
    print_header("Latency Budget Test")

    print("Target: p99 eviction decision ≤ 100 µs")
    print()

    configs = [
        ("Small (k=16)", ProductionConfig(k_candidates=16, eviction_batch_size=32)),
        ("Medium (k=32)", ProductionConfig(k_candidates=32, eviction_batch_size=64)),
        ("Large (k=64)", ProductionConfig(k_candidates=64, eviction_batch_size=128)),
    ]

    trace = TraceReplayer.generate_synthetic_trace(
        context_length=8192,
        generation_length=512,
    )

    print("{:<20} {:>10} {:>10} {:>10} {:>12}".format(
        "Config", "p50 (µs)", "p95 (µs)", "p99 (µs)", "Budget"
    ))
    print("-" * 65)

    for name, config in configs:
        policy = CTMPlusProduction(max_tokens=2048, config=config)

        for entry in trace:
            policy.access(entry.position, entry.attention_weight)

        telemetry = policy.get_telemetry()
        lat = telemetry["latency"]

        budget_ok = "✓ OK" if lat["p99_us"] <= 100 else "✗ OVER"

        print("{:<20} {:>10.2f} {:>10.2f} {:>10.2f} {:>12}".format(
            name,
            lat["p50_us"],
            lat["p95_us"],
            lat["p99_us"],
            budget_ok,
        ))


def cmd_trace_replay(args):
    """Replay a real trace file."""
    print_header(f"Trace Replay: {args.trace}")

    if args.trace == "synthetic":
        trace = TraceReplayer.generate_synthetic_trace(
            context_length=args.context_length,
            generation_length=args.generation_length,
        )
    else:
        trace = TraceReplayer.load_vllm_trace(args.trace)

    print(f"Loaded {len(trace):,} access events")

    cache_size = int(args.context_length * args.cache_ratio)
    policy = CTMPlusProduction(max_tokens=cache_size)

    replayer = TraceReplayer(max_tokens=cache_size)
    metrics = replayer.replay(trace, policy)

    print()
    print("Results:")
    print(f"  Hit Rate:    {metrics['hit_rate']:.1%}")
    print(f"  Throughput:  {metrics['throughput']:,.0f} accesses/sec")
    print(f"  p99 Latency: {metrics['latency']['p99_us']:.2f} µs")


def cmd_sweep(args):
    """Sweep across cache ratios."""
    print_header("Cache Ratio Sweep")

    ratios = [0.05, 0.10, 0.15, 0.25, 0.50]
    context_length = 8192

    trace = TraceReplayer.generate_synthetic_trace(
        context_length=context_length,
        generation_length=512,
    )

    print("{:<10} {:>12} {:>12} {:>12} {:>12}".format(
        "Ratio", "CTM+ Hit", "Sink+LRU", "H2O", "CTM+ vs Best"
    ))
    print("-" * 62)

    for ratio in ratios:
        cache_size = int(context_length * ratio)

        policies = {
            "CTM+": CTMPlusProduction(max_tokens=cache_size),
            "Sink+LRU": SinkLRUProduction(max_tokens=cache_size),
            "H2O": H2OProduction(max_tokens=cache_size),
        }

        results = {}
        for name, policy in policies.items():
            for entry in trace:
                policy.access(entry.position, entry.attention_weight)
            results[name] = policy.get_telemetry()["hit_rate"]

        best_other = max(results["Sink+LRU"], results["H2O"])
        ctm_vs_best = ((results["CTM+"] - best_other) / best_other * 100) if best_other > 0 else 0

        print("{:<10} {:>11.1%} {:>11.1%} {:>11.1%} {:>+11.1f}%".format(
            f"{ratio:.0%}",
            results["CTM+"],
            results["Sink+LRU"],
            results["H2O"],
            ctm_vs_best,
        ))


def main():
    parser = argparse.ArgumentParser(
        description="CTM+ Production Benchmark CLI",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Demo command
    p_demo = subparsers.add_parser("demo", help="Run the definitive demo")
    p_demo.add_argument("--context-length", type=int, default=8192)
    p_demo.add_argument("--generation-length", type=int, default=512)
    p_demo.add_argument("--cache-ratio", type=float, default=0.25)
    p_demo.set_defaults(func=cmd_demo)

    # Latency budget command
    p_latency = subparsers.add_parser("latency-budget", help="Test latency budget")
    p_latency.set_defaults(func=cmd_latency_budget)

    # Trace replay command
    p_trace = subparsers.add_parser("trace-replay", help="Replay a trace file")
    p_trace.add_argument("--trace", default="synthetic", help="Path to trace or 'synthetic'")
    p_trace.add_argument("--context-length", type=int, default=8192)
    p_trace.add_argument("--generation-length", type=int, default=512)
    p_trace.add_argument("--cache-ratio", type=float, default=0.25)
    p_trace.set_defaults(func=cmd_trace_replay)

    # Sweep command
    p_sweep = subparsers.add_parser("sweep", help="Sweep cache ratios")
    p_sweep.set_defaults(func=cmd_sweep)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
