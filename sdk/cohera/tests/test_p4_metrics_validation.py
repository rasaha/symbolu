"""P4 tests: distillation + FSCS gate telemetry, validation utilities."""

import math

import pytest

from cohera import (
    DistillationMetrics,
    FSCSGateMetrics,
    apply_rope_reference,
    assert_no_mask_leak,
    attention_mask_leak_positions,
    bf16_coherence_rel_error,
    get_runtime_hooks,
    gqa_broadcast_parity,
    gqa_broadcast_reference,
    record_distillation,
    record_fscs_gate,
    record_per_layer_coherence,
    rope_inv_freqs,
    rope_match_reference,
)


# ----- Distillation telemetry -----

def test_distillation_metrics_defaults():
    m = DistillationMetrics()
    assert m.teacher_ce == 0.0
    assert m.alpha_kl + m.alpha_ce == 1.0
    assert m.student_teacher_gap == 0.0


def test_distillation_gap_is_signed():
    m = DistillationMetrics(teacher_ce=1.0, student_ce=1.5)
    assert math.isclose(m.student_teacher_gap, 0.5)
    m.student_ce = 0.7
    assert m.student_teacher_gap < 0


def test_record_distillation_publishes_to_runtime_hooks():
    hooks = get_runtime_hooks()
    hooks.reset()
    m = DistillationMetrics(teacher_ce=1.2, student_ce=1.4, kl_div=0.3,
                            total_loss=0.85, tokens=2048)
    record_distillation(m)
    assert hooks.distillation is m
    assert hooks.to_dict()["distillation"]["tokens"] == 2048


def test_record_distillation_rejects_wrong_type():
    with pytest.raises(TypeError):
        record_distillation("not a metrics object")


# ----- FSCS gate telemetry -----

def test_fscs_gate_metrics_append_per_layer():
    hooks = get_runtime_hooks()
    hooks.reset()
    for idx in range(4):
        record_fscs_gate(FSCSGateMetrics(
            layer_idx=idx,
            gate_fraction=0.1 * (idx + 1),
            mean_coherence=0.8,
            tau=0.5,
        ))
    assert len(hooks.fscs_gate_per_layer) == 4
    assert [m.layer_idx for m in hooks.fscs_gate_per_layer] == [0, 1, 2, 3]


def test_fscs_gate_metrics_reset_clears():
    hooks = get_runtime_hooks()
    hooks.reset()
    record_fscs_gate(FSCSGateMetrics(layer_idx=0))
    assert len(hooks.fscs_gate_per_layer) == 1
    hooks.reset()
    assert hooks.fscs_gate_per_layer == []


def test_record_fscs_gate_rejects_wrong_type():
    with pytest.raises(TypeError):
        record_fscs_gate({"layer_idx": 0})


def test_record_per_layer_coherence_replaces_previous():
    hooks = get_runtime_hooks()
    hooks.reset()
    record_per_layer_coherence([0.1, 0.2, 0.3])
    assert hooks.coherence_per_layer == [0.1, 0.2, 0.3]
    record_per_layer_coherence([0.9], state_delta_per_layer=[0.5])
    assert hooks.coherence_per_layer == [0.9]
    assert hooks.state_delta_per_layer == [0.5]


# ----- GQA broadcast parity -----

def test_gqa_broadcast_reference_matches_repeat_interleave():
    # seq=2, num_kv_heads=2, head_dim=3
    kv = [
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        [[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
    ]
    out = gqa_broadcast_reference(kv, num_heads=4)
    # Each KV head repeated twice -> num_heads=4
    assert len(out) == 2
    assert len(out[0]) == 4
    assert out[0][0] == [1.0, 2.0, 3.0]
    assert out[0][1] == [1.0, 2.0, 3.0]
    assert out[0][2] == [4.0, 5.0, 6.0]
    assert out[0][3] == [4.0, 5.0, 6.0]
    # Parity against itself
    assert gqa_broadcast_parity(out, kv, num_heads=4)


def test_gqa_broadcast_mistral_7b_shape():
    # 1 token, 8 KV heads of head_dim=4, broadcast to 32 heads
    kv = [[[float(h)] * 4 for h in range(8)]]
    out = gqa_broadcast_reference(kv, num_heads=32)
    assert len(out[0]) == 32
    # Group size = 4; heads 0..3 share KV head 0, etc.
    for q in range(32):
        assert out[0][q] == [float(q // 4)] * 4


def test_gqa_broadcast_rejects_bad_divisibility():
    kv = [[[1.0], [2.0], [3.0]]]
    with pytest.raises(ValueError, match="divisible"):
        gqa_broadcast_reference(kv, num_heads=4)


def test_gqa_parity_detects_mismatch():
    kv = [[[1.0, 2.0], [3.0, 4.0]]]
    good = gqa_broadcast_reference(kv, num_heads=4)
    bad = [[list(good[0][0]), list(good[0][1]), list(good[0][2]), [9.0, 9.0]]]
    assert not gqa_broadcast_parity(bad, kv, num_heads=4)


# ----- RoPE reference -----

def test_rope_inv_freqs_mistral_default():
    freqs = rope_inv_freqs(128, base=10000.0)
    assert len(freqs) == 64
    assert math.isclose(freqs[0], 1.0)                    # base^0
    assert freqs[-1] < freqs[0]                            # monotonically decreasing


def test_rope_position_zero_is_identity():
    x = [float(i) for i in range(8)]
    freqs = rope_inv_freqs(8, base=10000.0)
    out = apply_rope_reference(x, position=0, rope_dim=8, inv_freqs=freqs)
    # theta = 0 -> cos=1, sin=0 -> rotation is identity
    for a, b in zip(out, x):
        assert math.isclose(a, b)


def test_rope_matches_complex_rotation_formula():
    # Single pair (head_dim=2, rope_dim=2) at position 3 with freq 0.1
    x = [1.0, 0.0]
    freqs = [0.1]
    out = apply_rope_reference(x, position=3, rope_dim=2, inv_freqs=freqs)
    theta = 3 * 0.1
    assert math.isclose(out[0], math.cos(theta), abs_tol=1e-12)
    assert math.isclose(out[1], math.sin(theta), abs_tol=1e-12)


def test_rope_upper_region_passthrough():
    # head_dim=6, rope_dim=4: elements 4 and 5 are untouched
    x = [0.5] * 6
    freqs = rope_inv_freqs(4, base=10000.0)
    out = apply_rope_reference(x, position=7, rope_dim=4, inv_freqs=freqs)
    assert math.isclose(out[4], 0.5)
    assert math.isclose(out[5], 0.5)


def test_rope_match_reference_helper_detects_drift():
    x = [1.0, 2.0, 3.0, 4.0]
    freqs = rope_inv_freqs(4, base=10000.0)
    ref = apply_rope_reference(x, position=5, rope_dim=4, inv_freqs=freqs)
    assert rope_match_reference(ref, x, 5, 4, freqs)
    # Mutate one entry well outside the 1e-6 budget
    broken = list(ref)
    broken[0] += 1e-3
    assert not rope_match_reference(broken, x, 5, 4, freqs)


# ----- BF16 coherence -----

def test_bf16_coherence_within_budget_aligned_phases():
    # Perfect alignment -> coherence 1; BF16 round-trip should stay within 1%
    phases = [0.0] * 64
    fp32, bf16, rel = bf16_coherence_rel_error(phases)
    assert math.isclose(fp32, 1.0, abs_tol=1e-12)
    assert math.isclose(bf16, 1.0, rel_tol=1e-3)
    assert rel < 0.01


def test_bf16_coherence_within_budget_clustered_phases():
    # Small deterministic jitter around 0 -> high (non-degenerate) coherence.
    # This is the regime phase attention actually operates in post-sync.
    phases = [0.3 * math.sin(i) for i in range(128)]
    fp32, bf16, rel = bf16_coherence_rel_error(phases)
    assert fp32 > 0.5, f"need meaningfully non-zero coherence, got {fp32}"
    assert rel < 0.01, f"BF16 rel error {rel} exceeded 1% budget"


def test_bf16_empty_sequence_is_zero():
    fp32, bf16, rel = bf16_coherence_rel_error([])
    assert fp32 == 0.0
    assert bf16 == 0.0
    assert rel == 0.0


# ----- Causal / sliding-window leak detection -----

def test_causal_mask_clean():
    # Lower-triangular weights, zero above diagonal
    w = [[1.0, 0.0, 0.0],
         [1.0, 1.0, 0.0],
         [1.0, 1.0, 1.0]]
    assert attention_mask_leak_positions(w, causal=True) == []
    assert_no_mask_leak(w, causal=True)


def test_causal_mask_detects_future_leak():
    w = [[1.0, 0.1, 0.0],   # position 0 sees position 1  -> LEAK
         [1.0, 1.0, 0.0],
         [1.0, 1.0, 1.0]]
    leaks = attention_mask_leak_positions(w, causal=True)
    assert (0, 1) in leaks
    with pytest.raises(AssertionError, match="leak"):
        assert_no_mask_leak(w, causal=True)


def test_sliding_window_drops_old_tokens():
    # window = 2: position 3 should only see {2, 3}
    w = [[1.0, 0.0, 0.0, 0.0],
         [1.0, 1.0, 0.0, 0.0],
         [0.0, 1.0, 1.0, 0.0],
         [0.0, 0.0, 1.0, 1.0]]
    assert attention_mask_leak_positions(
        w, causal=True, window_size=2,
    ) == []


def test_sliding_window_detects_far_past_leak():
    # window = 2: position 3 must not reach position 0 or 1
    w = [[1.0, 0.0, 0.0, 0.0],
         [1.0, 1.0, 0.0, 0.0],
         [0.0, 1.0, 1.0, 0.0],
         [0.2, 0.0, 1.0, 1.0]]  # (3, 0) violates
    leaks = attention_mask_leak_positions(w, causal=True, window_size=2)
    assert (3, 0) in leaks
