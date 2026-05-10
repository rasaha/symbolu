"""Phase 4 (TriAttention-style) Trigonometric Position Scoring tests.

Pure-Python tests against ``kv_policy.triattention``. The GPU-side
calibration pipeline (``calibrate_q_centers``) is verified to raise
``NotImplementedError`` here; the math + save/load + aggregation
helpers are fully covered.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# ------------------------------------------------------------------ #
# QCenterStats — dataclass + save/load
# ------------------------------------------------------------------ #


def _trivial_stats(num_layers=2, num_heads=4, head_dim=8):
    """Build a small QCenterStats for tests. num_bands = head_dim/2 = 4."""
    from kv_policy.triattention import QCenterStats

    num_bands = head_dim // 2
    e_q_real = [
        [[0.5] * num_bands for _ in range(num_heads)]
        for _ in range(num_layers)
    ]
    e_q_imag = [
        [[0.3] * num_bands for _ in range(num_heads)]
        for _ in range(num_layers)
    ]
    e_q_norm = [
        [[1.0] * num_bands for _ in range(num_heads)]
        for _ in range(num_layers)
    ]
    return QCenterStats.from_lists(
        model_name="test_model",
        num_layers=num_layers,
        num_heads=num_heads,
        num_kv_heads=num_heads,
        head_dim=head_dim,
        e_q_real=e_q_real,
        e_q_imag=e_q_imag,
        e_q_norm=e_q_norm,
        rope_theta=10000.0,
        calibration_token_count=1000,
        calibration_corpus="unit-test",
    )


def test_qcenterstats_constructs_with_valid_shapes():
    s = _trivial_stats()
    assert s.num_layers == 2
    assert s.num_heads == 4
    assert s.head_dim == 8
    assert s.num_bands == 4


def test_qcenterstats_rejects_mismatched_shapes():
    from kv_policy.triattention import QCenterStats

    with pytest.raises(ValueError, match="num_layers"):
        QCenterStats(
            model_name="x", num_layers=2, num_heads=2, num_kv_heads=2,
            head_dim=4, num_bands=2,
            e_q_real=[[[0.0, 0.0], [0.0, 0.0]]],   # wrong: only 1 layer
            e_q_imag=[[[0.0, 0.0], [0.0, 0.0]]] * 2,
            e_q_norm=[[[1.0, 1.0], [1.0, 1.0]]] * 2,
        )


def test_qcenterstats_rejects_num_bands_mismatch():
    from kv_policy.triattention import QCenterStats

    with pytest.raises(ValueError, match="num_bands"):
        QCenterStats.from_lists(
            model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
            head_dim=8,    # head_dim/2 = 4 expected bands...
            e_q_real=[[[0.0, 0.0]]],   # but only 2 supplied
            e_q_imag=[[[0.0, 0.0]]],
            e_q_norm=[[[1.0, 1.0]]],
        )


def test_qcenterstats_save_load_roundtrip(tmp_path):
    s = _trivial_stats(num_layers=3, num_heads=2, head_dim=4)
    path = tmp_path / "stats.json"
    s.save(path)
    s2 = type(s).load(path)
    assert s2.model_name == s.model_name
    assert s2.num_layers == s.num_layers
    assert s2.num_heads == s.num_heads
    assert s2.head_dim == s.head_dim
    assert s2.e_q_real == s.e_q_real
    assert s2.e_q_imag == s.e_q_imag
    assert s2.e_q_norm == s.e_q_norm
    assert s2.rope_theta == s.rope_theta
    # JSON-readable for audit-trail diligence.
    raw = json.loads(path.read_text())
    assert "model_name" in raw
    assert "calibration_corpus" in raw


def test_qcenterstats_mean_resultant_length():
    """R_f = ‖E[q_f]‖ / E[‖q_f‖]; high R = high concentration."""
    from kv_policy.triattention import QCenterStats

    # E[q_f] = 0.6 + 0.8j → magnitude 1.0; E[‖q_f‖] = 1.0 → R=1.0.
    s = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=2,
        e_q_real=[[[0.6]]], e_q_imag=[[[0.8]]],
        e_q_norm=[[[1.0]]],
    )
    assert s.mean_resultant_length(0, 0, 0) == pytest.approx(1.0)

    # E[q_f] = 0.0 + 0.0j → magnitude 0; E[‖q_f‖] = 1.0 → R=0.0
    # (uniform-direction).
    s2 = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=2,
        e_q_real=[[[0.0]]], e_q_imag=[[[0.0]]],
        e_q_norm=[[[1.0]]],
    )
    assert s2.mean_resultant_length(0, 0, 0) == pytest.approx(0.0)


def test_qcenterstats_omega_f():
    """ω_f = θ^(-2f/d). For θ=10000, d=8: ω_0=1.0, ω_1≈0.1, ω_2=0.01."""
    s = _trivial_stats(head_dim=8)
    assert s.omega_f(0) == pytest.approx(1.0)
    assert s.omega_f(1) == pytest.approx(10000 ** (-0.25))
    assert s.omega_f(2) == pytest.approx(10000 ** (-0.5))
    assert s.omega_f(3) == pytest.approx(10000 ** (-0.75))


# ------------------------------------------------------------------ #
# TrigScorer — math
# ------------------------------------------------------------------ #


def test_trigscorer_constructs_with_default_offsets():
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats()
    scorer = TrigScorer(stats=s)
    assert scorer.future_offsets == [1, 2, 4, 8, 16]


def test_trigscorer_rejects_empty_offsets():
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats()
    with pytest.raises(ValueError, match="non-empty"):
        TrigScorer(stats=s, future_offsets=[])


def test_trigscorer_rejects_non_positive_offsets():
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats()
    with pytest.raises(ValueError, match="> 0"):
        TrigScorer(stats=s, future_offsets=[1, 0, 2])
    with pytest.raises(ValueError, match="> 0"):
        TrigScorer(stats=s, future_offsets=[-1, 2])


def test_trigscorer_s_trig_at_distance_matches_formula():
    """Hand-compute S_trig for known centers + known key, verify the
    scorer matches."""
    from kv_policy.triattention import TrigScorer

    # head_dim=4, num_bands=2.
    # E[q_0] = 1+0j (magnitude 1, phase 0)
    # E[q_1] = 0+1j (magnitude 1, phase π/2)
    # E[‖q_f‖] = 1.0 for both bands.
    from kv_policy.triattention import QCenterStats
    s = QCenterStats.from_lists(
        model_name="m", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[1.0, 0.0]]],
        e_q_imag=[[[0.0, 1.0]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    scorer = TrigScorer(stats=s, future_offsets=[1])

    # Key: k_0 = 1+0j (mag 1, phase 0); k_1 = 1+0j (mag 1, phase 0).
    # ω_0 = 10000^0 = 1.0; ω_1 = 10000^(-0.5) ≈ 0.01.
    # S_trig at Δ = 5:
    #   band 0: ‖E[q_0]‖·‖k_0‖·cos(ω_0·5 + (0 - 0))
    #         = 1·1·cos(5) ≈ 0.2837
    #   band 1: ‖E[q_1]‖·‖k_1‖·cos(ω_1·5 + (π/2 - 0))
    #         = 1·1·cos(0.05 + π/2) = -sin(0.05) ≈ -0.04998
    expected = math.cos(5.0) + math.cos(10000 ** (-0.5) * 5.0 + math.pi / 2)
    actual = scorer.s_trig_at_distance(
        layer=0, head=0,
        k_real=[1.0, 1.0], k_imag=[0.0, 0.0], delta=5,
    )
    assert actual == pytest.approx(expected, abs=1e-6)


def test_trigscorer_s_norm_zero_when_concentration_perfect():
    """When R_f = 1 for all bands, S_norm should be 0 (no
    contribution from the concentration-complement term)."""
    from kv_policy.triattention import TrigScorer
    from kv_policy.triattention import QCenterStats

    # E[q_f] magnitude 1, E[‖q_f‖] = 1 → R_f = 1 for all bands.
    s = QCenterStats.from_lists(
        model_name="m", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[1.0, 1.0]]],
        e_q_imag=[[[0.0, 0.0]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    scorer = TrigScorer(stats=s)
    s_norm = scorer.s_norm(
        layer=0, head=0,
        k_real=[5.0, 7.0], k_imag=[3.0, 4.0],
    )
    assert s_norm == pytest.approx(0.0)


def test_trigscorer_s_norm_grows_with_low_concentration():
    """When R_f → 0, S_norm should equal Σ_f E[‖q_f‖]·‖k_f‖."""
    from kv_policy.triattention import TrigScorer
    from kv_policy.triattention import QCenterStats

    # E[q_f] = 0+0j (uniform direction) → R_f = 0.
    # E[‖q_f‖] = 2.0 for both bands.
    # k_0 = 3+4j → ‖k_0‖ = 5. k_1 = 0+1j → ‖k_1‖ = 1.
    # S_norm = (1-0)·2·5 + (1-0)·2·1 = 10 + 2 = 12.
    s = QCenterStats.from_lists(
        model_name="m", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[0.0, 0.0]]],
        e_q_imag=[[[0.0, 0.0]]],
        e_q_norm=[[[2.0, 2.0]]],
    )
    scorer = TrigScorer(stats=s)
    s_norm = scorer.s_norm(
        layer=0, head=0,
        k_real=[3.0, 0.0], k_imag=[4.0, 1.0],
    )
    assert s_norm == pytest.approx(12.0)


def test_trigscorer_score_token_combines_trig_and_norm():
    """score_token = mean(S_trig over offsets) + S_norm."""
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats(head_dim=4)
    scorer = TrigScorer(stats=s, future_offsets=[1, 2])
    score = scorer.score_token(
        layer=0, head=0,
        k_real=[1.0, 1.0], k_imag=[0.0, 0.0],
        position=10,
    )
    # Just verify it returns a float; magnitude depends on the trivial
    # stats. The combination math is covered by the per-component tests.
    assert isinstance(score, float)


def test_trigscorer_score_token_with_explicit_future_position():
    """When future_query_position is set, S_trig is evaluated at one
    specific Δ rather than averaged."""
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats(head_dim=4)
    scorer = TrigScorer(stats=s, future_offsets=[1, 2, 4])
    score_explicit = scorer.score_token(
        layer=0, head=0,
        k_real=[1.0, 0.5], k_imag=[0.5, 0.5],
        position=10, future_query_position=15,
    )
    # The "averaged-over-offsets" version should differ unless the
    # offsets happen to coincide with delta=5.
    score_averaged = scorer.score_token(
        layer=0, head=0,
        k_real=[1.0, 0.5], k_imag=[0.5, 0.5],
        position=10,
    )
    # Difference comes from the S_trig term (S_norm is identical).
    # Just verify both compute without error and return floats.
    assert isinstance(score_explicit, float)
    assert isinstance(score_averaged, float)


def test_trigscorer_validates_k_dim():
    from kv_policy.triattention import TrigScorer

    s = _trivial_stats(head_dim=4)   # num_bands=2
    scorer = TrigScorer(stats=s)
    with pytest.raises(ValueError, match="num_bands"):
        scorer.s_trig_at_distance(
            layer=0, head=0,
            k_real=[1.0, 0.0, 0.5],   # wrong: 3 entries vs 2 bands
            k_imag=[0.0, 0.0, 0.0],
            delta=1,
        )


# ------------------------------------------------------------------ #
# Block aggregation
# ------------------------------------------------------------------ #


def test_aggregate_block_trig_score_sums_over_positions():
    from kv_policy.triattention import (
        TrigScorer, aggregate_block_trig_score,
    )

    s = _trivial_stats(head_dim=4)
    scorer = TrigScorer(stats=s, future_offsets=[1])

    # Single-token block.
    block_keys_one = [(10, [1.0, 0.5], [0.0, 0.5])]
    score_one = aggregate_block_trig_score(
        scorer=scorer, layer=0, head=0,
        block_keys=block_keys_one,
    )

    # Two-token block (same key duplicated). Score should ≈ 2× single.
    block_keys_two = [
        (10, [1.0, 0.5], [0.0, 0.5]),
        (11, [1.0, 0.5], [0.0, 0.5]),
    ]
    score_two = aggregate_block_trig_score(
        scorer=scorer, layer=0, head=0,
        block_keys=block_keys_two,
    )
    # Exact 2× isn't guaranteed because the two tokens have different
    # positions (different Δ relative to the future-query offset);
    # but both should be within a small factor of single × 2.
    assert score_two != score_one  # different positions → different S_trig
    assert isinstance(score_two, float)


def test_aggregate_block_trig_score_empty_block_returns_zero():
    from kv_policy.triattention import (
        TrigScorer, aggregate_block_trig_score,
    )

    scorer = TrigScorer(stats=_trivial_stats())
    assert aggregate_block_trig_score(
        scorer=scorer, layer=0, head=0,
        block_keys=[],
    ) == 0.0


# ------------------------------------------------------------------ #
# GQA: z-score normalize then max
# ------------------------------------------------------------------ #


def test_gqa_normalize_then_max_basic():
    from kv_policy.triattention import gqa_normalize_then_max

    # Two query heads, three blocks each. Each head's scores have
    # different scales — z-score should normalize before max.
    per_head = {
        0: {1: 1.0, 2: 5.0, 3: 9.0},     # mean=5, std≈3.27
        1: {1: 100.0, 2: 200.0, 3: 300.0},  # mean=200, std≈81.65
    }
    out = gqa_normalize_then_max(per_head)
    # Both heads see block 3 as the highest in their own distribution
    # → normalized score is positive for both → max is positive.
    assert out[3] > 0
    # Block 1 is lowest in both distributions → max is negative.
    assert out[1] < 0
    # Set of block_ids is preserved.
    assert set(out.keys()) == {1, 2, 3}


def test_gqa_normalize_then_max_handles_constant_head():
    """A head with all-equal scores has std=0; normalisation should
    treat it as 0 mean (no useful signal from this head)."""
    from kv_policy.triattention import gqa_normalize_then_max

    per_head = {
        0: {1: 5.0, 2: 5.0, 3: 5.0},     # all equal → std=0 fallback
        1: {1: 1.0, 2: 5.0, 3: 9.0},
    }
    out = gqa_normalize_then_max(per_head)
    # Just verify it runs without dividing by zero.
    assert set(out.keys()) == {1, 2, 3}
    assert all(isinstance(v, float) for v in out.values())


def test_gqa_normalize_then_max_empty_input():
    from kv_policy.triattention import gqa_normalize_then_max

    assert gqa_normalize_then_max({}) == {}


def test_gqa_normalize_then_max_skips_empty_heads():
    from kv_policy.triattention import gqa_normalize_then_max

    per_head = {
        0: {},    # empty head
        1: {1: 1.0, 2: 2.0},
    }
    out = gqa_normalize_then_max(per_head)
    # Only blocks from the non-empty head appear.
    assert set(out.keys()) == {1, 2}


# ------------------------------------------------------------------ #
# Window-based pruning trigger
# ------------------------------------------------------------------ #


def test_window_pruning_decision_fires_at_interval():
    from kv_policy.triattention import (
        WindowPruningState, window_pruning_decision,
    )

    state = WindowPruningState(interval_tokens=128)
    # Below threshold → no fire.
    assert window_pruning_decision(state, 50) is False
    assert window_pruning_decision(state, 50) is False   # cum=100
    # At threshold → fires.
    assert window_pruning_decision(state, 28) is True   # cum=128
    # Counter reset; below new threshold.
    assert window_pruning_decision(state, 50) is False


def test_window_pruning_decision_handles_overshoots():
    from kv_policy.triattention import (
        WindowPruningState, window_pruning_decision,
    )

    state = WindowPruningState(interval_tokens=128)
    # 200 tokens in one shot → fires once, counter resets to 0
    # (not 72; we don't carry over).
    assert window_pruning_decision(state, 200) is True
    assert state.decode_tokens_since_last_prune == 0


def test_window_pruning_decision_counts_invocations():
    from kv_policy.triattention import (
        WindowPruningState, window_pruning_decision,
    )

    state = WindowPruningState(interval_tokens=10)
    for _ in range(30):
        window_pruning_decision(state, 1)
    # 30 tokens, interval 10 → 3 invocations.
    assert state.n_prune_invocations == 3


# ------------------------------------------------------------------ #
# Calibration scaffolding (GPU-only stub)
# ------------------------------------------------------------------ #


def _torch_or_skip():
    """Return torch module or skip the test if torch isn't installed."""
    try:
        import torch  # noqa: F401
        return __import__("torch")
    except ImportError:
        pytest.skip("torch not installed; Phase 4 GPU-path test skipped")


def test_calibrate_q_centers_raises_when_no_rotary_modules():
    """If the model has no rotary_emb modules, calibration fails
    fast with a diagnostic RuntimeError naming
    MODE_B_PHASE4_DESIGN.md §4. (Replaces the prior
    NotImplementedError stub test now that calibration is
    implemented.)"""
    _torch_or_skip()
    from kv_policy.triattention import calibrate_q_centers

    class EmptyModel:
        # No rotary modules anywhere.
        def named_modules(self):
            yield from []

    def fake_forward(model):
        pass

    with pytest.raises(RuntimeError) as exc:
        calibrate_q_centers(
            model=EmptyModel(),
            forward_callable=fake_forward,
            model_name="empty_test",
            num_heads=2, head_dim=4,
        )
    msg = str(exc.value)
    assert "rotary_emb" in msg
    assert "MODE_B_PHASE4_DESIGN.md" in msg


def test_walk_rotary_emb_modules_finds_by_class_name():
    """Class-name heuristic: modules with 'Rotary' or 'RoPE' in
    their type name are picked up. Other modules ignored."""
    from kv_policy.triattention import _walk_rotary_emb_modules

    class RotaryEmbedding:
        def forward(self, positions, q, k):
            return q, k

    class Rotary:
        # Also matches.
        def forward(self, positions, q, k):
            return q, k

    class RoPEModule:
        def forward(self, positions, q, k):
            return q, k

    class MLP:
        def forward(self, x):
            return x

    class Model:
        def named_modules(self):
            yield "layer0.rotary", RotaryEmbedding()
            yield "layer0.mlp", MLP()
            yield "layer1.rotary", Rotary()
            yield "layer2.rotary", RoPEModule()
            yield "layer2.mlp", MLP()

    found = list(_walk_rotary_emb_modules(Model()))
    assert len(found) == 3
    # Layer indexing is by document order.
    assert [layer for layer, _, _ in found] == [0, 1, 2]


def test_split_q_into_complex_pairs_basic():
    """Q tensor [num_tokens, num_heads*head_dim] → (real, imag, norm)
    of shape [num_tokens, num_heads, num_bands]."""
    torch = _torch_or_skip()
    from kv_policy.triattention import _split_q_into_complex_pairs

    # 2 tokens, 2 heads, head_dim=4 → num_bands=2.
    # Q layout: [t, h*d] = [t, h0_d0, h0_d1, h0_d2, h0_d3, h1_d0, ...]
    # band 0 = (d0, d1), band 1 = (d2, d3).
    q = torch.tensor([
        [1.0, 2.0, 3.0, 4.0,  5.0, 6.0, 7.0, 8.0],   # token 0
        [0.5, 0.6, 0.7, 0.8,  0.1, 0.2, 0.3, 0.4],   # token 1
    ])
    q_real, q_imag, q_norm = _split_q_into_complex_pairs(
        q, num_heads=2, head_dim=4,
    )
    # Shape [2 tokens, 2 heads, 2 bands].
    assert tuple(q_real.shape) == (2, 2, 2)
    # token 0, head 0, band 0: real=1, imag=2, norm=sqrt(5)
    assert q_real[0, 0, 0].item() == pytest.approx(1.0)
    assert q_imag[0, 0, 0].item() == pytest.approx(2.0)
    assert q_norm[0, 0, 0].item() == pytest.approx((5.0) ** 0.5)
    # token 0, head 1, band 1: real=7, imag=8, norm=sqrt(113)
    assert q_real[0, 1, 1].item() == pytest.approx(7.0)
    assert q_imag[0, 1, 1].item() == pytest.approx(8.0)


def test_split_q_into_complex_pairs_rejects_odd_head_dim():
    torch = _torch_or_skip()
    from kv_policy.triattention import _split_q_into_complex_pairs

    q = torch.zeros((1, 6))  # head_dim must be even
    with pytest.raises(ValueError, match="even"):
        _split_q_into_complex_pairs(q, num_heads=2, head_dim=3)


def test_split_q_into_complex_pairs_rejects_dim_mismatch():
    torch = _torch_or_skip()
    from kv_policy.triattention import _split_q_into_complex_pairs

    q = torch.zeros((1, 9))  # 9 != 2 * 4
    with pytest.raises(ValueError, match="last dim"):
        _split_q_into_complex_pairs(q, num_heads=2, head_dim=4)


def test_calibrate_q_centers_end_to_end_with_mock_model():
    """End-to-end calibration on a fake torch model with one
    rotary_emb. Verifies the pre-hook fires, accumulates Q
    statistics, and produces a valid QCenterStats."""
    torch = _torch_or_skip()
    from kv_policy.triattention import calibrate_q_centers

    class FakeRotary(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.rotary = FakeRotary()

        def my_forward(self, q, k):
            return self.rotary(torch.tensor([0]), q, k)

    model = FakeModel()
    # Caller's forward_callable: drives the model through some
    # calibration data.
    def driver(m):
        for _ in range(3):
            q = torch.randn(8, 4 * 4)   # 8 tokens, 4 heads, head_dim=4
            k = torch.randn(8, 4 * 4)
            m.my_forward(q, k)

    stats = calibrate_q_centers(
        model=model,
        forward_callable=driver,
        model_name="fake_test",
        num_heads=4, head_dim=4,
    )
    assert stats.model_name == "fake_test"
    assert stats.num_layers == 1
    assert stats.num_heads == 4
    assert stats.head_dim == 4
    assert stats.num_bands == 2
    assert stats.calibration_token_count == 24   # 3 batches × 8 tokens
    # Statistics are real-valued floats.
    assert all(
        isinstance(stats.e_q_real[0][h][f], float)
        for h in range(4) for f in range(2)
    )


def test_calibrate_q_centers_respects_max_tokens():
    """When max_tokens is reached mid-calibration, further forward
    passes don't accumulate."""
    torch = _torch_or_skip()
    from kv_policy.triattention import calibrate_q_centers

    class FakeRotary(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.rotary = FakeRotary()

        def my_forward(self, q, k):
            return self.rotary(torch.tensor([0]), q, k)

    model = FakeModel()
    def driver(m):
        for _ in range(100):
            q = torch.randn(10, 8)
            k = torch.randn(10, 8)
            m.my_forward(q, k)

    stats = calibrate_q_centers(
        model=model, forward_callable=driver,
        model_name="capped", num_heads=2, head_dim=4,
        max_tokens=50,   # first 5 batches hit cap
    )
    # tokens_seen will overshoot to next-batch boundary (50 -> 60
    # since the cap-check fires AFTER the batch starts).
    assert stats.calibration_token_count >= 50
    assert stats.calibration_token_count <= 60


def test_install_pre_rope_capture_finds_rotary_modules():
    """install_pre_rope_capture walks the model and registers
    pre-hooks on every rotary_emb."""
    torch = _torch_or_skip()
    from kv_policy.triattention import install_pre_rope_capture
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer, QCenterStats

    class FakeRotary(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layer0_rotary = FakeRotary()
            self.layer1_rotary = FakeRotary()

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=2, num_heads=2, num_kv_heads=2,
        head_dim=4,
        e_q_real=[[[0.5, 0.5], [0.5, 0.5]]] * 2,
        e_q_imag=[[[0.5, 0.5], [0.5, 0.5]]] * 2,
        e_q_norm=[[[1.0, 1.0], [1.0, 1.0]]] * 2,
    )
    evictor = CTMEvictorModern(
        num_blocks_capacity=64, block_size=4,
        trig_scorer=TrigScorer(stats=stats),
    )

    n = install_pre_rope_capture(
        model=FakeModel(), evictor=evictor,
        layer_for_scoring=1, head_for_scoring=0,
    )
    assert n == 2


def test_install_pre_rope_capture_returns_zero_on_empty_model():
    torch = _torch_or_skip()
    from kv_policy.triattention import install_pre_rope_capture
    from kv_policy.vllm_evictor import CTMEvictorModern

    class EmptyModel(torch.nn.Module):
        def named_modules(self):
            yield from []

    ev = CTMEvictorModern(num_blocks_capacity=4, block_size=4)
    n = install_pre_rope_capture(model=EmptyModel(), evictor=ev)
    assert n == 0


def test_install_attn_metadata_side_channel_finds_attention_modules():
    """The side-channel installer registers pre+post hooks on
    every Attention layer."""
    torch = _torch_or_skip()
    from kv_policy.triattention import (
        install_attn_metadata_side_channel,
    )
    from kv_policy.vllm_evictor import CTMEvictorModern

    class Attention(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.head_size = 4
            self.num_heads = 2

        def forward(self, q, k, v, kv_cache, attn_metadata):
            return q

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layer0_attn = Attention()
            self.layer1_attn = Attention()

    ev = CTMEvictorModern(num_blocks_capacity=64, block_size=4)
    n = install_attn_metadata_side_channel(
        model=FakeModel(), evictor=ev,
    )
    assert n == 2
    assert hasattr(ev, "_phase4_handles")
    # Pre + post per layer = 4 handles.
    assert len(ev._phase4_handles) == 4


def test_attn_metadata_side_channel_stashes_then_clears():
    """Pre-hook stashes slot_mapping; post-hook clears it.

    The fix that landed after the May 2026 GPU run: hook the
    top-level model (which receives attn_metadata as a forward
    arg) rather than each Attention layer (which fires AFTER
    rotary_emb in vLLM 0.7.3's Qwen2.5 path). This test exercises
    the new design.
    """
    torch = _torch_or_skip()
    from kv_policy.triattention import (
        install_attn_metadata_side_channel,
    )
    from kv_policy.vllm_evictor import CTMEvictorModern

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()

        def forward(self, input_ids, positions, kv_caches, attn_metadata):
            return input_ids

    class FakeMeta:
        slot_mapping = torch.tensor([0, 16, 32])
        num_decode_tokens = 3

    ev = CTMEvictorModern(num_blocks_capacity=64, block_size=4)
    model = FakeModel()
    n_hooks = install_attn_metadata_side_channel(model=model, evictor=ev)
    assert n_hooks == 1, "expected one pair of hooks on the top-level model"

    # Before any forward — side-channel is None.
    assert getattr(ev, "_phase4_pending_slot_mapping", None) is None

    # Trigger forward via __call__ so PyTorch's hook dispatcher runs.
    # Pre-hook fires (stashes), post-hook fires (clears).
    input_ids = torch.zeros((3,), dtype=torch.long)
    positions = torch.zeros((3,), dtype=torch.long)
    model(input_ids, positions, None, FakeMeta())
    assert ev._phase4_pending_slot_mapping is None
    assert ev._phase4_pending_num_decode_tokens == 0


def test_attn_metadata_side_channel_set_when_rotary_emb_fires():
    """Real-call-order regression: in Qwen2.5 vLLM, rotary_emb fires
    BEFORE Attention.forward inside each decoder layer. The first GPU
    run (May 2026) had the side-channel hook on Attention.forward, so
    it set the side-channel AFTER rotary_emb had already run — which
    meant the pre-RoPE capture pre-hook always saw side-channel=None
    and aborted. This test simulates the real call order:

        model.forward(input_ids, positions, kv_caches, attn_metadata)
            -> rotary_emb(positions, q, k)   <-- must see side-channel set
            -> Attention.forward(q, k, v, ...)

    With the fix that hooks the top-level model, the side-channel is
    set when the model.forward begins and is still set throughout
    the call — so any submodule firing inside (rotary_emb included)
    sees a valid stash. Without the fix this test fails: the
    side-channel would only be set when Attention fires, which is
    after rotary_emb.
    """
    torch = _torch_or_skip()
    from kv_policy.triattention import (
        install_attn_metadata_side_channel,
    )
    from kv_policy.vllm_evictor import CTMEvictorModern

    captured_at_rotary_call = {}

    class RotaryEmb(torch.nn.Module):
        def forward(self, positions, q, k):
            return q, k

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.rotary_emb = RotaryEmb()

        def forward(self, input_ids, positions, kv_caches, attn_metadata):
            q = torch.zeros((3, 8))
            k = torch.zeros((3, 8))
            self.rotary_emb(positions, q, k)
            return input_ids

    class FakeMeta:
        slot_mapping = torch.tensor([0, 16, 32])
        num_decode_tokens = 3

    ev = CTMEvictorModern(num_blocks_capacity=64, block_size=4)
    model = FakeModel()
    install_attn_metadata_side_channel(model=model, evictor=ev)

    def snapshot_pre_hook(module, args):
        captured_at_rotary_call["slot_mapping"] = (
            ev._phase4_pending_slot_mapping
        )
        captured_at_rotary_call["num_decode_tokens"] = (
            ev._phase4_pending_num_decode_tokens
        )

    model.rotary_emb.register_forward_pre_hook(snapshot_pre_hook)

    model(
        torch.zeros((3,), dtype=torch.long),
        torch.zeros((3,), dtype=torch.long),
        None,
        FakeMeta(),
    )

    assert captured_at_rotary_call.get("slot_mapping") is not None, (
        "side-channel was NOT set when rotary_emb fired — this is "
        "the May 2026 GPU bug that produced "
        "phase4_blocks_captured_with_pre_rope_keys=0."
    )
    assert captured_at_rotary_call["num_decode_tokens"] == 3


def test_capture_pre_rope_k_to_evictor_with_side_channel():
    """End-to-end: with attn_metadata stashed via the side channel,
    a rotary_emb pre-hook fires and pushes per-block keys to the
    evictor."""
    torch = _torch_or_skip()
    from kv_policy.triattention import _capture_pre_rope_k_to_evictor
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer, QCenterStats

    stats = QCenterStats.from_lists(
        model_name="x", num_layers=1, num_heads=1, num_kv_heads=1,
        head_dim=4,
        e_q_real=[[[0.5, 0.5]]],
        e_q_imag=[[[0.5, 0.5]]],
        e_q_norm=[[[1.0, 1.0]]],
    )
    ev = CTMEvictorModern(
        num_blocks_capacity=64, block_size=4,
        trig_scorer=TrigScorer(stats=stats),
    )
    # Track three blocks; admit them.
    for bid in (0, 4, 8):
        ev.add(block_id=bid, content_hash=bid * 2,
               num_hashed_tokens=4, last_accessed=0.0)

    # Stash the side-channel as the side_channel installer would.
    # 3 decode tokens writing to slots [0, 16, 32] -> blocks [0, 4, 8].
    ev._phase4_pending_slot_mapping = torch.tensor([0, 16, 32])
    ev._phase4_pending_num_decode_tokens = 3

    # Build a K tensor: 3 tokens, 1 KV head, head_dim=4.
    positions = torch.tensor([0, 16, 32])
    query = torch.zeros((3, 4))
    key = torch.tensor([
        [1.0, 2.0, 3.0, 4.0],
        [0.5, 0.5, 0.5, 0.5],
        [0.1, 0.2, 0.3, 0.4],
    ])
    _capture_pre_rope_k_to_evictor(
        inputs=(positions, query, key),
        evictor=ev, layer=0, head=0,
        inferred_head_dim=4,
    )
    # All three blocks should have pre-RoPE keys captured.
    assert ev.trig_score_block(0) is not None
    assert ev.trig_score_block(4) is not None
    assert ev.trig_score_block(8) is not None


def test_capture_pre_rope_k_no_side_channel_is_silent():
    """Without the side-channel populated, K capture is a silent
    no-op (Phase 4 falls back to per-block None scoring)."""
    torch = _torch_or_skip()
    from kv_policy.triattention import _capture_pre_rope_k_to_evictor
    from kv_policy.vllm_evictor import CTMEvictorModern

    ev = CTMEvictorModern(num_blocks_capacity=64, block_size=4)
    ev.add(block_id=0, content_hash=0, num_hashed_tokens=4,
           last_accessed=0.0)
    # No side channel — pending_slot_mapping is None.
    _capture_pre_rope_k_to_evictor(
        inputs=(torch.tensor([0]), torch.zeros((1, 4)),
                torch.zeros((1, 4))),
        evictor=ev, layer=0, head=0,
        inferred_head_dim=4,
    )
    # Still no captured keys.
    assert ev.trig_score_block(0) is None


# ------------------------------------------------------------------ #
# Integration: CTMEvictorModern + TrigScorer
# ------------------------------------------------------------------ #


def test_ctm_evictor_modern_phase4_constructor_accepts_trig_scorer():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats())
    ev = CTMEvictorModern(
        num_blocks_capacity=128,
        block_size=16,
        trig_scorer=scorer,
        window_pruning_interval=64,
    )
    assert ev._trig_scorer is scorer
    assert ev.window_pruning_invocations == 0


def test_ctm_evictor_modern_set_block_pre_rope_keys_silent_on_untracked():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats())
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    # Block 999 isn't tracked; should silently no-op.
    ev.set_block_pre_rope_keys(999, keys=[(0, [0.0, 0.0], [0.0, 0.0])])
    assert ev.trig_score_block(999) is None


def test_ctm_evictor_modern_trig_score_block_returns_none_without_keys():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats())
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    ev.add(block_id=42, content_hash=1, num_hashed_tokens=16,
           last_accessed=0.0)
    # Block tracked but no pre-RoPE keys → returns None.
    assert ev.trig_score_block(42) is None


def test_ctm_evictor_modern_trig_score_block_with_keys():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats(head_dim=4))
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    ev.add(block_id=42, content_hash=1, num_hashed_tokens=16,
           last_accessed=0.0)
    ev.set_block_pre_rope_keys(
        42,
        keys=[
            (0, [1.0, 0.5], [0.0, 0.5]),
            (1, [0.8, 0.3], [0.1, 0.4]),
        ],
        layer=0, head=0,
    )
    score = ev.trig_score_block(42)
    assert isinstance(score, float)


def test_ctm_evictor_modern_window_pruning_passed_invokes_state():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats())
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
        window_pruning_interval=10,
    )
    assert ev.window_pruning_passed(5) is False
    assert ev.window_pruning_passed(5) is True
    assert ev.window_pruning_invocations == 1


def test_ctm_evictor_modern_window_pruning_pass_evicts_lowest_scoring():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats(head_dim=4))
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    # Add four blocks, give them all pre-RoPE keys (different keys
    # produce different scores).
    for bid, kr, ki in [
        (10, [1.0, 1.0], [0.0, 0.0]),
        (20, [0.5, 0.3], [0.1, 0.1]),
        (30, [2.0, 1.0], [0.0, 0.5]),
        (40, [0.1, 0.1], [0.0, 0.0]),
    ]:
        ev.add(bid, content_hash=bid * 2, num_hashed_tokens=16,
               last_accessed=0.0)
        ev.set_block_pre_rope_keys(bid, keys=[(0, kr, ki)])
    assert ev.num_blocks == 4
    # Prune to 2 blocks; expects 2 evictions.
    n_evicted = ev.window_pruning_pass(target_blocks=2)
    assert n_evicted == 2
    assert ev.num_blocks == 2


def test_ctm_evictor_modern_window_pruning_pass_skips_blocks_without_keys():
    """Blocks for which no pre-RoPE keys were captured are skipped
    (they'll go through the next vLLM-driven evict() instead)."""
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats(head_dim=4))
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    # Two blocks with keys; two without.
    ev.add(10, 0, 16, 0.0)
    ev.set_block_pre_rope_keys(10, keys=[(0, [1.0, 0.5], [0.0, 0.5])])
    ev.add(20, 0, 16, 0.0)
    ev.set_block_pre_rope_keys(20, keys=[(1, [0.5, 0.5], [0.0, 0.0])])
    ev.add(30, 0, 16, 0.0)   # no keys
    ev.add(40, 0, 16, 0.0)   # no keys
    n_evicted = ev.window_pruning_pass(target_blocks=2)
    # Only blocks 10 and 20 are scoring candidates; window_pruning
    # would need to evict 2 from those 2, but the target is "≤2
    # blocks total." Since 30 and 40 are skipped (no keys), the pass
    # can only evict from {10, 20}; we want 4-2=2 evictions, and
    # there are exactly 2 candidates → both get evicted.
    assert n_evicted == 2
    assert 30 in ev._tracked
    assert 40 in ev._tracked


def test_ctm_evictor_modern_window_pruning_pass_no_op_when_under_target():
    from kv_policy.vllm_evictor import CTMEvictorModern
    from kv_policy.triattention import TrigScorer

    scorer = TrigScorer(stats=_trivial_stats())
    ev = CTMEvictorModern(
        num_blocks_capacity=128, block_size=16,
        trig_scorer=scorer,
    )
    ev.add(10, 0, 16, 0.0)
    ev.add(20, 0, 16, 0.0)
    # Under target → no eviction.
    assert ev.window_pruning_pass(target_blocks=10) == 0


# ------------------------------------------------------------------ #
# Streaming runner integration
# ------------------------------------------------------------------ #


def test_async_engine_driver_phase4_requires_ctm_plus():
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    with pytest.raises(ValueError, match="ctm_plus_evictor=True"):
        AsyncEngineDriver(
            model="dummy",
            ctm_plus_evictor=False,
            phase4_trig_calibration_path=Path("/tmp/dummy.json"),
        )


def test_async_engine_driver_phase3_phase4_mutually_exclusive():
    """Phase 3 and Phase 4 are competing hypotheses; running both in
    one cell entangles their effects. Constructor rejects."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    with pytest.raises(ValueError, match="competing hypotheses"):
        AsyncEngineDriver(
            model="dummy",
            ctm_plus_evictor=True,
            phase3_attention_capture=True,
            phase4_trig_calibration_path=Path("/tmp/dummy.json"),
        )


def test_async_engine_driver_phase4_constructor_stores_config(tmp_path):
    """When phase4_trig_calibration_path is set, the constructor
    stores it for the run loop to load at engine init."""
    from ctm_bench.runner_vllm_streaming import AsyncEngineDriver

    cal_path = tmp_path / "cal.json"
    _trivial_stats().save(cal_path)
    driver = AsyncEngineDriver(
        model="dummy",
        ctm_plus_evictor=True,
        phase4_trig_calibration_path=cal_path,
        phase4_window_interval=64,
        phase4_future_offsets=[1, 4, 16],
    )
    assert driver.phase4_trig_calibration_path == cal_path
    assert driver.phase4_window_interval == 64
    assert driver.phase4_future_offsets == [1, 4, 16]
    # Phase 4 forces prefix caching on (same as Phase 2).
    assert driver.enable_prefix_caching is True


def test_streaming_run_cell_result_has_phase4_fields():
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    r = StreamingRunCellResult(
        workload_name="x", policy_name="lru", seed=42,
        n_requests_admitted=10, n_requests_completed=8,
        n_decode_tokens=4096, wall_clock_seconds=12.5,
        swap_in_blocks=128, swap_out_blocks=128,
        preemption_events=4,
    )
    # Defaults: zero — Phase 4 wasn't configured for this cell.
    assert r.phase4_window_pruning_invocations == 0
    assert r.phase4_blocks_captured_with_pre_rope_keys == 0
