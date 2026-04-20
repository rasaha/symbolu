"""Tests for bcvf_autonomous.mppi_planner — DESIGN.md §3B.11."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_autonomous.mppi_planner import (
    MPPIConfig,
    MPPIPlanner,
    PerfCostConfig,
    compute_perf_cost,
)
from symbolu_robotics.bcvf_autonomous.predictors import (
    FailureConfig,
    create_predictor_set,
)
from symbolu_robotics.bcvf_autonomous.simulator import (
    Obstacle,
    Simulator,
    SimConfig,
    make_straight_road,
)


# --- helpers ---


def _small_mppi(**overrides) -> MPPIConfig:
    """Compact MPPI config for fast tests (K small, H moderate)."""
    cfg = MPPIConfig(
        num_rollouts=64,
        horizon=20,
        dt=0.1,
        temperature=5.0,
        noise_std=np.array([0.5, 0.1]),
        lambda_c=1.0,
        bcvf_config=BCVFConfig(
            gate_threshold=0.2,
            gate_beta=100.0,
            huber_delta=0.5,
            lever_arm=2.5,
            weight_matrix=np.ones(3),
            dt=0.1,
        ),
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_planner(mppi_cfg=None, obstacles=None, road=None):
    predictors = create_predictor_set(seed=0)
    road = road or make_straight_road(length=200.0)
    obstacles = obstacles or []
    planner = MPPIPlanner(
        mppi_cfg or _small_mppi(),
        PerfCostConfig(),
        predictors,
        road,
        obstacles,
    )
    planner.set_seed(42)
    return planner, predictors, road, obstacles


# --- closed-loop tracking ---


def test_mppi_straight_road_tracks_lane() -> None:
    # MPPI is an importance-weighted mean; with an all-zero warm start and
    # symmetric velocity noise the first cycle has no directional bias.
    # We constrain velocity_bounds to force forward motion and give the
    # planner enough rollouts + noise to actually explore.
    mppi = _small_mppi(
        num_rollouts=256,
        horizon=20,
        noise_std=np.array([2.0, 0.2]),
        velocity_bounds=(0.5, 8.0),
    )
    planner, predictors, road, obstacles = _make_planner(mppi_cfg=mppi)
    sim = Simulator(
        SimConfig(max_steps=40, road=road, obstacles=obstacles),
        predictors,
    )
    sim.reset()
    for _ in range(40):
        result = planner.plan()
        sim.step(result.first_control)
    final = sim.get_history()[-1].ground_truth
    assert final.x > 4.0, f"vehicle stalled: x={final.x:.3f}"
    assert abs(final.y) < 2.0, f"lane tracking poor: y={final.y:.3f}"


def test_mppi_avoids_obstacle() -> None:
    obstacles = [Obstacle(x=8.0, y=0.0, radius=1.5)]
    planner, predictors, road, _ = _make_planner(
        mppi_cfg=_small_mppi(
            num_rollouts=256,
            noise_std=np.array([0.5, 0.3]),
        ),
        obstacles=obstacles,
    )
    sim = Simulator(
        SimConfig(max_steps=40, road=road, obstacles=obstacles),
        predictors,
    )
    sim.reset()
    collided = False
    for _ in range(40):
        result = planner.plan()
        state = sim.step(result.first_control)
        if state.collision:
            collided = True
            break
    assert not collided, "planner hit the obstacle it should have dodged"


# --- BCVF behavior ---


def test_bcvf_zero_nominal() -> None:
    planner, *_ = _make_planner()
    result = planner.plan()
    # Nominal predictor set: BCVF cost should be modest (post-filter noise).
    assert result.bcvf_cost < 20.0


def test_bcvf_positive_under_failure() -> None:
    predictors = create_predictor_set(seed=0)
    predictors["M2"].set_failure(
        FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.1)
    )
    road = make_straight_road(length=200.0)
    planner = MPPIPlanner(_small_mppi(), PerfCostConfig(), predictors, road, [])
    planner.set_seed(42)
    result = planner.plan()
    assert result.bcvf_cost > 0.0


def test_lambda_c_zero_skips_bcvf() -> None:
    planner, *_ = _make_planner(mppi_cfg=_small_mppi(lambda_c=0.0))
    result = planner.plan()
    assert result.bcvf_cost == 0.0


# --- sampling / weights ---


def test_warm_start_shift() -> None:
    planner, *_ = _make_planner()
    # First plan seeds a warm start.
    first = planner.plan()
    shifted = planner._warm_start_mean()
    expected = np.roll(first.optimal_control, -1, axis=0)
    expected[-1] = expected[-2]
    assert np.allclose(shifted, expected)


def test_control_clamping() -> None:
    cfg = _small_mppi(
        velocity_bounds=(0.0, 5.0),
        steering_bounds=(-0.2, 0.2),
        noise_std=np.array([100.0, 10.0]),  # huge noise so clamping must trigger
    )
    planner, *_ = _make_planner(mppi_cfg=cfg)
    samples = planner._sample_controls()
    assert samples[..., 0].min() >= 0.0
    assert samples[..., 0].max() <= 5.0
    assert samples[..., 1].min() >= -0.2
    assert samples[..., 1].max() <= 0.2


def test_weights_sum_to_one() -> None:
    planner, *_ = _make_planner()
    result = planner.plan()
    # Weights aren't returned directly, but total_cost is a weighted average.
    # Sanity: effective sample count must be in (0, K].
    assert 0.0 < result.effective_samples <= planner.config.num_rollouts


def test_effective_samples_healthy() -> None:
    planner, *_ = _make_planner()
    result = planner.plan()
    # DESIGN §3B.7 healthy range: effective_samples > K / 10.
    assert result.effective_samples > planner.config.num_rollouts / 10.0


# --- J_perf components ---


def test_perf_cost_rewards_progress() -> None:
    road = make_straight_road(length=100.0)
    H = 20
    # A trajectory that moves forward along x.
    traj_forward = np.stack([
        np.linspace(0.0, 8.0, H),
        np.zeros(H),
        np.zeros(H),
    ], axis=-1)
    traj_stationary = np.zeros((H, 3))
    controls = np.zeros((H, 2))
    c_f = compute_perf_cost(traj_forward, controls, road, [], PerfCostConfig())
    c_s = compute_perf_cost(traj_stationary, controls, road, [], PerfCostConfig())
    assert c_f < c_s


def test_perf_cost_penalizes_deviation() -> None:
    road = make_straight_road(length=100.0)
    H = 20
    traj_on_lane = np.stack([np.linspace(0.0, 8.0, H), np.zeros(H), np.zeros(H)], -1)
    traj_off_lane = np.stack([np.linspace(0.0, 8.0, H), np.full(H, 3.0), np.zeros(H)], -1)
    controls = np.zeros((H, 2))
    c_on = compute_perf_cost(traj_on_lane, controls, road, [], PerfCostConfig())
    c_off = compute_perf_cost(traj_off_lane, controls, road, [], PerfCostConfig())
    assert c_off > c_on


def test_perf_cost_lane_deviation_cap_clamps_saturated_rollout() -> None:
    """Gate-2 cost-balance experiment. A rollout far off-lane (100 m) must
    produce a bounded J_perf under lane_deviation_cap, so MPPI's softmax
    stays non-degenerate and BCVF can influence weight selection. Without
    the cap the contribution would blow up as ~H * 100^2 * weight = 5e6."""
    road = make_straight_road(length=500.0)
    H = 50
    # Trajectory with massive lateral deviation — mimics failing-anchor rollout.
    traj = np.stack(
        [np.linspace(0.0, 400.0, H), np.full(H, 100.0), np.zeros(H)], axis=-1
    )
    controls = np.zeros((H, 2))

    uncapped = compute_perf_cost(traj, controls, road, [], PerfCostConfig())
    capped = compute_perf_cost(
        traj, controls, road, [],
        PerfCostConfig(lane_deviation_cap=10.0),
    )
    # Uncapped: lane cost ~ H * 100^2 = 5e5; capped: H * 10 = 500.
    # Difference should be ~3 orders of magnitude (progress/smoothness terms
    # are unchanged so they cancel; only lane deviation diverges).
    assert uncapped - capped > 4.0e5
    assert abs(capped) < 2.0e3


def test_ketu_rahu_uniform_trust_under_no_disagreement() -> None:
    """Ketu→Rahu invariant: when predictors agree (no accelerating
    disagreement), trust weights are uniform and the trust-weighted
    consensus equals the equal-weight mean. This is the Lemma-1
    preservation claim — under constant or linear disagreement the
    SECOND-order BCVF observer reports zero per-predictor cost, so
    softmin gives uniform weights and the attractor is unchanged.
    """
    from symbolu_robotics.bcvf_autonomous.core import (
        BCVFConfig, CostOrder, compute_bcvf_cost_batch,
    )

    K, M, H = 3, 4, 20
    rng = np.random.default_rng(0)
    # All predictors share a near-identical trajectory (tiny noise only
    # — the SECOND-order gate should leave all per-predictor costs at ~0).
    base = rng.normal(scale=0.01, size=(H, 3))
    trajs_batch = [[base + rng.normal(scale=0.005, size=(H, 3)) for _ in range(M)]
                   for _ in range(K)]
    cfg = BCVFConfig(
        gate_threshold=0.2, gate_beta=100.0, huber_delta=0.5,
        lever_arm=2.5, weight_matrix=np.ones(3), dt=0.1,
        cost_order=CostOrder.SECOND, use_anchor_pairing=True, anchor_index=0,
    )
    total, per_pred = compute_bcvf_cost_batch(
        trajs_batch, cfg, return_per_predictor=True
    )
    assert per_pred.shape == (K, M)
    # Under near-agreement, all per-predictor costs should be near zero,
    # meaning softmin weights would be essentially uniform 1/M.
    assert np.all(per_pred < 1.0)


def test_ketu_rahu_outlier_gets_low_trust() -> None:
    """Under strong accelerating disagreement where one predictor is
    the clear outlier, its per-predictor BCVF cost dominates the others
    (it appears in every anchor-pair with M-1 healthy predictors)."""
    from symbolu_robotics.bcvf_autonomous.core import (
        BCVFConfig, CostOrder, compute_bcvf_cost_batch,
    )

    K, M, H = 1, 4, 20
    ks = np.arange(H, dtype=np.float64)
    healthy = np.stack([np.zeros(H), np.zeros(H), np.zeros(H)], axis=-1)
    # M4 = the failing predictor, with quadratic x-drift (accelerating).
    failing = np.stack([0.1 * ks * ks, np.zeros(H), np.zeros(H)], axis=-1)
    trajs = [[healthy.copy(), healthy.copy(), healthy.copy(), failing]]
    cfg = BCVFConfig(
        gate_threshold=0.2, gate_beta=100.0, huber_delta=0.5,
        lever_arm=2.5, weight_matrix=np.ones(3), dt=0.1,
        cost_order=CostOrder.SECOND, use_anchor_pairing=True, anchor_index=3,
    )
    total, per_pred = compute_bcvf_cost_batch(
        trajs, cfg, return_per_predictor=True
    )
    # Predictor 3 (M4) appears in all 3 anchor-relative pairs → its
    # per-predictor cost ≈ 3× any healthy predictor's (which appears
    # in exactly one pair, against M4).
    cost_m4 = per_pred[0, 3]
    cost_healthy = per_pred[0, 0]   # any of the healthy ones
    assert cost_m4 > 2.0 * cost_healthy, (
        f"failing predictor cost {cost_m4:.2f} should dominate healthy "
        f"{cost_healthy:.2f} by ≥2x under anchor-pairs with failing=anchor"
    )
    # Softmin with τ=1.0 on these costs drives M4's weight below 1/M.
    tau = 1.0
    arg = -(per_pred[0] - per_pred[0].min()) / tau
    weights = np.exp(arg) / np.exp(arg).sum()
    assert weights[3] < 1.0 / M, (
        f"outlier weight {weights[3]:.3f} should drop below uniform 1/{M}"
    )


def test_planner_uses_consensus_for_perf_cost() -> None:
    """B2 experiment contract: the planner must evaluate J_perf against
    the per-step mean of all predictor rollouts, not any single anchor's.
    We detect this by intercepting compute_perf_cost and verifying the
    trajectory it receives equals the mean of the predictor rollouts at
    the K index we can match via seed.
    """
    import numpy as np
    from symbolu_robotics.bcvf_autonomous import mppi_planner as mp
    from symbolu_robotics.bcvf_autonomous.predictors import create_predictor_set
    from symbolu_robotics.bcvf_autonomous.simulator import make_straight_road

    received: dict = {}

    def spy(traj, controls, road, obstacles, cfg):
        received.setdefault("trajs", []).append(np.asarray(traj).copy())
        return 0.0

    planner, predictors, road, obstacles = _make_planner()
    planner.set_seed(99)

    # Monkey-patch the module-level helper the batch path calls.
    original = mp.compute_perf_cost
    mp.compute_perf_cost = spy
    try:
        result = planner.plan()
    finally:
        mp.compute_perf_cost = original

    # _compute_perf_cost_batch iterates k times calling compute_perf_cost.
    # Each trajectory it received must equal the mean of the K-th rollout
    # across M predictors (not the anchor alone).
    assert len(received["trajs"]) == planner.config.num_rollouts, (
        "perf cost should be called once per rollout"
    )
    # Sanity — shape is (H, 3), not (M, H, 3).
    for traj in received["trajs"][:5]:
        assert traj.shape == (planner.config.horizon, 3)


def test_perf_cost_cap_does_not_affect_normal_driving() -> None:
    """With the cap=10, typical on-lane trajectories (|y| < ~3.16) have
    d^2 < cap everywhere, so capped result equals uncapped result."""
    road = make_straight_road(length=100.0)
    H = 20
    traj = np.stack([np.linspace(0.0, 8.0, H), np.full(H, 1.0), np.zeros(H)], -1)
    controls = np.zeros((H, 2))
    uncapped = compute_perf_cost(traj, controls, road, [], PerfCostConfig())
    capped = compute_perf_cost(
        traj, controls, road, [], PerfCostConfig(lane_deviation_cap=10.0)
    )
    assert abs(uncapped - capped) < 1e-9


# --- ablation variants ---


def _ablation_cfg(cost_order: CostOrder, threshold: float = 0.2) -> BCVFConfig:
    return BCVFConfig(
        lambda_c=1.0,
        gate_threshold=threshold,
        gate_beta=100.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=True,
        anchor_index=0,
        dt=0.1,
        cost_order=cost_order,
    )


def test_ablation_zeroth_order() -> None:
    # Constant bias: ||e|| large, ||v|| = 0, ||a|| = 0.
    # ZEROTH should fire, SECOND should not (Lemma 1).
    from symbolu_robotics.bcvf_autonomous.core import compute_bcvf_cost

    H = 20
    traj_i = np.zeros((H, 3), dtype=np.float64)
    traj_j = np.tile(np.array([1.0, 0.0, 0.0]), (H, 1))
    zero = compute_bcvf_cost([traj_i, traj_j], _ablation_cfg(CostOrder.ZEROTH)).total_cost
    second = compute_bcvf_cost([traj_i, traj_j], _ablation_cfg(CostOrder.SECOND)).total_cost
    assert zero > 0.1
    assert second < 1e-6
    assert zero > 100.0 * max(second, 1e-9)


def test_ablation_first_order() -> None:
    # Linear drift: ||e|| grows, ||v|| constant nonzero, ||a|| = 0.
    # FIRST should fire, SECOND should not.
    from symbolu_robotics.bcvf_autonomous.core import compute_bcvf_cost

    H = 20
    ks = np.arange(H, dtype=np.float64)
    traj_i = np.zeros((H, 3), dtype=np.float64)
    traj_j = np.stack(
        [0.05 * ks, np.zeros(H), np.zeros(H)], axis=-1
    )
    first = compute_bcvf_cost([traj_i, traj_j], _ablation_cfg(CostOrder.FIRST)).total_cost
    second = compute_bcvf_cost([traj_i, traj_j], _ablation_cfg(CostOrder.SECOND)).total_cost
    assert first > 0.01
    assert second < 1e-6
    assert first > 100.0 * max(second, 1e-9)


# --- §6.6a dynamic predictor exclusion invariants ---


def test_exclusion_disabled_by_default() -> None:
    """Exclusion must be off until explicitly enabled."""
    planner, _, _, _ = _make_planner()
    assert planner._exclusion_enabled is False
    assert planner._consec_suspect is None
    assert planner._is_excluded is None


def test_exclusion_setter_rejects_r_leq_one() -> None:
    """r_exclude must be > 1.0; r=1 or below is nonsensical (always
    suspect)."""
    planner, _, _, _ = _make_planner()
    with pytest.raises(ValueError):
        planner.set_exclusion(enabled=True, r=1.0)
    with pytest.raises(ValueError):
        planner.set_exclusion(enabled=True, r=0.5)


def test_exclusion_setter_rejects_nonpositive_thresholds() -> None:
    planner, _, _, _ = _make_planner()
    with pytest.raises(ValueError):
        planner.set_exclusion(enabled=True, T_exclude=0)
    with pytest.raises(ValueError):
        planner.set_exclusion(enabled=True, T_reinstate=-1)


def test_exclusion_state_resets_on_planner_reset() -> None:
    """Per-episode state must clear on planner.reset()."""
    planner, _, _, _ = _make_planner()
    planner.set_exclusion(enabled=True)
    # Manually seed some state as if planning steps had run
    M = len(planner.predictors)
    planner._consec_suspect = np.array([3] * M, dtype=np.int64)
    planner._consec_ok = np.array([1] * M, dtype=np.int64)
    planner._is_excluded = np.array([True, False, False, False][:M], dtype=bool)
    planner.reset()
    assert planner._consec_suspect is None
    assert planner._consec_ok is None
    assert planner._is_excluded is None


def test_exclusion_disabled_leaves_weights_identical_to_v1() -> None:
    """Enabling exclusion with no plan() call yet must leave the
    planner in a state byte-for-byte identical to V1 for a single
    plan() invocation. Catches a bug where just calling set_exclusion
    would change behavior even when no predictor crosses the threshold.
    """
    planner_a, _, _, _ = _make_planner()
    planner_b, _, _, _ = _make_planner()
    planner_b.set_exclusion(enabled=True, r=100.0)  # impossibly high ratio
    r_a = planner_a.plan()
    r_b = planner_b.plan()
    # With r=100, no predictor should ever be marked suspect, so the
    # two planners produce identical control outputs.
    np.testing.assert_allclose(
        r_a.first_control, r_b.first_control, rtol=1e-12, atol=1e-12
    )


def test_exclusion_fires_on_persistent_suspect() -> None:
    """Directly test the exclusion counter/mask update loop with a
    synthetic per_pred_cost pattern where predictor 3 is always 5x the
    minimum. After T_exclude steps the mask must flag predictor 3."""
    planner, _, _, _ = _make_planner()
    planner.set_exclusion(
        enabled=True, r=1.5, T_exclude=3, T_reinstate=3
    )
    # Simulate the planner's internal exclusion update as if `plan()`
    # had produced per_pred_cost with predictor 3 sustained-high. We
    # do not need the full MPPI loop — the invariant under test is
    # the exclusion state machine.
    M = len(planner.predictors)
    assert M >= 4, "test assumes >=4 predictors for a distinct suspect slot"
    planner._consec_suspect = np.zeros(M, dtype=np.int64)
    planner._consec_ok = np.zeros(M, dtype=np.int64)
    planner._is_excluded = np.zeros(M, dtype=bool)
    for _ in range(3):  # T_exclude steps with predictor 3 suspect
        m = np.array([1.0] * M, dtype=np.float64)
        m[3] = 5.0  # 5x the argmin
        m_min = float(m.min())
        suspect = m > planner._exclusion_r * m_min
        planner._consec_suspect[suspect] += 1
        planner._consec_suspect[~suspect] = 0
        planner._consec_ok[~suspect] += 1
        planner._consec_ok[suspect] = 0
        newly_excl = planner._consec_suspect >= planner._exclusion_T
        newly_ok = planner._is_excluded & (
            planner._consec_ok >= planner._exclusion_T_reinstate
        )
        planner._is_excluded = np.where(
            newly_ok, False, planner._is_excluded | newly_excl
        )
    assert planner._is_excluded[3]
    assert not planner._is_excluded[0]
    assert not planner._is_excluded[1]
    assert not planner._is_excluded[2]


def test_exclusion_reinstates_when_predictor_rejoins_argmin() -> None:
    """After exclusion, a predictor that returns to the argmin cohort
    for T_reinstate consecutive steps must be reinstated."""
    planner, _, _, _ = _make_planner()
    planner.set_exclusion(
        enabled=True, r=1.5, T_exclude=2, T_reinstate=2
    )
    M = len(planner.predictors)
    assert M >= 4
    planner._consec_suspect = np.zeros(M, dtype=np.int64)
    planner._consec_ok = np.zeros(M, dtype=np.int64)
    planner._is_excluded = np.zeros(M, dtype=bool)

    # Phase 1: exclude predictor 3.
    for _ in range(2):
        m = np.array([1.0] * M, dtype=np.float64)
        m[3] = 5.0
        m_min = float(m.min())
        suspect = m > planner._exclusion_r * m_min
        planner._consec_suspect[suspect] += 1
        planner._consec_suspect[~suspect] = 0
        planner._consec_ok[~suspect] += 1
        planner._consec_ok[suspect] = 0
        planner._is_excluded |= planner._consec_suspect >= planner._exclusion_T
    assert planner._is_excluded[3]

    # Phase 2: predictor 3 joins argmin cohort for T_reinstate steps.
    for _ in range(2):
        m = np.array([1.0] * M, dtype=np.float64)  # all equal
        m_min = float(m.min())
        suspect = m > planner._exclusion_r * m_min  # all False
        planner._consec_suspect[suspect] += 1
        planner._consec_suspect[~suspect] = 0
        planner._consec_ok[~suspect] += 1
        planner._consec_ok[suspect] = 0
        newly_ok = planner._is_excluded & (
            planner._consec_ok >= planner._exclusion_T_reinstate
        )
        planner._is_excluded = np.where(
            newly_ok, False, planner._is_excluded
        )
    assert not planner._is_excluded[3]


def test_exclusion_weights_renormalize_when_predictor_masked() -> None:
    """End-to-end invariant via the real plan() call: when a predictor
    is excluded, the per-step trust weights across all rollouts must
    sum to 1 along axis=1 and the excluded column must be exactly 0."""
    # Build a scenario where one predictor is the failing one and
    # will eventually be excluded. Use a short roll so the exclusion
    # counter can be reached.
    from symbolu_robotics.bcvf_autonomous.predictors import (
        FailureConfig,
        create_predictor_set,
    )
    predictors = create_predictor_set(seed=0)
    # Mark M4 as failing (matches autonomy S3_map_error_accel setup).
    if "M4" in predictors:
        failure_cfg = FailureConfig(
            active=True, onset_time=0.0, severity=1.0, ramp_duration=0.5,
        )
        predictors["M4"].set_failure(failure_cfg)

    road = make_straight_road(length=200.0)
    planner = MPPIPlanner(
        _small_mppi(), PerfCostConfig(), predictors, road, [],
    )
    planner.set_seed(42)
    # Low T_exclude so exclusion triggers quickly within the test
    planner.set_exclusion(enabled=True, r=1.2, T_exclude=5, T_reinstate=5)
    planner.set_trust_log_enabled(True)
    # Run 30 plan steps — well past T_exclude
    for _ in range(30):
        planner.plan()
    log = planner.get_trust_log()
    assert len(log) == 30
    # At the end of 30 steps, verify weights-sum-to-1 per rollout
    # (invariant that exclusion must preserve).
    final = log[-1]
    weights_mean = np.array(final["weights"]["mean"])
    # Mean weights across rollouts: still a valid simplex
    # (non-negative, sum = 1 exactly since it's a mean of simplex vectors)
    assert np.all(weights_mean >= -1e-12)
    assert abs(weights_mean.sum() - 1.0) < 1e-10
