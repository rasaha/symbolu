#!/usr/bin/env python3
"""
Ontological Engine - Encoder Comparison Benchmark
==================================================

Compares hash encoder vs MiniLM encoder on the ontological engine.

Tests:
1. Domain classification accuracy
2. Reasoning vs Creativity separation
3. Latency comparison
4. Semantic coherence

Expected results:
- Hash encoder: ~20% domain accuracy (deterministic but not semantic)
- MiniLM (384D): ~75%+ domain accuracy (semantic understanding, 2.5x faster)

Run with:
    python -m symbolu.ontological.benchmark_comparison
"""

import time
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

# Check for PyTorch
try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not available. Some benchmarks will be skipped.")


@dataclass
class EncoderBenchmarkResult:
    """Results from encoder comparison."""
    encoder_name: str
    domain_accuracy: float
    reasoning_creativity_separation: float
    avg_latency_ms: float
    semantic_coherence: float
    samples_tested: int
    details: Dict[str, Any] = field(default_factory=dict)


def get_test_samples() -> Dict[str, List[str]]:
    """Get test samples for benchmarking."""
    return {
        "technical": [
            "The API endpoint accepts JSON payloads with authentication headers.",
            "Deploy the containerized application using Kubernetes orchestration.",
            "The algorithm has O(n log n) time complexity for sorting operations.",
            "Configure the database connection pool with maximum 50 connections.",
            "Implement the REST API with proper error handling and validation.",
        ],
        "reasoning": [
            "If the hypothesis is true, then the conclusion follows logically.",
            "Given the axioms, we can derive the theorem through induction.",
            "The evidence supports the claim because of causal correlation.",
            "By analyzing the data patterns, we deduce the underlying structure.",
            "The logical proof demonstrates the theorem holds for all cases.",
        ],
        "creative": [
            "Colors dance like whispered dreams across the velvet sky.",
            "The melody weaves emotions into tapestries of sound.",
            "Imagine a world where thoughts become visible butterflies.",
            "Poetry breathes life into the silence between words.",
            "Stars whisper secrets to the dreaming moon above.",
        ],
        "action": [
            "First, run the tests. Then deploy to staging. Finally, verify.",
            "Execute the migration script before the maintenance window.",
            "Initialize the system, configure parameters, then start services.",
            "Build the project, run linting, and push to the repository.",
            "Download the file, extract contents, and process each item.",
        ],
        "governance": [
            "AI systems must be fair, accountable, and transparent.",
            "Ethical guidelines require regular bias audits and monitoring.",
            "The responsible AI framework establishes compliance requirements.",
            "Privacy by design ensures data minimization and purpose limitation.",
            "Governance policies mandate quarterly security assessments.",
        ],
    }


def benchmark_encoder(encoder_type: str = "hash") -> EncoderBenchmarkResult:
    """
    Benchmark a specific encoder type.

    Args:
        encoder_type: "hash" or "minilm"

    Returns:
        EncoderBenchmarkResult with metrics
    """
    from symbolu.ontological.encoder import get_encoder, HashEncoder, SentenceTransformerEncoder
    from symbolu.ontological.engine import create_engine

    print(f"\n{'='*60}")
    print(f"BENCHMARKING: {encoder_type.upper()} Encoder")
    print("=" * 60)

    # Get encoder
    try:
        if encoder_type == "hash":
            encoder = HashEncoder(dimension=384)
        elif encoder_type == "minilm":
            encoder = SentenceTransformerEncoder()
            encoder._load_model()  # Force load
        else:
            encoder = get_encoder(encoder_type)
    except Exception as e:
        print(f"Failed to load {encoder_type} encoder: {e}")
        return EncoderBenchmarkResult(
            encoder_name=encoder_type,
            domain_accuracy=0,
            reasoning_creativity_separation=0,
            avg_latency_ms=0,
            semantic_coherence=0,
            samples_tested=0,
            details={"error": str(e)},
        )

    print(f"Encoder loaded: {encoder.name} ({encoder.dimension}D)")

    # Create engine with this encoder
    engine = create_engine()
    engine._encoder = encoder

    test_samples = get_test_samples()
    results = defaultdict(list)
    latencies = []

    # Expected dominant layers for each domain
    expected_layers = {
        "technical": "O7_REASONING",
        "reasoning": "O7_REASONING",
        "creative": "O4_STRUCTURE",
        "action": "O3_EXECUTION",
        "governance": "O8_PURPOSE",
    }

    print("\nAnalyzing samples...")

    for domain, samples in test_samples.items():
        for text in samples:
            start = time.perf_counter()
            vec = engine.analyze(text)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

            dominant, score = vec.dominant_layer()
            results[domain].append({
                "dominant": dominant,
                "score": score,
                "expected": expected_layers.get(domain),
            })

    # Calculate domain accuracy
    correct = 0
    total = 0
    domain_accuracies = {}

    for domain, items in results.items():
        expected = expected_layers.get(domain)
        if expected:
            matches = sum(1 for item in items if item["dominant"] == expected)
            domain_accuracies[domain] = matches / len(items)
            correct += matches
            total += len(items)

    overall_accuracy = correct / total if total > 0 else 0

    print(f"\nDomain Accuracies:")
    for domain, acc in domain_accuracies.items():
        status = "+" if acc >= 0.5 else "-"
        print(f"  [{status}] {domain}: {acc:.0%}")

    # Calculate reasoning vs creativity separation
    reasoning_o6 = []
    creativity_o2 = []

    for domain, samples in test_samples.items():
        for text in samples:
            vec = engine.analyze(text)
            values = list(vec.values)

            if domain == "reasoning":
                reasoning_o6.append(values[5])  # O6
            elif domain == "creative":
                creativity_o2.append(values[1])  # O2

    # Separation: do reasoning samples have higher O6 than O2?
    # And do creative samples have higher O2 than O6?
    reasoning_separation = 0
    creativity_separation = 0

    for domain, samples in test_samples.items():
        for text in samples:
            vec = engine.analyze(text)
            values = list(vec.values)
            o6, o2 = values[5], values[1]

            if domain == "reasoning" and o6 > o2:
                reasoning_separation += 1
            elif domain == "creative" and o2 > o6:
                creativity_separation += 1

    total_separation_tests = len(test_samples["reasoning"]) + len(test_samples["creative"])
    separation_accuracy = (reasoning_separation + creativity_separation) / total_separation_tests

    print(f"\nReasoning/Creativity Separation: {separation_accuracy:.0%}")
    print(f"  Reasoning (O6 > O2): {reasoning_separation}/{len(test_samples['reasoning'])}")
    print(f"  Creative (O2 > O6): {creativity_separation}/{len(test_samples['creative'])}")

    # Calculate semantic coherence (similar texts should have similar embeddings)
    coherence = calculate_semantic_coherence(encoder, test_samples)
    print(f"\nSemantic Coherence: {coherence:.2f}")

    # Latency
    avg_latency = sum(latencies) / len(latencies)
    print(f"\nAverage Latency: {avg_latency:.2f}ms")

    return EncoderBenchmarkResult(
        encoder_name=encoder.name,
        domain_accuracy=overall_accuracy,
        reasoning_creativity_separation=separation_accuracy,
        avg_latency_ms=avg_latency,
        semantic_coherence=coherence,
        samples_tested=total,
        details={
            "domain_accuracies": domain_accuracies,
            "reasoning_separation": reasoning_separation,
            "creativity_separation": creativity_separation,
        },
    )


def calculate_semantic_coherence(encoder, test_samples: Dict[str, List[str]]) -> float:
    """
    Calculate semantic coherence score.

    Measures whether same-domain samples cluster together in embedding space.
    Higher score = better semantic understanding.
    """
    import math

    domain_embeddings = {}
    for domain, samples in test_samples.items():
        embeddings = encoder.encode_batch(samples)
        domain_embeddings[domain] = embeddings

    # Calculate average intra-domain vs inter-domain distances
    intra_distances = []
    inter_distances = []

    for domain, embeddings in domain_embeddings.items():
        # Intra-domain: distances within same domain
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                dist = euclidean_distance(embeddings[i], embeddings[j])
                intra_distances.append(dist)

        # Inter-domain: distances to other domains
        for other_domain, other_embeddings in domain_embeddings.items():
            if domain != other_domain:
                for emb1 in embeddings:
                    for emb2 in other_embeddings:
                        dist = euclidean_distance(emb1, emb2)
                        inter_distances.append(dist)

    avg_intra = sum(intra_distances) / len(intra_distances) if intra_distances else 1
    avg_inter = sum(inter_distances) / len(inter_distances) if inter_distances else 1

    # Coherence = ratio of inter to intra distance
    # Higher = better (more separation between domains, tighter within domains)
    coherence = avg_inter / (avg_intra + 1e-10)

    return coherence


def euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    import math
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def run_comparison():
    """Run full comparison between hash and MiniLM encoders."""
    print("\n" + "=" * 60)
    print("   ONTOLOGICAL ENGINE - ENCODER COMPARISON")
    print("=" * 60)
    print("\nComparing hash encoder (baseline) vs MiniLM (384D semantic)")

    results = {}

    # Benchmark hash encoder
    results["hash"] = benchmark_encoder("hash")

    # Benchmark MiniLM encoder
    try:
        results["minilm"] = benchmark_encoder("minilm")
    except Exception as e:
        print(f"\nMiniLM benchmark failed: {e}")
        results["minilm"] = EncoderBenchmarkResult(
            encoder_name="minilm",
            domain_accuracy=0,
            reasoning_creativity_separation=0,
            avg_latency_ms=0,
            semantic_coherence=0,
            samples_tested=0,
            details={"error": str(e)},
        )

    # Print comparison
    print("\n" + "=" * 60)
    print("   COMPARISON SUMMARY")
    print("=" * 60)

    print("\n{:<30} {:>15} {:>15}".format("Metric", "Hash", "MiniLM"))
    print("-" * 60)

    hash_r = results["hash"]
    mini_r = results["minilm"]

    def improvement(h, b):
        if h == 0:
            return "N/A"
        delta = (b - h) / h * 100
        return f"{delta:+.0f}%"

    print("{:<30} {:>14.0%} {:>14.0%} ({})".format(
        "Domain Classification",
        hash_r.domain_accuracy,
        mini_r.domain_accuracy,
        improvement(hash_r.domain_accuracy, mini_r.domain_accuracy),
    ))

    print("{:<30} {:>14.0%} {:>14.0%} ({})".format(
        "Reasoning/Creativity Sep.",
        hash_r.reasoning_creativity_separation,
        mini_r.reasoning_creativity_separation,
        improvement(hash_r.reasoning_creativity_separation, mini_r.reasoning_creativity_separation),
    ))

    print("{:<30} {:>14.2f} {:>14.2f} ({})".format(
        "Semantic Coherence",
        hash_r.semantic_coherence,
        mini_r.semantic_coherence,
        improvement(hash_r.semantic_coherence, mini_r.semantic_coherence),
    ))

    print("{:<30} {:>13.2f}ms {:>13.2f}ms".format(
        "Avg Latency",
        hash_r.avg_latency_ms,
        mini_r.avg_latency_ms,
    ))

    print("\n" + "=" * 60)
    print("KEY INSIGHTS")
    print("=" * 60)

    if mini_r.domain_accuracy > hash_r.domain_accuracy:
        improvement_pct = (mini_r.domain_accuracy - hash_r.domain_accuracy) / hash_r.domain_accuracy * 100 if hash_r.domain_accuracy > 0 else 100
        print(f"\n+ MiniLM improves domain accuracy by {improvement_pct:.0f}%")
    else:
        print("\n- MiniLM did not improve domain accuracy (may need training)")

    if mini_r.reasoning_creativity_separation > hash_r.reasoning_creativity_separation:
        print("+ Better reasoning vs creativity separation with semantic encoder")
    else:
        print("- Reasoning/creativity separation similar (contrastive training needed)")

    if mini_r.semantic_coherence > hash_r.semantic_coherence:
        print("+ Higher semantic coherence confirms better domain clustering")

    print("\nNEXT STEPS:")
    print("  1. Train with contrastive loss to improve reasoning/creativity separation")
    print("  2. Use larger datasets (GSM8K, ROCStories) for domain specialization")
    print("  3. Fine-tune MiniLM on domain-specific data")

    return results


if __name__ == "__main__":
    run_comparison()
