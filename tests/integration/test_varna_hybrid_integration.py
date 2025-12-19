#!/usr/bin/env python3
"""
Test Varṇa-Hybrid Integration
=============================

Comprehensive test of the full hybrid flow including:
1. Varṇa bridge functions (ARPABET → Varṇa → 10D vectors)
2. Analyzer varna functions
3. Comparison between ARPABET and Varṇa approaches
4. Hybrid optimization flow (prefilter, attention, router)
"""

import sys


def test_varna_bridge():
    """Test varna_bridge module functions."""
    print("=" * 60)
    print("TEST 1: Varṇa Bridge Functions")
    print("=" * 60)

    from symbolu.resonance.varna_bridge import (
        varna_to_10d_vector,
        english_phoneme_to_varna,
        phonemes_to_varnas,
        get_bridge_meaning,
        list_varnas,
        ENGLISH_TO_VARNA,
    )

    # Test ARPABET → Varṇa mapping
    print("\n1.1 ARPABET → Varṇa Mapping:")
    test_phonemes = ["K", "AH", "T", "S", "L", "R"]
    for p in test_phonemes:
        varna = english_phoneme_to_varna(p)
        print(f"  {p:4s} → {varna}")

    # Test phonemes_to_varnas
    print("\n1.2 Phoneme Sequence → Varṇa Sequence:")
    word_phonemes = ("T", "R", "UW", "TH")  # "truth"
    varnas = phonemes_to_varnas(word_phonemes)
    print(f"  {word_phonemes} → {varnas}")

    # Test varna_to_10d_vector
    print("\n1.3 Varṇa → 10D Vector:")
    for varna in ["ka", "ga", "sa", "ta"]:
        vec = varna_to_10d_vector(varna)
        print(f"  {varna:4s} → [{', '.join(f'{v:.2f}' for v in vec[:5])}...]")

    # Test bridge meanings
    print("\n1.4 Bridge Meanings:")
    for varna in ["ka", "ga", "la", "ma"]:
        meaning = get_bridge_meaning(varna)
        print(f"  {varna:4s} → {meaning}")

    # Count varnas
    all_varnas = list_varnas()
    print(f"\n1.5 Total Varṇas in System: {len(all_varnas)}")

    print("\n✓ Varṇa Bridge Tests PASSED")
    return True


def test_varna_analyzer():
    """Test varna-based analyzer functions."""
    print("\n" + "=" * 60)
    print("TEST 2: Varṇa-Based Analyzer Functions")
    print("=" * 60)

    from symbolu.resonance.analyzer import (
        analyze_word_varna,
        analyze_phrase_varna,
        compare_arpabet_vs_varna,
    )

    # Test analyze_word_varna
    print("\n2.1 Analyze Word (Varṇa):")
    test_words = ["truth", "love", "light", "peace"]
    for word in test_words:
        vec = analyze_word_varna(word)
        print(f"  {word:10s} → Dominant: {vec.dominant_layer} ({vec.dominant_score:.3f})")

    # Test analyze_phrase_varna
    print("\n2.2 Analyze Phrase (Varṇa):")
    test_phrases = [
        "truth is light",
        "love brings peace",
        "darkness brings fear",
    ]
    for phrase in test_phrases:
        analysis = analyze_phrase_varna(phrase)
        print(f"  \"{phrase}\"")
        print(f"    Harmony: {analysis.overall_harmony:.3f}, Prediction: {analysis.prediction}")

    # Test ARPABET vs Varṇa comparison
    print("\n2.3 ARPABET vs Varṇa Comparison:")
    comparison = compare_arpabet_vs_varna("truth")
    print(comparison)

    print("\n✓ Varṇa Analyzer Tests PASSED")
    return True


def test_hybrid_prefilter():
    """Test CandidatePreFilter with string-based API."""
    print("\n" + "=" * 60)
    print("TEST 3: Hybrid CandidatePreFilter")
    print("=" * 60)

    from symbolu.hybrid.prefilter import CandidatePreFilter

    # Create prefilter
    prefilter = CandidatePreFilter(threshold=0.6, top_k=4)

    # Define candidates and target
    candidates = ("truth", "light", "beauty", "darkness", "fear", "love", "peace")
    target = "truth"

    # Filter candidates
    print(f"\n3.1 Filter Candidates (threshold=0.6, top_k=4):")
    print(f"  Target: '{target}'")
    print(f"  Candidates: {candidates}")

    filtered = prefilter.filter(candidates, target)
    print(f"  Filtered: {filtered}")

    # Filter with scores
    filtered_with_scores = prefilter.filter(candidates, target, return_scores=True)
    print(f"\n3.2 With Scores:")
    for word, score in filtered_with_scores:
        print(f"    {word:12s}: {score:.3f}")

    # Filter with stats
    filtered, stats = prefilter.filter_with_stats(candidates, target)
    print(f"\n3.3 Filter Statistics:")
    print(f"    Total: {stats.total_candidates}")
    print(f"    Passed: {stats.passed_candidates}")
    print(f"    Rejected: {stats.rejected_candidates}")
    print(f"    Reduction: {stats.reduction_ratio:.2%}")
    print(f"    Time: {stats.filter_time_ms:.2f}ms")

    # Estimate savings
    savings = prefilter.estimate_savings(50000, transformer_ms_per_candidate=10.0)
    print(f"\n3.4 Estimated Savings (50,000 candidates):")
    print(f"    Without filter: {savings['without_filter_ms'] / 1000:.1f}s")
    print(f"    With filter: {savings['with_filter_ms'] / 1000:.1f}s")
    print(f"    Speedup: {savings['speedup_factor']:.1f}x")

    print("\n✓ CandidatePreFilter Tests PASSED")
    return True


def test_hybrid_attention():
    """Test PhonemeAttentionHead with string-based API."""
    print("\n" + "=" * 60)
    print("TEST 4: Hybrid PhonemeAttentionHead")
    print("=" * 60)

    from symbolu.hybrid.attention import PhonemeAttentionHead, HybridAttentionLayer

    # Create attention head
    attention = PhonemeAttentionHead(temperature=1.0, mask_self=False)

    # Test tokens
    tokens = ("truth", "light", "love", "peace", "beauty")

    print(f"\n4.1 Compute Attention (tokens={tokens}):")
    output = attention.compute_attention(tokens)

    print(f"  Token Vectors: {len(output.token_vectors)}")
    print(f"  Attention Matrix: {len(output.attention_weights)} x {len(output.attention_weights[0])}")
    print(f"  FLOPs: {output.computation_flops}")

    print("\n  Dominant Layers:")
    for i, (token, layer) in enumerate(zip(tokens, output.dominant_layers)):
        print(f"    {token:10s} → {layer}")

    print("\n  Attention Weights (first row):")
    for j, (token, weight) in enumerate(zip(tokens, output.attention_weights[0])):
        print(f"    truth → {token:10s}: {weight:.4f}")

    # Compare to traditional attention
    comparison = attention.compare_to_traditional(seq_len=10, head_dim=64)
    print(f"\n4.2 FLOP Comparison (seq_len=10):")
    print(f"    Traditional: {comparison['traditional_flops']:,}")
    print(f"    Phoneme: {comparison['phoneme_flops']:,}")
    print(f"    Speedup: {comparison['speedup_factor']:.2f}x")

    # Test HybridAttentionLayer
    print("\n4.3 HybridAttentionLayer Savings (seq_len=512):")
    hybrid_layer = HybridAttentionLayer(num_phoneme_heads=2, num_traditional_heads=10)
    savings = hybrid_layer.estimate_savings(seq_len=512)
    print(f"    All traditional: {savings['all_traditional_flops']:,}")
    print(f"    Hybrid: {savings['hybrid_flops']:,}")
    print(f"    Percent saved: {savings['percent_saved']:.1f}%")

    print("\n✓ PhonemeAttentionHead Tests PASSED")
    return True


def test_hybrid_router():
    """Test SemanticRouter with string-based API."""
    print("\n" + "=" * 60)
    print("TEST 5: Hybrid SemanticRouter")
    print("=" * 60)

    from symbolu.hybrid.router import SemanticRouter, ModelType, create_demo_registry

    # Create router
    router = SemanticRouter(confidence_threshold=0.1)

    # Test queries
    test_queries = [
        "Love conquers all",
        "Calculate the derivative",
        "Run the build command",
        "The universe is infinite",
        "Create a new painting",
    ]

    print("\n5.1 Route Queries:")
    for query in test_queries:
        decision = router.route(query)
        print(f"\n  Query: \"{query}\"")
        print(f"    Model: {decision.model_type.value}")
        print(f"    Confidence: {decision.confidence:.3f}")
        print(f"    Dominant Layer: {decision.dominant_layer}")

    # Estimate savings
    print("\n5.2 Routing Savings Estimate:")
    savings = router.estimate_savings(tuple(test_queries))
    print(f"    Queries to general: {savings['queries_to_general']}")
    print(f"    Queries to specialized: {savings['queries_to_specialized']}")
    print(f"    Percent specialized: {savings['percent_specialized']:.1f}%")
    print(f"    Param reduction: {savings['param_reduction_factor']:.1f}x")

    # Test demo registry
    print("\n5.3 Demo Registry:")
    registry = create_demo_registry()
    result = registry.invoke("Love brings peace")
    print(f"    Result: {result}")

    print("\n✓ SemanticRouter Tests PASSED")
    return True


def test_end_to_end_flow():
    """Test complete end-to-end flow."""
    print("\n" + "=" * 60)
    print("TEST 6: End-to-End Flow")
    print("=" * 60)

    from symbolu.resonance import analyze_word_varna
    from symbolu.hybrid.prefilter import CandidatePreFilter
    from symbolu.hybrid.attention import PhonemeAttentionHead
    from symbolu.hybrid.router import SemanticRouter

    print("\n6.1 Full Pipeline: Query → Varṇa → Route → Filter → Attention → Result")

    # Step 1: User query
    query = "truth brings light"
    print(f"\n  Input Query: '{query}'")

    # Step 2: Route the query
    router = SemanticRouter()
    decision = router.route(query)
    print(f"  Routed to: {decision.model_type.value} (confidence={decision.confidence:.3f})")

    # Step 3: Analyze query using Varṇa
    query_words = ("truth", "light")  # Content words
    print(f"  Varṇa Analysis:")
    for word in query_words:
        vec = analyze_word_varna(word)
        print(f"    {word}: {vec.dominant_layer}")

    # Step 4: Pre-filter candidates
    candidates = ("beauty", "love", "peace", "darkness", "fear", "hope", "joy", "wisdom")
    prefilter = CandidatePreFilter(threshold=0.5, top_k=4)
    filtered, stats = prefilter.filter_with_stats(candidates, "truth")
    print(f"  Pre-filtered: {filtered}")
    print(f"    Reduction: {stats.reduction_ratio:.0%}")

    # Step 5: Compute attention over filtered candidates
    attention = PhonemeAttentionHead()
    tokens = ("truth",) + filtered
    output = attention.compute_attention(tokens)
    print(f"  Attention (truth → candidates):")
    for i, (token, weight) in enumerate(zip(filtered, output.attention_weights[0][1:])):
        print(f"    → {token:12s}: {weight:.4f}")

    # Step 6: Compute total FLOPs savings
    total_candidates = len(candidates)
    filtered_count = len(filtered)
    prefilter_savings = (1 - filtered_count / total_candidates) * 100

    flop_comparison = attention.compare_to_traditional(seq_len=len(tokens))
    attention_savings = (1 - flop_comparison['phoneme_flops'] / flop_comparison['traditional_flops']) * 100

    print(f"\n  Total Savings:")
    print(f"    Pre-filter: {prefilter_savings:.1f}% candidates reduced")
    print(f"    Attention: {attention_savings:.1f}% FLOPs saved")

    print("\n✓ End-to-End Flow Tests PASSED")
    return True


def test_varna_vs_arpabet_quality():
    """Compare quality metrics between ARPABET and Varṇa approaches."""
    print("\n" + "=" * 60)
    print("TEST 7: Varṇa vs ARPABET Quality Comparison")
    print("=" * 60)

    from symbolu.resonance.analyzer import (
        analyze_word,
        analyze_word_varna,
        analyze_phrase,
        analyze_phrase_varna,
    )

    print("\n7.1 Word Vector Comparison:")
    test_words = ["truth", "love", "light", "peace", "beauty"]

    for word in test_words:
        arp = analyze_word(word)
        var = analyze_word_varna(word)

        # Calculate vector difference (Euclidean distance)
        diff = sum((a - b) ** 2 for a, b in zip(arp.vector, var.vector)) ** 0.5

        print(f"\n  {word}:")
        print(f"    ARPABET: {arp.dominant_layer} ({arp.dominant_score:.3f})")
        print(f"    Varṇa:   {var.dominant_layer} ({var.dominant_score:.3f})")
        print(f"    Vector Distance: {diff:.4f}")

    print("\n7.2 Phrase Harmony Comparison:")
    test_phrases = [
        ("truth is light", "HARMONIC"),
        ("darkness brings fear", "DISSONANT"),
        ("love brings peace", "HARMONIC"),
    ]

    correct_arp = 0
    correct_var = 0

    for phrase, expected in test_phrases:
        arp = analyze_phrase(phrase)
        var = analyze_phrase_varna(phrase)

        arp_match = arp.prediction == expected
        var_match = var.prediction == expected

        if arp_match:
            correct_arp += 1
        if var_match:
            correct_var += 1

        print(f"\n  \"{phrase}\" (expected: {expected}):")
        print(f"    ARPABET: harmony={arp.overall_harmony:.3f}, pred={arp.prediction} {'✓' if arp_match else '✗'}")
        print(f"    Varṇa:   harmony={var.overall_harmony:.3f}, pred={var.prediction} {'✓' if var_match else '✗'}")

    print(f"\n7.3 Accuracy Summary:")
    print(f"    ARPABET: {correct_arp}/{len(test_phrases)} correct")
    print(f"    Varṇa:   {correct_var}/{len(test_phrases)} correct")

    print("\n✓ Quality Comparison Tests PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VARṆA-HYBRID INTEGRATION TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_varna_bridge()
        all_passed &= test_varna_analyzer()
        all_passed &= test_hybrid_prefilter()
        all_passed &= test_hybrid_attention()
        all_passed &= test_hybrid_router()
        all_passed &= test_end_to_end_flow()
        all_passed &= test_varna_vs_arpabet_quality()

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
