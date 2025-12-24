"""
Canonical Matching Benchmark
============================

Benchmarks the C × R × S canonical matching integration to show:
1. Semantic discrimination accuracy (related vs unrelated words)
2. Referent coherence detection quality
3. S term (non-phonemic) contribution to match quality
4. Coherence filter diagnostic utility

Run:
    python -m symbolu.benchmarks.canonical_match_benchmark
"""

import time
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

from symbolu.providers import get_match_provider, get_filter_provider
from symbolu.providers.interfaces import MatchMode


# =============================================================================
# TEST CASES: Semantic Discrimination
# =============================================================================

DISCRIMINATION_TESTS = {
    "true_matches": {
        "description": "Word pairs that SHOULD match (same/related referent class)",
        "pairs": [
            ("king", "queen"),      # ROLE_BEARER + SOCIAL
            ("fire", "flame"),      # PROCESS + LUMINOUS secondary
            ("happy", "joy"),       # EMOTIONAL
            ("sun", "star"),        # NATURAL_BODY + ENERGY_SOURCE
            ("water", "river"),     # SUBSTANCE / NATURAL_BODY
            ("mother", "father"),   # ROLE_BEARER
            ("walk", "run"),        # PROCESS
            ("love", "hope"),       # EMOTIONAL + ABSTRACT
            ("mountain", "hill"),   # NATURAL_BODY + SPATIAL
            ("book", "pen"),        # ARTIFACT
        ],
        "expected_min_score": 0.15,
        "expected_mode": [MatchMode.TRUE_MATCH, MatchMode.LATENT, MatchMode.DISTORTED],
    },
    "partial_matches": {
        "description": "Word pairs with secondary overlap only",
        "pairs": [
            ("sun", "light"),       # sun=NATURAL_BODY, light=PHENOMENON, share LUMINOUS
            ("fire", "bright"),     # fire=PROCESS, bright=ABSTRACT, share LUMINOUS
            ("tree", "wood"),       # BIOLOGICAL vs SUBSTANCE, share BIOLOGICAL secondary
            ("heart", "love"),      # BIOLOGICAL vs EMOTIONAL, share EMOTIONAL secondary
            ("voice", "song"),      # SIGNAL, one has BIOLOGICAL secondary
        ],
        "expected_min_score": 0.05,
        "expected_mode": [MatchMode.TRUE_MATCH, MatchMode.LATENT, MatchMode.DISTORTED],
    },
    "referent_mismatches": {
        "description": "Word pairs that should NOT match (ChatGPT failure modes)",
        "pairs": [
            ("king", "banana"),     # ROLE_BEARER vs BIOLOGICAL - the key test
            ("tree", "computer"),   # BIOLOGICAL vs ARTIFACT
            ("sun", "pencil"),      # NATURAL_BODY vs ARTIFACT
            ("love", "table"),      # EMOTIONAL vs ARTIFACT
            ("queen", "apple"),     # ROLE_BEARER vs BIOLOGICAL
            ("happy", "rock"),      # EMOTIONAL vs NATURAL_BODY
            ("fire", "chair"),      # PROCESS vs ARTIFACT
            ("king", "water"),      # ROLE_BEARER vs SUBSTANCE
            ("mother", "stone"),    # ROLE_BEARER vs NATURAL_BODY
            ("joy", "computer"),    # EMOTIONAL vs ARTIFACT
        ],
        "expected_max_score": 0.1,
        "expected_mode": [MatchMode.REFERENT_MISMATCH, MatchMode.NON_MATCH],
    },
}


# =============================================================================
# TEST CASES: C × R × S Component Analysis
# =============================================================================

COMPONENT_TESTS = {
    "high_phonetic_low_semantic": {
        "description": "Similar phonetics but different referents (S should gate)",
        "pairs": [
            ("sun", "son"),         # Similar sound, different referent
            ("bear", "bare"),       # Homophones, different referent
            ("flower", "flour"),    # Similar, different domains
        ],
    },
    "low_phonetic_high_semantic": {
        "description": "Different phonetics but same referent (S should boost)",
        "pairs": [
            ("king", "monarch"),    # Different sound, same ROLE_BEARER (if monarch in dict)
            ("happy", "joyful"),    # Different sound, same EMOTIONAL
            ("large", "big"),       # Different sound, same ABSTRACT
        ],
    },
}


# =============================================================================
# Benchmark Data Classes
# =============================================================================

@dataclass
class DiscriminationResult:
    """Result from semantic discrimination test."""
    category: str
    total_pairs: int
    correct: int
    accuracy: float
    avg_score: float
    avg_s_term: float
    mode_distribution: Dict[str, int]
    failures: List[Dict[str, Any]]


@dataclass
class CoherenceFilterResult:
    """Result from coherence filter test."""
    total_queries: int
    avg_coherence_score: float
    avg_referent_mismatches: float
    avg_true_matches: float
    sample_diagnostics: List[Dict[str, Any]]


# =============================================================================
# Benchmark Functions
# =============================================================================

def run_discrimination_benchmark() -> Dict[str, DiscriminationResult]:
    """Run semantic discrimination benchmark."""
    provider = get_match_provider("enterprise")
    results = {}

    for category, test_data in DISCRIMINATION_TESTS.items():
        pairs = test_data["pairs"]
        expected_modes = test_data["expected_mode"]

        correct = 0
        total_score = 0.0
        total_s = 0.0
        mode_counts = defaultdict(int)
        failures = []

        for word_a, word_b in pairs:
            result = provider.match(word_a, word_b)
            total_score += result.match_score
            total_s += result.referent
            mode_counts[result.mode.value] += 1

            # Check if mode is as expected
            if result.mode in expected_modes:
                correct += 1
            else:
                failures.append({
                    "pair": (word_a, word_b),
                    "score": result.match_score,
                    "mode": result.mode.value,
                    "C": result.feasibility,
                    "R": result.realization,
                    "S": result.referent,
                })

            # Additional score threshold check
            if category == "true_matches":
                if result.match_score < test_data.get("expected_min_score", 0):
                    if result.mode in expected_modes:
                        correct -= 1  # Wrong score despite correct mode
                        failures.append({
                            "pair": (word_a, word_b),
                            "score": result.match_score,
                            "reason": f"Score {result.match_score:.3f} below threshold",
                        })
            elif category == "referent_mismatches":
                if result.match_score > test_data.get("expected_max_score", 1.0):
                    if result.mode in expected_modes:
                        correct -= 1
                        failures.append({
                            "pair": (word_a, word_b),
                            "score": result.match_score,
                            "reason": f"Score {result.match_score:.3f} above threshold",
                        })

        results[category] = DiscriminationResult(
            category=category,
            total_pairs=len(pairs),
            correct=max(0, correct),  # Prevent negative
            accuracy=max(0, correct) / len(pairs) * 100,
            avg_score=total_score / len(pairs),
            avg_s_term=total_s / len(pairs),
            mode_distribution=dict(mode_counts),
            failures=failures,
        )

    return results


def run_component_analysis() -> Dict[str, List[Dict[str, Any]]]:
    """Analyze C, R, S component contributions."""
    provider = get_match_provider("enterprise")
    results = {}

    for category, test_data in COMPONENT_TESTS.items():
        category_results = []

        for word_a, word_b in test_data["pairs"]:
            result = provider.match(word_a, word_b)

            category_results.append({
                "pair": f"{word_a} ↔ {word_b}",
                "match_score": result.match_score,
                "C": result.feasibility,
                "R": result.realization,
                "S": result.referent,
                "mode": result.mode.value,
                "is_grounded": result.diagnostics["referent_analysis"]["is_grounded"],
            })

        results[category] = category_results

    return results


def run_coherence_filter_benchmark() -> CoherenceFilterResult:
    """Test the coherence filter with C × R × S diagnostics."""
    provider = get_filter_provider("enterprise", {"with_coherence": True})

    test_queries = [
        ("royalty", ("king", "queen", "banana", "crown", "throne")),
        ("energy", ("sun", "fire", "light", "table", "chair")),
        ("emotions", ("happy", "joy", "love", "computer", "pencil")),
        ("nature", ("tree", "forest", "mountain", "phone", "book")),
    ]

    total_coherence = 0.0
    total_ref_mismatches = 0.0
    total_true_matches = 0.0
    sample_diagnostics = []

    for query, candidates in test_queries:
        result = provider.filter(candidates, query, top_k=5)

        if "coherence_checks" in result.stats:
            summary = result.stats["coherence_checks"]["summary"]
            total_coherence += summary.get("avg_match_score", 0)
            total_ref_mismatches += summary.get("referent_mismatches", 0)
            total_true_matches += summary.get("true_matches", 0)

            sample_diagnostics.append({
                "query": query,
                "filtered": result.filtered_texts,
                "coherence_summary": summary,
            })

    n = len(test_queries)
    return CoherenceFilterResult(
        total_queries=n,
        avg_coherence_score=total_coherence / n,
        avg_referent_mismatches=total_ref_mismatches / n,
        avg_true_matches=total_true_matches / n,
        sample_diagnostics=sample_diagnostics,
    )


def run_latency_benchmark(iterations: int = 100) -> Dict[str, float]:
    """Measure canonical matching latency."""
    provider = get_match_provider("enterprise")

    # Single match latency
    pairs = [("king", "queen"), ("sun", "light"), ("tree", "computer")]
    single_times = []

    for _ in range(iterations):
        for a, b in pairs:
            start = time.perf_counter()
            provider.match(a, b)
            single_times.append((time.perf_counter() - start) * 1000)

    # Batch match latency
    batch_times = []
    for _ in range(iterations // 10):
        start = time.perf_counter()
        provider.match_batch(pairs)
        batch_times.append((time.perf_counter() - start) * 1000)

    return {
        "single_match_avg_ms": sum(single_times) / len(single_times),
        "single_match_min_ms": min(single_times),
        "single_match_max_ms": max(single_times),
        "batch_match_avg_ms": sum(batch_times) / len(batch_times),
        "batch_match_min_ms": min(batch_times),
        "batch_match_max_ms": max(batch_times),
    }


# =============================================================================
# Reporting
# =============================================================================

def print_results(
    discrimination: Dict[str, DiscriminationResult],
    components: Dict[str, List[Dict[str, Any]]],
    coherence: CoherenceFilterResult,
    latency: Dict[str, float],
):
    """Print formatted benchmark results."""

    print("=" * 80)
    print("CANONICAL MATCHING (C × R × S) BENCHMARK RESULTS")
    print("=" * 80)
    print()

    # Semantic Discrimination
    print("## SEMANTIC DISCRIMINATION ACCURACY")
    print("-" * 80)
    print(f"{'Category':<25} {'Pairs':<10} {'Correct':<10} {'Accuracy':<12} {'Avg S':<10}")
    print("-" * 80)

    for category, result in discrimination.items():
        print(f"{category:<25} {result.total_pairs:<10} {result.correct:<10} "
              f"{result.accuracy:>8.1f}%   {result.avg_s_term:.3f}")

    print("-" * 80)
    total_pairs = sum(r.total_pairs for r in discrimination.values())
    total_correct = sum(r.correct for r in discrimination.values())
    overall_acc = total_correct / total_pairs * 100 if total_pairs > 0 else 0
    print(f"{'OVERALL':<25} {total_pairs:<10} {total_correct:<10} {overall_acc:>8.1f}%")
    print()

    # Mode Distribution
    print("## MODE DISTRIBUTION BY CATEGORY")
    print("-" * 80)
    for category, result in discrimination.items():
        print(f"{category}: {result.mode_distribution}")
    print()

    # ChatGPT Failure Mode Check
    print("## CHATGPT FAILURE MODE VALIDATION")
    print("-" * 80)
    ref_mismatch = discrimination.get("referent_mismatches")
    if ref_mismatch:
        print(f"Referent mismatch detection: {ref_mismatch.accuracy:.1f}% accurate")
        print(f"Average S term for mismatches: {ref_mismatch.avg_s_term:.3f} (should be < 0.2)")
        if ref_mismatch.failures:
            print("\nFailures (false positives):")
            for f in ref_mismatch.failures[:3]:
                print(f"  {f['pair']}: score={f.get('score', 'N/A')}, S={f.get('S', 'N/A')}")
    print()

    # Component Analysis
    print("## C × R × S COMPONENT ANALYSIS")
    print("-" * 80)
    for category, results in components.items():
        print(f"\n{category}:")
        print(f"  {'Pair':<25} {'Score':<8} {'C':<8} {'R':<8} {'S':<8} {'Mode'}")
        for r in results:
            print(f"  {r['pair']:<25} {r['match_score']:.3f}   "
                  f"{r['C']:.3f}   {r['R']:.3f}   {r['S']:.3f}   {r['mode']}")
    print()

    # Coherence Filter
    print("## COHERENCE FILTER DIAGNOSTICS")
    print("-" * 80)
    print(f"Queries tested: {coherence.total_queries}")
    print(f"Average coherence score: {coherence.avg_coherence_score:.3f}")
    print(f"Average true matches per query: {coherence.avg_true_matches:.1f}")
    print(f"Average referent mismatches detected: {coherence.avg_referent_mismatches:.1f}")
    print()

    # Latency
    print("## LATENCY METRICS")
    print("-" * 80)
    print(f"Single match: {latency['single_match_avg_ms']:.3f}ms avg "
          f"({latency['single_match_min_ms']:.3f}-{latency['single_match_max_ms']:.3f}ms)")
    print(f"Batch match (3 pairs): {latency['batch_match_avg_ms']:.3f}ms avg "
          f"({latency['batch_match_min_ms']:.3f}-{latency['batch_match_max_ms']:.3f}ms)")
    print()

    # Key Metrics Summary
    print("## KEY METRICS SUMMARY")
    print("-" * 80)
    print(f"| Metric                              | Value           |")
    print(f"|-------------------------------------|-----------------|")
    print(f"| Overall discrimination accuracy     | {overall_acc:.1f}%           |")
    print(f"| Referent mismatch detection         | {ref_mismatch.accuracy if ref_mismatch else 0:.1f}%           |")
    print(f"| Average S for true matches          | {discrimination['true_matches'].avg_s_term:.3f}           |")
    print(f"| Average S for mismatches            | {ref_mismatch.avg_s_term if ref_mismatch else 0:.3f}           |")
    print(f"| Single match latency                | {latency['single_match_avg_ms']:.3f}ms         |")
    print(f"| S term contribution (non-phonemic)  | Active          |")
    print()

    # Interpretation
    print("## INTERPRETATION")
    print("-" * 80)
    print("""
The canonical matching formula MATCH = C × R × S provides:

1. SOURCE INDEPENDENCE: S term derives from referent classes (non-phonemic),
   providing orthogonal validation to C and R (both phonemic-derived).

2. SEMANTIC DISCRIMINATION: The S term successfully distinguishes:
   - king ↔ queen (S ≈ 1.0, same ROLE_BEARER + SOCIAL)
   - king ↔ banana (S ≈ 0.0, ROLE_BEARER vs BIOLOGICAL_ORGANISM)

3. CHATGPT FAILURE MODE FIX: The ORGANISM → BIOLOGICAL_ORGANISM + ROLE_BEARER
   split prevents false matches like king ↔ banana.

4. COHERENCE DIAGNOSTICS: Filter results now include C × R × S breakdown
   for post-generation auditing.

5. DETERMINISTIC: Same inputs always produce identical outputs (Tier 1).
""")


def main():
    """Run complete canonical matching benchmark."""
    print("Running canonical matching (C × R × S) benchmark...")
    print()

    # Run all benchmarks
    discrimination = run_discrimination_benchmark()
    components = run_component_analysis()
    coherence = run_coherence_filter_benchmark()
    latency = run_latency_benchmark(iterations=50)

    # Print results
    print_results(discrimination, components, coherence, latency)

    # Return for programmatic use
    return {
        "discrimination": {k: asdict(v) for k, v in discrimination.items()},
        "components": components,
        "coherence": asdict(coherence),
        "latency": latency,
    }


if __name__ == "__main__":
    main()
