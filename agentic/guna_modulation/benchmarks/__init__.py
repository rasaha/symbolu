"""
Benchmarks for SymbolU Guna Modulation
======================================

Benchmark modules:
- ema_vs_bayesian: Compare EMA 2.7 vs Bayesian 2.7 modes
"""

from agentic.guna_modulation.benchmarks.ema_vs_bayesian import (
    run_all_benchmarks,
    benchmark_ema,
    benchmark_bayesian,
    benchmark_convergence,
    BenchmarkResult,
)

__all__ = [
    "run_all_benchmarks",
    "benchmark_ema",
    "benchmark_bayesian",
    "benchmark_convergence",
    "BenchmarkResult",
]
