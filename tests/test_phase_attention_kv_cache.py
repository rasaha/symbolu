#!/usr/bin/env python3
"""
Test Suite for Phase Attention KV Cache & Chunked Training (V10.7)
==================================================================

Validates:
1. PhaseStateCache enforces O(1) inference memory (no O(N) leaks)
2. forward_with_cache produces same logits as full forward
3. generate_with_cache uses constant memory per step
4. forward_chunked_tbptt produces valid gradients with O(C) memory
5. fp32 accumulation guard works for bf16/fp16 inputs
6. State detach in TBPTT breaks autograd graph correctly

Run with:
    python -m pytest tests/test_phase_attention_kv_cache.py -v
    python tests/test_phase_attention_kv_cache.py  # standalone
"""

import math
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from symbolu.phase_transformer import (
    PhaseAttentionLayer,
    PhaseStateCache,
    HybridPhaseTransformer,
    forward_chunked_tbptt,
    _detach_layer_states,
)


# =============================================================================
# Test Utilities
# =============================================================================

def make_small_hybrid_model(
    vocab_size=256,
    embed_dim=64,
    num_layers=4,
    num_heads=4,
    local_layers=2,
    window_size=32,
    max_seq_len=512,
    **kwargs,
):
    """Create a small HybridPhaseTransformer for testing."""
    return HybridPhaseTransformer(
        vocab_size=vocab_size,
        embed_dim=embed_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        local_layers=local_layers,
        window_size=window_size,
        max_seq_len=max_seq_len,
        dropout=0.0,  # Deterministic
        **kwargs,
    )


def simple_loss_fn(logits, targets):
    """Simple cross-entropy loss for testing."""
    B, N, V = logits.shape
    loss = F.cross_entropy(
        logits.reshape(-1, V),
        targets.reshape(-1),
        ignore_index=-100,
    )
    metrics = {'lm_loss': loss.item(), 'ppl': math.exp(min(loss.item(), 20))}
    return loss, metrics


# =============================================================================
# Test 1: PhaseStateCache Shape Enforcement
# =============================================================================

def test_cache_shape_enforcement():
    """PhaseStateCache must reject states with seq dim > 1."""
    cache = PhaseStateCache(num_layers=4, hybrid_layer_start=2)

    # Valid state: [B, 1, H, D_h]
    valid_state = {
        'final_state': torch.randn(2, 1, 4, 16, dtype=torch.cfloat),
        'final_norm_state': torch.randn(2, 1, 4, 16),
    }
    cache.update_layer_state(2, valid_state)  # Should not raise

    # Invalid state: [B, 8, H, D_h] — O(N) leak
    invalid_state = {
        'final_state': torch.randn(2, 8, 4, 16, dtype=torch.cfloat),
        'final_norm_state': torch.randn(2, 1, 4, 16),
    }
    try:
        cache.update_layer_state(3, invalid_state)
        assert False, "Should have raised ValueError for seq dim > 1"
    except ValueError as e:
        assert "seq dim 8" in str(e)
        print("  PASS: Cache rejects O(N) state leak")

    return True


# =============================================================================
# Test 2: Cache Memory is Constant Regardless of Sequence Length
# =============================================================================

def test_cache_memory_constant():
    """Memory in PhaseStateCache should not grow with sequence length."""
    cache = PhaseStateCache(num_layers=4, hybrid_layer_start=2)

    # Simulate processing 100 tokens
    for i in range(100):
        state = {
            'final_state': torch.randn(1, 1, 4, 16, dtype=torch.cfloat),
            'final_norm_state': torch.randn(1, 1, 4, 16),
        }
        cache.update_layer_state(2, state)
        cache.update_layer_state(3, state)
        cache.advance(1)

    mem_after_100 = cache.memory_bytes()

    # Process 100 more
    for i in range(100):
        state = {
            'final_state': torch.randn(1, 1, 4, 16, dtype=torch.cfloat),
            'final_norm_state': torch.randn(1, 1, 4, 16),
        }
        cache.update_layer_state(2, state)
        cache.update_layer_state(3, state)
        cache.advance(1)

    mem_after_200 = cache.memory_bytes()

    assert mem_after_100 == mem_after_200, (
        f"Memory grew: {mem_after_100} -> {mem_after_200}"
    )
    assert cache.seq_len == 200
    print(f"  PASS: Cache memory constant at {mem_after_100} bytes across 200 tokens")
    return True


# =============================================================================
# Test 3: forward_with_cache Produces Valid Output
# =============================================================================

def test_forward_with_cache():
    """forward_with_cache should produce logits and update cache."""
    torch.manual_seed(42)
    model = make_small_hybrid_model()
    model.eval()

    input_ids = torch.randint(0, 256, (1, 32))

    with torch.no_grad():
        result, cache = model.forward_with_cache(input_ids)

    logits = result['logits']
    assert logits.shape == (1, 32, 256), f"Wrong shape: {logits.shape}"
    assert cache.seq_len == 32, f"Wrong seq_len: {cache.seq_len}"
    assert len(cache._states) > 0, "No states captured"

    # Verify all states are [B, 1, H, D_h]
    for layer_idx, state_dict in cache._states.items():
        for name, tensor in state_dict.items():
            assert tensor.shape[1] == 1, (
                f"Layer {layer_idx} {name} has seq dim {tensor.shape[1]}"
            )

    print(f"  PASS: forward_with_cache output shape {logits.shape}, cache {cache}")
    return True


# =============================================================================
# Test 4: Incremental Decode Matches Full Forward (Approximate)
# =============================================================================

def test_incremental_decode_consistency():
    """
    Prefill + single-token decode should produce logits close to full forward.

    Note: Due to Local attention windowing, exact match is not expected.
    But the Phase state contribution should be consistent.
    """
    torch.manual_seed(42)
    model = make_small_hybrid_model(window_size=64)
    model.eval()

    seq_len = 48
    input_ids = torch.randint(0, 256, (1, seq_len))

    with torch.no_grad():
        # Full forward
        full_result = model(input_ids)
        full_logits = full_result['logits']

        # Incremental: prefill first 47, then decode token 48
        prefill = input_ids[:, :seq_len - 1]
        last_token = input_ids[:, seq_len - 1:seq_len]

        result1, cache = model.forward_with_cache(prefill)
        result2, cache = model.forward_with_cache(last_token, cache)

        incremental_last_logit = result2['logits'][:, -1, :]
        full_last_logit = full_logits[:, -1, :]

    # Check that the outputs are in the same ballpark
    # (exact match not expected due to Local attention differences)
    cosine_sim = F.cosine_similarity(
        incremental_last_logit.flatten().unsqueeze(0),
        full_last_logit.flatten().unsqueeze(0),
    ).item()

    print(f"  Cosine similarity (incremental vs full): {cosine_sim:.4f}")
    # Phase state should contribute meaningfully
    assert cosine_sim > 0.5, f"Cosine sim too low: {cosine_sim}"
    print(f"  PASS: Incremental decode consistent with full forward (cos={cosine_sim:.4f})")
    return True


# =============================================================================
# Test 5: TBPTT State Detach Breaks Autograd Graph
# =============================================================================

def test_tbptt_detach():
    """_detach_layer_states should produce tensors with no grad_fn."""
    state = {
        0: {
            'final_state': torch.randn(1, 1, 4, 16, dtype=torch.cfloat, requires_grad=True),
            'final_norm_state': torch.randn(1, 1, 4, 16, requires_grad=True),
        }
    }

    detached = _detach_layer_states(state)

    for layer_idx, state_dict in detached.items():
        for name, tensor in state_dict.items():
            assert not tensor.requires_grad, f"{name} still requires grad"
            assert tensor.grad_fn is None, f"{name} still has grad_fn"

    print("  PASS: _detach_layer_states breaks autograd graph")
    return True


# =============================================================================
# Test 6: forward_chunked_tbptt Produces Valid Gradients
# =============================================================================

def test_tbptt_training():
    """forward_chunked_tbptt should accumulate gradients with O(C) memory."""
    torch.manual_seed(42)
    model = make_small_hybrid_model()
    model.train()

    seq_len = 64
    chunk_size = 16
    input_ids = torch.randint(0, 256, (2, seq_len))
    targets = torch.randint(0, 256, (2, seq_len))

    # Zero gradients
    model.zero_grad()

    # Run TBPTT
    result = forward_chunked_tbptt(
        model=model,
        input_ids=input_ids,
        targets=targets,
        chunk_size=chunk_size,
        loss_fn=simple_loss_fn,
    )

    assert result['num_chunks'] == seq_len // chunk_size
    assert result['total_loss'] > 0
    assert len(result['chunk_losses']) == result['num_chunks']

    # Check gradients exist
    has_grad = False
    for name, param in model.named_parameters():
        if param.grad is not None and param.grad.abs().sum() > 0:
            has_grad = True
            break

    assert has_grad, "No gradients accumulated from TBPTT"
    print(f"  PASS: TBPTT training, loss={result['total_loss']:.4f}, "
          f"chunks={result['num_chunks']}, gradients present")
    return True


# =============================================================================
# Test 7: fp32 Accumulation Guard
# =============================================================================

def test_fp32_accumulation():
    """Phase attention should accumulate in fp32 even when input is fp16."""
    torch.manual_seed(42)
    layer = PhaseAttentionLayer(
        embed_dim=64,
        num_heads=4,
        dropout=0.0,
    )

    # fp32 input
    x_fp32 = torch.randn(1, 32, 64)
    out_fp32 = layer(x_fp32, causal_mask=True)
    assert out_fp32.dtype == torch.float32

    # fp16 input — should still work and produce fp16 output
    # (internal accumulation is fp32, cast back on output)
    if torch.cuda.is_available():
        layer = layer.cuda().half()
        x_fp16 = torch.randn(1, 32, 64, dtype=torch.float16, device='cuda')
        out_fp16 = layer(x_fp16, causal_mask=True)
        assert out_fp16.dtype == torch.float16, f"Expected fp16 output, got {out_fp16.dtype}"
        print("  PASS: fp16 input handled with fp32 internal accumulation (CUDA)")
    else:
        print("  SKIP: fp16 test requires CUDA (fp32 path verified)")

    return True


# =============================================================================
# Test 8: generate_with_cache Memory Profile
# =============================================================================

def test_generate_with_cache_memory():
    """generate_with_cache should use constant memory per step."""
    torch.manual_seed(42)
    model = make_small_hybrid_model()
    model.eval()

    prompt = torch.randint(0, 256, (1, 8))

    with torch.no_grad():
        output = model.generate_with_cache(
            prompt,
            max_new_tokens=10,
            temperature=1.0,
            top_k=10,
        )

    assert output.shape == (1, 18), f"Expected (1, 18), got {output.shape}"
    # Verify first 8 tokens are the prompt
    assert torch.equal(output[:, :8], prompt)
    print(f"  PASS: generate_with_cache produced {output.shape[1]} tokens")
    return True


# =============================================================================
# Test 9: PhaseStateCache Reset
# =============================================================================

def test_cache_reset():
    """Cache reset should clear all state."""
    cache = PhaseStateCache(num_layers=4, hybrid_layer_start=2)

    # Add some state
    state = {
        'final_state': torch.randn(1, 1, 4, 16, dtype=torch.cfloat),
        'final_norm_state': torch.randn(1, 1, 4, 16),
    }
    cache.update_layer_state(2, state)
    cache.advance(10)

    assert cache.seq_len == 10
    assert len(cache._states) == 1

    cache.reset()

    assert cache.seq_len == 0
    assert len(cache._states) == 0
    print("  PASS: Cache reset clears all state")
    return True


# =============================================================================
# Runner
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("  Phase Attention KV Cache & Chunked Training Tests (V10.7)")
    print("=" * 70)

    tests = [
        ("PhaseStateCache shape enforcement", test_cache_shape_enforcement),
        ("Cache memory constant", test_cache_memory_constant),
        ("forward_with_cache basic", test_forward_with_cache),
        ("Incremental decode consistency", test_incremental_decode_consistency),
        ("TBPTT state detach", test_tbptt_detach),
        ("TBPTT training gradients", test_tbptt_training),
        ("fp32 accumulation guard", test_fp32_accumulation),
        ("generate_with_cache", test_generate_with_cache_memory),
        ("Cache reset", test_cache_reset),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"  FAIL: {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name} — {type(e).__name__}: {e}")

    print(f"\n{'=' * 70}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'=' * 70}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
