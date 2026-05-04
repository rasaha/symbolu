"""Tests for the multi-modal predictor adapter (`MULTI_MODAL_PREDICTORS_DESIGN.md`).

The thin-shim approach lifts non-SE(2) predictor outputs (lane-frame
``(s, d, psi)``) into SE(2) world-frame at the boundary, then feeds
the existing kernel unchanged. The load-bearing test is
:func:`test_lemma_1_carries_on_curved_lane` — the corrected
finding from §4.2 of the design doc, that BCVF's invariance
**survives the lift even on curved lanes** because the body-frame
error primitive transforms correctly with lane curvature.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    CostOrder,
    compute_bcvf_cost,
)
from symbolu_robotics.bcvf_autonomous.predictors import (
    LaneAnchor,
    MultiModalPredictor,
    PredictorStateSpace,
    lane_frame_to_se2,
    se2_to_lane_frame,
    unify_to_se2_bundle,
)


def _v1_config() -> BCVFConfig:
    return BCVFConfig(
        lambda_c=1.0,
        gate_threshold=0.05,
        gate_beta=400.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=False,
        anchor_index=0,
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )


# --------------------------------------------------------------------------- #
# LaneAnchor — geometry primitive
# --------------------------------------------------------------------------- #


def test_lane_anchor_straight_x_axis_has_zero_heading_throughout():
    a = LaneAnchor.straight_x_axis(length=100.0, n=11)
    assert a.n_waypoints == 11
    assert a.total_length == pytest.approx(100.0, abs=1e-12)
    np.testing.assert_allclose(a.centerline[:, 2], 0.0, atol=1e-12)


def test_lane_anchor_constant_curvature_is_circular_arc():
    a = LaneAnchor.constant_curvature(radius=50.0, arc_length=50.0, n=51)
    assert a.n_waypoints == 51
    # All centerline points lie on a circle of radius 50 centred at (0, 50).
    cx, cy = 0.0, 50.0
    radii = np.sqrt(
        (a.centerline[:, 0] - cx) ** 2 + (a.centerline[:, 1] - cy) ** 2
    )
    np.testing.assert_allclose(radii, 50.0, atol=1e-9)
    # Polyline arc length (sum of chord lengths) is slightly less than
    # the smooth arc length because chord ≤ arc; this is the
    # discretisation the lookup uses, so the test pins the actual
    # value the LaneAnchor stores rather than the smooth-curve target.
    assert a.total_length == pytest.approx(50.0, rel=1e-3)
    assert a.total_length <= 50.0


def test_lane_anchor_from_waypoints_rejects_zero_length_segment():
    waypoints = np.array([[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    with pytest.raises(ValueError):
        LaneAnchor.from_waypoints(waypoints)


def test_lane_anchor_from_waypoints_rejects_too_few():
    with pytest.raises(ValueError):
        LaneAnchor.from_waypoints(np.array([[0.0, 0.0]]))


def test_lane_anchor_constant_curvature_rejects_zero_radius():
    with pytest.raises(ValueError):
        LaneAnchor.constant_curvature(radius=0.0)


def test_lane_anchor_post_init_rejects_misshaped_centerline():
    with pytest.raises(ValueError):
        LaneAnchor(
            centerline=np.zeros((3, 2)),   # missing theta column
            arc_lengths=np.zeros(3),
        )


def test_lane_anchor_post_init_rejects_non_monotone_arc_lengths():
    with pytest.raises(ValueError):
        LaneAnchor(
            centerline=np.zeros((3, 3)),
            arc_lengths=np.array([0.0, 1.0, 0.5]),
        )


def test_lane_anchor_s_to_world_clips_outside_range():
    a = LaneAnchor.straight_x_axis(length=10.0, n=2)
    # Inside range — interpolated.
    x, y, theta = a.s_to_world(5.0)
    assert x == pytest.approx(5.0)
    assert y == pytest.approx(0.0)
    # Past the end clips to last waypoint.
    x, y, _ = a.s_to_world(99.0)
    assert x == pytest.approx(10.0)
    # Negative clips to first waypoint.
    x, y, _ = a.s_to_world(-5.0)
    assert x == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Lift / inverse-lift
# --------------------------------------------------------------------------- #


def test_lane_frame_to_se2_on_straight_lane_is_pass_through():
    """On a straight x-axis lane, lane-frame ``(s, d, psi)`` lifts
    bit-exact to SE(2) ``(s, d, psi)`` — Lemma-1-clean baseline."""
    anchor = LaneAnchor.straight_x_axis(length=50.0, n=11)
    H, dt = 10, 0.1
    s = 5.0 * dt * np.arange(H)
    lane = np.column_stack([s, np.full(H, 0.5), np.zeros(H)])
    se2 = lane_frame_to_se2(lane, anchor)
    np.testing.assert_allclose(se2[:, 0], s, atol=1e-12)
    np.testing.assert_allclose(se2[:, 1], 0.5, atol=1e-12)
    np.testing.assert_allclose(se2[:, 2], 0.0, atol=1e-12)


def test_round_trip_identity_on_straight_lane():
    """``se2_to_lane_frame ∘ lane_frame_to_se2`` is identity on the
    straight x-axis (modulo fp64 noise) — pins the inverse for
    cross-modal verification at the deployment-partner layer."""
    anchor = LaneAnchor.straight_x_axis(length=50.0, n=11)
    H = 10
    s = np.arange(H, dtype=np.float64)
    lane = np.column_stack([s, np.linspace(-0.4, 0.4, H), np.linspace(-0.1, 0.1, H)])
    se2 = lane_frame_to_se2(lane, anchor)
    recovered = se2_to_lane_frame(se2, anchor)
    np.testing.assert_allclose(recovered, lane, atol=1e-9)


def test_lane_frame_to_se2_rejects_misshaped_input():
    anchor = LaneAnchor.straight_x_axis()
    with pytest.raises(ValueError):
        lane_frame_to_se2(np.zeros((10, 2)), anchor)


def test_se2_to_lane_frame_rejects_misshaped_input():
    anchor = LaneAnchor.straight_x_axis()
    with pytest.raises(ValueError):
        se2_to_lane_frame(np.zeros((10, 2)), anchor)


# --------------------------------------------------------------------------- #
# MultiModalPredictor wrapper + bundle adapter
# --------------------------------------------------------------------------- #


def test_multi_modal_predictor_rejects_misshaped_trajectory():
    with pytest.raises(ValueError):
        MultiModalPredictor(
            trajectory=np.zeros((10, 2)),
            state_space=PredictorStateSpace.SE2_WORLD,
        )


def test_multi_modal_predictor_lane_frame_requires_anchor():
    with pytest.raises(ValueError):
        MultiModalPredictor(
            trajectory=np.zeros((10, 3)),
            state_space=PredictorStateSpace.LANE_FRAME,
            lane_anchor=None,
        )


def test_multi_modal_predictor_se2_must_not_carry_anchor():
    """Se2 predictors must NOT carry a lane_anchor — failing loud
    catches a copy-paste bug where a lane anchor is accidentally
    attached to an SE(2) predictor (and would be silently ignored)."""
    anchor = LaneAnchor.straight_x_axis()
    with pytest.raises(ValueError):
        MultiModalPredictor(
            trajectory=np.zeros((10, 3)),
            state_space=PredictorStateSpace.SE2_WORLD,
            lane_anchor=anchor,
        )


def test_unify_bundle_passes_through_se2_unchanged():
    """All-SE(2) bundle reproduces the existing single-modal input shape."""
    H = 10
    p0 = np.column_stack([np.arange(H, dtype=np.float64), np.zeros(H), np.zeros(H)])
    p1 = p0 + 0.5
    bundle = [
        MultiModalPredictor(p0, PredictorStateSpace.SE2_WORLD),
        MultiModalPredictor(p1, PredictorStateSpace.SE2_WORLD),
    ]
    trajs = unify_to_se2_bundle(bundle)
    assert trajs.shape == (2, H, 3)
    np.testing.assert_array_equal(trajs[0], p0)
    np.testing.assert_array_equal(trajs[1], p1)


def test_unify_bundle_rejects_mismatched_horizons():
    p0 = np.zeros((10, 3))
    p1 = np.zeros((11, 3))
    bundle = [
        MultiModalPredictor(p0, PredictorStateSpace.SE2_WORLD),
        MultiModalPredictor(p1, PredictorStateSpace.SE2_WORLD),
    ]
    with pytest.raises(ValueError):
        unify_to_se2_bundle(bundle)


def test_unify_bundle_rejects_empty():
    with pytest.raises(ValueError):
        unify_to_se2_bundle([])


def test_unify_bundle_lifts_lane_frame_to_se2():
    anchor = LaneAnchor.straight_x_axis(length=50.0, n=11)
    H = 5
    s = np.arange(H, dtype=np.float64)
    se2 = np.column_stack([s, np.zeros(H), np.zeros(H)])
    lane = np.column_stack([s, np.full(H, 0.3), np.zeros(H)])
    bundle = [
        MultiModalPredictor(se2, PredictorStateSpace.SE2_WORLD),
        MultiModalPredictor(lane, PredictorStateSpace.LANE_FRAME, anchor),
    ]
    trajs = unify_to_se2_bundle(bundle)
    np.testing.assert_array_equal(trajs[0], se2)
    np.testing.assert_allclose(trajs[1, :, 1], 0.3, atol=1e-12)


# --------------------------------------------------------------------------- #
# Lemma 1 carry-through — the load-bearing finding from DESIGN.md §4
# --------------------------------------------------------------------------- #


def test_lemma_1_carries_on_straight_lane():
    """§4.1: on a straight lane, a constant lateral offset between
    predictors lifts to a constant SE(2) offset → BCVF stays exactly
    zero. The Lemma-1-clean baseline."""
    anchor = LaneAnchor.straight_x_axis(length=100.0, n=11)
    H, dt = 50, 0.1
    s = 5.0 * dt * np.arange(H)
    p0_lane = np.column_stack([s, np.zeros(H), np.zeros(H)])
    p1_lane = np.column_stack([s, np.full(H, 0.5), np.zeros(H)])
    p0 = lane_frame_to_se2(p0_lane, anchor)
    p1 = lane_frame_to_se2(p1_lane, anchor)
    result = compute_bcvf_cost([p0, p1], _v1_config())
    assert result.total_cost < 1e-9


def test_lemma_1_carries_on_curved_lane():
    """§4.2: **the corrected finding.** BCVF Lemma 1 invariance
    survives the lift even on curved lanes when both predictors
    track the same path. The body-frame error primitive transforms
    correctly with lane curvature: a constant lane-frame offset
    becomes a constant body-frame offset between the two predictors,
    regardless of how the lane curves.

    A pre-implementation reading expected this to fail (curved lane
    → curved SE(2) trajectory → non-zero second derivative). The
    test pins the actual mathematical result. A future contributor
    "fixing" what they think is a bug in this case would break the
    documented behaviour.
    """
    anchor = LaneAnchor.constant_curvature(
        radius=50.0, arc_length=50.0, n=51,
    )
    H, dt = 50, 0.1
    s = 5.0 * dt * np.arange(H)
    p0_lane = np.column_stack([s, np.zeros(H), np.zeros(H)])
    p1_lane = np.column_stack([s, np.full(H, 0.5), np.zeros(H)])
    p0 = lane_frame_to_se2(p0_lane, anchor)
    p1 = lane_frame_to_se2(p1_lane, anchor)
    result = compute_bcvf_cost([p0, p1], _v1_config())
    assert result.total_cost < 1e-9, (
        f"Lemma 1 invariance broke on curved lane (cost={result.total_cost}); "
        "the body-frame error primitive should transform correctly with "
        "lane curvature — see DESIGN.md §4.2"
    )


def test_lemma_1_carries_on_tighter_curve():
    """Same finding at a tighter curvature radius. Pins that the
    invariance is genuinely curvature-independent (not a numerical
    accident at one specific radius)."""
    anchor = LaneAnchor.constant_curvature(
        radius=10.0, arc_length=15.0, n=51,
    )
    H, dt = 30, 0.1
    s = 5.0 * dt * np.arange(H)
    p0 = lane_frame_to_se2(
        np.column_stack([s, np.zeros(H), np.zeros(H)]), anchor,
    )
    p1 = lane_frame_to_se2(
        np.column_stack([s, np.full(H, 0.3), np.zeros(H)]), anchor,
    )
    result = compute_bcvf_cost([p0, p1], _v1_config())
    assert result.total_cost < 1e-9


def test_different_reference_paths_fires_kernel():
    """§4.3: two predictors tracking **genuinely different paths**
    (an SE(2) straight-line predictor vs a lane-frame predictor on
    a curved lane) produce non-trivial body-frame disagreement and
    BCVF correctly fires. This is the kernel doing its job, not a
    Lemma 1 violation.
    """
    anchor = LaneAnchor.constant_curvature(
        radius=50.0, arc_length=50.0, n=51,
    )
    H, dt = 50, 0.1
    s = 5.0 * dt * np.arange(H)
    # Predictor 0: SE(2) straight along +x.
    p0 = np.column_stack([s, np.zeros(H), np.zeros(H)])
    # Predictor 1: lane-frame on curved lane at the centerline.
    p1 = lane_frame_to_se2(
        np.column_stack([s, np.zeros(H), np.zeros(H)]), anchor,
    )
    result = compute_bcvf_cost([p0, p1], _v1_config())
    assert result.total_cost > 1e-3
    assert result.gate_activation_count > 0


def test_round_trip_identity_on_curved_lane_post_audit_fix():
    """Pinned regression for the post-v0.7 audit fix in
    ``se2_to_lane_frame``. Pre-fix: the inverse used the segment-
    direction tangent for ``psi`` while the forward used interpolated
    tangent — round-trip heading error on the 50 m / 1 m curved lane
    was ~0.02 rad (~1.15°), 200× the polyline-discretisation floor.
    Post-fix: inverse uses the same interpolated tangent as the
    forward; heading error drops to fp64 noise plus the residual
    polyline-vs-smooth-curve position-feedthrough.

    The position-recovery tolerances are bounded by the polyline
    discretisation (≈ 6 mm in ``s``, ≈ 50 µm in ``d`` on this lane);
    those are NOT a regression hot-spot, so the test pins them at
    loose tolerances + the heading at a tight one.
    """
    anchor = LaneAnchor.constant_curvature(
        radius=50.0, arc_length=50.0, n=51,
    )
    H = 10
    s_in = np.linspace(0.5, 49.0, H)
    lane_in = np.column_stack([
        s_in,
        np.linspace(-0.3, 0.3, H),
        np.linspace(-0.05, 0.05, H),
    ])
    se2 = lane_frame_to_se2(lane_in, anchor)
    lane_out = se2_to_lane_frame(se2, anchor)
    err = np.abs(lane_out - lane_in)
    # Heading: tight (the fix's load-bearing improvement).
    assert err[:, 2].max() < 1e-3, (
        f"psi error {err[:, 2].max():.4e} exceeds the post-fix bound; "
        "the inverse may have regressed to segment-direction tangent"
    )
    # Position: bounded by polyline discretisation.
    assert err[:, 0].max() < 1e-2  # s within 1 cm
    assert err[:, 1].max() < 1e-3  # d within 1 mm


def test_lane_frame_constant_d_bias_is_invisible_to_bcvf():
    """§4.4: the residual cybersecurity concern. A spoofed lane-frame
    predictor that reports a consistent `d` bias is **invisible** to
    BCVF at the kernel layer — same Lemma-1 trapdoor the
    `adversarial_consistent_bias` family characterises in the
    SE(2) case.

    Pinned so a future reader doesn't assume the multi-modal mode
    closes the trapdoor — defence in depth (UN ECE R155 §7.3.4
    cross-modal sensor attestation, calibration drift monitoring) is
    still required at a different layer.
    """
    anchor = LaneAnchor.straight_x_axis(length=100.0, n=11)
    H, dt = 50, 0.1
    s = 5.0 * dt * np.arange(H)
    # Honest lane-frame predictor at d=0.
    honest = lane_frame_to_se2(
        np.column_stack([s, np.zeros(H), np.zeros(H)]), anchor,
    )
    # Spoofed lane-frame predictor with consistent +0.05 m bias.
    spoofed = lane_frame_to_se2(
        np.column_stack([s, np.full(H, 0.05), np.zeros(H)]), anchor,
    )
    result = compute_bcvf_cost([honest, spoofed], _v1_config())
    # Constant offset → second derivative zero → BCVF stays quiet.
    assert result.total_cost < 1e-9
