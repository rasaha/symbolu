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
import math


@dataclass
class EncoderBenchmarkResult:
    """Results from benchmarking an encoder."""
    encoder_name: str
    domain_accuracy: float
    reasoning_creativity_separation: float
    avg_latency_ms: float
    semantic_coherence: float
    samples_tested: int
    details: Dict[str, Any] = field(default_factory=dict)


def get_test_samples() -> Dict[str, List[str]]:
    """Get test samples for each domain."""
    return {
        "technical": [
            "Implement a binary search tree with O(log n) insertion",
            "Debug the null pointer exception in the authentication module",
            "Optimize the database query using index-based lookup",
            "Refactor the API endpoint to use async/await pattern",
            "Write unit tests for the payment processing service",
        ],
        "reasoning": [
            "If all mammals are warm-blooded, and whales are mammals, then whales must be warm-blooded",
            "The argument fails because it assumes correlation implies causation",
            "Given premises A and B, we can deduce conclusion C through modus ponens",
            "The logical fallacy here is a false dichotomy - there are more than two options",
            "Let us analyze the validity of this syllogism step by step",
        ],
        "creative": [
            "The sunset painted the sky in hues of amber and rose",
            "Imagine a world where gravity works in reverse",
            "Her laughter was a symphony of joy and mischief",
            "Write a poem about the loneliness of a lighthouse keeper",
            "Design a character who can taste colors and see sounds",
        ],
        "action": [
            "Run the deployment script and verify the health check",
            "Click the submit button and wait for confirmation",
            "Execute the migration and rollback if errors occur",
            "Build the container image and push to registry",
            "Start the server and monitor the logs",
        ],
        "governance": [
            "Establish data retention policies compliant with GDPR",
            "Define access control rules for the admin dashboard",
            "Create guidelines for ethical AI usage in hiring",
            "Set up approval workflow for production deployments",
            "Document the incident response procedure",
        ],
    }


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0
    return dot / (norm1 * norm2)


def benchmark_encoder(encoder_type: str = "hash") -> EncoderBenchmarkResult:
    """
    Benchmark a specific encoder type.

    Args:
        encoder_type: "hash" or "minilm"

    Returns:
        EncoderBenchmarkResult with metrics
    """
    from symbolu.ontological.encoder import HashEncoder, SentenceTransformerEncoder

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
            raise ValueError(f"Unknown encoder type: {encoder_type}")
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

    test_samples = get_test_samples()
    latencies = []
    embeddings_by_domain: Dict[str, List[List[float]]] = defaultdict(list)

    print("\nEncoding samples...")

    # Encode all samples and measure latency
    for domain, samples in test_samples.items():
        for text in samples:
            start = time.perf_counter()
            embedding = encoder.encode(text)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)
            embeddings_by_domain[domain].append(embedding)

    # Calculate domain classification accuracy using centroid-based classification
    print("\nCalculating domain classification accuracy...")

    # Compute centroid for each domain
    centroids = {}
    for domain, embeddings in embeddings_by_domain.items():
        centroid = [sum(e[i] for e in embeddings) / len(embeddings) for i in range(len(embeddings[0]))]
        centroids[domain] = centroid

    # Classify each sample by nearest centroid (leave-one-out)
    correct = 0
    total = 0
    domain_accuracies = {}

    for true_domain, embeddings in embeddings_by_domain.items():
        domain_correct = 0
        for i, emb in enumerate(embeddings):
            # Find nearest centroid (excluding this sample from its own centroid)
            best_domain = None
            best_sim = -1
            for domain, centroid in centroids.items():
                # Adjust centroid if same domain (leave-one-out)
                if domain == true_domain and len(embeddings) > 1:
                    adjusted = [(c * len(embeddings) - emb[j]) / (len(embeddings) - 1)
                               for j, c in enumerate(centroid)]
                    sim = cosine_similarity(emb, adjusted)
                else:
                    sim = cosine_similarity(emb, centroid)

                if sim > best_sim:
                    best_sim = sim
                    best_domain = domain

            if best_domain == true_domain:
                domain_correct += 1
                correct += 1
            total += 1

        domain_accuracies[true_domain] = domain_correct / len(embeddings)

    overall_accuracy = correct / total if total > 0 else 0

    print(f"\nDomain Accuracies (centroid-based classification):")
    for domain, acc in domain_accuracies.items():
        status = "+" if acc >= 0.5 else "-"
        print(f"  [{status}] {domain}: {acc:.0%}")
    print(f"  Overall: {overall_accuracy:.0%}")

    # Calculate reasoning vs creativity separation
    print("\nCalculating reasoning/creativity separation...")

    reasoning_embs = embeddings_by_domain["reasoning"]
    creative_embs = embeddings_by_domain["creative"]

    # Measure how well-separated the two domains are
    # (intra-domain similarity should be higher than inter-domain similarity)

    # Intra-domain similarity
    reasoning_intra = []
    for i, e1 in enumerate(reasoning_embs):
        for j, e2 in enumerate(reasoning_embs):
            if i < j:
                reasoning_intra.append(cosine_similarity(e1, e2))

    creative_intra = []
    for i, e1 in enumerate(creative_embs):
        for j, e2 in enumerate(creative_embs):
            if i < j:
                creative_intra.append(cosine_similarity(e1, e2))

    # Inter-domain similarity
    inter_domain = []
    for e1 in reasoning_embs:
        for e2 in creative_embs:
            inter_domain.append(cosine_similarity(e1, e2))

    avg_reasoning_intra = sum(reasoning_intra) / len(reasoning_intra) if reasoning_intra else 0
    avg_creative_intra = sum(creative_intra) / len(creative_intra) if creative_intra else 0
    avg_inter = sum(inter_domain) / len(inter_domain) if inter_domain else 0

    # Separation score: how much higher is intra-domain similarity than inter-domain?
    intra_avg = (avg_reasoning_intra + avg_creative_intra) / 2
    separation_score = max(0, min(1, (intra_avg - avg_inter + 0.5)))  # Normalize to [0, 1]

    print(f"  Reasoning intra-similarity: {avg_reasoning_intra:.3f}")
    print(f"  Creative intra-similarity: {avg_creative_intra:.3f}")
    print(f"  Inter-domain similarity: {avg_inter:.3f}")
    print(f"  Separation score: {separation_score:.0%}")

    # Calculate semantic coherence (similar texts should have similar embeddings)
    coherence = calculate_semantic_coherence(embeddings_by_domain)
    print(f"\nSemantic Coherence: {coherence:.2f}")

    # Latency
    avg_latency = sum(latencies) / len(latencies)
    print(f"Average Latency: {avg_latency:.2f}ms")

    return EncoderBenchmarkResult(
        encoder_name=encoder.name,
        domain_accuracy=overall_accuracy,
        reasoning_creativity_separation=separation_score,
        avg_latency_ms=avg_latency,
        semantic_coherence=coherence,
        samples_tested=total,
        details={
            "domain_accuracies": domain_accuracies,
            "intra_similarity": intra_avg,
            "inter_similarity": avg_inter,
        },
    )


def calculate_semantic_coherence(embeddings_by_domain: Dict[str, List[List[float]]]) -> float:
    """
    Calculate semantic coherence score.

    Higher score means samples within the same domain are more similar to each other
    than to samples from other domains.
    """
    total_intra = 0
    total_inter = 0
    intra_count = 0
    inter_count = 0

    domains = list(embeddings_by_domain.keys())

    for i, d1 in enumerate(domains):
        embs1 = embeddings_by_domain[d1]

        # Intra-domain similarity
        for j, e1 in enumerate(embs1):
            for k, e2 in enumerate(embs1):
                if j < k:
                    total_intra += cosine_similarity(e1, e2)
                    intra_count += 1

        # Inter-domain similarity
        for d2 in domains[i+1:]:
            embs2 = embeddings_by_domain[d2]
            for e1 in embs1:
                for e2 in embs2:
                    total_inter += cosine_similarity(e1, e2)
                    inter_count += 1

    avg_intra = total_intra / intra_count if intra_count > 0 else 0
    avg_inter = total_inter / inter_count if inter_count > 0 else 0

    # Coherence: ratio of intra to inter similarity (capped at 2.0)
    if avg_inter > 0:
        coherence = min(2.0, avg_intra / avg_inter)
    else:
        coherence = 1.0

    return coherence


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
        improvement_pct = (mini_r.domain_accuracy - hash_r.domain_accuracy) / max(0.01, hash_r.domain_accuracy) * 100
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
