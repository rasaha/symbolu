"""
Stage 3 tests: instability / future-read-demand signal in KVCachePolicy.

Validates:
  1. Default-off: instability signal has zero effect when weight is 0.0
  2. Enabled: instability hint boosts block score proportionally
  3. Admission path: ensure_block(instability_hint=...) sets the field
  4. Post-admission: set_block_instability() updates the field
  5. Per-instance weight: set_instability_weight() does not modify globals
  6. No regression: existing signals + Stage 1 + Stage 2 unchanged
  7. All three stages compose correctly
"""

from __future__ import annotations

import random

import pytest

from simulator.pcam.kv_policy import (
    BlockState,
    InferencePhase,
    KVCachePolicy,
    PhaseWeights,
    PHASE_WEIGHTS,
)


def make_policy(max_blocks: int = 64) -> KVCachePolicy:
    p = KVCachePolicy(max_blocks=max_blocks, block_size=16, sink_tokens=4)
    p.set_rng(random.Random(42))
    return p


def admit_and_attend(
    policy: KVCachePolicy,
    block_id: int,
    seq_id: int,
    positions: list,
    attention_sum: float = 0.001,
    boundary_score: float = 0.0,
    band_class: float = 1.0,
    instability_hint: float = 0.0,
) -> None:
    policy.register_sequence(seq_id)
    policy.set_phase(seq_id, InferencePhase.DECODE)
    policy.ensure_block(block_id, seq_id, positions,
                        boundary_score=boundary_score,
                        band_class=band_class,
                        instability_hint=instability_hint)
    policy.on_block_attention(block_id, attention_sum, seq_id)


class TestInstabilityDefaultOff:
    """When instability weight is 0.0, the signal must have no effect."""

    def test_default_phase_weights_have_zero_instability(self):
        for phase, w in PHASE_WEIGHTS.items():
            assert w.instability == 0.0

    def test_score_unchanged_with_instability_present(self):
        p1 = make_policy()
        p2 = make_policy()

        admit_and_attend(p1, 10, 1, [100, 101], instability_hint=0.0)
        admit_and_attend(p2, 10, 1, [100, 101], instability_hint=1.0)

        assert p1.score_block(10) == p2.score_block(10)


class TestInstabilityEnabled:
    """When instability weight is non-zero, unstable blocks score higher."""

    def test_unstable_block_scores_higher(self):
        p = make_policy()
        p.set_instability_weight(0.15)

        admit_and_attend(p, 10, 1, [100, 101], instability_hint=0.0)
        admit_and_attend(p, 11, 1, [102, 103], instability_hint=0.9)

        s_stable = p.score_block(10)
        s_unstable = p.score_block(11)
        assert s_unstable > s_stable, (
            f"Unstable block should score higher: {s_unstable} vs {s_stable}"
        )

    def test_instability_is_proportional(self):
        p = make_policy()
        p.set_instability_weight(0.20)

        admit_and_attend(p, 10, 1, [100, 101], instability_hint=0.5)
        admit_and_attend(p, 11, 1, [102, 103], instability_hint=1.0)

        s_half = p.score_block(10)
        s_full = p.score_block(11)
        diff = s_full - s_half
        assert 0.08 < diff < 0.12, f"Expected ~0.10 diff, got {diff:.4f}"


class TestInstabilityAdmission:
    """Instability can be set at admission or post-admission."""

    def test_ensure_block_sets_instability(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101], instability_hint=0.7)
        assert p.blocks[10].instability_hint == 0.7

    def test_ensure_block_default_zero(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])
        assert p.blocks[10].instability_hint == 0.0

    def test_set_block_instability_updates(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])
        assert p.blocks[10].instability_hint == 0.0
        p.set_block_instability(10, 0.85)
        assert p.blocks[10].instability_hint == 0.85

    def test_set_block_instability_unknown_is_noop(self):
        p = make_policy()
        p.set_block_instability(999, 1.0)


class TestInstabilityWeight:
    """set_instability_weight() configures per-instance weights."""

    def test_does_not_modify_global(self):
        p = make_policy()
        p.set_instability_weight(0.25)

        assert PHASE_WEIGHTS[InferencePhase.PREFILL].instability == 0.0
        assert PHASE_WEIGHTS[InferencePhase.DECODE].instability == 0.0

        assert p._phase_weights[InferencePhase.PREFILL].instability == 0.25
        assert p._phase_weights[InferencePhase.DECODE].instability == 0.25

    def test_per_phase_weights(self):
        p = make_policy()
        p.set_instability_weight(0.10, prefill=0.05, decode=0.20)

        assert p._phase_weights[InferencePhase.PREFILL].instability == 0.05
        assert p._phase_weights[InferencePhase.DECODE].instability == 0.20

    def test_preserves_boundary_weight(self):
        """Setting instability weight should not clobber boundary weight."""
        p = make_policy()
        p.set_boundary_weight(0.10)
        p.set_instability_weight(0.15)

        assert p._phase_weights[InferencePhase.DECODE].boundary == 0.10
        assert p._phase_weights[InferencePhase.DECODE].instability == 0.15


class TestAllThreeStagesCompose:
    """All three FSCS-derived signals compose correctly."""

    def test_all_signals_contribute(self):
        """A block with boundary + global band + instability should
        score highest; a block with none should score lowest."""
        p = make_policy()
        p.set_boundary_weight(0.10)
        p.set_instability_weight(0.15)

        # Fully protected: boundary + global + unstable
        admit_and_attend(p, 10, 1, [100, 101],
                         boundary_score=0.9, band_class=1.3,
                         instability_hint=0.8)

        # Fully exposed: no boundary + local + stable
        admit_and_attend(p, 11, 1, [102, 103],
                         boundary_score=0.0, band_class=0.7,
                         instability_hint=0.0)

        s_protected = p.score_block(10)
        s_exposed = p.score_block(11)

        assert s_protected > s_exposed, (
            f"Protected block should score much higher: "
            f"{s_protected:.4f} vs {s_exposed:.4f}"
        )

    def test_backward_compat_phaseweights(self):
        """PhaseWeights(r, f, a, p) still works."""
        w = PhaseWeights(0.25, 0.25, 0.25, 0.25)
        assert w.boundary == 0.0
        assert w.instability == 0.0
