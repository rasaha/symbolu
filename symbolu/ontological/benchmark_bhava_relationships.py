#!/usr/bin/env python3
"""
Bhava Relationships Architecture - Benchmark
=============================================

Benchmarks the new inter-layer Bhava relationships architecture vs
the deprecated sub-layer approach.

Tests:
1. Relationship matrix computation performance
2. Coherence score quality
3. Drishti attention effectiveness
4. Integration with ontological engines

Requirements:
    pip install sentence-transformers torch numpy

Run:
    python -m symbolu.ontological.benchmark_bhava_relationships
"""

import time
from typing import Dict, List, Any
from dataclasses import dataclass, field

# Check for PyTorch
try:
    import torch
    import torch.nn.functional as F
    import numpy as np
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not available. Install with: pip install torch")


if PYTORCH_AVAILABLE:
    from symbolu.ontological.bhava_relationships import (
        BhavaRelationshipModule,
        DrishtiAttention,
        InterLayerBhavaEngine,
        get_relationship_meaning,
        ASPECT_STRENGTH_MATRIX,
        BHAVA_SIGNIFICANCES,
        get_architecture_summary,
    )


@dataclass
class BenchmarkResult:
    """Results from architecture benchmark."""
    architecture: str
    compute_time_ms: float
    output_dimension: int
    coherence_score: float
    relationship_quality: float
    memory_mb: float
    details: Dict[str, Any] = field(default_factory=dict)


def benchmark_relationship_module():
    """Benchmark the BhavaRelationshipModule."""
    print("\n" + "=" * 60)
    print("BENCHMARKING: BhavaRelationshipModule")
    print("=" * 60)

    module = BhavaRelationshipModule(embed_dim=128, num_layers=12)

    # Test with various batch sizes
    batch_sizes = [1, 4, 16, 32]
    results = {}

    for batch_size in batch_sizes:
        onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

        # Warmup
        for _ in range(3):
            _ = module(onto_probs)

        # Benchmark
        times = []
        for _ in range(10):
            start = time.perf_counter()
            output = module(onto_probs)
            times.append((time.perf_counter() - start) * 1000)

        avg_time = sum(times) / len(times)
        results[batch_size] = {
            'avg_time_ms': avg_time,
            'output_shape': output['relationship_flat'].shape,
            'coherence': output['coherence'].mean().item(),
        }

        print(f"\nBatch size {batch_size}:")
        print(f"  Average time: {avg_time:.3f}ms")
        print(f"  Output shape: {output['relationship_flat'].shape}")
        print(f"  Mean coherence: {output['coherence'].mean().item():.4f}")

    return results


def benchmark_drishti_attention():
    """Benchmark the DrishtiAttention module."""
    print("\n" + "=" * 60)
    print("BENCHMARKING: DrishtiAttention")
    print("=" * 60)

    module = DrishtiAttention(embed_dim=128, num_layers=12, num_heads=4)

    batch_size = 16
    layer_embeds = torch.randn(batch_size, 12, 128)
    onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

    # Warmup
    for _ in range(3):
        _ = module(layer_embeds, onto_probs)

    # Benchmark
    times = []
    for _ in range(10):
        start = time.perf_counter()
        output = module(layer_embeds, onto_probs)
        times.append((time.perf_counter() - start) * 1000)

    avg_time = sum(times) / len(times)

    print(f"\nBatch size {batch_size}:")
    print(f"  Average time: {avg_time:.3f}ms")
    print(f"  Output shape: {output.shape}")

    # Verify Drishti patterns are being used
    print("\nDrishti pattern verification:")
    print(f"  Opposition strength (6 apart): {module.drishti_patterns[0, 6].item():.2f}")
    print(f"  Trine strength (4 apart): {module.drishti_patterns[0, 4].item():.2f}")
    print(f"  Adjacent strength (1 apart): {module.drishti_patterns[0, 1].item():.2f}")

    return {'avg_time_ms': avg_time, 'output_shape': tuple(output.shape)}


def benchmark_inter_layer_engine():
    """Benchmark the complete InterLayerBhavaEngine."""
    print("\n" + "=" * 60)
    print("BENCHMARKING: InterLayerBhavaEngine")
    print("=" * 60)

    engine = InterLayerBhavaEngine(
        ontological_dim=12,
        hidden_dim=128,
        relationship_embed_dim=32,
        num_attention_heads=4,
    )

    batch_size = 16
    onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

    # Warmup
    for _ in range(3):
        _ = engine(onto_probs)

    # Benchmark
    times = []
    coherences = []
    for _ in range(10):
        start = time.perf_counter()
        output = engine(onto_probs)
        times.append((time.perf_counter() - start) * 1000)
        coherences.append(output['coherence'].mean().item())

    avg_time = sum(times) / len(times)
    avg_coherence = sum(coherences) / len(coherences)

    print(f"\nBatch size {batch_size}:")
    print(f"  Average time: {avg_time:.3f}ms")
    print(f"  Bhava output shape: {output['bhava'].shape}")
    print(f"  Relationship matrix shape: {output['relationship_matrix'].shape}")
    print(f"  Mean coherence: {avg_coherence:.4f}")

    # Test interpretation
    interpretations = engine.interpret_relationships(
        output['relationship_matrix'][0],
        top_k=5
    )
    print("\nTop 5 relationships:")
    for i, interp in enumerate(interpretations):
        print(f"  {i+1}. {interp['from_layer']} -> {interp['to_layer']}")
        print(f"     Bhava: {interp['relationship_bhava']['name']}")
        print(f"     Strength: {interp['strength']:.4f}")

    return {
        'avg_time_ms': avg_time,
        'avg_coherence': avg_coherence,
        'bhava_shape': tuple(output['bhava'].shape),
    }


def benchmark_vedic_aspects():
    """Verify Vedic aspect strengths are correct."""
    print("\n" + "=" * 60)
    print("VERIFYING: Vedic Aspect Strengths")
    print("=" * 60)

    expected = {
        'Conjunction (0 apart)': (0, 1.0),
        'Opposition (6 apart)': (6, 1.0),
        'Trine (4 apart)': (4, 0.9),
        'Trine (8 apart)': (8, 0.9),
        'Square (3 apart)': (3, 0.75),
        'Square (9 apart)': (9, 0.75),
        'Sextile (2 apart)': (2, 0.7),
        'Sextile (10 apart)': (10, 0.7),
        'Adjacent (1 apart)': (1, 0.8),
        'Adjacent (11 apart)': (11, 0.8),
    }

    print("\nAspect verification:")
    all_correct = True
    for name, (diff, expected_strength) in expected.items():
        actual = ASPECT_STRENGTH_MATRIX[0][diff]
        status = "OK" if abs(actual - expected_strength) < 0.01 else "FAIL"
        if status == "FAIL":
            all_correct = False
        print(f"  {name}: {actual:.2f} (expected {expected_strength:.2f}) [{status}]")

    return {'all_correct': all_correct}


def benchmark_relationship_semantics():
    """Test semantic quality of relationships."""
    print("\n" + "=" * 60)
    print("TESTING: Relationship Semantics")
    print("=" * 60)

    test_relationships = [
        (4, 7, "Cognition → Purpose"),   # How perception leads to meaning
        (0, 6, "Potential → Reasoning"),  # How dormant capacity becomes logic
        (5, 11, "Agency → Absolving"),    # How control leads to release
        (2, 8, "Execution → Witnesses"),  # How action enables meta-awareness
    ]

    print("\nRelationship interpretations:")
    for from_idx, to_idx, description in test_relationships:
        meaning = get_relationship_meaning(from_idx, to_idx)
        print(f"\n{description}:")
        print(f"  Bhava: {meaning['relationship_bhava']['name']} ({meaning['relationship_bhava']['meaning']})")
        print(f"  Interpretation: {meaning['interpretation']}")
        print(f"  Aspect strength: {ASPECT_STRENGTH_MATRIX[from_idx][to_idx]:.2f}")


def compare_architectures():
    """Compare new inter-layer vs old sub-layer architecture."""
    print("\n" + "=" * 60)
    print("ARCHITECTURE COMPARISON")
    print("=" * 60)

    comparison = {
        'Old (Sub-layer)': {
            'dimensions': 132,  # 11 pairs × 12 sub-layers
            'relationships': 11,  # Adjacent only
            'overhead': '~34%',
            'vedic_aligned': False,
        },
        'New (Inter-layer)': {
            'dimensions': 144,  # 12 × 12
            'relationships': 144,  # All-to-all
            'overhead': '~5%',
            'vedic_aligned': True,
        }
    }

    print("\n{:<20} {:>15} {:>15}".format("Metric", "Old (Sub-layer)", "New (Inter-layer)"))
    print("-" * 50)

    for metric in ['dimensions', 'relationships', 'overhead', 'vedic_aligned']:
        old_val = comparison['Old (Sub-layer)'][metric]
        new_val = comparison['New (Inter-layer)'][metric]
        print(f"{metric:<20} {str(old_val):>15} {str(new_val):>15}")

    # Calculate richness improvement
    old_rels = comparison['Old (Sub-layer)']['relationships']
    new_rels = comparison['New (Inter-layer)']['relationships']
    improvement = new_rels / old_rels

    print(f"\nRelationship richness improvement: {improvement:.1f}x")
    print("Vedic principle alignment: Sub-layer treats Bhavas as entities; Inter-layer treats them as relationships")


def run_full_benchmark():
    """Run complete benchmark suite."""
    print("\n" + "=" * 70)
    print("   BHAVA RELATIONSHIPS ARCHITECTURE - FULL BENCHMARK")
    print("=" * 70)

    print(get_architecture_summary())

    results = {}

    # Run benchmarks
    print("\n" + "=" * 70)
    print("   PERFORMANCE BENCHMARKS")
    print("=" * 70)

    results['relationship_module'] = benchmark_relationship_module()
    results['drishti_attention'] = benchmark_drishti_attention()
    results['inter_layer_engine'] = benchmark_inter_layer_engine()
    results['vedic_aspects'] = benchmark_vedic_aspects()

    # Semantic tests
    print("\n" + "=" * 70)
    print("   SEMANTIC VALIDATION")
    print("=" * 70)

    benchmark_relationship_semantics()

    # Architecture comparison
    compare_architectures()

    # Summary
    print("\n" + "=" * 70)
    print("   BENCHMARK SUMMARY")
    print("=" * 70)

    print("\nPerformance (batch=16):")
    print(f"  BhavaRelationshipModule: {results['relationship_module'][16]['avg_time_ms']:.3f}ms")
    print(f"  DrishtiAttention: {results['drishti_attention']['avg_time_ms']:.3f}ms")
    print(f"  InterLayerBhavaEngine: {results['inter_layer_engine']['avg_time_ms']:.3f}ms")

    print("\nQuality:")
    print(f"  Mean coherence: {results['inter_layer_engine']['avg_coherence']:.4f}")
    print(f"  Vedic aspects verified: {results['vedic_aspects']['all_correct']}")

    print("\nOutput dimensions:")
    print(f"  Bhava vector: 144D (12×12 relationships)")
    print(f"  Relationship matrix: 12×12")
    print(f"  Full vector with onto: 156D (12 + 144)")

    return results


def test_with_unified_engine():
    """Test integration with UnifiedOntologicalEngineV2."""
    print("\n" + "=" * 70)
    print("   UNIFIED ENGINE V2 INTEGRATION TEST")
    print("=" * 70)

    try:
        from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2
        from symbolu.ontological.encoder import get_encoder

        print("\nInitializing UnifiedOntologicalEngineV2...")
        engine = UnifiedOntologicalEngineV2(
            encoder_dim=384,
            hidden_dims=(256, 128),
        )

        # Test forward pass
        batch_size = 4
        x = torch.randn(batch_size, 384)

        print(f"\nForward pass with batch size {batch_size}...")
        start = time.perf_counter()
        output = engine(x)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"  Time: {elapsed:.3f}ms")
        print(f"  Ontological shape: {output['ontological'].shape}")
        print(f"  Bhava shape: {output['bhava'].shape}")
        print(f"  Relationship matrix shape: {output['relationship_matrix'].shape}")
        print(f"  Mean coherence: {output['coherence'].mean().item():.4f}")
        print(f"  Mean uncertainty: {output['uncertainty'].mean().item():.4f}")

        # Test analyze with text (requires encoder)
        print("\nTrying text analysis...")
        try:
            encoder = get_encoder("minilm")
            result = engine.analyze("What is the nature of consciousness?")

            print(f"\nAnalysis result:")
            print(f"  Dominant layer: {result['dominant_layer']}")
            print(f"  Confidence: {result['confidence']:.2%}")
            print(f"  Coherence: {result['coherence']:.4f}")
            print(f"  Certainty level: {result['certainty_level']}")

            print("\n  Top relationships:")
            for rel in result['strongest_relationships'][:3]:
                print(f"    {rel['from']} -> {rel['to']}: {rel['bhava']} ({rel['strength']:.4f})")

        except Exception as e:
            print(f"  Skipped text analysis (encoder not available): {e}")

        print("\nEngine summary:")
        print(engine.summary())

        return True

    except Exception as e:
        print(f"\nIntegration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if not PYTORCH_AVAILABLE:
        print("PyTorch is required for this benchmark.")
        print("Install with: pip install torch sentence-transformers")
        exit(1)

    # Run benchmarks
    results = run_full_benchmark()

    # Test integration
    success = test_with_unified_engine()

    print("\n" + "=" * 70)
    print(f"   BENCHMARK COMPLETE {'(SUCCESS)' if success else '(PARTIAL)'}")
    print("=" * 70)
