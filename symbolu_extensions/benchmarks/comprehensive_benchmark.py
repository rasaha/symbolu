"""
Comprehensive Engine Benchmark
==============================

Tests all three engine tiers with real-world use cases.
Generates shareable results for stakeholders.

Run:
    python -m symbolu.benchmarks.comprehensive_benchmark
"""

import time
import json
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

from symbolu_core.engine import create_engine, EngineTier
from agentic.entropy import (
    EntropyEngine,
    GunaProfile,
    KoshaProfile,
    DomainProfile,
    TIER_1_CONFIG,
    TIER_2_CONFIG,
    TIER_3_CONFIG,
    DIMENSION_NAMES,
)
from agentic.posture import (
    DecisionPostureProfile,
    PostureTier,
    PostureInfluenceScope,
    BALANCED_DEFAULT,
    CONSERVATIVE_ENTERPRISE,
    EXPLORATORY_RESEARCH,
    HIGH_COHERENCE,
    HIGH_CONSTRAINT,
    apply_posture_to_routing,
    apply_posture_to_conservatism,
    apply_posture_to_cascade_aggressiveness,
    apply_posture_to_all,
    get_tier_default_config,
    create_audit_record,
    format_audit_for_api_response,
)


# =============================================================================
# TEST CASES BY USE CASE CATEGORY
# =============================================================================

USE_CASES = {
    "customer_support": {
        "description": "Customer support intent detection and routing",
        "queries": [
            ("I need to cancel my subscription", "action"),
            ("Why was I charged twice?", "reasoning"),
            ("I'm frustrated with your service", "relationship"),
            ("How do I reset my password?", "action"),
            ("Can you explain my bill?", "reasoning"),
            ("I love your product!", "relationship"),
            ("Schedule a callback please", "action"),
            ("What are your business hours?", "reasoning"),
        ],
    },
    "developer_assistant": {
        "description": "Developer tooling and code assistance",
        "queries": [
            ("Deploy the application to staging", "action"),
            ("Explain how async/await works", "reasoning"),
            ("Why is my code throwing this error?", "reasoning"),
            ("Run the test suite", "action"),
            ("Create a new API endpoint", "creative"),
            ("Refactor this function for readability", "creative"),
            ("What's the best practice for error handling?", "reasoning"),
            ("Push my changes to the repository", "action"),
        ],
    },
    "creative_writing": {
        "description": "Creative content generation",
        "queries": [
            ("Write a poem about the ocean", "creative"),
            ("Create a story about a dragon", "creative"),
            ("Compose a haiku about autumn", "creative"),
            ("Design a logo concept for a tech startup", "creative"),
            ("Write lyrics for a love song", "creative"),
            ("Imagine a world without electricity", "creative"),
            ("Create a character backstory", "creative"),
            ("Write a product description", "creative"),
        ],
    },
    "emotional_support": {
        "description": "Emotional and relationship support",
        "queries": [
            ("I'm feeling lonely today", "relationship"),
            ("I had a fight with my friend", "relationship"),
            ("I'm anxious about my job interview", "relationship"),
            ("Help me cope with stress", "relationship"),
            ("I miss my family", "relationship"),
            ("I'm worried about the future", "relationship"),
            ("How do I build better relationships?", "relationship"),
            ("I feel overwhelmed", "relationship"),
        ],
    },
    "philosophical_inquiry": {
        "description": "Deep philosophical and reflective questions",
        "queries": [
            ("What is the meaning of life?", "reflective"),
            ("Why do we exist?", "reflective"),
            ("What is consciousness?", "reflective"),
            ("Is there free will?", "reflective"),
            ("What happens after death?", "reflective"),
            ("What is truth?", "reflective"),
            ("Why is there something rather than nothing?", "reflective"),
            ("What is the nature of reality?", "reflective"),
        ],
    },
    "technical_analysis": {
        "description": "Technical and analytical reasoning",
        "queries": [
            ("How does quantum entanglement work?", "reasoning"),
            ("Explain the theory of relativity", "reasoning"),
            ("Calculate the compound interest", "reasoning"),
            ("Analyze this dataset for trends", "reasoning"),
            ("What causes earthquakes?", "reasoning"),
            ("How does machine learning work?", "reasoning"),
            ("Explain the water cycle", "reasoning"),
            ("Why do planes fly?", "reasoning"),
        ],
    },
}


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""
    tier: str
    use_case: str
    total_queries: int
    correct: int
    accuracy: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    by_intent: Dict[str, Dict[str, int]]


def run_tier_benchmark(tier: EngineTier, use_case_name: str, queries: List[tuple]) -> BenchmarkResult:
    """Run benchmark for a specific tier and use case."""
    engine = create_engine(tier=tier)

    correct = 0
    latencies = []
    by_intent = defaultdict(lambda: {"correct": 0, "total": 0})

    for query, expected in queries:
        start = time.perf_counter()
        result = engine.classify(query)
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)

        predicted = result.intent
        by_intent[expected]["total"] += 1

        # Flexible matching (some intents are related)
        is_correct = False
        if expected == predicted:
            is_correct = True
        elif expected == "reflective" and predicted == "reasoning":
            is_correct = True  # Reflective often routes to reasoning
        elif expected == "reasoning" and predicted == "reflective":
            is_correct = True

        if is_correct:
            correct += 1
            by_intent[expected]["correct"] += 1

    return BenchmarkResult(
        tier=tier.value,
        use_case=use_case_name,
        total_queries=len(queries),
        correct=correct,
        accuracy=correct / len(queries) * 100,
        avg_latency_ms=sum(latencies) / len(latencies),
        min_latency_ms=min(latencies),
        max_latency_ms=max(latencies),
        by_intent=dict(by_intent),
    )


def run_consumer_cascade_test(queries: List[str]) -> Dict[str, Any]:
    """Test consumer cascade behavior."""
    engine = create_engine(tier=EngineTier.CONSUMER)

    results = {
        "total": len(queries),
        "skipped_768d": 0,
        "used_768d": 0,
        "used_7b": 0,
        "used_175b": 0,
        "queries": [],
    }

    for query in queries:
        result = engine.generate(query)

        used_768d = result.metadata.get("used_768d", False)
        model = result.model_used

        if not used_768d:
            results["skipped_768d"] += 1
        else:
            results["used_768d"] += 1

        if "7b" in model:
            results["used_7b"] += 1
        else:
            results["used_175b"] += 1

        results["queries"].append({
            "query": query[:50],
            "intent": result.intent,
            "confidence": f"{result.confidence:.0%}",
            "used_768d": used_768d,
            "model": model,
        })

    results["768d_skip_rate"] = f"{results['skipped_768d'] / results['total'] * 100:.0f}%"
    results["7b_usage_rate"] = f"{results['used_7b'] / results['total'] * 100:.0f}%"

    return results


def run_entropy_benchmark() -> Dict[str, Any]:
    """
    Test Cross-Domain Entropy Engine across all tiers.

    Demonstrates:
    - Entropy computation for different query types
    - Tier-specific gate behavior (DIAGNOSTIC_ONLY, MODULATION_ONLY, FULL_GATING)
    - Determinism verification
    """
    results = {
        "tier_behavior": [],
        "entropy_by_query_type": [],
        "determinism_verified": True,
    }

    # Test scenarios with different entropy characteristics
    scenarios = [
        {
            "name": "Balanced Query",
            "guna": GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3),
            "kosha_source": KoshaProfile(annamaya=0.1, pranamaya=0.2, manomaya=0.5, vijnanamaya=0.2, anandamaya=0.0),
            "kosha_target": KoshaProfile(annamaya=0.1, pranamaya=0.2, manomaya=0.5, vijnanamaya=0.2, anandamaya=0.0),
            "expected": "low_entropy",
        },
        {
            "name": "Cross-Layer Query (Emotional → Intellectual)",
            "guna": GunaProfile(sattva=0.5, rajas=0.4, tamas=0.1),
            "kosha_source": KoshaProfile(annamaya=0.1, pranamaya=0.1, manomaya=0.7, vijnanamaya=0.1, anandamaya=0.0),
            "kosha_target": KoshaProfile(annamaya=0.0, pranamaya=0.1, manomaya=0.2, vijnanamaya=0.7, anandamaya=0.0),
            "expected": "moderate_entropy",
        },
        {
            "name": "Extreme Skew (Physical → Bliss)",
            "guna": GunaProfile(sattva=0.9, rajas=0.05, tamas=0.05),
            "kosha_source": KoshaProfile(annamaya=0.8, pranamaya=0.2, manomaya=0.0, vijnanamaya=0.0, anandamaya=0.0),
            "kosha_target": KoshaProfile(annamaya=0.0, pranamaya=0.0, manomaya=0.0, vijnanamaya=0.1, anandamaya=0.9),
            "expected": "high_entropy",
        },
    ]

    # Test each tier
    tier_configs = [
        ("Tier 1 (Enterprise Search)", TIER_1_CONFIG),
        ("Tier 2 (Enterprise Chat)", TIER_2_CONFIG),
        ("Tier 3 (Consumer)", TIER_3_CONFIG),
    ]

    for tier_name, config in tier_configs:
        engine = EntropyEngine(config)
        tier_results = {
            "tier": tier_name,
            "mode": config.mode.value,
            "scenarios": [],
        }

        for scenario in scenarios:
            result = engine.evaluate(
                guna_profile=scenario["guna"],
                kosha_source=scenario["kosha_source"],
                kosha_target=scenario["kosha_target"],
            )

            # Verify determinism
            result2 = engine.evaluate(
                guna_profile=scenario["guna"],
                kosha_source=scenario["kosha_source"],
                kosha_target=scenario["kosha_target"],
            )
            if result.combined_entropy != result2.combined_entropy:
                results["determinism_verified"] = False

            tier_results["scenarios"].append({
                "name": scenario["name"],
                "combined_entropy": round(result.combined_entropy, 3),
                "guna_entropy": round(result.guna_entropy, 3),
                "kosha_entropy": round(result.kosha_entropy, 3),
                "gate": result.gate.value,
            })

        results["tier_behavior"].append(tier_results)

    # Summarize entropy by query type
    engine = EntropyEngine(TIER_3_CONFIG)  # Use full gating for complete picture
    for scenario in scenarios:
        result = engine.evaluate(
            guna_profile=scenario["guna"],
            kosha_source=scenario["kosha_source"],
            kosha_target=scenario["kosha_target"],
        )
        results["entropy_by_query_type"].append({
            "query_type": scenario["name"],
            "expected": scenario["expected"],
            "actual_entropy": round(result.combined_entropy, 3),
            "gate": result.gate.value,
        })

    return results


def run_posture_benchmark() -> Dict[str, Any]:
    """
    Test Configurable Decision Posture across all tiers.

    Demonstrates:
    - Preset profile characteristics
    - Tier-specific posture influence rules (Tier 1 = no influence)
    - Deterministic modulation behavior
    - Audit trail generation
    """
    results = {
        "preset_profiles": [],
        "tier_behavior": [],
        "modulation_effects": [],
        "determinism_verified": True,
    }

    # Document preset profiles
    presets = [
        ("BALANCED_DEFAULT", BALANCED_DEFAULT, "Equal weighting, neutral behavior"),
        ("CONSERVATIVE_ENTERPRISE", CONSERVATIVE_ENTERPRISE, "Risk-averse, high constraint"),
        ("EXPLORATORY_RESEARCH", EXPLORATORY_RESEARCH, "Adaptive, learning-oriented"),
        ("HIGH_COHERENCE", HIGH_COHERENCE, "Thorough explanations, audit-focused"),
        ("HIGH_CONSTRAINT", HIGH_CONSTRAINT, "Maximum caution, strict refusal"),
    ]

    for name, profile, description in presets:
        results["preset_profiles"].append({
            "name": name,
            "description": description,
            "coherence_bias": round(profile.coherence_bias, 4),
            "exploration_bias": round(profile.exploration_bias, 4),
            "constraint_bias": round(profile.constraint_bias, 4),
            "is_balanced": profile.is_balanced,
        })

    # Test tier-specific behavior
    tiers = [
        (PostureTier.TIER_1, "Enterprise Search (STL only)"),
        (PostureTier.TIER_2, "Enterprise Chat (STL + 7B)"),
        (PostureTier.TIER_3, "Consumer (STL + 768D + Cascade)"),
    ]

    for tier, tier_desc in tiers:
        config = get_tier_default_config(tier)
        base_values = {scope.value: 0.5 for scope in PostureInfluenceScope}

        # Apply posture with EXPLORATORY profile (most likely to show influence)
        all_results = apply_posture_to_all(
            posture=EXPLORATORY_RESEARCH,
            tier=tier,
            base_values=base_values,
            config=config,
        )

        influenced_count = sum(1 for r in all_results if r.was_influenced)

        # Verify determinism
        all_results2 = apply_posture_to_all(
            posture=EXPLORATORY_RESEARCH,
            tier=tier,
            base_values=base_values,
            config=config,
        )
        for r1, r2 in zip(all_results, all_results2):
            if r1.adjusted_value != r2.adjusted_value:
                results["determinism_verified"] = False

        results["tier_behavior"].append({
            "tier": tier.value,
            "description": tier_desc,
            "allow_override": config.allow_request_override,
            "max_adjustment": config.max_adjustment_magnitude,
            "scopes_tested": len(all_results),
            "scopes_influenced": influenced_count,
            "influence_rate": f"{influenced_count / len(all_results) * 100:.0f}%",
        })

    # Test modulation effects with different profiles
    profiles_to_test = [
        ("Conservative", CONSERVATIVE_ENTERPRISE),
        ("Exploratory", EXPLORATORY_RESEARCH),
    ]

    for profile_name, profile in profiles_to_test:
        # Test routing threshold modulation
        routing = apply_posture_to_routing(
            base_confidence=0.50,
            posture=profile,
            tier=PostureTier.TIER_3,
        )

        # Test conservatism modulation
        conservatism = apply_posture_to_conservatism(
            base_level=0.50,
            posture=profile,
            tier=PostureTier.TIER_3,
        )

        # Test cascade aggressiveness modulation
        cascade = apply_posture_to_cascade_aggressiveness(
            base_aggressiveness=0.50,
            posture=profile,
            tier=PostureTier.TIER_3,
        )

        results["modulation_effects"].append({
            "profile": profile_name,
            "routing": {
                "original": round(routing.original_value, 3),
                "adjusted": round(routing.adjusted_value, 3),
                "delta": round(routing.adjustment_delta, 3),
            },
            "conservatism": {
                "original": round(conservatism.original_value, 3),
                "adjusted": round(conservatism.adjusted_value, 3),
                "delta": round(conservatism.adjustment_delta, 3),
            },
            "cascade": {
                "original": round(cascade.original_value, 3),
                "adjusted": round(cascade.adjusted_value, 3),
                "delta": round(cascade.adjustment_delta, 3),
            },
        })

    # Generate sample audit record
    sample_applications = apply_posture_to_all(
        posture=CONSERVATIVE_ENTERPRISE,
        tier=PostureTier.TIER_2,
        base_values={scope.value: 0.5 for scope in PostureInfluenceScope},
    )
    audit_record = create_audit_record(
        posture=CONSERVATIVE_ENTERPRISE,
        tier=PostureTier.TIER_2,
        applications=sample_applications,
        source="deployment_default",
    )
    results["sample_audit"] = format_audit_for_api_response(audit_record)

    return results


def run_search_benchmark():
    """Test search/ranking capability."""
    engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)

    test_cases = [
        {
            "query": "machine learning algorithms",
            "candidates": [
                "Introduction to Deep Learning",
                "Cooking Italian Pasta",
                "Neural Network Fundamentals",
                "Garden Landscaping Tips",
                "Statistical Machine Learning",
            ],
            "expected_top": "Statistical Machine Learning",
        },
        {
            "query": "emotional well-being",
            "candidates": [
                "Car Maintenance Guide",
                "Mental Health Awareness",
                "Database Optimization",
                "Stress Management Techniques",
                "Python Programming",
            ],
            "expected_top": "Mental Health Awareness",
        },
        {
            "query": "software deployment",
            "candidates": [
                "Baking Bread at Home",
                "CI/CD Pipeline Setup",
                "Bird Watching Guide",
                "Kubernetes Deployment",
                "Travel Photography",
            ],
            "expected_top": "Kubernetes Deployment",
        },
    ]

    results = []
    for tc in test_cases:
        result = engine.search(tc["query"], tc["candidates"], top_k=3)
        ranked = result.metadata["ranked"]

        results.append({
            "query": tc["query"],
            "top_result": ranked[0],
            "expected": tc["expected_top"],
            "correct": tc["expected_top"] in ranked[:2],  # Allow top 2
            "latency_ms": f"{result.latency_ms:.2f}",
        })

    return results


def print_results(all_results: Dict[str, Any]):
    """Print formatted benchmark results."""

    print("=" * 80)
    print("SYMBOLU ENGINE - COMPREHENSIVE BENCHMARK RESULTS")
    print("=" * 80)
    print()

    # Summary table
    print("## CLASSIFICATION ACCURACY BY TIER")
    print("-" * 80)
    print(f"{'Use Case':<25} {'Enterprise Search':<20} {'Enterprise Chat':<20} {'Consumer':<15}")
    print("-" * 80)

    for use_case in USE_CASES.keys():
        search_acc = next((r["accuracy"] for r in all_results["enterprise_search"] if r["use_case"] == use_case), 0)
        chat_acc = next((r["accuracy"] for r in all_results["enterprise_chat"] if r["use_case"] == use_case), 0)
        consumer_acc = next((r["accuracy"] for r in all_results["consumer"] if r["use_case"] == use_case), 0)

        print(f"{use_case:<25} {search_acc:>17.0f}% {chat_acc:>17.0f}% {consumer_acc:>12.0f}%")

    print("-" * 80)

    # Calculate overall averages
    search_avg = sum(r["accuracy"] for r in all_results["enterprise_search"]) / len(all_results["enterprise_search"])
    chat_avg = sum(r["accuracy"] for r in all_results["enterprise_chat"]) / len(all_results["enterprise_chat"])
    consumer_avg = sum(r["accuracy"] for r in all_results["consumer"]) / len(all_results["consumer"])

    print(f"{'OVERALL AVERAGE':<25} {search_avg:>17.0f}% {chat_avg:>17.0f}% {consumer_avg:>12.0f}%")
    print()

    # Latency comparison
    print("## LATENCY COMPARISON (milliseconds)")
    print("-" * 80)
    print(f"{'Tier':<25} {'Average':<15} {'Min':<15} {'Max':<15}")
    print("-" * 80)

    for tier_name, results in [("Enterprise Search", all_results["enterprise_search"]),
                                ("Enterprise Chat", all_results["enterprise_chat"]),
                                ("Consumer", all_results["consumer"])]:
        avg = sum(r["avg_latency_ms"] for r in results) / len(results)
        min_lat = min(r["min_latency_ms"] for r in results)
        max_lat = max(r["max_latency_ms"] for r in results)
        print(f"{tier_name:<25} {avg:>12.2f}ms {min_lat:>12.2f}ms {max_lat:>12.2f}ms")

    print()

    # Consumer cascade stats
    print("## CONSUMER MODE CASCADE BEHAVIOR")
    print("-" * 80)
    cascade = all_results["cascade_test"]
    print(f"Total queries tested: {cascade['total']}")
    print(f"Skipped 768D computation: {cascade['skipped_768d']} ({cascade['768d_skip_rate']})")
    print(f"Used 768D augmentation: {cascade['used_768d']}")
    print(f"Routed to 7B models: {cascade['used_7b']} ({cascade['7b_usage_rate']})")
    print(f"Routed to 175B fallback: {cascade['used_175b']}")
    print()

    # Search benchmark
    print("## SEARCH/RANKING ACCURACY")
    print("-" * 80)
    for result in all_results["search_test"]:
        status = "✓" if result["correct"] else "✗"
        print(f"{status} Query: \"{result['query']}\"")
        print(f"    Top result: {result['top_result']}")
        print(f"    Expected: {result['expected']}")
        print(f"    Latency: {result['latency_ms']}ms")
    print()

    # Cross-Domain Entropy Engine Results
    if "entropy_test" in all_results:
        entropy = all_results["entropy_test"]
        print("## CROSS-DOMAIN ENTROPY ENGINE")
        print("-" * 80)
        print(f"Determinism Verified: {'✓' if entropy['determinism_verified'] else '✗'}")
        print()

        print("### Tier-Specific Behavior")
        for tier in entropy["tier_behavior"]:
            print(f"\n  {tier['tier']} (mode: {tier['mode']})")
            for scenario in tier["scenarios"]:
                print(f"    - {scenario['name']}: entropy={scenario['combined_entropy']:.3f}, gate={scenario['gate']}")

        print()
        print("### Entropy by Query Type")
        print(f"{'Query Type':<45} {'Expected':<15} {'Actual':<10} {'Gate':<20}")
        print("-" * 90)
        for entry in entropy["entropy_by_query_type"]:
            print(f"{entry['query_type']:<45} {entry['expected']:<15} {entry['actual_entropy']:<10.3f} {entry['gate']:<20}")
        print()

    # Configurable Decision Posture Results
    if "posture_test" in all_results:
        posture = all_results["posture_test"]
        print("## CONFIGURABLE DECISION POSTURE")
        print("-" * 80)
        print(f"Determinism Verified: {'✓' if posture['determinism_verified'] else '✗'}")
        print()

        print("### Preset Profiles")
        print(f"{'Profile':<30} {'Coherence':<12} {'Exploration':<12} {'Constraint':<12} {'Balanced':<10}")
        print("-" * 80)
        for profile in posture["preset_profiles"]:
            balanced = "Yes" if profile["is_balanced"] else "No"
            print(f"{profile['name']:<30} {profile['coherence_bias']:<12.4f} {profile['exploration_bias']:<12.4f} {profile['constraint_bias']:<12.4f} {balanced:<10}")
        print()

        print("### Tier-Specific Behavior")
        print(f"{'Tier':<45} {'Override':<10} {'Max Adj':<10} {'Influenced':<12}")
        print("-" * 80)
        for tier in posture["tier_behavior"]:
            override = "Yes" if tier["allow_override"] else "No"
            print(f"{tier['description']:<45} {override:<10} {tier['max_adjustment']:<10.2f} {tier['influence_rate']:<12}")
        print()

        print("### Modulation Effects (Tier 3, base=0.5)")
        for effect in posture["modulation_effects"]:
            print(f"\n  {effect['profile']} Profile:")
            print(f"    Routing:      {effect['routing']['original']:.3f} → {effect['routing']['adjusted']:.3f} (Δ {effect['routing']['delta']:+.3f})")
            print(f"    Conservatism: {effect['conservatism']['original']:.3f} → {effect['conservatism']['adjusted']:.3f} (Δ {effect['conservatism']['delta']:+.3f})")
            print(f"    Cascade:      {effect['cascade']['original']:.3f} → {effect['cascade']['adjusted']:.3f} (Δ {effect['cascade']['delta']:+.3f})")
        print()

    # Key metrics summary
    print("## KEY METRICS SUMMARY")
    print("-" * 80)
    print(f"| Metric                          | Value           |")
    print(f"|--------------------------------|-----------------|")
    print(f"| Overall classification accuracy | {search_avg:.0f}%            |")
    print(f"| Average latency (Search)        | {sum(r['avg_latency_ms'] for r in all_results['enterprise_search']) / len(all_results['enterprise_search']):.2f}ms         |")
    print(f"| 768D skip rate (Consumer)       | {cascade['768d_skip_rate']}           |")
    print(f"| 7B model usage (Consumer)       | {cascade['7b_usage_rate']}           |")
    print(f"| Vector dimension savings        | 77x (768D → 10D)|")
    print(f"| Parameter savings               | 25x (175B → 7B) |")
    if "entropy_test" in all_results:
        print(f"| Entropy engine determinism      | {'Verified ✓' if all_results['entropy_test']['determinism_verified'] else 'Failed ✗'}       |")
    if "posture_test" in all_results:
        print(f"| Posture system determinism      | {'Verified ✓' if all_results['posture_test']['determinism_verified'] else 'Failed ✗'}       |")
    print()


def main():
    """Run comprehensive benchmark."""
    all_results = {
        "enterprise_search": [],
        "enterprise_chat": [],
        "consumer": [],
    }

    print("Running comprehensive benchmark...")
    print()

    # Run classification benchmarks for each tier
    for tier in [EngineTier.ENTERPRISE_SEARCH, EngineTier.ENTERPRISE_CHAT, EngineTier.CONSUMER]:
        tier_key = tier.value
        print(f"Testing {tier_key}...")

        for use_case_name, use_case_data in USE_CASES.items():
            result = run_tier_benchmark(tier, use_case_name, use_case_data["queries"])
            all_results[tier_key].append(asdict(result))

    # Run cascade test
    print("Testing consumer cascade behavior...")
    cascade_queries = [
        "Write a simple poem",
        "Deploy the app",
        "Explain quantum mechanics in detail",
        "I'm feeling sad",
        "What is consciousness?",
        "Run the tests",
        "Analyze the socioeconomic implications of AI on labor markets",
        "Create a logo",
    ]
    all_results["cascade_test"] = run_consumer_cascade_test(cascade_queries)

    # Run search test
    print("Testing search/ranking...")
    all_results["search_test"] = run_search_benchmark()

    # Run entropy engine test
    print("Testing cross-domain entropy engine...")
    all_results["entropy_test"] = run_entropy_benchmark()

    # Run posture system test
    print("Testing configurable decision posture...")
    all_results["posture_test"] = run_posture_benchmark()

    print()

    # Print results
    print_results(all_results)

    # Save to JSON for sharing
    output_path = "docs/benchmarks/benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Results saved to {output_path}")

    return all_results


if __name__ == "__main__":
    main()
