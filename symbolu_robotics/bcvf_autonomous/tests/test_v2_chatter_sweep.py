"""Tests for the V2 chatter-reduction sweep + promotion decision."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.v2_chatter_sweep import (
    V2ChatterPerSeed,
    V2ChatterSweepConfig,
    V2ChatterSweepResult,
    V2PromotionDecisionResult,
    _argmax_flips,
    _binomial_tail_geq,
    _mcnemar_one_sided_v2_worse,
    run_v2_chatter_sweep,
    run_v2_promotion_decision,
)


# --------------------------------------------------------------------------- #
# Helper primitives
# --------------------------------------------------------------------------- #


def test_argmax_flips_short_record_is_zero():
    assert _argmax_flips(np.zeros((1, 4))) == 0
    assert _argmax_flips(np.zeros((0, 4))) == 0


def test_argmax_flips_constant_argmax_is_zero():
    weights = np.zeros((10, 4))
    weights[:, 0] = 1.0
    assert _argmax_flips(weights) == 0


def test_argmax_flips_alternating_is_full():
    weights = np.zeros((4, 2))
    weights[0::2, 0] = 1.0
    weights[1::2, 1] = 1.0
    assert _argmax_flips(weights) == 3   # flips at t=1, 2, 3


def test_mcnemar_no_discordant_returns_one():
    """Both b and c zero => no evidence either way => p = 1.0."""
    assert _mcnemar_one_sided_v2_worse(0, 0) == 1.0


def test_mcnemar_v2_strictly_better_p_is_high():
    # V2 fixed 5 V1 collisions, broke 0 V1 rescues => V2 clearly better.
    # Test direction is "V2 worse", so p must be high.
    p = _mcnemar_one_sided_v2_worse(b=0, c=5)
    assert p > 0.5


def test_mcnemar_v2_strictly_worse_p_is_low():
    # V2 broke 5 V1 rescues, fixed 0 V1 collisions.
    p = _mcnemar_one_sided_v2_worse(b=5, c=0)
    assert p < 0.05


# --------------------------------------------------------------------------- #
# Direct binomial-tail unit tests — pin the k=1 off-by-one fix
# --------------------------------------------------------------------------- #


def test_binomial_tail_k_zero_is_one():
    """P(X >= 0) is identically 1 for any n, p."""
    assert _binomial_tail_geq(0, 0) == 1.0
    assert _binomial_tail_geq(0, 5) == 1.0
    assert _binomial_tail_geq(-1, 5) == 1.0


def test_binomial_tail_k_greater_than_n_is_zero():
    assert _binomial_tail_geq(2, 1) == 0.0
    assert _binomial_tail_geq(6, 5) == 0.0


def test_binomial_tail_k_one_n_one_is_one_half():
    """Pinned regression: prior implementation returned 0.0 for k=1.

    P(X >= 1) for X ~ Bin(1, 0.5) = 1 - P(X = 0) = 1 - 0.5 = 0.5.
    """
    assert _binomial_tail_geq(1, 1) == pytest.approx(0.5, abs=1e-12)


def test_binomial_tail_k_one_matches_textbook_for_n_5():
    """k=1, n=5: P(X >= 1) = 1 - (1/2)^5 = 31/32 = 0.96875."""
    assert _binomial_tail_geq(1, 5) == pytest.approx(31.0 / 32.0, abs=1e-12)


def test_binomial_tail_full_pmf_matches_textbook_for_n_5():
    """k=2..5 against textbook complementary CDF for Bin(5, 0.5)."""
    # P(X = 0..5) for Bin(5, 0.5) = (1, 5, 10, 10, 5, 1) / 32.
    assert _binomial_tail_geq(2, 5) == pytest.approx(26.0 / 32.0, abs=1e-12)
    assert _binomial_tail_geq(3, 5) == pytest.approx(16.0 / 32.0, abs=1e-12)
    assert _binomial_tail_geq(4, 5) == pytest.approx(6.0 / 32.0, abs=1e-12)
    assert _binomial_tail_geq(5, 5) == pytest.approx(1.0 / 32.0, abs=1e-12)


def test_binomial_tail_loaded_coin_p_07():
    """Sanity check at p != 0.5: P(X >= 1 | n=2, p=0.7) = 1 - 0.3^2 = 0.91."""
    assert _binomial_tail_geq(1, 2, 0.7) == pytest.approx(0.91, abs=1e-12)


def test_mcnemar_one_sided_b_one_c_zero_is_one_half():
    """Pinned regression: with b=1, c=0 the pre-fix code returned p=0.0
    (false significant). The exact one-sided McNemar p-value for one
    discordant pair is 0.5."""
    p = _mcnemar_one_sided_v2_worse(b=1, c=0)
    assert p == pytest.approx(0.5, abs=1e-12)


# --------------------------------------------------------------------------- #
# End-to-end small sweep — hits the actual planner, takes ~30-60 s
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_run_v2_chatter_sweep_smoke_on_S1_normal_driving(tmp_path):
    """Smoke test: small N on a benign scenario. Just verifies the
    sweep runs to completion and produces a well-shaped result."""
    cfg = V2ChatterSweepConfig(
        scenario_name="S1_normal_driving",
        N=2,
        mppi_rollouts=32,
        output_dir=str(tmp_path),
    )
    result = run_v2_chatter_sweep(cfg, write_artifacts=True)
    assert isinstance(result, V2ChatterSweepResult)
    assert result.n_seeds == 2
    assert len(result.per_seed) == 2
    # Each per-seed entry has matched paired data
    for s in result.per_seed:
        assert s.v1_total_steps > 0
        assert s.v2_total_steps > 0
        assert 0 <= s.v1_flip_rate <= 1
        assert 0 <= s.v2_flip_rate <= 1
        # V2 state distribution sums to total steps
        assert (
            s.v2_state_distribution.get("uniform", 0)
            + s.v2_state_distribution.get("engaged", 0)
            + s.v2_state_distribution.get("", 0)
            == s.v2_total_steps
        )
    # Artifacts on disk
    assert (tmp_path / "v2_chatter_sweep.json").exists()
    assert (tmp_path / "v2_chatter_sweep_report.md").exists()
    payload = json.loads((tmp_path / "v2_chatter_sweep.json").read_text())
    assert payload["n_seeds"] == 2


# --------------------------------------------------------------------------- #
# Decision plumbing — synthetic per-seed inputs, no planner
# --------------------------------------------------------------------------- #


def _synth_result(
    *,
    v1_rates,
    v2_rates,
    v1_collisions,
    v2_collisions,
    chatter_min_red=0.5,
    chatter_min_win=0.7,
) -> V2ChatterSweepResult:
    """Build a sweep result from per-seed primitives without running
    the planner. Used to exercise the gate logic."""
    cfg = V2ChatterSweepConfig(
        chatter_min_median_reduction=chatter_min_red,
        chatter_min_v2_win_rate=chatter_min_win,
    )
    per_seed = []
    for i, (r1, r2, c1, c2) in enumerate(
        zip(v1_rates, v2_rates, v1_collisions, v2_collisions)
    ):
        red = (r1 - r2) / r1 if r1 > 1e-12 else 0.0
        per_seed.append(V2ChatterPerSeed(
            seed=i, v1_argmax_flips=0, v2_argmax_flips=0,
            v1_total_steps=100, v2_total_steps=100,
            v1_collision=c1, v2_collision=c2,
            v1_flip_rate=r1, v2_flip_rate=r2,
            flip_rate_reduction=red,
            v2_state_distribution={"uniform": 0, "engaged": 0, "": 0},
        ))
    v1_arr = np.array(v1_rates)
    v2_arr = np.array(v2_rates)
    median_red = float(np.median([s.flip_rate_reduction for s in per_seed]))
    v2_wins = sum(1 for s in per_seed if s.v2_flip_rate < s.v1_flip_rate - 1e-9)
    win_rate = v2_wins / len(per_seed)
    chatter_pass = median_red >= chatter_min_red and win_rate >= chatter_min_win

    b = sum(1 for s in per_seed if (not s.v1_collision) and s.v2_collision)
    c = sum(1 for s in per_seed if s.v1_collision and (not s.v2_collision))
    p_worse = _mcnemar_one_sided_v2_worse(b, c)
    rescue_pass = b <= c and p_worse > 0.05

    return V2ChatterSweepResult(
        config=cfg, n_seeds=len(per_seed), per_seed=per_seed,
        median_v1_flip_rate=float(np.median(v1_arr)),
        median_v2_flip_rate=float(np.median(v2_arr)),
        median_flip_rate_reduction=median_red,
        v2_wins_per_seed=v2_wins, v2_win_rate=win_rate,
        chatter_gate_pass=chatter_pass,
        v1_collision_count=sum(v1_collisions),
        v2_collision_count=sum(v2_collisions),
        v1_rescue_v2_collide=b, v1_collide_v2_rescue=c,
        rescue_gate_pass=rescue_pass, mcnemar_p_v2_worse=p_worse,
        promotion_recommended=chatter_pass and rescue_pass,
    )


def test_synth_chatter_clear_pass():
    r = _synth_result(
        v1_rates=[0.5, 0.6, 0.4, 0.5, 0.55],
        v2_rates=[0.0, 0.0, 0.0, 0.0, 0.0],
        v1_collisions=[False] * 5,
        v2_collisions=[False] * 5,
    )
    assert r.median_flip_rate_reduction == pytest.approx(1.0)
    assert r.v2_win_rate == pytest.approx(1.0)
    assert r.chatter_gate_pass


def test_synth_chatter_marginal_fail():
    r = _synth_result(
        v1_rates=[0.5, 0.6, 0.4, 0.5, 0.55],
        v2_rates=[0.45, 0.55, 0.38, 0.48, 0.52],   # ~10% reduction
        v1_collisions=[False] * 5,
        v2_collisions=[False] * 5,
    )
    assert r.median_flip_rate_reduction < 0.5
    assert not r.chatter_gate_pass


def test_synth_rescue_clear_pass():
    """V2 didn't break any rescues; in fact fixed one collision."""
    r = _synth_result(
        v1_rates=[0.5] * 5, v2_rates=[0.0] * 5,
        v1_collisions=[True, False, False, False, False],
        v2_collisions=[False, False, False, False, False],
    )
    assert r.v1_rescue_v2_collide == 0
    assert r.v1_collide_v2_rescue == 1
    assert r.rescue_gate_pass


def test_synth_rescue_clear_fail():
    """V2 broke 5 V1 rescues, fixed 0 collisions."""
    r = _synth_result(
        v1_rates=[0.5] * 5, v2_rates=[0.0] * 5,
        v1_collisions=[False] * 5,
        v2_collisions=[True] * 5,
    )
    assert r.v1_rescue_v2_collide == 5
    assert r.v1_collide_v2_rescue == 0
    assert not r.rescue_gate_pass


def test_synth_promotion_requires_both_gates():
    """Chatter pass + rescue fail ⇒ no promotion."""
    chatter = _synth_result(
        v1_rates=[0.5] * 5, v2_rates=[0.0] * 5,
        v1_collisions=[False] * 5, v2_collisions=[False] * 5,
    )
    rescue = _synth_result(
        v1_rates=[0.5] * 5, v2_rates=[0.0] * 5,
        v1_collisions=[False] * 5,
        v2_collisions=[True] * 5,   # V2 broke 5 rescues
    )
    assert chatter.chatter_gate_pass
    assert not rescue.rescue_gate_pass
    promo = chatter.chatter_gate_pass and rescue.rescue_gate_pass
    assert not promo


@pytest.mark.slow
def test_run_v2_promotion_decision_writes_artifacts(tmp_path):
    """End-to-end orchestration smoke at N=2 — reports written, decision
    field set, both inner sweeps captured."""
    decision = run_v2_promotion_decision(
        chatter_scenario="S1_normal_driving",
        rescue_scenario="S3_map_error_accel",
        N=2,
        base_seed=100,
        output_dir=tmp_path,
        mppi_rollouts=32,
    )
    assert isinstance(decision, V2PromotionDecisionResult)
    assert decision.chatter_sweep.n_seeds == 2
    assert decision.rescue_sweep.n_seeds == 2
    assert (tmp_path / "promotion_decision.json").exists()
    assert (tmp_path / "promotion_decision_report.md").exists()
    payload = json.loads((tmp_path / "promotion_decision.json").read_text())
    assert "chatter_sweep" in payload
    assert "rescue_sweep" in payload
    assert "promotion_recommended" in payload
