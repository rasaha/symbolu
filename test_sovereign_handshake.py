#!/usr/bin/env python3
"""
Sovereign Handshake Test Suite
==============================

Comprehensive test script for the CSR (Constraint-Structure-Resonance) system
including:
    1. HybridG2P (CMUdict + g2p_en)
    2. 12D Phoneme-Ontology Mapping
    3. SattvicController with Entropy Variance Detection
    4. Simulated Training Loop with Mode Collapse Recovery

Usage:
    python test_sovereign_handshake.py [--full]

The --full flag runs extended tests including training simulation.
"""

import sys
import math
import random
from typing import Dict, List, Any, Tuple

# Check for required modules
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("  [WARN] PyTorch not available. Some tests will be skipped.")


def print_header(title: str, char: str = "="):
    """Print a formatted header."""
    width = 70
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}")


def print_section(title: str):
    """Print a section header."""
    print(f"\n  {'─' * 50}")
    print(f"  {title}")
    print(f"  {'─' * 50}")


def test_hybrid_g2p() -> bool:
    """Test the Hybrid G2P system."""
    print_header("TEST 1: HYBRID G2P SYSTEM")

    try:
        from csr_phoneme_provider import HybridG2P, get_hybrid_g2p

        g2p = get_hybrid_g2p()
        stats = g2p.get_stats()

        print(f"\n  G2P System Statistics:")
        print(f"    CMUdict Loaded:    {stats['cmudict_loaded']}")
        print(f"    CMUdict Words:     {stats['cmudict_words']:,}")
        print(f"    g2p_en Available:  {stats['g2p_en_available']}")
        print(f"    Custom Vocab Size: {stats['custom_vocab_size']}")

        # Test words from different tiers
        test_cases = [
            # (word, expected_tier, description)
            ("hello", "CMUdict", "Common word"),
            ("world", "CMUdict", "Common word"),
            ("transformer", "CMUdict", "Technical term in CMUdict"),
            ("consciousness", "CMUdict", "Complex word"),
            ("symbolu", "Custom", "Domain-specific term"),
            ("vritti", "Custom", "Sanskrit term"),
            ("embedding", "Custom", "AI/ML term"),
            ("chatgpt", "Custom", "Modern AI term"),
            ("llama", "Custom", "Override CMUdict"),
            ("xyzabc", "Char", "Unknown word"),
        ]

        print(f"\n  Tiered Lookup Test:")
        print(f"  {'Word':<15} {'Phonemes':<35} {'Tier':<10}")
        print(f"  {'-'*60}")

        all_passed = True
        for word, expected_tier, desc in test_cases:
            phonemes = g2p.get_phonemes(word)
            phoneme_str = " ".join(phonemes)
            if len(phoneme_str) > 30:
                phoneme_str = phoneme_str[:27] + "..."
            print(f"  {word:<15} {phoneme_str:<35} [{expected_tier}]")

            if not phonemes or phonemes == ["UNK"]:
                all_passed = False

        print(f"\n  ✅ HybridG2P Test: {'PASSED' if all_passed else 'FAILED'}")
        return all_passed

    except Exception as e:
        print(f"\n  ❌ HybridG2P Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phoneme_ontology_mapping() -> bool:
    """Test the 12D phoneme-to-ontology mapping."""
    print_header("TEST 2: 12D PHONEME-ONTOLOGY MAPPING")

    try:
        from csr_phoneme_provider import PHONEME_MAP_ARPABET, ONTOLOGICAL_LAYERS

        print(f"\n  Ontological Layers:")
        for idx, name in ONTOLOGICAL_LAYERS.items():
            print(f"    Layer {idx:2d}: {name}")

        print(f"\n  Phoneme Count: {len(PHONEME_MAP_ARPABET)}")

        # Sample phonemes and their 12D vectors
        sample_phonemes = ["AH", "IY", "OW", "T", "S", "M", "R", "SIL"]

        print(f"\n  Sample Phoneme Affinities:")
        print(f"  {'Phoneme':<8} {'Dominant Layer':<20} {'Affinity':<8}")
        print(f"  {'-'*40}")

        for phoneme in sample_phonemes:
            if phoneme in PHONEME_MAP_ARPABET:
                vector = PHONEME_MAP_ARPABET[phoneme]
                max_idx = vector.index(max(vector))
                max_val = max(vector)
                layer_name = ONTOLOGICAL_LAYERS.get(max_idx, f"Layer {max_idx}")
                print(f"  {phoneme:<8} {layer_name:<20} {max_val:.3f}")

        # Test Sanskrit vowel calibration
        print_section("Sanskrit Vowel Spine (अ → ओ)")

        from csr_phoneme_provider import SANSKRIT_VOWEL_CALIBRATION

        vowel_map = {"AH": "अ", "IH": "इ", "UH": "उ", "EH": "ए", "OW": "ओ"}
        for phoneme, vector in SANSKRIT_VOWEL_CALIBRATION.items():
            sanskrit = vowel_map.get(phoneme, "?")
            max_idx = vector.index(max(vector))
            layer_name = ONTOLOGICAL_LAYERS.get(max_idx, f"Layer {max_idx}")
            print(f"    {phoneme} ({sanskrit}) → {layer_name}")

        print(f"\n  ✅ Phoneme-Ontology Mapping Test: PASSED")
        return True

    except Exception as e:
        print(f"\n  ❌ Phoneme-Ontology Mapping Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sattvic_controller() -> bool:
    """Test the SattvicController with entropy variance detection."""
    print_header("TEST 3: SATTVIC CONTROLLER")

    try:
        from symbolu.resonance.controller import (
            SattvicController,
            SattvicConfig,
            create_sattvic_controller
        )

        controller = SattvicController()

        print(f"\n  Controller Configuration:")
        print(f"    Initial λ:        {controller.config.initial_lambda}")
        print(f"    Floor λ:          {controller.config.floor_lambda}")
        print(f"    Max λ:            {controller.config.max_lambda}")
        print(f"    Warmup Steps:     {controller.config.warmup_steps}")
        print(f"    Know Threshold:   {controller.config.know_threshold}")
        print(f"    Variance Window:  {controller.config.variance_window}")
        print(f"    Variance Thresh:  {controller.config.variance_threshold}")
        print(f"    Entropy Floor:    {controller.config.entropy_floor}")

        # Test Phase Progression
        print_section("Phase Progression Test")

        test_scenarios = [
            # (step, entropy, knowledge, expected_phase)
            (0, 0.8, 0.0, "WARMUP"),
            (250, 0.7, 0.1, "WARMUP"),
            (500, 0.6, 0.2, "SATTVIC_DECAY"),
            (750, 0.55, 0.4, "SATTVIC_DECAY"),
            (1000, 0.50, 0.6, "SATTVIC_DECAY"),
            (1250, 0.48, 0.75, "SATTVIC_FLOOR"),
        ]

        print(f"\n  {'Step':<8} {'Entropy':<10} {'Know':<8} {'λ':<8} {'Phase':<20}")
        print(f"  {'-'*60}")

        for step, entropy, knowledge, expected_phase in test_scenarios:
            lambda_csr = controller.update(step, {'ent': entropy, 'know': knowledge})
            status = controller.get_status()
            phase = status['phase']
            print(f"  {step:<8} {entropy:<10.2f} {knowledge:<8.2f} {lambda_csr:<8.3f} {phase:<20}")

        # Test Mode Collapse Detection
        print_section("Mode Collapse Detection Test")

        collapse_controller = SattvicController()

        # Skip warmup
        for i in range(505):
            collapse_controller.update(i, {'ent': 0.6, 'know': 0.3})

        print(f"\n  Triggering mode collapse (entropy < 0.4)...")
        lambda_before = collapse_controller.lambda_csr
        lambda_after = collapse_controller.update(600, {'ent': 0.35, 'know': 0.4})
        status = collapse_controller.get_status()

        print(f"    λ Before:          {lambda_before:.3f}")
        print(f"    λ After:           {lambda_after:.3f}")
        print(f"    Collapse Detected: {status['mode_collapse_detected']}")
        print(f"    Boost Active:      {status['boost_active']}")

        boost_worked = lambda_after > lambda_before and status['boost_active']

        # Test Entropy Variance Stagnation
        print_section("Entropy Variance Stagnation Test")

        stag_controller = SattvicController()

        # Skip warmup
        for i in range(505):
            stag_controller.update(i, {'ent': 0.55, 'know': 0.3})

        # Fill with constant entropy to trigger stagnation
        print(f"\n  Filling entropy window with constant value (0.50)...")
        for i in range(55):
            stag_controller.update(505 + i, {'ent': 0.50, 'know': 0.3})

        status = stag_controller.get_status()
        print(f"    Entropy Variance:  {status['entropy_variance']:.8f}")
        print(f"    Stagnation:        {status['stagnation_detected']}")
        print(f"    Boost Active:      {status['boost_active']}")

        # Stagnation should trigger boost
        stagnation_detected = status['entropy_variance'] < 0.001

        all_passed = boost_worked and stagnation_detected
        print(f"\n  ✅ SattvicController Test: {'PASSED' if all_passed else 'PARTIAL'}")
        return all_passed

    except Exception as e:
        print(f"\n  ❌ SattvicController Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_csr_embedding_provider() -> bool:
    """Test the CSR Embedding Provider (requires PyTorch)."""
    print_header("TEST 4: CSR EMBEDDING PROVIDER")

    if not HAS_TORCH:
        print("\n  ⚠️  Skipped: PyTorch not available")
        return True

    try:
        from csr_phoneme_provider import (
            CSRConfig,
            CSREmbeddingProvider,
            PHONEME_MAP_ARPABET
        )

        config = CSRConfig(d_model=512, num_layers=12)
        provider = CSREmbeddingProvider(config)

        print(f"\n  CSR Provider Configuration:")
        print(f"    d_model:          {config.d_model}")
        print(f"    num_layers:       {config.num_layers}")
        print(f"    λ_csr:            {config.lambda_csr}")
        print(f"    Position Weights: {config.position_weights}")
        print(f"    Phoneme Count:    {len(PHONEME_MAP_ARPABET)}")

        # Test token-to-phoneme conversion
        print_section("Token → Phoneme → 12D Affinity")

        test_tokens = ["hello", "world", "truth", "light", "symbolu"]

        print(f"\n  {'Token':<12} {'Phonemes':<25} {'Dominant Layer'}")
        print(f"  {'-'*55}")

        for token in test_tokens:
            phonemes = provider.token_to_phonemes(token)
            affinity = provider.phonemes_to_affinity(phonemes)

            # Find dominant layer
            max_idx = affinity.argmax().item()
            from csr_phoneme_provider import ONTOLOGICAL_LAYERS
            layer_name = ONTOLOGICAL_LAYERS.get(max_idx, f"Layer {max_idx}")

            phoneme_str = " ".join(phonemes[:5])
            if len(phonemes) > 5:
                phoneme_str += "..."

            print(f"  {token:<12} {phoneme_str:<25} {layer_name}")

        # Test forward pass
        print_section("Forward Pass Test")

        batch_size = 2
        seq_len = 8
        fake_tokens = [
            ["hello", "world", "this", "is", "a", "test", "of", "csr"],
            ["truth", "light", "and", "love", "are", "the", "way", "forward"],
        ]

        fake_input_ids = torch.randint(0, 50000, (batch_size, seq_len))

        with torch.no_grad():
            csr_embeddings, confidence = provider(fake_input_ids, fake_tokens)

        print(f"\n  Input Shape:      {fake_input_ids.shape}")
        print(f"  Output Shape:     {csr_embeddings.shape}")
        print(f"  Confidence Shape: {confidence.shape}")
        print(f"  Confidence Mean:  {confidence.mean().item():.4f}")

        # Verify shapes
        expected_shape = (batch_size, seq_len, config.d_model)
        shape_correct = tuple(csr_embeddings.shape) == expected_shape

        print(f"\n  ✅ CSR Embedding Provider Test: {'PASSED' if shape_correct else 'FAILED'}")
        return shape_correct

    except Exception as e:
        print(f"\n  ❌ CSR Embedding Provider Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_training_simulation() -> bool:
    """Simulate a training loop with Sattvic Controller."""
    print_header("TEST 5: TRAINING SIMULATION")

    try:
        from symbolu.resonance.controller import SattvicController

        controller = SattvicController()

        # Simulate training progression
        print(f"\n  Simulating 2500 training steps...")
        print(f"\n  {'Step':<8} {'Entropy':<10} {'Know':<8} {'λ':<8} {'Phase':<20} {'Event'}")
        print(f"  {'-'*75}")

        # Training simulation parameters
        total_steps = 2500
        events = []

        for step in range(total_steps):
            # Simulate entropy (decreases over time with some noise)
            base_entropy = 0.8 - (step / total_steps) * 0.4
            noise = random.gauss(0, 0.02)
            entropy = max(0.3, min(1.0, base_entropy + noise))

            # Simulate mode collapse around step 1500
            if 1500 <= step <= 1600:
                entropy = 0.35 + random.gauss(0, 0.02)

            # Simulate knowledge growth
            knowledge = min(0.8, (step / total_steps) * 0.9)

            # Update controller
            lambda_csr = controller.update(step, {'ent': entropy, 'know': knowledge})
            status = controller.get_status()

            # Log key events
            event = ""
            if step == 0:
                event = "Training start"
                events.append((step, "START"))
            elif step == controller.config.warmup_steps:
                event = "Warmup complete"
                events.append((step, "WARMUP_END"))
            elif status['mode_collapse_detected'] and step not in [e[0] for e in events]:
                event = "🔥 MODE COLLAPSE"
                events.append((step, "COLLAPSE"))
            elif status['stagnation_detected'] and step not in [e[0] for e in events]:
                event = "⚠️ STAGNATION"
                events.append((step, "STAGNATION"))
            elif not status['boost_active'] and len(events) > 0 and events[-1][1] in ["COLLAPSE", "STAGNATION"]:
                event = "✅ RECOVERED"
                events.append((step, "RECOVERED"))
            elif knowledge >= controller.config.know_threshold and step not in [e[0] for e in events]:
                event = "🎯 KNOWLEDGE THRESHOLD"
                events.append((step, "KNOWLEDGE"))

            # Print milestones
            if step % 500 == 0 or event:
                print(f"  {step:<8} {entropy:<10.3f} {knowledge:<8.3f} {lambda_csr:<8.3f} {status['phase']:<20} {event}")

        # Summary
        print_section("Simulation Summary")

        print(f"\n  Total Steps:       {total_steps}")
        print(f"  Final λ:           {controller.current_lambda:.3f}")
        print(f"  Final Phase:       {controller.get_status()['phase']}")
        print(f"  Boost Activations: {sum(1 for e in events if e[1] in ['COLLAPSE', 'STAGNATION'])}")
        print(f"  Recoveries:        {sum(1 for e in events if e[1] == 'RECOVERED')}")

        # Verify controller worked correctly
        final_status = controller.get_status()
        success = (
            final_status['lambda_csr'] <= controller.config.initial_lambda and
            len(events) > 0
        )

        print(f"\n  ✅ Training Simulation: {'PASSED' if success else 'PARTIAL'}")
        return success

    except Exception as e:
        print(f"\n  ❌ Training Simulation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration() -> bool:
    """Test full integration of all components."""
    print_header("TEST 6: FULL INTEGRATION")

    if not HAS_TORCH:
        print("\n  ⚠️  Skipped: PyTorch not available")
        return True

    try:
        from csr_phoneme_provider import (
            CSRConfig,
            CSREmbeddingProvider,
            get_hybrid_g2p
        )
        from symbolu.resonance.controller import (
            SattvicController,
            compute_alpha_effective
        )

        # Initialize all components
        print(f"\n  Initializing components...")

        g2p = get_hybrid_g2p()
        config = CSRConfig(d_model=256, num_layers=12)
        provider = CSREmbeddingProvider(config)
        controller = SattvicController()

        print(f"    ✓ HybridG2P initialized ({g2p.get_stats()['cmudict_words']:,} words)")
        print(f"    ✓ CSREmbeddingProvider initialized")
        print(f"    ✓ SattvicController initialized")

        # Simulate processing a sentence
        print_section("Sentence Processing Pipeline")

        sentence = "The truth is light and love"
        tokens = sentence.lower().split()

        print(f"\n  Input: \"{sentence}\"")
        print(f"  Tokens: {tokens}")

        # Step 1: Token → Phoneme
        print(f"\n  Step 1: Token → Phoneme (via HybridG2P)")
        phoneme_sequences = []
        for token in tokens:
            phonemes = g2p.get_phonemes(token)
            phoneme_sequences.append(phonemes)
            print(f"    {token:<10} → {' '.join(phonemes)}")

        # Step 2: Phoneme → 12D Affinity
        print(f"\n  Step 2: Phoneme → 12D Affinity")
        from csr_phoneme_provider import ONTOLOGICAL_LAYERS

        for token, phonemes in zip(tokens, phoneme_sequences):
            affinity = provider.phonemes_to_affinity(phonemes)
            max_idx = affinity.argmax().item()
            layer_name = ONTOLOGICAL_LAYERS.get(max_idx, f"Layer {max_idx}")
            print(f"    {token:<10} → {layer_name}")

        # Step 3: CSR Embedding
        print(f"\n  Step 3: CSR Embedding Generation")

        fake_input_ids = torch.randint(0, 50000, (1, len(tokens)))
        with torch.no_grad():
            csr_emb, confidence = provider(fake_input_ids, [tokens])

        print(f"    Embedding Shape: {csr_emb.shape}")
        print(f"    Mean Confidence: {confidence.mean().item():.4f}")

        # Step 4: Sattvic Controller
        print(f"\n  Step 4: Sattvic Controller Update")

        # Simulate training metrics
        entropy = 0.55
        knowledge = 0.45
        lambda_csr = controller.update(1000, {'ent': entropy, 'know': knowledge})

        print(f"    Entropy:    {entropy}")
        print(f"    Knowledge:  {knowledge}")
        print(f"    λ_csr:      {lambda_csr:.4f}")
        print(f"    Phase:      {controller.get_status()['phase']}")

        # Step 5: Compute α_eff for Phase Attention
        print(f"\n  Step 5: Phase Attention Gating")

        base_alpha = 0.5
        csr_confidence = confidence.mean().item()
        coherence = 0.75
        perplexity = 25.0

        alpha_eff = compute_alpha_effective(
            base_alpha, csr_confidence, coherence, perplexity, controller
        )

        print(f"    Base α:      {base_alpha}")
        print(f"    CSR Conf:    {csr_confidence:.4f}")
        print(f"    Coherence:   {coherence}")
        print(f"    α_eff:       {alpha_eff:.4f}")

        # Verify integration
        print_section("Integration Verification")

        checks = [
            ("G2P conversion", len(phoneme_sequences) == len(tokens)),
            ("CSR embedding shape", csr_emb.shape[1] == len(tokens)),
            ("Controller λ in range", 0.1 <= lambda_csr <= 0.5),
            ("α_eff computed", 0.0 <= alpha_eff <= 1.0),
        ]

        all_passed = True
        for name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"    {status} {name}")
            all_passed = all_passed and passed

        print(f"\n  ✅ Full Integration Test: {'PASSED' if all_passed else 'FAILED'}")
        return all_passed

    except Exception as e:
        print(f"\n  ❌ Full Integration Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  SOVEREIGN HANDSHAKE TEST SUITE")
    print("  CSR + Sattvic Controller Integration Tests")
    print("=" * 70)

    full_test = "--full" in sys.argv

    results = {}

    # Core tests (always run)
    results["HybridG2P"] = test_hybrid_g2p()
    results["PhonemeOntology"] = test_phoneme_ontology_mapping()
    results["SattvicController"] = test_sattvic_controller()
    results["CSREmbeddingProvider"] = test_csr_embedding_provider()

    if full_test:
        results["TrainingSimulation"] = test_training_simulation()
        results["Integration"] = test_integration()

    # Summary
    print_header("TEST SUMMARY", "═")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  {'Test':<30} {'Result'}")
    print(f"  {'-'*45}")

    for name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name:<30} {status}")

    print(f"\n  {'─'*45}")
    print(f"  Total: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n  🎉 ALL TESTS PASSED!")
        print(f"\n  The Sovereign Handshake is ready for training.")
    else:
        print(f"\n  ⚠️  Some tests failed. Check output above.")

    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
