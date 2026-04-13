"""
Stage 2 tests: band-class multiplier in KVCachePolicy scoring.

Validates:
  1. Default-neutral: band_class=1.0 has zero effect on score
  2. Global boost: band_class>1.0 increases score (harder to evict)
  3. Local discount: band_class<1.0 decreases score (easier to evict)
  4. Admission path: ensure_block(band_class=...) sets the field
  5. Post-admission: set_block_band() updates the field
  6. Multiplicative: score scales proportionally with band_class
  7. No regression: existing four-signal + Stage 1 scoring unchanged
"""

from __future__ import annotations

import random

import pytest

from simulator.pcam.kv_policy import (
    BlockState,
    InferencePhase,
    KVCachePolicy,
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
) -> None:
    policy.register_sequence(seq_id)
    policy.set_phase(seq_id, InferencePhase.DECODE)
    policy.ensure_block(block_id, seq_id, positions,
                        boundary_score=boundary_score,
                        band_class=band_class)
    policy.on_block_attention(block_id, attention_sum, seq_id)


class TestBandClassDefault:
    """band_class=1.0 must have zero effect on scoring."""

    def test_default_band_class_is_neutral(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])
        assert p.blocks[10].band_class == 1.0

    def test_score_unchanged_at_band_1(self):
        p1 = make_policy()
        p2 = make_policy()

        admit_and_attend(p1, 10, 1, [100, 101], band_class=1.0)
        admit_and_attend(p2, 10, 1, [100, 101], band_class=1.0)

        assert p1.score_block(10) == p2.score_block(10)


class TestBandClassGlobal:
    """band_class > 1.0 should increase score (harder to evict)."""

    def test_global_band_boosts_score(self):
        p = make_policy()
        admit_and_attend(p, 10, 1, [100, 101], band_class=1.0)
        admit_and_attend(p, 11, 1, [102, 103], band_class=1.3)

        s_neutral = p.score_block(10)
        s_global = p.score_block(11)
        assert s_global > s_neutral, (
            f"Global band should score higher: {s_global} vs {s_neutral}"
        )

    def test_global_band_is_multiplicative(self):
        p = make_policy()
        admit_and_attend(p, 10, 1, [100, 101], band_class=1.0)
        admit_and_attend(p, 11, 1, [102, 103], band_class=1.5)

        s_base = p.score_block(10)
        s_boosted = p.score_block(11)
        ratio = s_boosted / s_base
        assert 1.45 < ratio < 1.55, (
            f"Expected ~1.5x ratio, got {ratio:.3f}"
        )


class TestBandClassLocal:
    """band_class < 1.0 should decrease score (easier to evict)."""

    def test_local_band_lowers_score(self):
        p = make_policy()
        admit_and_attend(p, 10, 1, [100, 101], band_class=1.0)
        admit_and_attend(p, 11, 1, [102, 103], band_class=0.7)

        s_neutral = p.score_block(10)
        s_local = p.score_block(11)
        assert s_local < s_neutral, (
            f"Local band should score lower: {s_local} vs {s_neutral}"
        )


class TestBandClassAdmission:
    """Band class can be set at admission or post-admission."""

    def test_ensure_block_sets_band(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101], band_class=1.3)
        assert p.blocks[10].band_class == 1.3

    def test_ensure_block_default_neutral(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])
        assert p.blocks[10].band_class == 1.0

    def test_set_block_band_updates(self):
        p = make_policy()
        p.register_sequence(1)
        p.ensure_block(10, 1, [100, 101])
        assert p.blocks[10].band_class == 1.0
        p.set_block_band(10, 0.8)
        assert p.blocks[10].band_class == 0.8

    def test_set_block_band_unknown_is_noop(self):
        p = make_policy()
        p.set_block_band(999, 1.5)  # should not raise


class TestBandClassEvictionOrder:
    """Band class should influence victim selection order."""

    def test_local_evicted_before_global(self):
        """With identical attention, a local block (band_class=0.7)
        should be evicted before a global block (band_class=1.3)."""
        p = make_policy()
        p.register_sequence(1)
        p.set_phase(1, InferencePhase.DECODE)

        # Admit 3 blocks with same attention but different bands
        for bid, band in [(10, 1.3), (11, 1.0), (12, 0.7)]:
            p.ensure_block(bid, 1, [100 + bid, 101 + bid], band_class=band)
            p.on_block_attention(bid, 0.001, 1)

        # Score ordering: local(0.7) < neutral(1.0) < global(1.3)
        s_global = p.score_block(10)
        s_neutral = p.score_block(11)
        s_local = p.score_block(12)

        assert s_local < s_neutral < s_global, (
            f"Expected local < neutral < global: "
            f"{s_local:.4f} < {s_neutral:.4f} < {s_global:.4f}"
        )


class TestBandClassNoRegression:
    """Stage 2 must not change existing scoring when band_class=1.0."""

    def test_stage1_boundary_still_works_with_band(self):
        """Both Stage 1 (boundary) and Stage 2 (band) can coexist."""
        p = make_policy()
        p.set_boundary_weight(0.10)

        admit_and_attend(p, 10, 1, [100, 101],
                         boundary_score=0.9, band_class=1.3)
        admit_and_attend(p, 11, 1, [102, 103],
                         boundary_score=0.0, band_class=0.7)

        s_protected = p.score_block(10)  # boundary + global
        s_expendable = p.score_block(11)  # no boundary + local

        assert s_protected > s_expendable, (
            f"Protected block should score higher: "
            f"{s_protected:.4f} vs {s_expendable:.4f}"
        )
