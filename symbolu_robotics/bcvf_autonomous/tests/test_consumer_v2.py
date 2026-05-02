"""Tests for the §14a V2 Schmitt-triggered consumer."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    ConsumerState,
    ConsumerV2Config,
    TrustWeightComputer,
)


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #


def test_config_rejects_inverted_thresholds():
    with pytest.raises(ValueError):
        ConsumerV2Config(
            enabled=True,
            engage_threshold=0.2,
            disengage_threshold=0.5,
        )


def test_config_rejects_equal_thresholds():
    with pytest.raises(ValueError):
        ConsumerV2Config(
            enabled=True,
            engage_threshold=0.4,
            disengage_threshold=0.4,
        )


def test_config_rejects_zero_consecutive_counts():
    with pytest.raises(ValueError):
        ConsumerV2Config(enabled=True, T_engage=0)
    with pytest.raises(ValueError):
        ConsumerV2Config(enabled=True, T_disengage=0)


# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #


def _computer(**v2_kwargs) -> TrustWeightComputer:
    c = TrustWeightComputer(BCVFConfig(lambda_c=1.0))
    c.set_v2_consumer(ConsumerV2Config(enabled=True, **v2_kwargs))
    return c


def test_starts_in_uniform_state():
    c = _computer()
    assert c.v2_state == ConsumerState.UNIFORM


def test_engages_after_T_engage_consecutive_above_threshold():
    c = _computer(engage_threshold=0.5, disengage_threshold=0.2, T_engage=3)
    for _ in range(2):
        c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.UNIFORM, "must not engage early"
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.ENGAGED


def test_below_engage_resets_counter():
    """A break in the streak resets the engage counter — three near-misses
    interleaved with a sub-threshold tick must NOT engage."""
    c = _computer(engage_threshold=0.5, T_engage=3)
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    c._update_v2_state(0.4)  # below threshold — resets streak
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.UNIFORM
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.ENGAGED


def test_disengages_after_T_disengage_consecutive_below_threshold():
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=2,
        T_disengage=3,
    )
    # Engage first.
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.ENGAGED

    c._update_v2_state(0.1)
    c._update_v2_state(0.1)
    assert c.v2_state == ConsumerState.ENGAGED, "must not disengage early"
    c._update_v2_state(0.1)
    assert c.v2_state == ConsumerState.UNIFORM


def test_hysteresis_holds_engaged_in_dead_zone():
    """Signal in the (disengage_threshold, engage_threshold) range while
    ENGAGED must not flip the state — that's the entire point of the
    Schmitt trigger."""
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=2,
        T_disengage=3,
    )
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.ENGAGED

    # Dead zone: 50 ticks at 0.3 — never disengages.
    for _ in range(50):
        c._update_v2_state(0.3)
    assert c.v2_state == ConsumerState.ENGAGED


def test_hysteresis_holds_uniform_in_dead_zone():
    """Signal in the dead zone while UNIFORM must not flip either —
    hysteresis goes both ways."""
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=2,
        T_disengage=3,
    )
    for _ in range(50):
        c._update_v2_state(0.3)
    assert c.v2_state == ConsumerState.UNIFORM


def test_state_transition_resets_both_counters():
    """When ENGAGED happens, the disengage counter must be zero so a
    half-counted disengage streak from before doesn't carry over."""
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=2,
        T_disengage=3,
    )
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    # Now ENGAGED — both counters should be zero.
    assert c.v2_state == ConsumerState.ENGAGED
    assert c._v2_above_count == 0
    assert c._v2_below_count == 0


def test_reset_returns_to_uniform_with_zero_counters():
    c = _computer(engage_threshold=0.5, T_engage=2)
    c._update_v2_state(0.6)
    c._update_v2_state(0.6)
    assert c.v2_state == ConsumerState.ENGAGED
    c.reset()
    assert c.v2_state == ConsumerState.UNIFORM
    assert c._v2_above_count == 0
    assert c._v2_below_count == 0


# --------------------------------------------------------------------------- #
# compute() integration — UNIFORM forces 1/M, ENGAGED runs V1 pipeline
# --------------------------------------------------------------------------- #


def _trajectories_with_outlier(K: int = 4, M: int = 3, H: int = 10) -> np.ndarray:
    """Trajectories with predictor 1 quadratically diverging — guarantees
    non-zero per-pred cost and non-uniform softmin weights under V1.
    """
    base = np.zeros((H, 3), dtype=np.float64)
    base[:, 0] = np.arange(H) * 0.5
    arr = np.broadcast_to(base[None, None, :, :], (K, M, H, 3)).copy()
    ks = np.arange(H, dtype=np.float64)
    arr[:, 1, :, 1] += 0.3 * ks * ks
    return arr


def _trajectories_quiet(K: int = 4, M: int = 3, H: int = 10) -> np.ndarray:
    """All predictors identical — bcvf_total ≈ 0 across rollouts."""
    base = np.zeros((H, 3), dtype=np.float64)
    base[:, 0] = np.arange(H) * 0.5
    return np.broadcast_to(base[None, None, :, :], (K, M, H, 3)).copy()


def test_disabled_v2_matches_v1_behavior():
    """With ConsumerV2Config(enabled=False) the result must be identical to
    no V2 config at all — regression check that V2 is opt-in."""
    cfg_disabled = ConsumerV2Config(enabled=False)
    bcvf_cfg = BCVFConfig(lambda_c=1.0)

    a = TrustWeightComputer(bcvf_cfg)
    b = TrustWeightComputer(bcvf_cfg)
    b.set_v2_consumer(cfg_disabled)

    trajs = _trajectories_with_outlier()
    res_a = a.compute(trajs)
    res_b = b.compute(trajs)

    np.testing.assert_array_equal(res_a.weights, res_b.weights)
    assert res_a.v2_state is None
    assert res_b.v2_state is None


def test_uniform_state_forces_uniform_weights_even_with_outlier():
    """Quiet engage signal + strong per-predictor outlier ⇒ V2 stays in
    UNIFORM; weights stay 1/M; the V1 softmin's preferences are
    suppressed. This is the core safety guarantee of V2."""
    c = _computer(engage_threshold=1e9, disengage_threshold=1e8, T_engage=1)
    trajs = _trajectories_with_outlier()
    res = c.compute(trajs)
    assert res.v2_state == "uniform"
    expected = np.full((4, 3), 1 / 3, dtype=np.float64)
    np.testing.assert_allclose(res.weights, expected, atol=1e-12)


def test_engaged_state_runs_v1_softmin():
    """When ENGAGED, V2 must hand off to V1 — non-uniform per-predictor
    cost ⇒ non-uniform weights. The exact ordering depends on the
    pairing mode (anchor splits blame; non-anchor concentrates on the
    outlier), so the assertion is just that weights are not uniform."""
    c = _computer(engage_threshold=0.0, disengage_threshold=-1.0, T_engage=1)
    trajs = _trajectories_with_outlier()
    res = c.compute(trajs)
    assert res.v2_state == "engaged"
    mean_weights = res.weights.mean(axis=0)
    # Not uniform → softmin actually ran (not bypassed).
    assert mean_weights.std() > 1e-6


def test_v2_signal_field_populated():
    """v2_signal in the result must equal bcvf_total.mean() when V2 is on."""
    c = _computer(engage_threshold=1e9, T_engage=1)
    trajs = _trajectories_with_outlier()
    res = c.compute(trajs)
    assert res.v2_signal is not None
    assert res.v2_signal == pytest.approx(float(res.bcvf_total.mean()))


def test_anti_chatter_engage_disengage_sequence():
    """Real-world chatter scenario: signal oscillates around the engage
    threshold but never sustains either direction. V2 must NOT flip
    states. V1 (without V2) would flip its softmin output every tick."""
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=3,
        T_disengage=3,
    )
    seq = [0.6, 0.4, 0.6, 0.4, 0.6, 0.4] * 5  # 30 ticks oscillating
    for s in seq:
        c._update_v2_state(s)
    assert c.v2_state == ConsumerState.UNIFORM


def test_strong_sustained_failure_engages_and_stays():
    c = _computer(
        engage_threshold=0.5,
        disengage_threshold=0.2,
        T_engage=3,
        T_disengage=3,
    )
    for _ in range(20):
        c._update_v2_state(2.0)
    assert c.v2_state == ConsumerState.ENGAGED


# --------------------------------------------------------------------------- #
# Integration with TrustDiagnosticsRecorder
# --------------------------------------------------------------------------- #


def test_diagnostics_record_carries_v2_state():
    from symbolu_robotics.bcvf_autonomous import TrustDiagnosticsRecorder

    c = _computer(engage_threshold=1e9, T_engage=1)  # locked UNIFORM
    rec = TrustDiagnosticsRecorder(M=3)
    trajs = _trajectories_with_outlier()
    res = c.compute(trajs)
    record = rec.record(res)
    assert record.v2_state == "uniform"
    assert record.v2_signal is not None


def test_episode_record_serializes_v2_fields():
    from symbolu_robotics.bcvf_autonomous import TrustDiagnosticsRecorder

    c = _computer(engage_threshold=1e9, T_engage=1)
    rec = TrustDiagnosticsRecorder(M=3)
    trajs = _trajectories_with_outlier()
    for _ in range(3):
        rec.record(c.compute(trajs))

    episode = rec.finalize()
    assert episode.per_step_v2_state == ["uniform", "uniform", "uniform"]
    assert episode.per_step_v2_signal.shape == (3,)

    payload = json.loads(json.dumps(episode.to_dict()))
    assert payload["per_step_v2_state"] == ["uniform"] * 3
    assert len(payload["per_step_v2_signal"]) == 3


# --------------------------------------------------------------------------- #
# End-to-end through Runner
# --------------------------------------------------------------------------- #


def test_runner_v2_enabled_reports_v2_diagnostics(tmp_path):
    from symbolu_robotics.bcvf_autonomous import (
        MPPIConfig,
        PerfCostConfig,
        Runner,
        SimConfig,
    )
    from symbolu_robotics.bcvf_autonomous.runner import RunConfig
    from symbolu_robotics.bcvf_autonomous.simulator import (
        make_straight_road,
    )

    diag_path = tmp_path / "v2_diag.json"
    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1,
            max_steps=8,
            road=make_straight_road(length=80.0),
            obstacles=[],
            seed=4,
        ),
        mppi=MPPIConfig(num_rollouts=64, horizon=10, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=4,
        trust_diagnostics_enabled=True,
        trust_diagnostics_path=str(diag_path),
        v2_enabled=True,
        v2_engage_threshold=0.5,
        v2_disengage_threshold=0.2,
        v2_T_engage=3,
        v2_T_disengage=3,
    )
    runner = Runner(cfg)
    runner.run()

    diag = runner.trust_diagnostics()
    assert diag is not None
    assert all(s in ("uniform", "engaged") for s in diag.per_step_v2_state)

    with open(diag_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert "per_step_v2_state" in payload["diagnostics"]
    assert "per_step_v2_signal" in payload["diagnostics"]
    assert len(payload["diagnostics"]["per_step_v2_state"]) == diag.n_steps


def test_runner_v2_disabled_keeps_v2_state_empty():
    from symbolu_robotics.bcvf_autonomous import (
        MPPIConfig,
        PerfCostConfig,
        Runner,
        SimConfig,
    )
    from symbolu_robotics.bcvf_autonomous.runner import RunConfig
    from symbolu_robotics.bcvf_autonomous.simulator import (
        make_straight_road,
    )

    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1, max_steps=4,
            road=make_straight_road(length=50.0),
            obstacles=[], seed=0,
        ),
        mppi=MPPIConfig(num_rollouts=16, horizon=8, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=0,
        trust_diagnostics_enabled=True,
        v2_enabled=False,
    )
    runner = Runner(cfg)
    runner.run()
    diag = runner.trust_diagnostics()
    assert diag is not None
    # V2 disabled ⇒ every per-step state is the empty marker.
    assert all(s == "" for s in diag.per_step_v2_state)
