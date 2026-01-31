#!/usr/bin/env python3
"""
CTM+ KV Cache Benchmark CLI

Benchmark tool for comparing CTM+ against other eviction policies
for KV cache management in LLM inference.

Usage:
    python -m ctm_plus_vllm.benchmark_cli --help
    python -m ctm_plus_vllm.benchmark_cli run --workload sequential --seq-len 4096
    python -m ctm_plus_vllm.benchmark_cli compare --cache-ratio 0.5
    python -m ctm_plus_vllm.benchmark_cli quality --seq-len 8192 --cache-ratio 0.25
"""

import argparse
import json
import sys
import time
from typing import Optional

from .kv_cache_simulator import (
    EvictionPolicy,
    CTMKVConfig,
    KVCacheSimulator,
    WorkloadGenerator,
    AttentionPatternGenerator,
    run_benchmark,
    quality_preservation_test,
)


def print_header(title: str):
    """Print a formatted header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_table(headers: list[str], rows: list[list], col_widths: Optional[list[int]] = None):
    """Print a formatted table."""
    if col_widths is None:
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

    # Header
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    print(separator)
    print(header_line)
    print(separator)

    # Rows
    for row in rows:
        row_line = "| " + " | ".join(str(v).ljust(w) for v, w in zip(row, col_widths)) + " |"
        print(row_line)

    print(separator)


def cmd_run(args):
    """Run a single benchmark."""
    print_header(f"KV Cache Benchmark: {args.workload}")

    print(f"\nConfiguration:")
    print(f"  Sequence Length: {args.seq_len:,}")
    print(f"  Cache Size:      {args.cache_size:,} tokens ({args.cache_size/args.seq_len*100:.1f}% of seq)")
    print(f"  Workload:        {args.workload}")
    print(f"  Policy:          {args.policy}")

    # Generate workload
    print(f"\nGenerating workload...")
    gen = WorkloadGenerator(args.seq_len, seed=args.seed)

    if args.workload == "sequential":
        workload = gen.sequential(args.seq_len)
    elif args.workload == "conversation":
        workload = gen.multi_turn_conversation(
            num_turns=args.num_turns,
            tokens_per_turn=args.seq_len // args.num_turns,
        )
    elif args.workload == "document_qa":
        workload = gen.document_qa(
            doc_length=args.seq_len,
            num_questions=args.num_questions,
        )
    elif args.workload == "zipfian":
        workload = gen.zipfian_hotspot(args.seq_len * 10, s=args.zipf_s)
    else:
        print(f"Unknown workload: {args.workload}", file=sys.stderr)
        return 1

    print(f"  Generated {len(workload):,} accesses")

    # Get policy
    policy = EvictionPolicy(args.policy)

    # Get config
    if args.config == "chatbot":
        config = CTMKVConfig.for_chatbot()
    elif args.config == "long_context":
        config = CTMKVConfig.for_long_context()
    elif args.config == "batch":
        config = CTMKVConfig.for_batch_processing()
    else:
        config = CTMKVConfig()

    # Run benchmark
    print(f"\nRunning benchmark...")
    sim = KVCacheSimulator(args.cache_size, policy, config)

    start_time = time.perf_counter()
    hits = 0
    misses = 0

    for i, (pos, token_type, attention) in enumerate(workload):
        is_hit = sim.access(pos, token_type, attention)
        if is_hit:
            hits += 1
        else:
            misses += 1

        # Progress
        if args.verbose and (i + 1) % 10000 == 0:
            print(f"  Processed {i+1:,}/{len(workload):,} accesses...")

    elapsed = time.perf_counter() - start_time

    # Results
    print_header("Results")
    stats = sim.get_stats()

    print(f"\nPerformance:")
    print(f"  Hit Rate:        {stats['hit_rate']*100:.2f}%")
    print(f"  Hits:            {stats['hits']:,}")
    print(f"  Misses:          {stats['misses']:,}")
    print(f"  Evictions:       {stats['evictions']:,}")
    print(f"  Cache Utilization: {stats['cache_size']:,}/{args.cache_size:,}")

    print(f"\nThroughput:")
    print(f"  Total Time:      {elapsed:.3f} seconds")
    print(f"  Accesses/sec:    {len(workload)/elapsed:,.0f}")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump({
                "config": {
                    "seq_len": args.seq_len,
                    "cache_size": args.cache_size,
                    "workload": args.workload,
                    "policy": args.policy,
                },
                "stats": stats,
                "elapsed": elapsed,
            }, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


def cmd_compare(args):
    """Compare all eviction policies."""
    print_header("KV Cache Policy Comparison")

    print(f"\nConfiguration:")
    print(f"  Sequence Length: {args.seq_len:,}")
    print(f"  Cache Ratio:     {args.cache_ratio*100:.0f}%")
    print(f"  Cache Size:      {int(args.seq_len * args.cache_ratio):,} tokens")
    print(f"  Workload:        {args.workload}")

    # Generate workload
    print(f"\nGenerating workload...")
    gen = WorkloadGenerator(args.seq_len, seed=args.seed)

    if args.workload == "sequential":
        workload = gen.sequential(args.seq_len)
    elif args.workload == "conversation":
        workload = gen.multi_turn_conversation(
            num_turns=10,
            tokens_per_turn=args.seq_len // 10,
        )
    elif args.workload == "document_qa":
        workload = gen.document_qa(
            doc_length=args.seq_len,
            num_questions=5,
        )
    elif args.workload == "zipfian":
        workload = gen.zipfian_hotspot(args.seq_len * 10, s=1.0)
    else:
        workload = gen.sequential(args.seq_len)

    print(f"  Generated {len(workload):,} accesses")

    # Run benchmark for each policy
    policies = [
        EvictionPolicy.LRU,
        EvictionPolicy.FIFO,
        EvictionPolicy.RANDOM,
        EvictionPolicy.CTM_PLUS,
    ]

    cache_size = int(args.seq_len * args.cache_ratio)
    config = CTMKVConfig.for_long_context()

    print(f"\nRunning benchmarks...")
    results = run_benchmark(workload, cache_size, policies, config)

    # Display results
    print_header("Results")

    headers = ["Policy", "Hit Rate", "Evictions", "Time (s)", "Throughput"]
    rows = []

    lru_hit_rate = results["lru"]["hit_rate"]

    for policy_name, stats in results.items():
        hit_rate = stats["hit_rate"]
        delta = ((hit_rate - lru_hit_rate) / lru_hit_rate * 100) if lru_hit_rate > 0 else 0

        hit_rate_str = f"{hit_rate*100:.2f}%"
        if policy_name != "lru":
            sign = "+" if delta >= 0 else ""
            hit_rate_str += f" ({sign}{delta:.1f}%)"

        rows.append([
            policy_name.upper(),
            hit_rate_str,
            f"{stats['evictions']:,}",
            f"{stats['elapsed_seconds']:.3f}",
            f"{stats['accesses_per_second']:,.0f}/s",
        ])

    print_table(headers, rows)

    # Summary
    ctm_hit = results["ctm_plus"]["hit_rate"]
    lru_hit = results["lru"]["hit_rate"]
    improvement = ((ctm_hit - lru_hit) / lru_hit * 100) if lru_hit > 0 else 0

    print(f"\nSummary:")
    print(f"  CTM+ vs LRU: {'+' if improvement >= 0 else ''}{improvement:.2f}% hit rate improvement")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


def cmd_quality(args):
    """Test quality preservation under eviction pressure."""
    print_header("Quality Preservation Test")

    print(f"\nConfiguration:")
    print(f"  Sequence Length: {args.seq_len:,}")
    print(f"  Cache Ratio:     {args.cache_ratio*100:.0f}%")
    print(f"  (Only {args.cache_ratio*100:.0f}% of tokens can be retained)")

    policies = [
        EvictionPolicy.LRU,
        EvictionPolicy.FIFO,
        EvictionPolicy.RANDOM,
        EvictionPolicy.CTM_PLUS,
    ]

    print(f"\nRunning quality tests...")
    results = quality_preservation_test(
        args.seq_len,
        args.cache_ratio,
        policies,
    )

    # Display results
    print_header("Important Token Retention")

    headers = ["Policy", "Retention Rate", "vs LRU"]
    rows = []

    lru_retention = results["lru"]

    for policy_name, retention in results.items():
        delta = ((retention - lru_retention) / lru_retention * 100) if lru_retention > 0 else 0

        retention_str = f"{retention*100:.1f}%"
        delta_str = f"{'+' if delta >= 0 else ''}{delta:.1f}%" if policy_name != "lru" else "-"

        rows.append([
            policy_name.upper(),
            retention_str,
            delta_str,
        ])

    print_table(headers, rows)

    # Interpretation
    ctm_retention = results["ctm_plus"]
    lru_retention = results["lru"]

    print(f"\nInterpretation:")
    print(f"  With {args.cache_ratio*100:.0f}% cache capacity:")
    print(f"    LRU retains  {lru_retention*100:.1f}% of important tokens")
    print(f"    CTM+ retains {ctm_retention*100:.1f}% of important tokens")

    if ctm_retention > lru_retention:
        quality_preserved = (1 - (1 - ctm_retention)) / (1 - (1 - lru_retention)) if lru_retention < 1 else 1
        print(f"\n  CTM+ preserves {(ctm_retention/lru_retention - 1)*100:.1f}% more important tokens!")

    return 0


def cmd_sweep(args):
    """Sweep across cache ratios."""
    print_header("Cache Ratio Sweep")

    print(f"\nConfiguration:")
    print(f"  Sequence Length: {args.seq_len:,}")
    print(f"  Cache Ratios:    {args.min_ratio*100:.0f}% to {args.max_ratio*100:.0f}%")
    print(f"  Steps:           {args.steps}")

    # Generate workload once
    gen = WorkloadGenerator(args.seq_len, seed=args.seed)
    workload = gen.sequential(args.seq_len)

    policies = [
        EvictionPolicy.LRU,
        EvictionPolicy.CTM_PLUS,
    ]

    config = CTMKVConfig.for_long_context()

    # Sweep
    ratios = [
        args.min_ratio + (args.max_ratio - args.min_ratio) * i / (args.steps - 1)
        for i in range(args.steps)
    ]

    print(f"\nRunning sweep...")

    all_results = []
    for ratio in ratios:
        cache_size = int(args.seq_len * ratio)
        results = run_benchmark(workload, cache_size, policies, config)
        all_results.append({
            "ratio": ratio,
            "cache_size": cache_size,
            **{f"{p}_hit_rate": results[p]["hit_rate"] for p in ["lru", "ctm_plus"]},
        })
        print(f"  Ratio {ratio*100:5.1f}%: LRU={results['lru']['hit_rate']*100:.1f}%, CTM+={results['ctm_plus']['hit_rate']*100:.1f}%")

    # Display results
    print_header("Sweep Results")

    headers = ["Cache %", "LRU Hit Rate", "CTM+ Hit Rate", "Improvement"]
    rows = []

    for r in all_results:
        improvement = ((r["ctm_plus_hit_rate"] - r["lru_hit_rate"]) / r["lru_hit_rate"] * 100) if r["lru_hit_rate"] > 0 else 0
        rows.append([
            f"{r['ratio']*100:.0f}%",
            f"{r['lru_hit_rate']*100:.1f}%",
            f"{r['ctm_plus_hit_rate']*100:.1f}%",
            f"+{improvement:.1f}%" if improvement >= 0 else f"{improvement:.1f}%",
        ])

    print_table(headers, rows)

    # ASCII chart
    print("\nHit Rate Comparison:")
    print("-" * 60)
    for r in all_results:
        lru_bar = int(r["lru_hit_rate"] * 40)
        ctm_bar = int(r["ctm_plus_hit_rate"] * 40)
        print(f"{r['ratio']*100:3.0f}% | LRU:  {'#' * lru_bar} {r['lru_hit_rate']*100:.1f}%")
        print(f"     | CTM+: {'#' * ctm_bar} {r['ctm_plus_hit_rate']*100:.1f}%")
        print()

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


def cmd_stress(args):
    """Stress test with high eviction pressure."""
    print_header("Stress Test: High Eviction Pressure")

    print(f"\nConfiguration:")
    print(f"  Sequence Length: {args.seq_len:,}")
    print(f"  Cache Size:      {args.cache_size:,} tokens ({args.cache_size/args.seq_len*100:.1f}%)")
    print(f"  Access Pattern:  Mixed (sequential + random hotspots)")
    print(f"  Duration:        {args.duration} seconds")

    policies = [
        EvictionPolicy.LRU,
        EvictionPolicy.CTM_PLUS,
    ]

    config = CTMKVConfig.for_batch_processing()
    results = {}

    for policy in policies:
        sim = KVCacheSimulator(args.cache_size, policy, config)
        gen = WorkloadGenerator(args.seq_len, seed=args.seed)

        start_time = time.perf_counter()
        access_count = 0
        batch_num = 0

        while time.perf_counter() - start_time < args.duration:
            # Alternate between workload types
            if batch_num % 3 == 0:
                workload = gen.sequential(args.seq_len)
            elif batch_num % 3 == 1:
                workload = gen.zipfian_hotspot(args.seq_len * 2, s=1.2)
            else:
                workload = gen.document_qa(args.seq_len // 2, 3)

            for pos, token_type, attention in workload:
                sim.access(pos, token_type, attention)
                access_count += 1

            batch_num += 1

        elapsed = time.perf_counter() - start_time
        stats = sim.get_stats()
        stats["total_accesses"] = access_count
        stats["elapsed"] = elapsed
        stats["throughput"] = access_count / elapsed
        results[policy.value] = stats

        print(f"\n{policy.value.upper()}:")
        print(f"  Accesses: {access_count:,}")
        print(f"  Hit Rate: {stats['hit_rate']*100:.2f}%")
        print(f"  Throughput: {stats['throughput']:,.0f} accesses/sec")

    # Comparison
    print_header("Stress Test Results")

    lru = results["lru"]
    ctm = results["ctm_plus"]

    print(f"\nHit Rate:")
    print(f"  LRU:  {lru['hit_rate']*100:.2f}%")
    print(f"  CTM+: {ctm['hit_rate']*100:.2f}%")
    improvement = ((ctm['hit_rate'] - lru['hit_rate']) / lru['hit_rate'] * 100) if lru['hit_rate'] > 0 else 0
    print(f"  Improvement: {'+' if improvement >= 0 else ''}{improvement:.2f}%")

    print(f"\nThroughput:")
    print(f"  LRU:  {lru['throughput']:,.0f} accesses/sec")
    print(f"  CTM+: {ctm['throughput']:,.0f} accesses/sec")
    overhead = ((lru['throughput'] - ctm['throughput']) / lru['throughput'] * 100) if lru['throughput'] > 0 else 0
    print(f"  CTM+ overhead: {overhead:.1f}%")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="CTM+ KV Cache Benchmark CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single benchmark
  python -m ctm_plus_vllm.benchmark_cli run --workload sequential --seq-len 4096

  # Compare all policies
  python -m ctm_plus_vllm.benchmark_cli compare --seq-len 8192 --cache-ratio 0.5

  # Test quality preservation
  python -m ctm_plus_vllm.benchmark_cli quality --seq-len 8192 --cache-ratio 0.25

  # Sweep cache ratios
  python -m ctm_plus_vllm.benchmark_cli sweep --seq-len 4096

  # Stress test
  python -m ctm_plus_vllm.benchmark_cli stress --duration 30
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a single benchmark")
    run_parser.add_argument("--seq-len", type=int, default=4096, help="Sequence length")
    run_parser.add_argument("--cache-size", type=int, default=1024, help="Cache size in tokens")
    run_parser.add_argument("--workload", choices=["sequential", "conversation", "document_qa", "zipfian"], default="sequential")
    run_parser.add_argument("--policy", choices=["lru", "fifo", "random", "ctm_plus"], default="ctm_plus")
    run_parser.add_argument("--config", choices=["default", "chatbot", "long_context", "batch"], default="default")
    run_parser.add_argument("--num-turns", type=int, default=10, help="Number of conversation turns")
    run_parser.add_argument("--num-questions", type=int, default=5, help="Number of QA questions")
    run_parser.add_argument("--zipf-s", type=float, default=1.0, help="Zipfian skew parameter")
    run_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    run_parser.add_argument("--output", "-o", type=str, help="Output JSON file")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare all eviction policies")
    compare_parser.add_argument("--seq-len", type=int, default=4096, help="Sequence length")
    compare_parser.add_argument("--cache-ratio", type=float, default=0.5, help="Cache size as ratio of seq length")
    compare_parser.add_argument("--workload", choices=["sequential", "conversation", "document_qa", "zipfian"], default="sequential")
    compare_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    compare_parser.add_argument("--output", "-o", type=str, help="Output JSON file")

    # Quality command
    quality_parser = subparsers.add_parser("quality", help="Test quality preservation")
    quality_parser.add_argument("--seq-len", type=int, default=8192, help="Sequence length")
    quality_parser.add_argument("--cache-ratio", type=float, default=0.25, help="Cache size as ratio")

    # Sweep command
    sweep_parser = subparsers.add_parser("sweep", help="Sweep across cache ratios")
    sweep_parser.add_argument("--seq-len", type=int, default=4096, help="Sequence length")
    sweep_parser.add_argument("--min-ratio", type=float, default=0.1, help="Minimum cache ratio")
    sweep_parser.add_argument("--max-ratio", type=float, default=0.9, help="Maximum cache ratio")
    sweep_parser.add_argument("--steps", type=int, default=9, help="Number of steps")
    sweep_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    sweep_parser.add_argument("--output", "-o", type=str, help="Output JSON file")

    # Stress command
    stress_parser = subparsers.add_parser("stress", help="Stress test under high pressure")
    stress_parser.add_argument("--seq-len", type=int, default=8192, help="Sequence length")
    stress_parser.add_argument("--cache-size", type=int, default=1024, help="Cache size in tokens")
    stress_parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    stress_parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "compare":
        return cmd_compare(args)
    elif args.command == "quality":
        return cmd_quality(args)
    elif args.command == "sweep":
        return cmd_sweep(args)
    elif args.command == "stress":
        return cmd_stress(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
