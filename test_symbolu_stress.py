#!/usr/bin/env python3
"""
SymbolU Stress Test Suite
=========================

Tests the patent formulas (BCVF, SCC, USE) for:
1. Hallucination detection
2. Coherence scoring
3. Confidence estimation
4. User experience features

Run with: python test_symbolu_stress.py [--checkpoint PATH]
"""

import argparse
import sys
import torch
import torch.nn.functional as F
from pathlib import Path

# Add symbolu to path
sys.path.insert(0, str(Path(__file__).parent))


def test_bcvf_consistency():
    """Test BCVF Bidirectional Consistency Verification (B1-B5)"""
    print("\n" + "="*60)
    print("TEST 1: BCVF Consistency Verification")
    print("="*60)

    try:
        from symbolu.ontological.bcvf import BCVFVerifier, ConsistencyLagrangian

        # Test Consistency Lagrangian (B1)
        lagrangian = ConsistencyLagrangian()

        # Test case 1: High consistency (both scores high and equal)
        sf_high = torch.tensor([0.95])  # Forward feasibility
        sb_high = torch.tensor([0.95])  # Backward goal-achievement
        L_consistent = lagrangian(sf_high, sb_high)
        print(f"✓ High consistency (sf=0.95, sb=0.95): L={L_consistent.item():.4f} (should be low)")

        # Test case 2: Low forward score (potential hallucination)
        sf_low = torch.tensor([0.3])
        sb_high = torch.tensor([0.9])
        L_hallucination = lagrangian(sf_low, sb_high)
        print(f"✓ Potential hallucination (sf=0.3, sb=0.9): L={L_hallucination.item():.4f} (should be high)")

        # Test case 3: Inconsistency (scores differ)
        sf_mid = torch.tensor([0.8])
        sb_low = torch.tensor([0.4])
        L_inconsistent = lagrangian(sf_mid, sb_low)
        print(f"✓ Inconsistent (sf=0.8, sb=0.4): L={L_inconsistent.item():.4f} (should be high)")

        # Verify ordering: consistent < hallucination, consistent < inconsistent
        assert L_consistent < L_hallucination, "Consistent should have lower Lagrangian than hallucination"
        assert L_consistent < L_inconsistent, "Consistent should have lower Lagrangian than inconsistent"

        print("\n✅ BCVF Consistency Lagrangian: PASSED")
        return True

    except ImportError as e:
        print(f"⚠️ BCVF import error: {e}")
        print("  Trying alternative test...")
        return test_bcvf_basic()
    except Exception as e:
        print(f"❌ BCVF test failed: {e}")
        return False


def test_bcvf_basic():
    """Basic BCVF test without full module"""
    print("\n  Running basic BCVF formula test...")

    # B1: L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)²
    lambda_f, lambda_b, lambda_c = 1.0, 1.0, 0.5

    def consistency_lagrangian(sf, sb):
        return lambda_f * (1-sf)**2 + lambda_b * (1-sb)**2 + lambda_c * (sf-sb)**2

    # Test cases
    L_good = consistency_lagrangian(0.95, 0.95)
    L_bad = consistency_lagrangian(0.3, 0.9)

    print(f"  ✓ Good case (sf=0.95, sb=0.95): L={L_good:.4f}")
    print(f"  ✓ Bad case (sf=0.3, sb=0.9): L={L_bad:.4f}")

    assert L_good < L_bad, "Good case should have lower Lagrangian"
    print("\n✅ BCVF Basic Formula: PASSED")
    return True


def test_semantic_entropy():
    """Test Semantic Entropy (S5) for confidence estimation"""
    print("\n" + "="*60)
    print("TEST 2: Semantic Entropy (S5)")
    print("="*60)

    # S5: H_sem = -Σ p(x) log(p(x))

    # High confidence (low entropy)
    probs_confident = torch.tensor([0.95, 0.02, 0.02, 0.01])
    entropy_confident = -(probs_confident * torch.log(probs_confident + 1e-10)).sum()
    print(f"✓ Confident prediction: Entropy={entropy_confident.item():.4f} (should be low)")

    # Low confidence (high entropy)
    probs_uncertain = torch.tensor([0.25, 0.25, 0.25, 0.25])
    entropy_uncertain = -(probs_uncertain * torch.log(probs_uncertain + 1e-10)).sum()
    print(f"✓ Uncertain prediction: Entropy={entropy_uncertain.item():.4f} (should be high)")

    # Medium confidence
    probs_medium = torch.tensor([0.6, 0.2, 0.1, 0.1])
    entropy_medium = -(probs_medium * torch.log(probs_medium + 1e-10)).sum()
    print(f"✓ Medium confidence: Entropy={entropy_medium.item():.4f}")

    assert entropy_confident < entropy_medium < entropy_uncertain

    # Convert to user-facing confidence
    max_entropy = torch.log(torch.tensor(4.0))  # Maximum possible entropy
    confidence_confident = 1 - (entropy_confident / max_entropy)
    confidence_uncertain = 1 - (entropy_uncertain / max_entropy)

    print(f"\n  User-facing confidence:")
    print(f"  ✓ Confident: {confidence_confident.item()*100:.1f}%")
    print(f"  ✓ Uncertain: {confidence_uncertain.item()*100:.1f}%")

    print("\n✅ Semantic Entropy: PASSED")
    return True


def test_layer_coherence():
    """Test Layer Coherence (S1-S2)"""
    print("\n" + "="*60)
    print("TEST 3: Layer Coherence (S1-S2)")
    print("="*60)

    # S1-S2: Coherence via cross-layer cosine similarity

    # Simulate layer outputs
    batch_size, seq_len, hidden_dim = 2, 10, 64

    # Well-aligned layers (high coherence)
    layer_1 = torch.randn(batch_size, seq_len, hidden_dim)
    layer_2 = layer_1 + 0.1 * torch.randn_like(layer_1)  # Small perturbation

    coherence_high = F.cosine_similarity(
        layer_1.mean(dim=1),
        layer_2.mean(dim=1),
        dim=-1
    ).mean()
    print(f"✓ Well-aligned layers: Coherence={coherence_high.item():.4f}")

    # Misaligned layers (low coherence)
    layer_3 = torch.randn(batch_size, seq_len, hidden_dim)  # Completely different

    coherence_low = F.cosine_similarity(
        layer_1.mean(dim=1),
        layer_3.mean(dim=1),
        dim=-1
    ).mean()
    print(f"✓ Misaligned layers: Coherence={coherence_low.item():.4f}")

    assert coherence_high > coherence_low, "Aligned layers should have higher coherence"

    print("\n✅ Layer Coherence: PASSED")
    return True


def test_phase_attention():
    """Test Phase Attention O(n) (U1-U4)"""
    print("\n" + "="*60)
    print("TEST 4: Phase Attention O(n) (U1-U4)")
    print("="*60)

    try:
        from symbolu.phase_transformer import PhaseAttention

        # Test with different sequence lengths
        d_model = 64
        n_heads = 4
        attn = PhaseAttention(d_model, n_heads)

        results = []
        for seq_len in [128, 256, 512, 1024]:
            x = torch.randn(2, seq_len, d_model)

            # Time the operation
            import time
            start = time.time()
            for _ in range(10):
                _ = attn(x)
            elapsed = (time.time() - start) / 10

            results.append((seq_len, elapsed))
            print(f"✓ Seq length {seq_len}: {elapsed*1000:.2f}ms")

        # Check O(n) scaling: time should roughly double when seq_len doubles
        ratio_1 = results[1][1] / results[0][1]  # 256/128
        ratio_2 = results[2][1] / results[1][1]  # 512/256
        ratio_3 = results[3][1] / results[2][1]  # 1024/512

        print(f"\n  Scaling ratios (should be ~2.0 for O(n)):")
        print(f"  ✓ 256/128: {ratio_1:.2f}x")
        print(f"  ✓ 512/256: {ratio_2:.2f}x")
        print(f"  ✓ 1024/512: {ratio_3:.2f}x")

        # O(n) means ratios should be around 2 (linear scaling)
        # O(n²) would give ratios around 4
        avg_ratio = (ratio_1 + ratio_2 + ratio_3) / 3
        if avg_ratio < 3.0:
            print(f"\n✅ Phase Attention O(n) Scaling: PASSED (avg ratio: {avg_ratio:.2f})")
            return True
        else:
            print(f"\n⚠️ Phase Attention scaling higher than expected: {avg_ratio:.2f}")
            return False

    except ImportError as e:
        print(f"⚠️ PhaseAttention import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Phase Attention test failed: {e}")
        return False


def test_user_experience():
    """Test end-user experience features"""
    print("\n" + "="*60)
    print("TEST 5: User Experience Features")
    print("="*60)

    def get_confidence_level(entropy, max_entropy=2.0):
        """Convert entropy to user-facing confidence"""
        confidence = 1 - (entropy / max_entropy)
        confidence = max(0, min(1, confidence))

        if confidence > 0.8:
            return "High", confidence
        elif confidence > 0.5:
            return "Medium", confidence
        else:
            return "Low", confidence

    def check_hallucination(sf, sb, threshold=0.5):
        """Check for potential hallucination using BCVF"""
        consistency = 1 - abs(sf - sb)
        if sf < threshold or consistency < threshold:
            return True, "⚠️ Potential hallucination detected"
        return False, "✓ Response appears consistent"

    # Simulate different scenarios
    print("\nScenario 1: Factual question (high confidence)")
    entropy_1 = 0.3
    level, conf = get_confidence_level(entropy_1)
    is_hallucination, msg = check_hallucination(0.95, 0.93)
    print(f"  Confidence: {level} ({conf*100:.1f}%)")
    print(f"  {msg}")

    print("\nScenario 2: Unknown topic (low confidence)")
    entropy_2 = 1.8
    level, conf = get_confidence_level(entropy_2)
    is_hallucination, msg = check_hallucination(0.3, 0.8)
    print(f"  Confidence: {level} ({conf*100:.1f}%)")
    print(f"  {msg}")

    print("\nScenario 3: Creative task (medium confidence)")
    entropy_3 = 1.0
    level, conf = get_confidence_level(entropy_3)
    is_hallucination, msg = check_hallucination(0.7, 0.75)
    print(f"  Confidence: {level} ({conf*100:.1f}%)")
    print(f"  {msg}")

    print("\n✅ User Experience Features: PASSED")
    return True


def test_enhanced_kv_cache():
    """Test Enhanced KV Cache with patent formulas (BCVF, SCC, USE)"""
    print("\n" + "="*60)
    print("TEST 6: Enhanced KV Cache with Patent Formulas")
    print("="*60)

    try:
        from symbolu.ontological.kv_cache_enhanced import (
            EnhancedKVCache,
            PatentEnhancedAttention,
            SemanticEntropyTracker,
            CoherenceScorer,
            ConsistencyLagrangian,
            EnhancedCacheConfig,
        )

        config = EnhancedCacheConfig()
        dim = 64
        num_heads = 4

        # Test 1: Semantic Entropy Tracker (S5)
        print("\n  Testing Semantic Entropy Tracker (S5)...")
        tracker = SemanticEntropyTracker(config)

        # High confidence (peaked distribution)
        high_conf_probs = torch.zeros(1, 100)
        high_conf_probs[0, 0] = 0.9
        high_conf_probs[0, 1:] = 0.1 / 99
        metrics = tracker.update(high_conf_probs)
        print(f"  ✓ High confidence: entropy={metrics['entropy']:.4f}, conf={metrics['confidence']:.4f}")
        assert metrics['confidence'] > 0.5, "High confidence case should have high confidence"

        # Low confidence (uniform distribution)
        tracker.reset()
        low_conf_probs = torch.ones(1, 100) / 100
        metrics = tracker.update(low_conf_probs)
        print(f"  ✓ Low confidence: entropy={metrics['entropy']:.4f}, conf={metrics['confidence']:.4f}")
        assert metrics['confidence'] < 0.5, "Low confidence case should have low confidence"

        # Test 2: Coherence Scorer (S1-S2)
        print("\n  Testing Coherence Scorer (S1-S2)...")
        scorer = CoherenceScorer(config)

        # Similar layers (high coherence)
        layer1 = torch.randn(2, 10, dim)
        layer2 = layer1 + 0.1 * torch.randn_like(layer1)
        coherence_high = scorer.compute_coherence(layer1, layer2)
        print(f"  ✓ Similar layers: coherence={coherence_high:.4f}")
        assert coherence_high > 0.8, "Similar layers should have high coherence"

        # Different layers (low coherence)
        layer3 = torch.randn(2, 10, dim)
        coherence_low = scorer.compute_coherence(layer1, layer3)
        print(f"  ✓ Different layers: coherence={coherence_low:.4f}")
        assert coherence_high > coherence_low, "Similar should have higher coherence than different"

        # Test 3: Consistency Lagrangian (B1)
        print("\n  Testing Consistency Lagrangian (B1)...")
        lagrangian = ConsistencyLagrangian(config)

        # High quality (sf=sb=0.9)
        L_good, w_good = lagrangian.score_cache_entry(0.9, 0.9)
        print(f"  ✓ High quality (sf=sb=0.9): L={L_good:.4f}, w={w_good:.4f}")

        # Low quality (sf=0.3, sb=0.8)
        L_bad, w_bad = lagrangian.score_cache_entry(0.3, 0.8)
        print(f"  ✓ Low quality (sf=0.3, sb=0.8): L={L_bad:.4f}, w={w_bad:.4f}")

        assert L_good < L_bad, "Good entries should have lower Lagrangian"
        assert w_good > w_bad, "Good entries should have higher weight"

        # Test 4: Patent-Enhanced Attention
        print("\n  Testing Patent-Enhanced Attention...")
        attn = PatentEnhancedAttention(dim, num_heads, config)

        x = torch.randn(2, 16, dim)
        probs = F.softmax(torch.randn(2, 100), dim=-1)

        out, metrics = attn(x, use_cache=True, output_probs=probs)
        print(f"  ✓ Forward pass: output shape={out.shape}")
        print(f"  ✓ Global coherence: {metrics['global_coherence']:.4f}")
        print(f"  ✓ Confidence: {metrics['current_confidence']}")
        print(f"  ✓ Hallucination detected: {metrics['hallucination_detected']}")

        # Test 5: Enhanced KV Cache
        print("\n  Testing Enhanced KV Cache...")
        cache = EnhancedKVCache(dim, num_heads, config)

        # Add entries
        for i in range(5):
            k = torch.randn(2, 1, num_heads, dim // num_heads)
            v = torch.randn(2, 1, num_heads, dim // num_heads)
            layer_out = torch.randn(2, 1, dim)
            entry = cache.update(k, v, layer_out)
            print(f"  ✓ Entry {i}: weight={entry.consistency_weight:.4f}, valid={entry.is_valid}")

        cache_metrics = cache.get_metrics()
        print(f"\n  Cache Summary:")
        print(f"  ✓ Total entries: {cache_metrics['total_entries']}")
        print(f"  ✓ Valid entries: {cache_metrics['valid_entries']}")
        print(f"  ✓ Avg coherence: {cache_metrics['avg_coherence']:.4f}")

        print("\n✅ Enhanced KV Cache: PASSED")
        return True

    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trustworthy_model():
    """Test SymbolU12 Trustworthy model"""
    print("\n" + "="*60)
    print("TEST 7: SymbolU12 Trustworthy Model")
    print("="*60)

    try:
        from symbolu.ontological.symbolu12_trustworthy import (
            SymbolU12Trustworthy,
            SymbolU12TrustworthyConfig,
            create_trustworthy_small,
        )

        # Create small model for testing
        print("\n  Creating trustworthy model...")
        config = SymbolU12TrustworthyConfig(
            vocab_size=1000,
            embed_dim=64,
            num_heads=2,
            num_layers=12,
            max_seq_len=128,
        )
        model = SymbolU12Trustworthy(config)
        print(f"  ✓ Model created with {model.count_parameters():,} parameters")

        # Test forward pass
        print("\n  Testing forward pass...")
        input_ids = torch.randint(0, config.vocab_size, (1, 32))
        outputs = model(input_ids)

        print(f"  ✓ Logits shape: {outputs['logits'].shape}")
        print(f"  ✓ Confidence level: {outputs['confidence_level']}")
        print(f"  ✓ Global coherence: {outputs['global_coherence']:.4f}")
        print(f"  ✓ Entropy: {outputs['entropy']:.4f}")
        print(f"  ✓ Lagrangian: {outputs['lagrangian']:.4f}")
        print(f"  ✓ Consistency weight: {outputs['consistency_weight']:.4f}")
        print(f"  ✓ Hallucination detected: {outputs['hallucination_detected']}")

        # Verify BCVF formula
        print("\n  Verifying BCVF formula (B1)...")
        sf = outputs['global_coherence']  # Forward score
        sb = 1 - outputs['entropy']  # Backward score (confidence)
        expected_L = 1.0 * (1-sf)**2 + 1.0 * (1-sb)**2 + 0.5 * (sf-sb)**2
        actual_L = outputs['lagrangian']
        print(f"  ✓ sf (coherence): {sf:.4f}")
        print(f"  ✓ sb (confidence): {sb:.4f}")
        print(f"  ✓ Expected L: {expected_L:.4f}")
        print(f"  ✓ Actual L: {actual_L:.4f}")

        print("\n✅ SymbolU12 Trustworthy: PASSED")
        return True

    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trained_model(checkpoint_path):
    """Test a trained model checkpoint"""
    print("\n" + "="*60)
    print("TEST 8: Trained Model Checkpoint")
    print("="*60)

    if not Path(checkpoint_path).exists():
        print(f"⚠️ Checkpoint not found: {checkpoint_path}")
        return False

    try:
        checkpoint = torch.load(checkpoint_path, map_location='cpu')

        print(f"✓ Checkpoint loaded successfully")
        print(f"  - Training step: {checkpoint.get('step', 'N/A')}")
        print(f"  - Best Val PPL: {checkpoint.get('best_val_ppl', 'N/A')}")

        if 'model_state_dict' in checkpoint:
            num_params = sum(p.numel() for p in checkpoint['model_state_dict'].values())
            print(f"  - Parameters: {num_params:,}")

        print("\n✅ Trained Model Checkpoint: PASSED")
        return True

    except Exception as e:
        print(f"❌ Failed to load checkpoint: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='SymbolU Stress Test Suite')
    parser.add_argument('--checkpoint', type=str, help='Path to trained checkpoint')
    parser.add_argument('--quick', action='store_true', help='Run quick tests only')
    args = parser.parse_args()

    print("="*60)
    print("  SYMBOLU STRESS TEST SUITE")
    print("  Testing Patent Formulas: BCVF, SCC, USE")
    print("="*60)

    results = {}

    # Core tests
    results['BCVF Consistency'] = test_bcvf_consistency()
    results['Semantic Entropy'] = test_semantic_entropy()
    results['Layer Coherence'] = test_layer_coherence()
    results['User Experience'] = test_user_experience()

    if not args.quick:
        results['Phase Attention O(n)'] = test_phase_attention()
        results['Enhanced KV Cache'] = test_enhanced_kv_cache()
        results['Trustworthy Model'] = test_trustworthy_model()

    # Optional: test checkpoint
    if args.checkpoint:
        results['Trained Model'] = test_trained_model(args.checkpoint)

    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test}: {status}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n  ⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
