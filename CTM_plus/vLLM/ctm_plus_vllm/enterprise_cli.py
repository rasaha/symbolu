#!/usr/bin/env python3
"""
Enterprise KV Cache Benchmark CLI

Runs comprehensive benchmarks comparing CTM+ against industry-realistic baselines.
Generates quality metrics that matter for production deployments.

Usage:
    python -m ctm_plus_vllm.enterprise_cli full-report
    python -m ctm_plus_vllm.enterprise_cli workload --type long-context
    python -m ctm_plus_vllm.enterprise_cli pressure-test --ratios 0.1,0.25,0.5
"""

import argparse
import sys
import time
from .enterprise_benchmark import (
    EnterprisePolicy,
    EnterpriseConfig,
    EnterpriseKVCache,
    EnterpriseWorkloadGenerator,
    run_enterprise_benchmark,
    quality_under_pressure_test,
)


# All policies to compare
ALL_POLICIES = [
    EnterprisePolicy.LRU,
    EnterprisePolicy.SINK_LRU,
    EnterprisePolicy.ATTENTION_LRU,
    EnterprisePolicy.INDUSTRY_BASELINE,
    EnterprisePolicy.H2O,
    EnterprisePolicy.CTM_PLUS,
]

# Policies for quick comparison
QUICK_POLICIES = [
    EnterprisePolicy.LRU,
    EnterprisePolicy.INDUSTRY_BASELINE,
    EnterprisePolicy.H2O,
    EnterprisePolicy.CTM_PLUS,
]


def print_header(title: str):
    """Print a formatted header."""
    print()
    print("=" * 70)
    print("  {}".format(title))
    print("=" * 70)
    print()


def print_subheader(title: str):
    """Print a formatted subheader."""
    print()
    print("-" * 70)
    print("  {}".format(title))
    print("-" * 70)
    print()


def cmd_workload(args):
    """Run benchmark on a specific workload type."""
    print_header("Enterprise KV Cache Benchmark: {} Workload".format(args.type.upper()))

    gen = EnterpriseWorkloadGenerator(seed=args.seed)
    config = EnterpriseConfig(tokens_per_block=args.block_size)

    # Generate workload
    print("Generating {} workload...".format(args.type))
    if args.type == "long-context":
        workload = gen.long_context_generation(
            context_length=args.context_length,
            tokens_per_block=args.block_size,
            generation_length=args.generation_length,
        )
    elif args.type == "multi-tenant":
        workload = gen.multi_tenant_batch(
            num_sequences=args.num_sequences,
            context_length=args.context_length,
            tokens_per_block=args.block_size,
        )
    elif args.type == "document-qa":
        workload = gen.document_qa_rag(
            doc_length=args.context_length,
            num_queries=args.num_queries,
            tokens_per_block=args.block_size,
        )
    elif args.type == "code":
        workload = gen.code_completion(
            file_length=args.context_length,
            tokens_per_block=args.block_size,
            num_completions=20,
        )
    else:
        print("Unknown workload type: {}".format(args.type))
        return

    print("  Generated {:,} block accesses".format(len(workload)))

    # Calculate cache size
    num_blocks = args.context_length // args.block_size
    max_blocks = int(num_blocks * args.cache_ratio)
    print("  Cache: {} blocks ({:.0f}% of context)".format(max_blocks, args.cache_ratio * 100))
    print()

    # Run benchmarks
    policies = ALL_POLICIES if args.full else QUICK_POLICIES
    results = run_enterprise_benchmark(workload, max_blocks, policies, config)

    # Print results table
    print_results_table(results, policies)


def cmd_pressure_test(args):
    """Test quality at different memory pressure levels."""
    print_header("Quality Under Memory Pressure Test")

    ratios = [float(r) for r in args.ratios.split(",")]
    policies = ALL_POLICIES if args.full else QUICK_POLICIES

    print("Configuration:")
    print("  Context Length: {:,} tokens".format(args.context_length))
    print("  Block Size:     {} tokens".format(args.block_size))
    print("  Cache Ratios:   {}".format(ratios))
    print()

    results = quality_under_pressure_test(
        cache_ratios=ratios,
        policies=policies,
        context_length=args.context_length,
        tokens_per_block=args.block_size,
    )

    # Print comparison table for each ratio
    for ratio in ratios:
        print_subheader("Cache Ratio: {:.0f}%".format(ratio * 100))

        # Header
        print("{:<22} {:>10} {:>12} {:>12} {:>10}".format(
            "Policy", "Hit Rate", "Attn Cov", "Imp Retain", "Sinks"
        ))
        print("-" * 70)

        # Get LRU baseline for comparison
        lru_metrics = results.get("lru", {}).get(ratio, {})
        lru_important = lru_metrics.get("important_retention", 0)

        for policy in policies:
            m = results[policy.value].get(ratio, {})
            imp_ret = m.get("important_retention", 0)

            # Calculate improvement vs LRU
            if lru_important > 0 and policy != EnterprisePolicy.LRU:
                improvement = ((imp_ret - lru_important) / lru_important) * 100
                imp_str = "{:>10.1f}% ({:+.0f}%)".format(imp_ret * 100, improvement)
            else:
                imp_str = "{:>10.1f}%".format(imp_ret * 100)

            print("{:<22} {:>9.1f}% {:>11.1f}% {:>20} {:>9.1f}%".format(
                policy.value,
                m.get("hit_rate", 0) * 100,
                m.get("attention_coverage", 0) * 100,
                imp_str,
                m.get("sink_retention", 0) * 100,
            ))


def cmd_full_report(args):
    """Generate comprehensive benchmark report."""
    print_header("CTM+ Enterprise Benchmark Report")
    print("Comparing against industry-realistic baselines")
    print("Timestamp: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))

    gen = EnterpriseWorkloadGenerator(seed=42)
    config = EnterpriseConfig(tokens_per_block=16)

    workloads = [
        ("Long Context (32K)", gen.long_context_generation(context_length=8192, generation_length=256)),
        ("Multi-Tenant (8 seq)", gen.multi_tenant_batch(num_sequences=8, context_length=2048)),
        ("Document QA", gen.document_qa_rag(doc_length=4096, num_queries=10)),
        ("Code Completion", gen.code_completion(file_length=2048, num_completions=20)),
    ]

    cache_ratios = [0.10, 0.25, 0.50]

    for workload_name, workload in workloads:
        print_subheader("Workload: {}".format(workload_name))
        print("  {:,} block accesses".format(len(workload)))

        for ratio in cache_ratios:
            max_blocks = max(16, int(512 * ratio))  # Approximate
            print("\n  Cache Ratio: {:.0f}%".format(ratio * 100))

            results = run_enterprise_benchmark(workload, max_blocks, QUICK_POLICIES, config)

            # Compact results
            print("  {:<20} {:>8} {:>10} {:>12}".format("Policy", "Hit", "Attn Cov", "Imp Retain"))
            for policy in QUICK_POLICIES:
                r = results[policy.value]
                print("  {:<20} {:>7.1f}% {:>9.1f}% {:>11.1f}%".format(
                    policy.value,
                    r["hit_rate"] * 100,
                    r["attention_coverage"] * 100,
                    r["important_retention"] * 100,
                ))

    # Summary comparison
    print_header("Summary: CTM+ vs Industry Baseline")

    print("Quality Improvements (Important Token Retention):")
    print()

    # Run pressure test for summary
    ratios = [0.10, 0.25, 0.50]
    results = quality_under_pressure_test(ratios, QUICK_POLICIES, context_length=8192)

    print("{:<15} {:>12} {:>12} {:>12}".format("Cache Ratio", "Ind.Baseline", "H2O", "CTM+"))
    print("-" * 55)

    for ratio in ratios:
        baseline = results["industry_baseline"].get(ratio, {}).get("important_retention", 0) * 100
        h2o = results["h2o"].get(ratio, {}).get("important_retention", 0) * 100
        ctm = results["ctm_plus"].get(ratio, {}).get("important_retention", 0) * 100

        print("{:<15} {:>11.1f}% {:>11.1f}% {:>11.1f}%".format(
            "{:.0f}%".format(ratio * 100),
            baseline,
            h2o,
            ctm,
        ))

    # Calculate improvements
    print()
    print("CTM+ Improvement vs Industry Baseline:")
    for ratio in ratios:
        baseline = results["industry_baseline"].get(ratio, {}).get("important_retention", 0)
        ctm = results["ctm_plus"].get(ratio, {}).get("important_retention", 0)
        if baseline > 0:
            improvement = ((ctm - baseline) / baseline) * 100
            print("  At {:>3.0f}% cache: {:+.1f}%".format(ratio * 100, improvement))


def cmd_latency(args):
    """Measure latency distribution across policies."""
    print_header("Latency Distribution Test")

    gen = EnterpriseWorkloadGenerator(seed=42)
    config = EnterpriseConfig(tokens_per_block=16)

    # Use long-context for latency testing
    workload = gen.long_context_generation(
        context_length=args.context_length,
        generation_length=args.generation_length,
    )

    max_blocks = int((args.context_length // 16) * args.cache_ratio)
    policies = ALL_POLICIES if args.full else QUICK_POLICIES

    print("Configuration:")
    print("  Context:   {:,} tokens".format(args.context_length))
    print("  Accesses:  {:,}".format(len(workload)))
    print("  Cache:     {} blocks ({:.0f}%)".format(max_blocks, args.cache_ratio * 100))
    print()

    results = run_enterprise_benchmark(workload, max_blocks, policies, config)

    print("{:<22} {:>12} {:>12} {:>12} {:>12}".format(
        "Policy", "p50 (us)", "p95 (us)", "p99 (us)", "Throughput"
    ))
    print("-" * 72)

    for policy in policies:
        r = results[policy.value]
        print("{:<22} {:>12.2f} {:>12.2f} {:>12.2f} {:>10.0f}/s".format(
            policy.value,
            r["p50_latency_us"],
            r["p95_latency_us"],
            r["p99_latency_us"],
            r["throughput"],
        ))


def cmd_head_to_head(args):
    """Head-to-head comparison: CTM+ vs specific baseline."""
    baseline_map = {
        "lru": EnterprisePolicy.LRU,
        "industry": EnterprisePolicy.INDUSTRY_BASELINE,
        "h2o": EnterprisePolicy.H2O,
        "sink-lru": EnterprisePolicy.SINK_LRU,
        "attention-lru": EnterprisePolicy.ATTENTION_LRU,
    }

    baseline = baseline_map.get(args.baseline.lower())
    if not baseline:
        print("Unknown baseline: {}".format(args.baseline))
        print("Available: {}".format(list(baseline_map.keys())))
        return

    print_header("Head-to-Head: CTM+ vs {}".format(baseline.value.upper()))

    gen = EnterpriseWorkloadGenerator(seed=42)
    config = EnterpriseConfig()

    workloads = {
        "long_context": gen.long_context_generation(context_length=8192, generation_length=256),
        "multi_tenant": gen.multi_tenant_batch(num_sequences=8, context_length=2048),
        "document_qa": gen.document_qa_rag(doc_length=4096, num_queries=10),
        "code": gen.code_completion(file_length=2048, num_completions=20),
    }

    cache_ratios = [0.10, 0.25, 0.50]
    policies = [baseline, EnterprisePolicy.CTM_PLUS]

    print("{:<15} {:>8} {:>12} {:>12} {:>12} {:>12}".format(
        "Workload", "Cache%", "Base Hit", "CTM+ Hit", "Base Imp", "CTM+ Imp"
    ))
    print("-" * 75)

    ctm_wins = 0
    total_tests = 0

    for wl_name, workload in workloads.items():
        for ratio in cache_ratios:
            max_blocks = max(16, int(512 * ratio))
            results = run_enterprise_benchmark(workload, max_blocks, policies, config)

            base_r = results[baseline.value]
            ctm_r = results["ctm_plus"]

            print("{:<15} {:>7.0f}% {:>11.1f}% {:>11.1f}% {:>11.1f}% {:>11.1f}%".format(
                wl_name[:14],
                ratio * 100,
                base_r["hit_rate"] * 100,
                ctm_r["hit_rate"] * 100,
                base_r["important_retention"] * 100,
                ctm_r["important_retention"] * 100,
            ))

            # Track wins
            if ctm_r["important_retention"] > base_r["important_retention"]:
                ctm_wins += 1
            total_tests += 1

    print()
    print("CTM+ wins on important token retention: {}/{} tests ({:.0f}%)".format(
        ctm_wins, total_tests, (ctm_wins / total_tests) * 100
    ))


def print_results_table(results: dict, policies: list):
    """Print formatted results table."""
    print("{:<22} {:>8} {:>10} {:>10} {:>10} {:>10}".format(
        "Policy", "Hit%", "AttnCov%", "ImpRet%", "Sinks%", "Evictions"
    ))
    print("-" * 72)

    # Get LRU baseline
    lru_hit = results.get("lru", {}).get("hit_rate", 0)

    for policy in policies:
        r = results[policy.value]

        # Calculate improvement vs LRU
        if lru_hit > 0 and policy != EnterprisePolicy.LRU:
            improvement = ((r["hit_rate"] - lru_hit) / lru_hit) * 100
            hit_str = "{:.1f}% ({:+.0f}%)".format(r["hit_rate"] * 100, improvement)
        else:
            hit_str = "{:.1f}%".format(r["hit_rate"] * 100)

        print("{:<22} {:>12} {:>9.1f}% {:>9.1f}% {:>9.1f}% {:>10,}".format(
            policy.value,
            hit_str,
            r["attention_coverage"] * 100,
            r["important_retention"] * 100,
            r["sink_retention"] * 100,
            r["evictions"],
        ))


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise KV Cache Benchmark CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Workload command
    p_workload = subparsers.add_parser("workload", help="Run specific workload benchmark")
    p_workload.add_argument("--type", choices=["long-context", "multi-tenant", "document-qa", "code"],
                           default="long-context", help="Workload type")
    p_workload.add_argument("--context-length", type=int, default=8192, help="Context length in tokens")
    p_workload.add_argument("--generation-length", type=int, default=256, help="Generation length")
    p_workload.add_argument("--num-sequences", type=int, default=8, help="Number of sequences for multi-tenant")
    p_workload.add_argument("--num-queries", type=int, default=10, help="Number of queries for document-qa")
    p_workload.add_argument("--cache-ratio", type=float, default=0.25, help="Cache ratio (0.0-1.0)")
    p_workload.add_argument("--block-size", type=int, default=16, help="Tokens per block")
    p_workload.add_argument("--seed", type=int, default=42, help="Random seed")
    p_workload.add_argument("--full", action="store_true", help="Test all policies")
    p_workload.set_defaults(func=cmd_workload)

    # Pressure test command
    p_pressure = subparsers.add_parser("pressure-test", help="Test quality under memory pressure")
    p_pressure.add_argument("--ratios", default="0.10,0.25,0.50", help="Cache ratios to test (comma-separated)")
    p_pressure.add_argument("--context-length", type=int, default=8192, help="Context length")
    p_pressure.add_argument("--block-size", type=int, default=16, help="Tokens per block")
    p_pressure.add_argument("--full", action="store_true", help="Test all policies")
    p_pressure.set_defaults(func=cmd_pressure_test)

    # Full report command
    p_report = subparsers.add_parser("full-report", help="Generate comprehensive benchmark report")
    p_report.set_defaults(func=cmd_full_report)

    # Latency command
    p_latency = subparsers.add_parser("latency", help="Measure latency distribution")
    p_latency.add_argument("--context-length", type=int, default=8192, help="Context length")
    p_latency.add_argument("--generation-length", type=int, default=256, help="Generation length")
    p_latency.add_argument("--cache-ratio", type=float, default=0.25, help="Cache ratio")
    p_latency.add_argument("--full", action="store_true", help="Test all policies")
    p_latency.set_defaults(func=cmd_latency)

    # Head-to-head command
    p_h2h = subparsers.add_parser("head-to-head", help="Compare CTM+ vs specific baseline")
    p_h2h.add_argument("--baseline", default="industry", help="Baseline to compare against")
    p_h2h.set_defaults(func=cmd_head_to_head)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
