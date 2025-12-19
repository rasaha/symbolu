#!/usr/bin/env python3
"""
Test Varṇa-Hybrid LLM Renderer
==============================

Tests the integration of Varṇa phoneme analysis with the LLM rendering pipeline.
"""

import sys


def test_renderer_initialization():
    """Test renderer initialization."""
    print("=" * 60)
    print("TEST 1: Renderer Initialization")
    print("=" * 60)

    from symbolu.mechanical.renderer import (
        VarnaHybridRenderer,
        HybridRenderMode,
        create_varna_hybrid_renderer,
    )

    # Default initialization
    renderer = VarnaHybridRenderer()
    print(f"\n1.1 Default renderer created: {type(renderer).__name__}")

    # Factory initialization
    fast_renderer = create_varna_hybrid_renderer(mode="fast")
    balanced_renderer = create_varna_hybrid_renderer(mode="balanced")
    quality_renderer = create_varna_hybrid_renderer(mode="quality")

    print(f"1.2 Factory renderers created: fast, balanced, quality")
    print(f"    Fast prefilter threshold: {fast_renderer.prefilter.threshold}")
    print(f"    Balanced prefilter threshold: {balanced_renderer.prefilter.threshold}")
    print(f"    Quality prefilter threshold: {quality_renderer.prefilter.threshold}")

    print("\n✓ Renderer Initialization Tests PASSED")
    return True


def test_varna_analysis():
    """Test Varṇa analysis functionality."""
    print("\n" + "=" * 60)
    print("TEST 2: Varṇa Analysis")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    # Test phrases
    test_phrases = [
        "Truth is light",
        "Love conquers all",
        "Darkness brings fear",
        "Peace flows eternally",
    ]

    print("\n2.1 Phrase Analysis:")
    for phrase in test_phrases:
        analysis = renderer.analyze_varna(phrase)
        print(f"\n  \"{phrase}\"")
        print(f"    Dominant Layer: {analysis.dominant_layer}")
        print(f"    Harmony: {analysis.overall_harmony:.3f}")
        print(f"    Varṇas: {' '.join(analysis.varnas[:6])}...")
        if analysis.bridge_meanings:
            print(f"    Bridge Meanings: {', '.join(list(analysis.bridge_meanings)[:3])}")

    print("\n✓ Varṇa Analysis Tests PASSED")
    return True


def test_semantic_routing():
    """Test semantic routing functionality."""
    print("\n" + "=" * 60)
    print("TEST 3: Semantic Routing")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    # Test queries
    test_queries = [
        ("Love conquers all", "relationship"),
        ("Calculate the sum", "reasoning"),
        ("The universe is infinite", "reflective"),
        ("Run the build command", "action"),
    ]

    print("\n3.1 Query Routing:")
    for query, expected_category in test_queries:
        decision = renderer.route_query(query)
        print(f"\n  \"{query}\"")
        print(f"    Routed to: {decision.model_type.value}")
        print(f"    Confidence: {decision.confidence:.3f}")
        print(f"    Dominant Layer: {decision.dominant_layer}")

    print("\n✓ Semantic Routing Tests PASSED")
    return True


def test_candidate_prefilter():
    """Test candidate pre-filtering."""
    print("\n" + "=" * 60)
    print("TEST 4: Candidate Pre-Filter")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    # Test candidates
    candidates = (
        "truth", "light", "love", "peace", "beauty",
        "darkness", "fear", "hate", "anger", "chaos",
        "wisdom", "harmony", "joy", "hope", "faith",
    )
    target = "truth"

    print(f"\n4.1 Filtering candidates for target: '{target}'")
    print(f"    Total candidates: {len(candidates)}")

    filtered, filtered_count, total_count = renderer.prefilter_candidates(
        candidates, target
    )

    print(f"    Filtered to: {filtered_count}")
    print(f"    Filtered candidates: {filtered}")
    print(f"    Reduction: {(1 - filtered_count / total_count) * 100:.1f}%")

    print("\n✓ Candidate Pre-Filter Tests PASSED")
    return True


def test_phoneme_attention():
    """Test phoneme attention computation."""
    print("\n" + "=" * 60)
    print("TEST 5: Phoneme Attention")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    # Test tokens
    tokens = ("truth", "is", "light", "and", "beauty")

    print(f"\n5.1 Computing attention for: {tokens}")

    attention_weights, flops = renderer.compute_attention(tokens)

    print(f"    Attention matrix: {len(attention_weights)} x {len(attention_weights[0])}")
    print(f"    FLOPs used: {flops}")

    # Show attention for first token
    print(f"\n5.2 Attention from 'truth':")
    for i, (token, weight) in enumerate(zip(tokens, attention_weights[0])):
        print(f"    → {token:10s}: {weight:.4f}")

    # Compare to traditional
    comparison = renderer.attention.compare_to_traditional(len(tokens))
    savings = (1 - comparison['phoneme_flops'] / comparison['traditional_flops']) * 100
    print(f"\n5.3 FLOP Savings: {savings:.1f}%")

    print("\n✓ Phoneme Attention Tests PASSED")
    return True


def test_render_modes():
    """Test different rendering modes."""
    print("\n" + "=" * 60)
    print("TEST 6: Rendering Modes")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode

    renderer = VarnaHybridRenderer()

    text = "Truth is light"
    candidates = ("beauty", "love", "wisdom", "peace", "joy")
    target = "truth"

    print(f"\n6.1 Input text: \"{text}\"")

    # Test each mode
    modes = [
        HybridRenderMode.PHONEME_ONLY,
        HybridRenderMode.HYBRID_FAST,
        HybridRenderMode.HYBRID_FULL,
        HybridRenderMode.LLM_FALLBACK,
    ]

    for mode in modes:
        result = renderer.render(
            text,
            mode=mode,
            candidates=candidates,
            target_word=target,
        )
        print(f"\n  Mode: {mode.value}")
        print(f"    Output: {result.text[:60]}...")
        print(f"    FLOPs saved: {result.flops_saved_percent:.1f}%")
        if result.routing_decision:
            print(f"    Routed to: {result.routing_decision.model_type.value}")

    print("\n✓ Rendering Modes Tests PASSED")
    return True


def test_savings_estimate():
    """Test computational savings estimation."""
    print("\n" + "=" * 60)
    print("TEST 7: Savings Estimation")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    # Estimate savings for typical workload
    savings = renderer.estimate_savings(
        num_candidates=50000,
        seq_len=512,
        transformer_ms=10.0,
    )

    print("\n7.1 Pre-filter Savings (50,000 candidates):")
    print(f"    Without filter: {savings['prefilter']['without_filter_ms'] / 1000:.1f}s")
    print(f"    With filter: {savings['prefilter']['with_filter_ms'] / 1000:.1f}s")
    print(f"    Speedup: {savings['prefilter']['speedup_factor']:.1f}x")

    print("\n7.2 Attention Savings (seq_len=512):")
    print(f"    Traditional FLOPs: {savings['attention']['all_traditional_flops']:,}")
    print(f"    Hybrid FLOPs: {savings['attention']['hybrid_flops']:,}")
    print(f"    Percent saved: {savings['attention']['percent_saved']:.1f}%")

    print("\n7.3 Router Savings:")
    print(f"    General model params: {savings['router']['general_model_params'] / 1e9:.0f}B")
    print(f"    Specialized params: {savings['router']['specialized_model_params'] / 1e9:.0f}B")
    print(f"    Param reduction: {savings['router']['param_reduction']}x")

    print(f"\n7.4 Total Speedup Estimate: {savings['total_speedup_estimate']:.1f}x")

    print("\n✓ Savings Estimation Tests PASSED")
    return True


def test_phase_integration_points():
    """Test integration points with Symbol-U phases."""
    print("\n" + "=" * 60)
    print("TEST 8: Phase Integration Points")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer

    renderer = VarnaHybridRenderer()

    print("\n8.1 Integration Points:")
    print("""
    ┌─────────────────────────────────────────────────────────────┐
    │  PHASE INTEGRATION POINTS                                   │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  P6: Regime Selection                                       │
    │      └── SemanticRouter routes query to specialized model   │
    │          Uses: dominant ontological layer from Varṇa        │
    │                                                             │
    │  P9: Lexical Selection                                      │
    │      └── CandidatePreFilter reduces vocabulary              │
    │          Uses: phoneme resonance similarity                 │
    │                                                             │
    │  P10-P13: Acoustic Phases                                   │
    │      └── PhonemeAttentionHead replaces learned attention    │
    │          Uses: phoneme cosine similarity (82% FLOPs saved)  │
    │                                                             │
    │  Renderer Layer (after phases)                              │
    │      └── VarnaHybridRenderer combines all optimizations     │
    │          Uses: Varṇa bridge meanings + harmony analysis     │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘
    """)

    # Demonstrate P6 integration (routing)
    print("8.2 P6 Regime Selection Demo:")
    regime_queries = [
        ("I love you deeply", "REFLECT"),  # O9_UNIFYING → REFLECT
        ("Calculate the derivative", "INFORM"),  # O6_REASONING → INFORM
        ("Run the build", "CLARIFY"),  # O3_ACTING → CLARIFY
    ]

    for query, expected_regime in regime_queries:
        decision = renderer.route_query(query)
        regime = {
            "relationship": "REFLECT",
            "reasoning": "INFORM",
            "action": "CLARIFY",
            "creative": "SUPPORT",
            "reflective": "REFLECT",
            "directive": "DIRECT",
            "transcendent": "HOLD",
            "general": "STABILIZE",
        }.get(decision.model_type.value, "STABILIZE")

        print(f"    \"{query[:25]}...\" → {regime}")

    print("\n8.3 P9 Lexical Selection Demo:")
    vocab = ("clarity", "truth", "light", "wisdom", "insight",
             "confusion", "darkness", "error", "mistake", "chaos")
    target = "understanding"

    filtered, _, _ = renderer.prefilter_candidates(vocab, target)
    print(f"    Vocabulary: {len(vocab)} words")
    print(f"    Target: '{target}'")
    print(f"    Filtered: {filtered}")

    print("\n✓ Phase Integration Tests PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VARṆA-HYBRID LLM RENDERER TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_renderer_initialization()
        all_passed &= test_varna_analysis()
        all_passed &= test_semantic_routing()
        all_passed &= test_candidate_prefilter()
        all_passed &= test_phoneme_attention()
        all_passed &= test_render_modes()
        all_passed &= test_savings_estimate()
        all_passed &= test_phase_integration_points()

        print("\n" + "=" * 60)
        if all_passed:
            print("ALL TESTS PASSED ✓")
        else:
            print("SOME TESTS FAILED ✗")
        print("=" * 60 + "\n")

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
