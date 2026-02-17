#!/usr/bin/env python3
"""
Critic Benchmarking Utilities

Compare performance of different critic implementations:
- Rule-based (free, fast, lower quality)
- Local models (cheap, medium speed, good quality)
- API-based (expensive, slow, best quality)

USAGE:
    python -m symbolu.agentic_framework.benchmark_critics

    # With specific backends
    python -m symbolu.agentic_framework.benchmark_critics --ollama phi4-mini
    python -m symbolu.agentic_framework.benchmark_critics --transformers microsoft/Phi-4-mini-instruct

METRICS:
    - Latency (ms per evaluation)
    - Cost (estimated USD per 1000 evaluations)
    - Quality agreement (vs reference scores)
    - Consistency (variance across runs)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .reflective_loop import QualityCritic, QualityCritique, RuleBasedCritic


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = [
    {
        "name": "simple_greeting",
        "prompt": "Say hello",
        "response": "Hello! How can I help you today?",
        "expected_quality": "high",  # Should score well
    },
    {
        "name": "too_short",
        "prompt": "Explain how photosynthesis works",
        "response": "Plants use sunlight.",
        "expected_quality": "low",  # Too short for the question
    },
    {
        "name": "good_explanation",
        "prompt": "What is Python?",
        "response": """Python is a high-level, interpreted programming language known for its
clear syntax and readability. Created by Guido van Rossum in 1991, it supports multiple
programming paradigms including procedural, object-oriented, and functional programming.
Python is widely used in web development, data science, machine learning, automation,
and scientific computing. Its extensive standard library and large ecosystem of third-party
packages make it versatile for many applications.""",
        "expected_quality": "high",
    },
    {
        "name": "off_topic",
        "prompt": "How do I install Python?",
        "response": """The weather today is quite nice. I enjoy sunny days because they
make me feel happy. Sometimes I like to go for walks in the park when it's warm outside.""",
        "expected_quality": "low",  # Completely off-topic
    },
    {
        "name": "code_with_explanation",
        "prompt": "Write a function to check if a number is prime",
        "response": """Here's a Python function to check if a number is prime:

```python
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True
```

This function works by:
1. Handling edge cases (numbers less than 2, and 2 itself)
2. Eliminating even numbers quickly
3. Only checking odd divisors up to the square root of n

Time complexity: O(√n), Space complexity: O(1)""",
        "expected_quality": "high",
    },
    {
        "name": "repetitive",
        "prompt": "What are the benefits of exercise?",
        "response": """Exercise is good. Exercise helps you. Exercise is beneficial.
Exercise makes you healthy. Exercise is important. Exercise is good for you.
Exercise helps your body. Exercise is recommended.""",
        "expected_quality": "low",  # Repetitive, not informative
    },
    {
        "name": "technical_accurate",
        "prompt": "Explain how HTTPS works",
        "response": """HTTPS (Hypertext Transfer Protocol Secure) secures web communications
through TLS/SSL encryption. The process works as follows:

1. **TLS Handshake**: Client sends supported cipher suites, server responds with certificate
2. **Certificate Verification**: Client verifies server's certificate against trusted CAs
3. **Key Exchange**: Using asymmetric encryption, both parties establish a shared secret
4. **Symmetric Encryption**: All subsequent data is encrypted with the shared session key

Key benefits:
- Confidentiality: Data is encrypted in transit
- Integrity: Data cannot be modified without detection
- Authentication: Server identity is verified

HTTPS uses port 443 by default and is essential for protecting sensitive data like
passwords, payment information, and personal data.""",
        "expected_quality": "high",
    },
    {
        "name": "medium_quality",
        "prompt": "What is machine learning?",
        "response": """Machine learning is a type of AI that allows computers to learn
from data. It uses algorithms to find patterns and make predictions. Common types
include supervised learning, unsupervised learning, and reinforcement learning.""",
        "expected_quality": "medium",  # Correct but could be more detailed
    },
]


@dataclass
class BenchmarkResult:
    """Result from benchmarking a single critic."""
    critic_name: str
    test_case: str
    latency_ms: float
    quality_score: float
    coherence: float
    correctness: float
    completeness: float
    relevance: float
    expected_quality: str


@dataclass
class CriticBenchmark:
    """Aggregated benchmark results for a critic."""
    critic_name: str
    results: List[BenchmarkResult] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.latency_ms for r in self.results)

    @property
    def latency_stddev(self) -> float:
        if len(self.results) < 2:
            return 0.0
        return statistics.stdev(r.latency_ms for r in self.results)

    @property
    def avg_quality_score(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.quality_score for r in self.results)

    @property
    def quality_accuracy(self) -> float:
        """How well scores match expected quality levels."""
        if not self.results:
            return 0.0

        correct = 0
        for r in self.results:
            if r.expected_quality == "high" and r.quality_score >= 0.7:
                correct += 1
            elif r.expected_quality == "low" and r.quality_score < 0.5:
                correct += 1
            elif r.expected_quality == "medium" and 0.5 <= r.quality_score < 0.8:
                correct += 1

        return correct / len(self.results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "critic_name": self.critic_name,
            "total_tests": len(self.results),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "latency_stddev_ms": round(self.latency_stddev, 2),
            "avg_quality_score": round(self.avg_quality_score, 3),
            "quality_accuracy": round(self.quality_accuracy, 3),
            "estimated_cost_per_1k": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        """Estimate cost per 1000 evaluations."""
        if "rule" in self.critic_name.lower():
            return 0.0
        elif "local" in self.critic_name.lower() or "ollama" in self.critic_name.lower():
            return 0.10  # ~$0.0001 per eval
        elif "api" in self.critic_name.lower() or "gpt" in self.critic_name.lower():
            return 10.0  # ~$0.01 per eval
        return 0.0


def benchmark_critic(
    critic: QualityCritic,
    critic_name: str,
    test_cases: Optional[List[Dict]] = None,
    runs_per_test: int = 1,
) -> CriticBenchmark:
    """
    Benchmark a critic against test cases.

    Args:
        critic: Critic to benchmark
        critic_name: Name for reporting
        test_cases: Test cases (defaults to TEST_CASES)
        runs_per_test: Number of runs per test for averaging

    Returns:
        CriticBenchmark with results
    """
    cases = test_cases or TEST_CASES
    benchmark = CriticBenchmark(critic_name=critic_name)

    for case in cases:
        for _ in range(runs_per_test):
            start = time.perf_counter()
            critique = critic.evaluate(case["prompt"], case["response"])
            elapsed_ms = (time.perf_counter() - start) * 1000

            result = BenchmarkResult(
                critic_name=critic_name,
                test_case=case["name"],
                latency_ms=elapsed_ms,
                quality_score=critique.overall_score,
                coherence=critique.coherence,
                correctness=critique.correctness,
                completeness=critique.completeness,
                relevance=critique.relevance,
                expected_quality=case["expected_quality"],
            )
            benchmark.results.append(result)

    return benchmark


def compare_critics(
    critics: List[Tuple[QualityCritic, str]],
    test_cases: Optional[List[Dict]] = None,
    runs_per_test: int = 3,
) -> Dict[str, Any]:
    """
    Compare multiple critics.

    Args:
        critics: List of (critic, name) tuples
        test_cases: Test cases to use
        runs_per_test: Runs per test for averaging

    Returns:
        Comparison report
    """
    benchmarks = []

    for critic, name in critics:
        print(f"Benchmarking {name}...", file=sys.stderr)
        benchmark = benchmark_critic(critic, name, test_cases, runs_per_test)
        benchmarks.append(benchmark)

    # Build comparison report
    report = {
        "summary": [],
        "per_test_comparison": {},
        "recommendations": [],
    }

    # Summary per critic
    for b in benchmarks:
        report["summary"].append(b.to_dict())

    # Per-test comparison
    cases = test_cases or TEST_CASES
    for case in cases:
        case_name = case["name"]
        report["per_test_comparison"][case_name] = {}

        for b in benchmarks:
            case_results = [r for r in b.results if r.test_case == case_name]
            if case_results:
                avg_score = statistics.mean(r.quality_score for r in case_results)
                avg_latency = statistics.mean(r.latency_ms for r in case_results)
                report["per_test_comparison"][case_name][b.critic_name] = {
                    "avg_score": round(avg_score, 3),
                    "avg_latency_ms": round(avg_latency, 2),
                }

    # Generate recommendations
    if len(benchmarks) >= 2:
        # Find best quality/cost ratio
        best_ratio = None
        best_name = None
        for b in benchmarks:
            cost = b._estimate_cost()
            if cost == 0:
                cost = 0.01  # Avoid division by zero
            ratio = b.quality_accuracy / cost
            if best_ratio is None or ratio > best_ratio:
                best_ratio = ratio
                best_name = b.critic_name

        if best_name:
            report["recommendations"].append(
                f"Best quality/cost ratio: {best_name}"
            )

        # Find fastest
        fastest = min(benchmarks, key=lambda b: b.avg_latency_ms)
        report["recommendations"].append(
            f"Fastest: {fastest.critic_name} ({fastest.avg_latency_ms:.1f}ms avg)"
        )

        # Find most accurate
        most_accurate = max(benchmarks, key=lambda b: b.quality_accuracy)
        report["recommendations"].append(
            f"Most accurate: {most_accurate.critic_name} ({most_accurate.quality_accuracy:.1%})"
        )

    return report


def print_report(report: Dict[str, Any]) -> None:
    """Print formatted benchmark report."""
    print("\n" + "=" * 70)
    print(" CRITIC BENCHMARK REPORT")
    print("=" * 70)

    # Summary table
    print("\n## Summary\n")
    print(f"{'Critic':<25} {'Latency':>10} {'Quality':>10} {'Accuracy':>10} {'Cost/1K':>10}")
    print("-" * 70)

    for s in report["summary"]:
        print(
            f"{s['critic_name']:<25} "
            f"{s['avg_latency_ms']:>8.1f}ms "
            f"{s['avg_quality_score']:>10.3f} "
            f"{s['quality_accuracy']:>9.1%} "
            f"${s['estimated_cost_per_1k']:>8.2f}"
        )

    # Per-test scores
    print("\n## Per-Test Quality Scores\n")
    critics = list(report["summary"])
    critic_names = [c["critic_name"] for c in critics]

    header = f"{'Test Case':<25}" + "".join(f"{n[:12]:>15}" for n in critic_names)
    print(header)
    print("-" * len(header))

    for test_name, scores in report["per_test_comparison"].items():
        row = f"{test_name:<25}"
        for name in critic_names:
            if name in scores:
                row += f"{scores[name]['avg_score']:>15.3f}"
            else:
                row += f"{'N/A':>15}"
        print(row)

    # Recommendations
    if report["recommendations"]:
        print("\n## Recommendations\n")
        for rec in report["recommendations"]:
            print(f"  - {rec}")

    print("\n" + "=" * 70)


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark critic implementations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Benchmark rule-based only
  python -m symbolu.agentic_framework.benchmark_critics

  # Include Ollama local model
  python -m symbolu.agentic_framework.benchmark_critics --ollama phi4-mini

  # Include HuggingFace model
  python -m symbolu.agentic_framework.benchmark_critics --transformers microsoft/Phi-4-mini-instruct

  # Output as JSON
  python -m symbolu.agentic_framework.benchmark_critics --json
""",
    )

    parser.add_argument(
        "--ollama",
        type=str,
        help="Ollama model to benchmark (e.g., phi4-mini)",
    )
    parser.add_argument(
        "--transformers",
        type=str,
        help="HuggingFace model to benchmark",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Runs per test case (default: 3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    # Build list of critics to benchmark
    critics: List[Tuple[QualityCritic, str]] = [
        (RuleBasedCritic(), "RuleBasedCritic"),
    ]

    if args.ollama:
        try:
            from .local_critic import create_ollama_critic
            critic = create_ollama_critic(model=args.ollama, fallback_to_rules=False)
            if critic.backend.is_available():
                critics.append((critic, f"Ollama:{args.ollama}"))
            else:
                print(f"Warning: Ollama model {args.ollama} not available", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create Ollama critic: {e}", file=sys.stderr)

    if args.transformers:
        try:
            from .local_critic import create_transformers_critic
            critic = create_transformers_critic(model_id=args.transformers, fallback_to_rules=False)
            if critic.backend.is_available():
                critics.append((critic, f"Transformers:{args.transformers.split('/')[-1]}"))
            else:
                print(f"Warning: Transformers not available", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create Transformers critic: {e}", file=sys.stderr)

    # Run benchmark
    report = compare_critics(critics, runs_per_test=args.runs)

    # Output
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
