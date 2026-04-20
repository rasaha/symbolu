"""Tests for §6.2 dataset-adapter scaffolding.

Verifies the abstract interface + the ``synthetic_realistic`` adapter
that bridges pure-SE(2) synthetic (§6.1) and real nuScenes data
(§6.2). Catches shape bugs and failure-injection parity issues before
real data enters the picture.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.datasets.base import (
    DatasetAdapter,
    SceneRecord,
)
from symbolu_robotics.bcvf_autonomous.datasets.synthetic_realistic import (
    RealisticNoiseAdapter,
    RealisticNoiseConfig,
)


# --- SceneRecord validation ---


def test_scene_record_shape_validation() -> None:
    T = 50
    H = 20
    ego = np.zeros((T, 3))
    predictors = {
        "M1": np.zeros((T, H, 3)),
        "M2": np.zeros((T, H, 3)),
    }
    rec = SceneRecord(
        scene_id="s0", ego_trace=ego, predictor_trajectories=predictors,
    )
    assert rec.num_steps == T
    assert rec.num_predictors == 2
    assert rec.horizon == H


def test_scene_record_rejects_bad_ego_shape() -> None:
    with pytest.raises(ValueError):
        SceneRecord(
            scene_id="s0",
            ego_trace=np.zeros((50, 2)),  # wrong trailing dim
            predictor_trajectories={"M1": np.zeros((50, 20, 3))},
        )


def test_scene_record_rejects_predictor_shape_mismatch() -> None:
    with pytest.raises(ValueError):
        SceneRecord(
            scene_id="s0",
            ego_trace=np.zeros((50, 3)),
            predictor_trajectories={
                "M1": np.zeros((40, 20, 3)),  # T mismatch
            },
        )


# --- RealisticNoiseAdapter ---


def test_realistic_adapter_produces_21_scenes() -> None:
    adapter = RealisticNoiseAdapter()
    ids = adapter.scene_ids()
    assert len(ids) == 21


def test_realistic_adapter_scene_ids_reference_all_failure_types() -> None:
    adapter = RealisticNoiseAdapter()
    ids = adapter.scene_ids()
    ftypes_in_ids = set()
    for sid in ids:
        # format: scene_{seed}_{idx}_{failure_type}
        tail = "_".join(sid.split("_")[3:])
        ftypes_in_ids.add(tail)
    expected = set(RealisticNoiseConfig().failure_types)
    assert ftypes_in_ids == expected


def test_realistic_adapter_load_scene_returns_record() -> None:
    adapter = RealisticNoiseAdapter()
    for sid in adapter.scene_ids()[:2]:
        rec = adapter.load_scene(sid)
        assert isinstance(rec, SceneRecord)
        assert rec.num_steps == 400
        assert rec.num_predictors == 4
        assert rec.horizon == 20


def test_realistic_adapter_scene_is_deterministic() -> None:
    """Same seed + scene_id → bit-identical trajectories."""
    adapter = RealisticNoiseAdapter()
    sid = adapter.scene_ids()[0]
    rec1 = adapter.load_scene(sid)
    rec2 = adapter.load_scene(sid)
    for name in rec1.predictor_trajectories:
        np.testing.assert_array_equal(
            rec1.predictor_trajectories[name],
            rec2.predictor_trajectories[name],
        )


def test_realistic_adapter_failure_injection_shows_in_m4() -> None:
    """M4 should diverge from M1/M2/M3 after the failure onset for
    non-benign failure types."""
    adapter = RealisticNoiseAdapter()
    # Pick a GPS-multipath scene (has an onset)
    sid = next(
        sid for sid in adapter.scene_ids()
        if sid.endswith("gps_multipath")
    )
    rec = adapter.load_scene(sid)
    onset = rec.failure_metadata["onset_step"]
    dur = rec.failure_metadata["duration_steps"]
    m4 = rec.predictor_trajectories["M4"]
    m1 = rec.predictor_trajectories["M1"]
    # Pre-onset: M4 and M1 should have similar lateral stats
    pre_diff = np.abs(m4[:onset, :, 1] - m1[:onset, :, 1]).mean()
    # During-failure: M4 should drift laterally vs M1
    during_diff = np.abs(
        m4[onset:onset + dur, :, 1] - m1[onset:onset + dur, :, 1]
    ).mean()
    assert during_diff > pre_diff * 2.0, (
        f"expected failure injection to amplify M4 vs M1 lateral "
        f"divergence; pre={pre_diff:.3f} during={during_diff:.3f}"
    )


def test_realistic_adapter_constant_bias_is_lemma1_benign() -> None:
    """constant_bias_sanity scenes have no onset — bias applied whole
    scene. Used as a Lemma 1 negative control downstream; test here
    just verifies the onset-step metadata is None."""
    adapter = RealisticNoiseAdapter()
    sid = next(
        sid for sid in adapter.scene_ids()
        if sid.endswith("constant_bias_sanity")
    )
    rec = adapter.load_scene(sid)
    assert rec.failure_metadata["onset_step"] is None


def test_realistic_adapter_iteration() -> None:
    """Adapter supports __iter__ and __len__."""
    adapter = RealisticNoiseAdapter()
    scenes = list(adapter)
    assert len(scenes) == 21
    assert len(adapter) == 21


# --- End-to-end: trust computer consumes a SceneRecord ---


def test_trust_computer_runs_on_realistic_adapter_output() -> None:
    """Sanity check: the V1 trust computer can process a SceneRecord's
    predictor trajectories without shape or numerical errors."""
    from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
    from symbolu_robotics.bcvf_autonomous.trust import TrustWeightComputer

    adapter = RealisticNoiseAdapter()
    rec = adapter.load_scene(adapter.scene_ids()[0])

    bcvf_cfg = BCVFConfig(
        gate_threshold=0.05,
        gate_beta=400.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3),
        use_anchor_pairing=False,
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )
    computer = TrustWeightComputer(bcvf_cfg)
    computer.set_ema_alpha(0.05)
    computer.set_deadband_k_sigma(2.0)

    # Step through the scene one timestep at a time. At each step,
    # stack M predictors' forecasts into (K=1, M, H, 3).
    for t in range(0, rec.num_steps, 20):  # sample every 20th step
        trajectories = np.stack(
            [rec.predictor_trajectories[f"M{i+1}"][t]
             for i in range(rec.num_predictors)],
            axis=0,
        )  # (M, H, 3)
        trajectories = trajectories[np.newaxis, ...]  # (1, M, H, 3)
        result = computer.compute(trajectories)
        assert result.weights.shape == (1, 4)
        np.testing.assert_allclose(result.weights.sum(axis=1), 1.0, atol=1e-10)
        assert np.all(result.weights >= -1e-12)
