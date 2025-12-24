"""
Benchmark: EMA 2.7 vs Bayesian 2.7
==================================

Compares computational cost, convergence, and when each is appropriate.

Usage:
    python -m symbolu.guna_modulation.benchmarks.ema_vs_bayesian

Results help determine:
- When Bayesian is overkill
- When EMA is insufficient
- Resource trade-offs
"""

import time
import statistics
from dataclasses import dataclass
from typing import List, Tuple
import random

# Import both modes
from symbolu.guna_modulation import (
    # EMA mode
    create_state_engine_for_tier,
    # Bayesian mode
    create_bayesian_engine_for_tier,
    # Shared
    Observables,
    StateRegister,
    TIER_ENTERPRISE_1,
    TIER_ENTERPRISE_2,
    TIER_CONSUMER,
)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_us: float
    min_time_us: float
    max_time_us: float
    std_dev_us: float
    memory_estimate_bytes: int
    final_value: float
    has_uncertainty: bool
    confidence: float = 0.0
    credible_interval: Tuple[float, float] = (0.0, 0.0)


def generate_observables(seed: int = None) -> Observables:
    """Generate random but valid observables."""
    if seed is not None:
        random.seed(seed)

    # Random Guna distribution (must sum to 1)
    s = random.uniform(0.2, 0.6)
    r = random.uniform(0.1, 0.4)
    t = 1.0 - s - r
    t = max(0.0, min(1.0, t))

    # Renormalize
    total = s + r + t
    s, r, t = s/total, r/total, t/total

    return Observables(
        s=s, r=r, t=t,
        H=random.uniform(0.2, 0.8),
        delta_sem=random.uniform(0.1, 0.5),
        C_contr=random.uniform(0.0, 0.3),
        F_fail=random.uniform(0.0, 0.1),
    )


def benchmark_ema(iterations: int, tier: str = TIER_ENTERPRISE_2) -> BenchmarkResult:
    """Benchmark EMA mode."""
    engine = create_state_engine_for_tier(tier=tier, enabled=True)

    times = []
    obs_list = [generate_observables(i) for i in range(iterations)]

    # Warmup
    for obs in obs_list[:10]:
        engine.update(obs)

    # Reset engine
    engine = create_state_engine_for_tier(tier=tier, enabled=True)

    # Benchmark
    for obs in obs_list:
        start = time.perf_counter_ns()
        audit = engine.update(obs)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000)  # Convert to microseconds

    total_ms = sum(times) / 1000

    return BenchmarkResult(
        name="EMA 2.7",
        iterations=iterations,
        total_time_ms=total_ms,
        avg_time_us=statistics.mean(times),
        min_time_us=min(times),
        max_time_us=max(times),
        std_dev_us=statistics.stdev(times) if len(times) > 1 else 0,
        memory_estimate_bytes=estimate_ema_memory(),
        final_value=engine.state.tau_768,
        has_uncertainty=False,
    )


def benchmark_bayesian(iterations: int, tier: str = TIER_ENTERPRISE_2) -> BenchmarkResult:
    """Benchmark Bayesian mode."""
    engine = create_bayesian_engine_for_tier(tier=tier)

    times = []
    obs_list = [generate_observables(i) for i in range(iterations)]

    # Warmup
    for obs in obs_list[:10]:
        engine.update(obs)

    # Reset engine
    engine = create_bayesian_engine_for_tier(tier=tier)

    # Benchmark
    for obs in obs_list:
        start = time.perf_counter_ns()
        audit = engine.update(obs)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000)

    total_ms = sum(times) / 1000

    # Get uncertainty info
    confidence = engine.bayesian_confidence if hasattr(engine, 'bayesian_confidence') else 0.0

    return BenchmarkResult(
        name="Bayesian 2.7",
        iterations=iterations,
        total_time_ms=total_ms,
        avg_time_us=statistics.mean(times),
        min_time_us=min(times),
        max_time_us=max(times),
        std_dev_us=statistics.stdev(times) if len(times) > 1 else 0,
        memory_estimate_bytes=estimate_bayesian_memory(),
        final_value=engine.state.tau_768,
        has_uncertainty=True,
        confidence=confidence if confidence else 0.0,
    )


def estimate_ema_memory() -> int:
    """Estimate memory usage for EMA mode."""
    # StateRegister: 5 floats (8 bytes each) + tuples
    state_register = 5 * 8 + 3 * 8 * 2  # tau_768, tau_175, b_policy + w_tone, w_guna
    # Config: small
    config = 200
    # Audit history: minimal
    audit = 100
    return state_register + config + audit


def estimate_bayesian_memory() -> int:
    """Estimate memory usage for Bayesian mode."""
    # StateRegister: same as EMA
    state_register = 5 * 8 + 3 * 8 * 2
    # BayesianPosterior: 4 per parameter (alpha, beta, n_obs, cached)
    # 4 parameters × 4 floats × 8 bytes
    posteriors = 4 * 4 * 8
    # BayesianStateRegister: holds all posteriors
    bayesian_state = posteriors * 4 + 100  # overhead
    # Config: larger
    config = 400
    # Audit history: richer
    audit = 300
    return state_register + bayesian_state + config + audit


def benchmark_convergence(target: float = 0.7, max_iter: int = 100) -> dict:
    """
    Compare convergence speed to a target value.

    Shows how quickly each mode reaches stable estimates.
    """
    ema_engine = create_state_engine_for_tier(tier=TIER_ENTERPRISE_2, enabled=True)
    bay_engine = create_bayesian_engine_for_tier(tier=TIER_ENTERPRISE_2)

    # Generate observations that push toward target
    results = {
        "ema_values": [],
        "bayesian_values": [],
        "bayesian_confidence": [],
        "target": target,
    }

    for i in range(max_iter):
        # Observables biased toward target
        s = target * 0.8 + random.uniform(-0.1, 0.1)
        s = max(0.1, min(0.9, s))
        r = (1 - s) * 0.5
        t = 1 - s - r

        obs = Observables(
            s=s, r=r, t=t,
            H=0.3 + random.uniform(-0.1, 0.1),
            delta_sem=0.2,
            C_contr=0.1,
            F_fail=0.0,
        )

        ema_engine.update(obs)
        bay_engine.update(obs)

        results["ema_values"].append(ema_engine.state.tau_768)
        results["bayesian_values"].append(bay_engine.state.tau_768)

        conf = bay_engine.bayesian_confidence if hasattr(bay_engine, 'bayesian_confidence') else 0
        results["bayesian_confidence"].append(conf if conf else 0)

    return results


def print_comparison_table(ema: BenchmarkResult, bayesian: BenchmarkResult):
    """Print side-by-side comparison."""
    print("\n" + "=" * 70)
    print("BENCHMARK: EMA 2.7 vs Bayesian 2.7")
    print("=" * 70)

    print(f"\n{'Metric':<30} {'EMA 2.7':>18} {'Bayesian 2.7':>18}")
    print("-" * 70)

    print(f"{'Iterations':<30} {ema.iterations:>18,} {bayesian.iterations:>18,}")
    print(f"{'Total Time (ms)':<30} {ema.total_time_ms:>18.2f} {bayesian.total_time_ms:>18.2f}")
    print(f"{'Avg Time (μs)':<30} {ema.avg_time_us:>18.2f} {bayesian.avg_time_us:>18.2f}")
    print(f"{'Min Time (μs)':<30} {ema.min_time_us:>18.2f} {bayesian.min_time_us:>18.2f}")
    print(f"{'Max Time (μs)':<30} {ema.max_time_us:>18.2f} {bayesian.max_time_us:>18.2f}")
    print(f"{'Std Dev (μs)':<30} {ema.std_dev_us:>18.2f} {bayesian.std_dev_us:>18.2f}")
    print(f"{'Memory Est. (bytes)':<30} {ema.memory_estimate_bytes:>18,} {bayesian.memory_estimate_bytes:>18,}")
    print(f"{'Final τ_768':<30} {ema.final_value:>18.4f} {bayesian.final_value:>18.4f}")
    print(f"{'Has Uncertainty':<30} {'No':>18} {'Yes':>18}")
    print(f"{'Confidence':<30} {'N/A':>18} {bayesian.confidence:>18.2%}")

    # Compute ratios
    time_ratio = bayesian.avg_time_us / ema.avg_time_us if ema.avg_time_us > 0 else 0
    memory_ratio = bayesian.memory_estimate_bytes / ema.memory_estimate_bytes

    print("\n" + "-" * 70)
    print(f"{'Time Overhead':<30} {time_ratio:>18.2f}x")
    print(f"{'Memory Overhead':<30} {memory_ratio:>18.2f}x")


def print_decision_matrix():
    """Print when to use each mode."""
    print("\n" + "=" * 70)
    print("DECISION MATRIX: When to Use Each Mode")
    print("=" * 70)

    print("""
┌─────────────────────────────────────┬─────────┬───────────┐
│ Scenario                            │   EMA   │ Bayesian  │
├─────────────────────────────────────┼─────────┼───────────┤
│ Simple, stable environment          │   ✅    │  Overkill │
│ Resource-constrained deployment     │   ✅    │     ❌    │
│ High-volume, low-latency required   │   ✅    │     ❌    │
│ Need uncertainty quantification     │   ❌    │     ✅    │
│ Regulatory/compliance audit         │   ❌    │     ✅    │
│ Cold start with domain expertise    │   ❌    │     ✅    │
│ High-stakes decisions               │   ❌    │     ✅    │
│ Want "confidence" signal            │   ❌    │     ✅    │
│ Need credible intervals             │   ❌    │     ✅    │
│ Batch processing (no real-time)     │   ✅    │     ✅    │
└─────────────────────────────────────┴─────────┴───────────┘

RULE OF THUMB:
  - If you need to ask "how confident is this estimate?" → Bayesian
  - If you just need a number and trust the process → EMA
  - If latency matters more than uncertainty → EMA
  - If you have prior knowledge to incorporate → Bayesian
""")


def print_convergence_analysis(results: dict):
    """Print convergence comparison."""
    print("\n" + "=" * 70)
    print("CONVERGENCE ANALYSIS")
    print("=" * 70)

    ema_vals = results["ema_values"]
    bay_vals = results["bayesian_values"]
    bay_conf = results["bayesian_confidence"]
    target = results["target"]

    # Find iterations to reach within 5% of final value
    def iterations_to_stable(values, threshold=0.05):
        if len(values) < 10:
            return len(values)
        final = values[-1]
        for i, v in enumerate(values):
            if abs(v - final) < threshold * abs(final):
                # Check if it stays stable
                remaining = values[i:]
                if all(abs(rv - final) < threshold * abs(final) for rv in remaining):
                    return i
        return len(values)

    ema_stable = iterations_to_stable(ema_vals)
    bay_stable = iterations_to_stable(bay_vals)

    print(f"\nTarget value: {target}")
    print(f"\nIterations to stability (within 5% of final):")
    print(f"  EMA:      {ema_stable:>5} iterations")
    print(f"  Bayesian: {bay_stable:>5} iterations")

    print(f"\nFinal values after {len(ema_vals)} iterations:")
    print(f"  EMA:      τ_768 = {ema_vals[-1]:.4f}")
    print(f"  Bayesian: τ_768 = {bay_vals[-1]:.4f} (confidence: {bay_conf[-1]:.2%})")

    print("\nSample trajectory (every 10 iterations):")
    print(f"{'Iter':>6} {'EMA τ_768':>12} {'Bay τ_768':>12} {'Bay Conf':>12}")
    print("-" * 45)
    for i in range(0, len(ema_vals), 10):
        print(f"{i:>6} {ema_vals[i]:>12.4f} {bay_vals[i]:>12.4f} {bay_conf[i]:>11.2%}")
    print(f"{len(ema_vals)-1:>6} {ema_vals[-1]:>12.4f} {bay_vals[-1]:>12.4f} {bay_conf[-1]:>11.2%}")


def print_resource_summary():
    """Print resource usage summary."""
    print("\n" + "=" * 70)
    print("RESOURCE SUMMARY")
    print("=" * 70)

    ema_mem = estimate_ema_memory()
    bay_mem = estimate_bayesian_memory()

    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│                        RESOURCE COMPARISON                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Memory per engine instance:                                        │
│    EMA:      ~{ema_mem:,} bytes ({ema_mem/1024:.1f} KB)                              │
│    Bayesian: ~{bay_mem:,} bytes ({bay_mem/1024:.1f} KB)                              │
│    Overhead: {bay_mem/ema_mem:.1f}x                                                   │
│                                                                     │
│  Computational complexity per update:                               │
│    EMA:      O(1) - fixed arithmetic operations                     │
│    Bayesian: O(1) - fixed but ~2-3x more operations                 │
│                                                                     │
│  Scalability (1M concurrent sessions):                              │
│    EMA:      ~{ema_mem * 1_000_000 / 1_000_000_000:.1f} GB RAM                                             │
│    Bayesian: ~{bay_mem * 1_000_000 / 1_000_000_000:.1f} GB RAM                                             │
│                                                                     │
│  When Bayesian is OVERKILL:                                         │
│    - Simple tuning tasks                                            │
│    - Stable, well-understood domains                                │
│    - No regulatory requirements                                     │
│    - Latency-critical paths (<1μs budget)                           │
│    - Resource-constrained edge devices                              │
│                                                                     │
│  When EMA is INSUFFICIENT:                                          │
│    - Need to quantify uncertainty                                   │
│    - Regulatory/audit requirements                                  │
│    - High-stakes decisions                                          │
│    - Cold start with prior knowledge                                │
│    - Need "confidence" signals for escalation                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
""")


def run_all_benchmarks():
    """Run complete benchmark suite."""
    print("\n" + "=" * 70)
    print("SymbolU v2.7: EMA vs Bayesian Benchmark Suite")
    print("=" * 70)

    iterations = 1000

    print(f"\nRunning {iterations:,} iterations per mode...")

    # Run benchmarks
    ema_result = benchmark_ema(iterations)
    bayesian_result = benchmark_bayesian(iterations)

    # Print comparison
    print_comparison_table(ema_result, bayesian_result)

    # Run convergence analysis
    print("\nRunning convergence analysis...")
    convergence = benchmark_convergence(target=0.7, max_iter=100)
    print_convergence_analysis(convergence)

    # Print decision matrix
    print_decision_matrix()

    # Print resource summary
    print_resource_summary()

    print("\n" + "=" * 70)
    print("Benchmark complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_all_benchmarks()
