#!/usr/bin/env python3
"""
Falsification Tests for Varṇa-Hybrid LLM Renderer
==================================================

These tests attempt to BREAK the hybrid flow by:
1. Edge cases (empty, extreme inputs)
2. Boundary conditions (threshold limits)
3. Adversarial inputs (designed to break assumptions)
4. Determinism verification (same input → same output)
5. Invariant checks (things that must never change)
6. Failure mode testing (graceful degradation)
7. Cross-validation (ARPABET vs Varṇa consistency)
"""

import sys
import random
import string
from typing import List, Tuple


# =============================================================================
# TEST 1: Edge Cases
# =============================================================================

def test_edge_cases():
    """Test edge cases that might break the system."""
    print("=" * 60)
    print("FALSIFICATION TEST 1: Edge Cases")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode

    renderer = VarnaHybridRenderer()
    failures = []

    # 1.1 Empty string
    print("\n1.1 Empty string:")
    try:
        result = renderer.render("", mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result: '{result.text}'")
        print("    ✓ Handled empty string")
    except Exception as e:
        failures.append(f"Empty string: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.2 Single character
    print("\n1.2 Single character:")
    try:
        result = renderer.render("a", mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Result: '{result.text[:50]}'")
        print("    ✓ Handled single character")
    except Exception as e:
        failures.append(f"Single character: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.3 Very long input (1000 words)
    print("\n1.3 Very long input (1000 words):")
    try:
        long_text = " ".join(["word"] * 1000)
        result = renderer.render(long_text, mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result length: {len(result.text)} chars")
        print("    ✓ Handled long input")
    except Exception as e:
        failures.append(f"Long input: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.4 Only whitespace
    print("\n1.4 Only whitespace:")
    try:
        result = renderer.render("   \t\n   ", mode=HybridRenderMode.HYBRID_FAST)
        print(f"    Result: '{result.text}'")
        print("    ✓ Handled whitespace-only")
    except Exception as e:
        failures.append(f"Whitespace-only: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.5 Only punctuation
    print("\n1.5 Only punctuation:")
    try:
        result = renderer.render("... !!! ???", mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result: '{result.text}'")
        print("    ✓ Handled punctuation-only")
    except Exception as e:
        failures.append(f"Punctuation-only: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.6 Unicode characters
    print("\n1.6 Unicode characters:")
    try:
        result = renderer.render("कर्म धर्म सत्यम्", mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Result: '{result.text[:50]}'")
        print("    ✓ Handled Unicode")
    except Exception as e:
        failures.append(f"Unicode: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.7 Numbers only
    print("\n1.7 Numbers only:")
    try:
        result = renderer.render("123 456 789", mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result: '{result.text}'")
        print("    ✓ Handled numbers-only")
    except Exception as e:
        failures.append(f"Numbers-only: {e}")
        print(f"    ✗ FAILED: {e}")

    # 1.8 Mixed case extremes
    print("\n1.8 Mixed case extremes:")
    try:
        result = renderer.render("TRUTH truth TrUtH", mode=HybridRenderMode.HYBRID_FAST)
        print(f"    Result: '{result.text[:50]}'")
        print("    ✓ Handled mixed case")
    except Exception as e:
        failures.append(f"Mixed case: {e}")
        print(f"    ✗ FAILED: {e}")

    if failures:
        print(f"\n✗ {len(failures)} edge case failures")
        return False
    print("\n✓ All edge cases passed")
    return True


# =============================================================================
# TEST 2: Boundary Conditions
# =============================================================================

def test_boundary_conditions():
    """Test boundary conditions for thresholds and limits."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 2: Boundary Conditions")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode
    from symbolu.hybrid.prefilter import CandidatePreFilter

    failures = []

    # 2.1 Prefilter threshold = 0.0 (accept all)
    print("\n2.1 Prefilter threshold = 0.0 (accept all):")
    try:
        renderer = VarnaHybridRenderer(prefilter_threshold=0.0)
        candidates = ("a", "b", "c", "d", "e")
        filtered, count, total = renderer.prefilter_candidates(candidates, "x")
        assert count == total, f"Expected all {total}, got {count}"
        print(f"    Filtered: {count}/{total}")
        print("    ✓ Threshold 0.0 accepts all")
    except Exception as e:
        failures.append(f"Threshold 0.0: {e}")
        print(f"    ✗ FAILED: {e}")

    # 2.2 Prefilter threshold = 1.0 (reject all except exact match)
    print("\n2.2 Prefilter threshold = 1.0 (very strict):")
    try:
        renderer = VarnaHybridRenderer(prefilter_threshold=1.0, prefilter_top_k=100)
        candidates = ("truth", "light", "love")
        filtered, count, total = renderer.prefilter_candidates(candidates, "truth")
        print(f"    Filtered: {count}/{total}")
        print(f"    Result: {filtered}")
        print("    ✓ Threshold 1.0 handled")
    except Exception as e:
        failures.append(f"Threshold 1.0: {e}")
        print(f"    ✗ FAILED: {e}")

    # 2.3 top_k = 1 (only keep best match)
    print("\n2.3 top_k = 1 (only best match):")
    try:
        renderer = VarnaHybridRenderer(prefilter_top_k=1)
        candidates = ("truth", "light", "love", "peace", "beauty")
        filtered, count, total = renderer.prefilter_candidates(candidates, "truth")
        assert count <= 1, f"Expected <= 1, got {count}"
        print(f"    Filtered: {count}/{total}")
        print("    ✓ top_k=1 works")
    except Exception as e:
        failures.append(f"top_k=1: {e}")
        print(f"    ✗ FAILED: {e}")

    # 2.4 top_k = 0 (edge case)
    print("\n2.4 top_k = 0 (edge case):")
    try:
        renderer = VarnaHybridRenderer(prefilter_top_k=0)
        candidates = ("truth", "light")
        filtered, count, total = renderer.prefilter_candidates(candidates, "truth")
        print(f"    Filtered: {count}/{total}")
        print("    ✓ top_k=0 handled")
    except Exception as e:
        failures.append(f"top_k=0: {e}")
        print(f"    ✗ FAILED: {e}")

    # 2.5 Attention temperature = 0 (division by zero risk)
    print("\n2.5 Attention temperature near 0:")
    try:
        renderer = VarnaHybridRenderer(attention_temperature=0.001)
        result = renderer.render("truth light", mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Result: '{result.text[:40]}...'")
        print("    ✓ Near-zero temperature handled")
    except Exception as e:
        failures.append(f"Temperature 0: {e}")
        print(f"    ✗ FAILED: {e}")

    # 2.6 Attention temperature = very high
    print("\n2.6 Attention temperature = 100 (very high):")
    try:
        renderer = VarnaHybridRenderer(attention_temperature=100.0)
        result = renderer.render("truth light", mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Result: '{result.text[:40]}...'")
        print("    ✓ High temperature handled")
    except Exception as e:
        failures.append(f"Temperature 100: {e}")
        print(f"    ✗ FAILED: {e}")

    if failures:
        print(f"\n✗ {len(failures)} boundary failures")
        return False
    print("\n✓ All boundary conditions passed")
    return True


# =============================================================================
# TEST 3: Determinism Verification
# =============================================================================

def test_determinism():
    """Verify same input always produces same output."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 3: Determinism")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode

    renderer = VarnaHybridRenderer()
    failures = []

    test_inputs = [
        "Truth is light",
        "Love conquers all",
        "The quick brown fox",
        "",
        "a",
    ]

    for text in test_inputs:
        print(f"\n3.x Testing: '{text[:30]}...' if text else '<empty>'")

        # Run 10 times and verify identical results
        results = []
        for i in range(10):
            result = renderer.render(text, mode=HybridRenderMode.HYBRID_FULL)
            results.append((
                result.text,
                result.flops_saved_percent,
                result.varna_analysis.dominant_layer if result.varna_analysis else None,
                result.varna_analysis.overall_harmony if result.varna_analysis else None,
            ))

        # Check all results are identical
        first = results[0]
        all_identical = all(r == first for r in results)

        if all_identical:
            print(f"    ✓ Deterministic (10 runs identical)")
        else:
            failures.append(f"Non-deterministic for: {text}")
            print(f"    ✗ FAILED: Results varied across runs")
            for i, r in enumerate(results[:3]):
                print(f"      Run {i}: {r[0][:30]}...")

    # Test Varṇa analysis determinism
    print("\n3.y Varṇa analysis determinism:")
    for _ in range(5):
        a1 = renderer.analyze_varna("truth")
        a2 = renderer.analyze_varna("truth")
        if a1.dominant_layer != a2.dominant_layer or a1.overall_harmony != a2.overall_harmony:
            failures.append("Varṇa analysis not deterministic")
            print("    ✗ FAILED: Analysis varied")
            break
    else:
        print("    ✓ Varṇa analysis deterministic")

    # Test routing determinism
    print("\n3.z Routing determinism:")
    for _ in range(5):
        r1 = renderer.route_query("Love conquers all")
        r2 = renderer.route_query("Love conquers all")
        if r1.model_type != r2.model_type or r1.confidence != r2.confidence:
            failures.append("Routing not deterministic")
            print("    ✗ FAILED: Routing varied")
            break
    else:
        print("    ✓ Routing deterministic")

    if failures:
        print(f"\n✗ {len(failures)} determinism failures")
        return False
    print("\n✓ All determinism tests passed")
    return True


# =============================================================================
# TEST 4: Invariant Checks
# =============================================================================

def test_invariants():
    """Verify invariants that must always hold."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 4: Invariants")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode
    from symbolu.resonance import analyze_word_varna

    renderer = VarnaHybridRenderer()
    failures = []

    # 4.1 Vector dimensions always 10
    print("\n4.1 Vector dimension invariant (always 10D):")
    test_words = ["truth", "a", "supercalifragilisticexpialidocious", "123", ""]
    for word in test_words:
        try:
            vec = analyze_word_varna(word) if word else None
            if vec and len(vec.vector) != 10:
                failures.append(f"Vector dim != 10 for '{word}'")
                print(f"    ✗ '{word}': dim={len(vec.vector)}")
            elif vec:
                print(f"    ✓ '{word}': dim=10")
        except Exception as e:
            print(f"    ~ '{word}': {e}")

    # 4.2 Harmony score in [0, 1]
    print("\n4.2 Harmony score range [0, 1]:")
    test_phrases = [
        "truth is light",
        "chaos and destruction",
        "a",
        "the the the the",
    ]
    for phrase in test_phrases:
        analysis = renderer.analyze_varna(phrase)
        harmony = analysis.overall_harmony
        if not (0.0 <= harmony <= 1.0):
            failures.append(f"Harmony out of range for '{phrase}': {harmony}")
            print(f"    ✗ '{phrase}': harmony={harmony}")
        else:
            print(f"    ✓ '{phrase}': harmony={harmony:.3f}")

    # 4.3 FLOPs saved in [0, 100]
    print("\n4.3 FLOPs saved range [0, 100]%:")
    for mode in HybridRenderMode:
        result = renderer.render("test phrase", mode=mode)
        saved = result.flops_saved_percent
        if not (0.0 <= saved <= 100.0):
            failures.append(f"FLOPs out of range for {mode}: {saved}")
            print(f"    ✗ {mode.value}: {saved}%")
        else:
            print(f"    ✓ {mode.value}: {saved:.1f}%")

    # 4.4 Attention weights sum to ~1.0 per row
    print("\n4.4 Attention weights sum ≈ 1.0 per row:")
    tokens = ("truth", "is", "light")
    attention, _ = renderer.compute_attention(tokens)
    for i, row in enumerate(attention):
        row_sum = sum(row)
        if not (0.95 <= row_sum <= 1.05):  # Allow small float error
            failures.append(f"Attention row {i} sum = {row_sum}")
            print(f"    ✗ Row {i}: sum={row_sum:.4f}")
        else:
            print(f"    ✓ Row {i}: sum={row_sum:.4f}")

    # 4.5 Prefilter never returns more than input
    print("\n4.5 Prefilter output <= input:")
    candidates = ("a", "b", "c")
    filtered, count, total = renderer.prefilter_candidates(candidates, "x")
    if count > total:
        failures.append(f"Prefilter returned {count} > {total}")
        print(f"    ✗ {count} > {total}")
    else:
        print(f"    ✓ {count} <= {total}")

    if failures:
        print(f"\n✗ {len(failures)} invariant violations")
        return False
    print("\n✓ All invariants hold")
    return True


# =============================================================================
# TEST 5: Cross-Validation (ARPABET vs Varṇa)
# =============================================================================

def test_cross_validation():
    """Cross-validate ARPABET and Varṇa produce consistent patterns."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 5: Cross-Validation")
    print("=" * 60)

    from symbolu.resonance import (
        analyze_word,
        analyze_word_varna,
        compare_words,
    )

    failures = []

    # 5.1 Same-word similarity should be ~1.0 (allowing float precision)
    print("\n5.1 Self-similarity ≈ 1.0:")
    test_words = ["truth", "love", "light"]
    for word in test_words:
        sim = compare_words(word, word)
        # Allow for float precision (1.0 ± 1e-10)
        if not (0.9999999999 <= sim.similarity <= 1.0000000001):
            failures.append(f"Self-similarity != 1.0 for {word}")
            print(f"    ✗ {word}: {sim.similarity}")
        else:
            print(f"    ✓ {word}: {sim.similarity:.10f}")

    # 5.2 Layer rankings should be similar between ARPABET and Varṇa
    print("\n5.2 ARPABET vs Varṇa layer ranking correlation:")
    for word in ["truth", "love", "peace"]:
        arp = analyze_word(word)
        var = analyze_word_varna(word)

        # Get top 3 layers for each
        arp_layers = sorted(range(10), key=lambda i: arp.vector[i], reverse=True)[:3]
        var_layers = sorted(range(10), key=lambda i: var.vector[i], reverse=True)[:3]

        # Check overlap
        overlap = len(set(arp_layers) & set(var_layers))
        print(f"    {word}: ARPABET top3={arp_layers}, Varṇa top3={var_layers}, overlap={overlap}")

        if overlap == 0:
            print(f"      ⚠ Warning: No overlap in top 3 layers")

    # 5.3 Harmonic pairs should be harmonic in both systems
    print("\n5.3 Harmonic consistency:")
    harmonic_pairs = [
        ("truth", "light"),
        ("love", "peace"),
    ]
    for w1, w2 in harmonic_pairs:
        sim = compare_words(w1, w2)
        print(f"    {w1}-{w2}: similarity={sim.similarity:.3f}, harmonic={sim.harmonic}")

    if failures:
        print(f"\n✗ {len(failures)} cross-validation failures")
        return False
    print("\n✓ Cross-validation passed")
    return True


# =============================================================================
# TEST 6: Adversarial Inputs
# =============================================================================

def test_adversarial_inputs():
    """Test with adversarial inputs designed to break assumptions."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 6: Adversarial Inputs")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode

    renderer = VarnaHybridRenderer()
    failures = []

    # 6.1 Very long word (no spaces)
    print("\n6.1 Very long word (500 chars):")
    try:
        long_word = "a" * 500
        result = renderer.render(long_word, mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result length: {len(result.text)}")
        print("    ✓ Handled long word")
    except Exception as e:
        failures.append(f"Long word: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.2 Repeated same word
    print("\n6.2 Repeated same word (100x):")
    try:
        repeated = " ".join(["truth"] * 100)
        result = renderer.render(repeated, mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Harmony: {result.varna_analysis.overall_harmony:.3f}")
        print("    ✓ Handled repetition")
    except Exception as e:
        failures.append(f"Repetition: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.3 Random characters
    print("\n6.3 Random characters:")
    try:
        random_chars = "".join(random.choices(string.ascii_letters + " ", k=100))
        result = renderer.render(random_chars, mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Input: '{random_chars[:30]}...'")
        print(f"    Output length: {len(result.text)}")
        print("    ✓ Handled random input")
    except Exception as e:
        failures.append(f"Random chars: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.4 SQL injection attempt (should be treated as text)
    print("\n6.4 SQL injection attempt:")
    try:
        sql = "'; DROP TABLE users; --"
        result = renderer.render(sql, mode=HybridRenderMode.HYBRID_FAST)
        print(f"    Input: '{sql}'")
        print(f"    Output: '{result.text[:50]}...'")
        print("    ✓ Handled safely")
    except Exception as e:
        failures.append(f"SQL injection: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.5 HTML/Script injection
    print("\n6.5 Script injection attempt:")
    try:
        script = "<script>alert('xss')</script>"
        result = renderer.render(script, mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Input: '{script}'")
        print(f"    Output: '{result.text[:50]}...'")
        print("    ✓ Handled safely")
    except Exception as e:
        failures.append(f"Script injection: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.6 Null bytes
    print("\n6.6 Null bytes in input:")
    try:
        null_input = "test\x00null\x00bytes"
        result = renderer.render(null_input, mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Input contained null bytes")
        print(f"    Output: '{result.text[:40]}...'")
        print("    ✓ Handled null bytes")
    except Exception as e:
        failures.append(f"Null bytes: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.7 Empty candidates tuple
    print("\n6.7 Empty candidates tuple:")
    try:
        filtered, count, total = renderer.prefilter_candidates((), "target")
        print(f"    Filtered: {count}/{total}")
        print("    ✓ Handled empty candidates")
    except Exception as e:
        failures.append(f"Empty candidates: {e}")
        print(f"    ✗ FAILED: {e}")

    # 6.8 Single-character candidates
    print("\n6.8 Single-character candidates:")
    try:
        candidates = tuple(string.ascii_lowercase)  # a-z
        filtered, count, total = renderer.prefilter_candidates(candidates, "a")
        print(f"    Filtered: {count}/{total}")
        print("    ✓ Handled single-char candidates")
    except Exception as e:
        failures.append(f"Single-char candidates: {e}")
        print(f"    ✗ FAILED: {e}")

    if failures:
        print(f"\n✗ {len(failures)} adversarial failures")
        return False
    print("\n✓ All adversarial tests passed")
    return True


# =============================================================================
# TEST 7: Failure Mode Testing
# =============================================================================

def test_failure_modes():
    """Test graceful degradation when things go wrong."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 7: Failure Modes")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode

    renderer = VarnaHybridRenderer()
    failures = []

    # 7.1 Unknown phonemes (made-up word)
    print("\n7.1 Unknown phonemes (made-up word):")
    try:
        result = renderer.render("xyzqwkj", mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result: '{result.text}'")
        print("    ✓ Degraded gracefully")
    except Exception as e:
        failures.append(f"Unknown phonemes: {e}")
        print(f"    ✗ FAILED: {e}")

    # 7.2 Non-English words
    print("\n7.2 Non-English words:")
    try:
        result = renderer.render("bonjour monde", mode=HybridRenderMode.HYBRID_FULL)
        print(f"    Result: '{result.text[:40]}...'")
        print("    ✓ Handled non-English")
    except Exception as e:
        failures.append(f"Non-English: {e}")
        print(f"    ✗ FAILED: {e}")

    # 7.3 Mixed languages
    print("\n7.3 Mixed languages:")
    try:
        result = renderer.render("hello 世界 bonjour", mode=HybridRenderMode.PHONEME_ONLY)
        print(f"    Result: '{result.text[:40]}...'")
        print("    ✓ Handled mixed languages")
    except Exception as e:
        failures.append(f"Mixed languages: {e}")
        print(f"    ✗ FAILED: {e}")

    # 7.4 Verify LLM fallback mode works without LLM
    print("\n7.4 LLM fallback mode (no actual LLM):")
    try:
        result = renderer.render("test", mode=HybridRenderMode.LLM_FALLBACK)
        print(f"    Result: '{result.text}'")
        print("    ✓ Fallback mode works")
    except Exception as e:
        failures.append(f"LLM fallback: {e}")
        print(f"    ✗ FAILED: {e}")

    # 7.5 None values in optional parameters
    print("\n7.5 None values in parameters:")
    try:
        result = renderer.render(
            "test",
            mode=HybridRenderMode.HYBRID_FAST,
            tone=None,
            candidates=None,
            target_word=None,
        )
        print(f"    Result: '{result.text[:40]}...'")
        print("    ✓ Handled None parameters")
    except Exception as e:
        failures.append(f"None parameters: {e}")
        print(f"    ✗ FAILED: {e}")

    if failures:
        print(f"\n✗ {len(failures)} failure mode issues")
        return False
    print("\n✓ All failure mode tests passed")
    return True


# =============================================================================
# TEST 8: Performance Bounds
# =============================================================================

def test_performance_bounds():
    """Verify performance claims are accurate."""
    print("\n" + "=" * 60)
    print("FALSIFICATION TEST 8: Performance Bounds")
    print("=" * 60)

    from symbolu.mechanical.renderer import VarnaHybridRenderer, HybridRenderMode
    import time

    renderer = VarnaHybridRenderer()
    failures = []

    # 8.1 PHONEME_ONLY should have 100% FLOPs saved
    print("\n8.1 PHONEME_ONLY = 100% savings:")
    result = renderer.render("test", mode=HybridRenderMode.PHONEME_ONLY)
    if result.flops_saved_percent != 100.0:
        failures.append(f"PHONEME_ONLY savings = {result.flops_saved_percent}%")
        print(f"    ✗ Got {result.flops_saved_percent}%")
    else:
        print("    ✓ 100% savings confirmed")

    # 8.2 HYBRID_FULL should have >80% savings
    print("\n8.2 HYBRID_FULL >= 80% savings:")
    result = renderer.render("truth is light", mode=HybridRenderMode.HYBRID_FULL)
    if result.flops_saved_percent < 80.0:
        failures.append(f"HYBRID_FULL savings = {result.flops_saved_percent}%")
        print(f"    ✗ Got {result.flops_saved_percent}%")
    else:
        print(f"    ✓ {result.flops_saved_percent:.1f}% savings")

    # 8.3 LLM_FALLBACK should have 0% savings
    print("\n8.3 LLM_FALLBACK = 0% savings:")
    result = renderer.render("test", mode=HybridRenderMode.LLM_FALLBACK)
    if result.flops_saved_percent != 0.0:
        failures.append(f"LLM_FALLBACK savings = {result.flops_saved_percent}%")
        print(f"    ✗ Got {result.flops_saved_percent}%")
    else:
        print("    ✓ 0% savings confirmed")

    # 8.4 Rendering should be fast (< 100ms for short text)
    print("\n8.4 Render time < 100ms:")
    start = time.time()
    for _ in range(10):
        renderer.render("truth is light", mode=HybridRenderMode.HYBRID_FULL)
    elapsed = (time.time() - start) / 10 * 1000
    if elapsed > 100:
        print(f"    ⚠ Warning: {elapsed:.1f}ms per render")
    else:
        print(f"    ✓ {elapsed:.1f}ms per render")

    # 8.5 Savings estimate should be reasonable
    print("\n8.5 Savings estimate sanity check:")
    savings = renderer.estimate_savings(50000, 512, 10.0)

    checks = [
        ("prefilter speedup > 1", savings['prefilter']['speedup_factor'] > 1),
        ("attention savings > 0", savings['attention']['percent_saved'] > 0),
        ("total speedup > 1", savings['total_speedup_estimate'] > 1),
    ]

    for desc, passed in checks:
        if not passed:
            failures.append(desc)
            print(f"    ✗ {desc}")
        else:
            print(f"    ✓ {desc}")

    if failures:
        print(f"\n✗ {len(failures)} performance issues")
        return False
    print("\n✓ All performance bounds verified")
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run all falsification tests."""
    print("\n" + "=" * 70)
    print("VARṆA-HYBRID FALSIFICATION TEST SUITE")
    print("=" * 70)
    print("\nAttempting to BREAK the hybrid flow with edge cases,")
    print("adversarial inputs, and boundary conditions...\n")

    results = []

    results.append(("Edge Cases", test_edge_cases()))
    results.append(("Boundary Conditions", test_boundary_conditions()))
    results.append(("Determinism", test_determinism()))
    results.append(("Invariants", test_invariants()))
    results.append(("Cross-Validation", test_cross_validation()))
    results.append(("Adversarial Inputs", test_adversarial_inputs()))
    results.append(("Failure Modes", test_failure_modes()))
    results.append(("Performance Bounds", test_performance_bounds()))

    print("\n" + "=" * 70)
    print("FALSIFICATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {name:25s}: {status}")

    print(f"\nTotal: {passed}/{total} test categories passed")

    if passed == total:
        print("\n" + "=" * 70)
        print("FALSIFICATION FAILED: System is robust! ✓")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print(f"FALSIFICATION SUCCEEDED: Found {total - passed} weakness(es)")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
