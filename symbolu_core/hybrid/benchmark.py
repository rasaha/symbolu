"""
Computation Benchmark
=====================

Benchmarks comparing phoneme-based vs transformer computation.

Demonstrates the computational savings from:
1. PhonemeAttentionHead vs traditional attention
2. CandidatePreFilter vs brute-force inference
3. SemanticRouter vs single general model
"""

from dataclasses import dataclass
from typing import Tuple, List, Dict
import time

from symbolu_core.hybrid.attention import PhonemeAttentionHead, HybridAttentionLayer
from symbolu_core.hybrid.prefilter import CandidatePreFilter, ProgressiveFilter
from symbolu_core.hybrid.router import SemanticRouter, ModelType


@dataclass(frozen=True)
class BenchmarkResult:
    """Result from a benchmark run."""
    name: str
    traditional_cost: float  # FLOPs or time
    optimized_cost: float
    savings_percent: float
    speedup_factor: float
    details: Dict[str, float]


class ComputationBenchmark:
    """
    Benchmarks for phoneme-based optimizations.

    Demonstrates computational savings compared to traditional
    transformer approaches.
    """

    def __init__(self):
        self.attention = PhonemeAttentionHead()
        self.hybrid_layer = HybridAttentionLayer()
        self.prefilter = CandidatePreFilter(threshold=0.5)
        self.router = SemanticRouter()

    def benchmark_attention(
        self,
        tokens: Tuple[str, ...],
    ) -> BenchmarkResult:
        """
        Benchmark phoneme attention vs traditional attention.

        Args:
            tokens: Sequence of word tokens

        Returns:
            BenchmarkResult comparing FLOPs
        """
        seq_len = len(tokens)
        head_dim = 64  # Typical attention head dimension

        # Compute phoneme attention (also measures FLOPs)
        result = self.attention.compute_attention(tokens)
        phoneme_flops = result.computation_flops

        # Estimate traditional attention FLOPs
        # QK^T: n × n × d, softmax: n × n, AV: n × n × d
        traditional_flops = seq_len * seq_len * head_dim * 2 + seq_len * seq_len

        savings = (traditional_flops - phoneme_flops) / traditional_flops * 100
        speedup = traditional_flops / phoneme_flops if phoneme_flops > 0 else 0

        return BenchmarkResult(
            name="Attention Head",
            traditional_cost=traditional_flops,
            optimized_cost=phoneme_flops,
            savings_percent=savings,
            speedup_factor=speedup,
            details={
                "sequence_length": seq_len,
                "head_dimension": head_dim,
                "phoneme_dimension": 10,
            },
        )

    def benchmark_prefilter(
        self,
        candidates: Tuple[str, ...],
        target: str,
        transformer_ms_per_call: float = 10.0,
    ) -> BenchmarkResult:
        """
        Benchmark pre-filtering vs brute-force inference.

        Args:
            candidates: Candidate set
            target: Target word to compare against
            transformer_ms_per_call: Assumed transformer inference time

        Returns:
            BenchmarkResult comparing time
        """
        # Time the pre-filter
        start = time.perf_counter()
        filtered, stats = self.prefilter.filter_with_stats(candidates, target)
        filter_time_ms = (time.perf_counter() - start) * 1000

        # Calculate costs
        num_candidates = len(candidates)
        num_filtered = len(filtered)

        # Without filter: transformer on all
        traditional_ms = num_candidates * transformer_ms_per_call

        # With filter: filter time + transformer on filtered
        optimized_ms = filter_time_ms + num_filtered * transformer_ms_per_call

        savings = (traditional_ms - optimized_ms) / traditional_ms * 100
        speedup = traditional_ms / optimized_ms if optimized_ms > 0 else 0

        return BenchmarkResult(
            name="Candidate Pre-Filter",
            traditional_cost=traditional_ms,
            optimized_cost=optimized_ms,
            savings_percent=savings,
            speedup_factor=speedup,
            details={
                "total_candidates": num_candidates,
                "filtered_candidates": num_filtered,
                "filter_time_ms": filter_time_ms,
                "transformer_calls_saved": num_candidates - num_filtered,
            },
        )

    def benchmark_router(
        self,
        queries: Tuple[str, ...],
        general_params: int = 175_000_000_000,
        specialized_params: int = 7_000_000_000,
    ) -> BenchmarkResult:
        """
        Benchmark semantic routing vs single model.

        Args:
            queries: Sample queries
            general_params: Parameters in general model
            specialized_params: Parameters in specialized models

        Returns:
            BenchmarkResult comparing parameter usage
        """
        savings = self.router.estimate_savings(
            queries, general_params, specialized_params
        )

        traditional = savings["params_without_routing"]
        optimized = savings["params_with_routing"]

        savings_percent = (traditional - optimized) / traditional * 100 if traditional > 0 else 0
        speedup = traditional / optimized if optimized > 0 else 0

        return BenchmarkResult(
            name="Semantic Router",
            traditional_cost=traditional,
            optimized_cost=optimized,
            savings_percent=savings_percent,
            speedup_factor=speedup,
            details={
                "queries_to_general": savings["queries_to_general"],
                "queries_to_specialized": savings["queries_to_specialized"],
                "percent_specialized": savings["percent_specialized"],
            },
        )

    def benchmark_hybrid_layer(
        self,
        seq_len: int,
    ) -> BenchmarkResult:
        """
        Benchmark hybrid attention layer (phoneme + traditional heads).

        Args:
            seq_len: Sequence length

        Returns:
            BenchmarkResult comparing FLOPs
        """
        savings = self.hybrid_layer.estimate_savings(seq_len)

        traditional = savings["all_traditional_flops"]
        optimized = savings["hybrid_flops"]

        return BenchmarkResult(
            name="Hybrid Attention Layer",
            traditional_cost=traditional,
            optimized_cost=optimized,
            savings_percent=savings["percent_saved"],
            speedup_factor=traditional / optimized if optimized > 0 else 0,
            details={
                "phoneme_heads": savings["phoneme_heads"],
                "traditional_heads": savings["traditional_heads"],
                "sequence_length": seq_len,
            },
        )

    def run_all_benchmarks(
        self,
        sample_tokens: Tuple[str, ...] = ("truth", "is", "light", "and", "love"),
        sample_candidates: Tuple[str, ...] = None,
        sample_queries: Tuple[str, ...] = None,
    ) -> List[BenchmarkResult]:
        """
        Run all benchmarks with sample data.

        Returns list of BenchmarkResult for each optimization.
        """
        if sample_candidates is None:
            # Generate sample candidates
            sample_candidates = tuple(
                f"word{i}" for i in range(1000)
            )

        if sample_queries is None:
            sample_queries = (
                "Love conquers all",
                "Calculate the derivative",
                "Run the build process",
                "What is the meaning of life",
                "Create a new function",
            )

        results = []

        # Attention benchmark
        results.append(self.benchmark_attention(sample_tokens))

        # Pre-filter benchmark
        results.append(self.benchmark_prefilter(sample_candidates, "truth"))

        # Router benchmark
        results.append(self.benchmark_router(sample_queries))

        # Hybrid layer benchmark
        results.append(self.benchmark_hybrid_layer(len(sample_tokens)))

        return results

    def print_summary(self, results: List[BenchmarkResult] = None):
        """Print a summary of benchmark results."""
        if results is None:
            results = self.run_all_benchmarks()

        print("=" * 70)
        print("PHONEME-TRANSFORMER HYBRID OPTIMIZATION BENCHMARK")
        print("=" * 70)
        print()

        for result in results:
            print(f"📊 {result.name}")
            print(f"   Traditional: {result.traditional_cost:,.0f}")
            print(f"   Optimized:   {result.optimized_cost:,.0f}")
            print(f"   Savings:     {result.savings_percent:.1f}%")
            print(f"   Speedup:     {result.speedup_factor:.1f}x")
            for key, value in result.details.items():
                if isinstance(value, float):
                    print(f"   {key}: {value:.2f}")
                else:
                    print(f"   {key}: {value}")
            print()

        print("=" * 70)
        total_savings = sum(r.savings_percent for r in results) / len(results)
        print(f"Average savings across all optimizations: {total_savings:.1f}%")
        print("=" * 70)


def run_demo():
    """Run a demonstration of the benchmark."""
    benchmark = ComputationBenchmark()

    # Custom sample data
    tokens = ("truth", "is", "light", "and", "love", "conquers", "darkness")

    candidates = (
        "light", "bright", "sun", "glow", "shine",
        "dark", "shadow", "night", "gloom", "dim",
        "love", "peace", "joy", "harmony", "unity",
        "war", "hate", "conflict", "strife", "anger",
        "truth", "wisdom", "knowledge", "insight", "clarity",
    )

    queries = (
        "Love is eternal",
        "Calculate the sum",
        "Run the tests",
        "Beauty is truth",
        "What is consciousness",
        "Create a new module",
        "Peace and harmony",
        "Analyze the data",
    )

    print("\n🔬 Running benchmarks with custom data...\n")

    results = [
        benchmark.benchmark_attention(tokens),
        benchmark.benchmark_prefilter(candidates, "truth"),
        benchmark.benchmark_router(queries),
        benchmark.benchmark_hybrid_layer(len(tokens)),
    ]

    benchmark.print_summary(results)

    return results


if __name__ == "__main__":
    run_demo()
