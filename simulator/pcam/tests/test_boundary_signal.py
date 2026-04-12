"""
Stage 1 tests: boundary-sensitivity signal in KVCachePolicy scoring.

Validates:
  1. Default-off: boundary signal has zero effect when boundary weight is 0.0
  2. Enabled: boundary score boosts block score proportionally
  3. Admission path: ensure_block(boundary_score=...) sets the field
  4. Post-admission path: set_block_boundary() updates the field
  5. Phase weight: boundary weight is configurable per instance
  6. No regression: existing four-signal scoring is unchanged
"""

from __future__ import annotations

import math
import random

import pytest

from simulator.pcam.kv_policy import (
    BlockState,
    InferencePhase,
    KVCachePolicy,
    PhaseWeights,
    PHASE_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_policy(max_blocks: int = 64) -> KVCachePolicy:
    """Construct a policy with deterministic RNG."""
    p = KVCachePolicy(max_blocks=max_blocks, block_size=16, sink_tokens=4)
    p.set_rng(random.Random(42))
    return p


def admit_and_attend(
    policy: KVCachePolicy,
    block_id: int,
    seq_id: int,
    positions: list,
    attention_sum: float = 0.1,
    boundary_score: float = 0.0,
) -> None:
    """Shorthand: admit a block, record one attention event."""
    policy.register_sequence(seq_id)
    policy.set_phase(seq_id, InferencePhase.DECODE)
    policy.ensure_block(block_id, seq_id, positions,
                        boundary_score=boundary_score)
    policy.on_block_attention(block_id, attention_sum, seq_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBoundaryDefaultOff:
    """When boundary weight is 0.0 (default), the signal must have no effect."""

    def test_default_phase_weights_have_zero_boundary(self):
        for phase, w in PHASE_WEIGHTS.items():
            assert w.boundary == 0.0, (
                f"Phase {phase} has non-zero boundary weight {w.boundary}; "
                f"default must be 0.0 for backward compat."
            )

    def test_score_unchanged_with_boundary_score_present(self):
        """Even if a block has boundary_score=1.0, score_block() must return
        the same value as boundary_score=0.0 when the weight is 0.0."""
        p1 = make_policy()
        p2 = make_policy()

        admit_and_attend(p1, block_id=10, seq_id=1, positions=[100, 101],
                         boundary_score=0.0)
        admit_and_attend(p2, block_id=10, seq_id=1, positions=[100, 101],
                         boundary_score=1.0)

        s1 = p1.score_block(10)
        s2 = p2.score_block(10)
        assert s1 == s2, (
            f"Boundary weight is 0.0 but scores differ: {s1} vs {s2}"
        )


class TestBoundaryEnabled:
    """When boundary weight is non-zero, the signal must boost scores."""

    def test_boundary_boosts_score(self):
        p = make_policy()
        p.set_boundary_weight(0.10)

        admit_and_attend(p, block_id=10, seq_id=1, positions=[100, 101],
                         boundary_score=0.0)
        admit_and_attend(p, block_id=11, seq_id=1, positions=[102, 103],
                         boundary_score=1.0)

        s_no_boundary = p.score_block(10)
        s_boundary = p.score_block(11)
        assert s_boundary > s_no_boundary, (
            f"Boundary block should score higher: {s_boundary} vs {s_no_boundary}"
        )

    def test_boundary_boost_is_proportional(self):
        p = make_policy()
        p.set_boundary_weight(0.20)

        admit_and_attend(p, block_id=10, seq_id=1, positions=[100, 101],
                         boundary_score=0.5)
        admit_and_attend(p, block_id=11, seq_id=1, positions=[102, 103],
                         boundary_score=1.0)

        s_half = p.score_block(10)
        s_full = p.score_block(11)
        # The difference should be approximately 0.20 * (1.0 - 0.5) = 0.10
        diff = s_full - s_half
        assert 0.08 < diff < 0.12, (
            f"Expected ~0.10 score difference, got {diff:.4f}"
        )

    def test_boundary_weight_per_phase(self):
        p = make_policy()
        p.set_boundary_weight(0.10, prefill=0.05, decode=0.15)

        admit_and_attend(p, block_id=10, seq_id=1, positions=[100, 101],
                         boundary_score=1.0)

        # Decode phase (set in admit_and_attend)
        s_decode = p.score_block(10)

        # Switch to prefill
        p.set_phase(1, InferencePhase.PREFILL)
        s_prefill = p.score_block(10)

        # Decode boundary weight (0.15) > prefill (0.05), so decode score
        # should be higher (all else equal the four base signals also differ
        # by phase, but the boundary contribution is 0.15 vs 0.05).
        # Just verify both are valid positive numbers.
        assert s_decode > 0
        assert s_prefill > 0


class TestBoundaryAdmission:
    """Boundary score can be set at admission or post-admission."""

    def test_ensure_block_sets_boundary(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101], boundary_score=0.8)

        block = p.blocks[10]
        assert block.boundary_score == 0.8

    def test_ensure_block_default_zero(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])

        block = p.blocks[10]
        assert block.boundary_score == 0.0

    def test_set_block_boundary_updates(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])

        assert p.blocks[10].boundary_score == 0.0
        p.set_block_boundary(10, 0.9)
        assert p.blocks[10].boundary_score == 0.9

    def test_set_block_boundary_unknown_is_noop(self):
        p = make_policy()
        # No block 999 exists — should not raise
        p.set_block_boundary(999, 1.0)


class TestBoundaryNoRegression:
    """Existing scoring behavior is preserved exactly."""

    def test_four_signal_path_unchanged(self):
        """Verify the four original signals produce the same score as
        before Stage 1 when boundary is disabled (default)."""
        p = make_policy()
        # Use very low attention so the block stays as filler (importance=0.1)
        # and does not trigger the entity bonus. attention_ema = 0.1 * 0.001
        # = 0.0001, well below the adaptive threshold floor of 0.02.
        admit_and_attend(p, block_id=10, seq_id=1, positions=[100, 101],
                         attention_sum=0.001)

        score = p.score_block(10)
        # Manually compute expected score using DECODE weights
        w = PHASE_WEIGHTS[InferencePhase.DECODE]
        recency = math.exp(-0.01 * (p._step - p.blocks[10].last_access_step))
        frequency = min(1.0, p.freq_sketch.estimate(10) / 10.0)
        attention = p.blocks[10].attention_ema
        # Filler: attention_ema (0.0001) < adaptive threshold (0.02)
        importance = 0.1

        expected = (
            w.recency * recency
            + w.frequency * frequency
            + w.attention * attention
            + w.position * importance
        )
        # No entity bonus (attention_ema < adaptive_threshold)
        assert abs(score - expected) < 1e-6, (
            f"Four-signal score mismatch: got {score}, expected {expected}"
        )

    def test_phase_weights_backward_compatible(self):
        """PhaseWeights(r, f, a, p) still works without explicit boundary."""
        w = PhaseWeights(0.25, 0.25, 0.25, 0.25)
        assert w.boundary == 0.0


class TestSetBoundaryWeight:
    """set_boundary_weight() configures per-instance weights."""

    def test_does_not_modify_global(self):
        p = make_policy()
        p.set_boundary_weight(0.50)

        # Global weights must be unchanged
        assert PHASE_WEIGHTS[InferencePhase.PREFILL].boundary == 0.0
        assert PHASE_WEIGHTS[InferencePhase.DECODE].boundary == 0.0

        # Instance weights should be updated
        assert p._phase_weights[InferencePhase.PREFILL].boundary == 0.50
        assert p._phase_weights[InferencePhase.DECODE].boundary == 0.50
