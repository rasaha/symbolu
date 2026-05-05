"""Tests for the post-hoc analysis harness."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    ConsumerV2Config,
    RolloutAggregation,
    TrustDiagnosticsRecorder,
    TrustShapedEpisodeRecord,
    TrustWeightComputer,
)
from symbolu_robotics.bcvf_autonomous.analysis import (
    ArgmaxFlip,
    EpisodeSummary,
    FleetSummary,
    NearVeto,
    V2StateFlip,
    aggregate_fleet,
    episode_record_from_dict,
    find_argmax_flips,
    find_near_vetoes,
    find_v2_state_flips,
    summarize_episode,
)


# --------------------------------------------------------------------------- #
# Hand-built records for deterministic detector tests
# --------------------------------------------------------------------------- #


def _empty_record(n_steps: int, M: int) -> TrustShapedEpisodeRecord:
    """Construct a TrustShapedEpisodeRecord with the right shapes filled in."""
    zeros_TM_f = np.zeros((n_steps, M), dtype=np.float64)
    zeros_TM_i = np.zeros((n_steps, M), dtype=np.int64)
    zeros_TM_b = np.zeros((n_steps, M), dtype=bool)
    zeros_T_f = np.zeros(n_steps, dtype=np.float64)
    zeros_T_i = np.zeros(n_steps, dtype=np.int64)
    zeros_T_b = np.zeros(n_steps, dtype=bool)
    return TrustShapedEpisodeRecord(
        n_steps=n_steps,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((n_steps, M), 1.0 / M, dtype=np.float64),
        per_step_costs=zeros_TM_f.copy(),
        per_step_residuals=zeros_TM_f.copy(),
        per_step_ema_mean=zeros_TM_f.copy(),
        per_step_ema_std=zeros_TM_f.copy(),
        per_step_bcvf_total=zeros_T_f.copy(),
        per_step_deadband_active_count=zeros_T_i.copy(),
        per_step_deadband_fired=zeros_T_b.copy(),
        per_step_is_excluded=zeros_TM_b.copy(),
        per_step_gate_activations=zeros_T_i.copy(),
        per_step_v2_state=[""] * n_steps,
        per_step_v2_signal=np.full(n_steps, np.nan),
        per_step_consec_suspect=np.full((n_steps, M), -1, dtype=np.int64),
        per_step_consec_ok=np.full((n_steps, M), -1, dtype=np.int64),
        exclusion_T=None,
    )


# --------------------------------------------------------------------------- #
# Argmax flip detection
# --------------------------------------------------------------------------- #


def test_find_argmax_flips_no_flips_when_constant():
    rec = _empty_record(n_steps=10, M=3)
    rec.per_step_weights[:] = np.array([1.0, 0.0, 0.0])
    flips = find_argmax_flips(rec, "ep1")
    assert flips == []


def test_find_argmax_flips_detects_each_transition():
    rec = _empty_record(n_steps=4, M=3)
    rec.per_step_weights[0] = [1.0, 0.0, 0.0]
    rec.per_step_weights[1] = [1.0, 0.0, 0.0]
    rec.per_step_weights[2] = [0.0, 1.0, 0.0]
    rec.per_step_weights[3] = [0.0, 0.0, 1.0]
    flips = find_argmax_flips(rec, "epA")
    assert len(flips) == 2
    assert flips[0].tick == 2
    assert flips[0].from_predictor == 0
    assert flips[0].to_predictor == 1
    assert flips[1].tick == 3
    assert flips[1].from_predictor == 1
    assert flips[1].to_predictor == 2


def test_find_argmax_flips_short_record_is_empty():
    rec = _empty_record(n_steps=1, M=3)
    assert find_argmax_flips(rec, "epShort") == []


def test_argmax_flip_carries_weight_context():
    rec = _empty_record(n_steps=2, M=3)
    rec.per_step_weights[0] = [0.6, 0.3, 0.1]
    rec.per_step_weights[1] = [0.1, 0.7, 0.2]
    flips = find_argmax_flips(rec, "epW")
    assert len(flips) == 1
    np.testing.assert_allclose(flips[0].weights_before, [0.6, 0.3, 0.1])
    np.testing.assert_allclose(flips[0].weights_after, [0.1, 0.7, 0.2])


# --------------------------------------------------------------------------- #
# V2 state flip detection
# --------------------------------------------------------------------------- #


def test_v2_state_flips_disabled_returns_empty():
    rec = _empty_record(n_steps=10, M=3)
    assert find_v2_state_flips(rec, "ep") == []


def test_v2_state_flips_detects_uniform_to_engaged():
    rec = _empty_record(n_steps=5, M=3)
    rec.per_step_v2_state = [
        "uniform", "uniform", "engaged", "engaged", "uniform"
    ]
    rec.per_step_v2_signal[:] = [0.1, 0.2, 0.6, 0.5, 0.1]
    flips = find_v2_state_flips(rec, "epV2")
    assert len(flips) == 2
    assert flips[0].tick == 2
    assert flips[0].from_state == "uniform"
    assert flips[0].to_state == "engaged"
    assert flips[0].signal == pytest.approx(0.6)
    assert flips[1].tick == 4
    assert flips[1].from_state == "engaged"
    assert flips[1].to_state == "uniform"


# --------------------------------------------------------------------------- #
# Near-veto detection
# --------------------------------------------------------------------------- #


def test_find_near_vetoes_disabled_returns_empty():
    rec = _empty_record(n_steps=10, M=3)
    assert find_near_vetoes(rec, "ep") == []


def test_find_near_vetoes_detects_predictor_above_fraction():
    rec = _empty_record(n_steps=20, M=3)
    rec.exclusion_T = 10
    consec = np.full((20, 3), 0, dtype=np.int64)
    # Predictor 1 climbs to 8 / 10 (80 %, above 0.7) but never excluded.
    consec[:, 1] = np.arange(20).clip(max=8)
    rec.per_step_consec_suspect = consec
    rec.per_step_consec_ok = np.zeros_like(consec)
    nvs = find_near_vetoes(rec, "epNV", near_veto_fraction=0.7)
    assert len(nvs) == 1
    nv = nvs[0]
    assert nv.predictor == 1
    assert nv.peak_consec_suspect == 8
    assert nv.peak_fraction == pytest.approx(0.8)
    assert nv.threshold_T == 10
    assert not nv.excluded_during_episode


def test_find_near_vetoes_skips_predictor_below_fraction():
    rec = _empty_record(n_steps=10, M=3)
    rec.exclusion_T = 10
    consec = np.full((10, 3), 0, dtype=np.int64)
    consec[:, 0] = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1]  # peak 5/10 = 0.5
    rec.per_step_consec_suspect = consec
    nvs = find_near_vetoes(rec, "epNV2", near_veto_fraction=0.7)
    assert nvs == []


def test_find_near_vetoes_reports_excluded_predictors_too():
    """A predictor that was actually excluded should still be reported
    (so a triage tool can correlate near-vetoes that escalated)."""
    rec = _empty_record(n_steps=10, M=3)
    rec.exclusion_T = 5
    consec = np.full((10, 3), 0, dtype=np.int64)
    consec[:, 2] = [0, 1, 2, 3, 4, 5, 5, 5, 5, 5]
    rec.per_step_consec_suspect = consec
    rec.per_step_is_excluded[5:, 2] = True
    nvs = find_near_vetoes(rec, "epExcluded", near_veto_fraction=0.7)
    assert len(nvs) == 1
    assert nvs[0].predictor == 2
    assert nvs[0].excluded_during_episode is True


def test_find_near_vetoes_invalid_fraction_rejected():
    rec = _empty_record(n_steps=5, M=3)
    rec.exclusion_T = 5
    rec.per_step_consec_suspect = np.zeros((5, 3), dtype=np.int64)
    with pytest.raises(ValueError):
        find_near_vetoes(rec, "ep", near_veto_fraction=0.0)
    with pytest.raises(ValueError):
        find_near_vetoes(rec, "ep", near_veto_fraction=1.5)


# --------------------------------------------------------------------------- #
# Episode summary
# --------------------------------------------------------------------------- #


def test_summarize_episode_basic():
    rec = _empty_record(n_steps=4, M=3)
    rec.per_step_weights[0] = [1.0, 0.0, 0.0]
    rec.per_step_weights[1] = [0.0, 1.0, 0.0]   # flip
    rec.per_step_weights[2] = [0.0, 1.0, 0.0]
    rec.per_step_weights[3] = [0.0, 0.0, 1.0]   # flip
    rec.per_step_v2_state = ["uniform", "engaged", "engaged", "uniform"]
    rec.per_step_v2_signal[:] = [0.1, 0.6, 0.5, 0.1]
    rec.per_step_bcvf_total[:] = [0.1, 0.6, 0.5, 0.1]
    rec.per_step_deadband_fired[:] = [False, True, False, False]
    summary = summarize_episode(
        rec, episode_id="epS",
        classification="no_collision",
        metadata={"scenario": "highway"},
    )
    assert summary.episode_id == "epS"
    assert summary.classification == "no_collision"
    assert summary.n_steps == 4
    assert summary.M == 3
    assert summary.n_argmax_flips == 2
    assert summary.n_v2_state_flips == 2
    assert summary.fraction_engaged == pytest.approx(0.5)
    assert summary.deadband_fired_rate == pytest.approx(0.25)
    assert summary.metadata["scenario"] == "highway"


def test_summarize_episode_handles_no_v2():
    rec = _empty_record(n_steps=5, M=3)
    summary = summarize_episode(rec, episode_id="ep_no_v2")
    assert summary.fraction_engaged is None


def test_episode_summary_round_trips_through_dict():
    rec = _empty_record(n_steps=3, M=3)
    rec.per_step_v2_state = ["engaged", "engaged", "uniform"]
    summary = summarize_episode(rec, "epD", "ok", metadata={"foo": "bar"})
    payload = summary.to_dict()
    assert payload["episode_id"] == "epD"
    assert payload["fraction_engaged"] == pytest.approx(2 / 3)
    assert payload["metadata"]["foo"] == "bar"


# --------------------------------------------------------------------------- #
# Fleet aggregator
# --------------------------------------------------------------------------- #


def test_aggregate_fleet_empty_returns_zero_summary():
    fleet = aggregate_fleet([])
    assert fleet.n_episodes == 0
    assert fleet.classification_counts == {}
    assert fleet.argmax_flips_per_step["mean"] == 0.0


def test_aggregate_fleet_counts_classifications():
    rec_a = _empty_record(n_steps=5, M=3)
    rec_b = _empty_record(n_steps=5, M=3)
    rec_c = _empty_record(n_steps=5, M=3)
    fleet = aggregate_fleet(
        [rec_a, rec_b, rec_c],
        episode_ids=["e1", "e2", "e3"],
        classifications=["collision", "no_collision", "no_collision"],
    )
    assert fleet.n_episodes == 3
    assert fleet.classification_counts == {
        "collision": 1, "no_collision": 2,
    }
    assert len(fleet.episodes) == 3


def test_aggregate_fleet_argmax_flip_percentiles():
    """Three episodes with very different argmax-flip rates; check that
    the fleet percentiles read correctly."""
    rec_quiet = _empty_record(n_steps=10, M=3)
    rec_quiet.per_step_weights[:] = [1.0, 0.0, 0.0]

    rec_chatter = _empty_record(n_steps=10, M=3)
    for t in range(10):
        rec_chatter.per_step_weights[t] = (
            [1.0, 0.0, 0.0] if t % 2 == 0 else [0.0, 1.0, 0.0]
        )

    rec_mid = _empty_record(n_steps=10, M=3)
    for t in range(10):
        rec_mid.per_step_weights[t] = (
            [1.0, 0.0, 0.0] if t < 5 else [0.0, 1.0, 0.0]
        )

    fleet = aggregate_fleet([rec_quiet, rec_chatter, rec_mid])
    flip_rates = sorted([0 / 10, 9 / 10, 1 / 10])
    assert fleet.argmax_flips_per_step["mean"] == pytest.approx(
        sum(flip_rates) / 3
    )
    assert fleet.argmax_flips_per_step["p50"] == pytest.approx(
        np.percentile(flip_rates, 50)
    )


def test_aggregate_fleet_reports_near_vetoes():
    rec = _empty_record(n_steps=10, M=3)
    rec.exclusion_T = 10
    rec.per_step_consec_suspect = np.zeros((10, 3), dtype=np.int64)
    rec.per_step_consec_suspect[:, 1] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]
    fleet = aggregate_fleet([rec], near_veto_fraction=0.7)
    assert len(fleet.near_vetoes) == 1
    nv = fleet.near_vetoes[0]
    assert nv.predictor == 1
    assert nv.peak_fraction == pytest.approx(0.8)


def test_aggregate_fleet_to_dict_round_trips_json():
    rec = _empty_record(n_steps=5, M=3)
    rec.per_step_v2_state = ["uniform"] * 5
    fleet = aggregate_fleet(
        [rec], episode_ids=["e1"], classifications=["nominal"]
    )
    encoded = json.dumps(fleet.to_dict())
    decoded = json.loads(encoded)
    assert decoded["n_episodes"] == 1
    assert decoded["classification_counts"] == {"nominal": 1}
    assert isinstance(decoded["episodes"], list)


def test_aggregate_fleet_misaligned_inputs_rejected():
    rec = _empty_record(n_steps=3, M=3)
    with pytest.raises(ValueError):
        aggregate_fleet(
            [rec, rec],
            episode_ids=["only_one_id"],
        )


# --------------------------------------------------------------------------- #
# IO — JSON round-trip via a real planner episode + Runner
# --------------------------------------------------------------------------- #


def test_episode_record_from_dict_round_trips():
    """to_dict() → episode_record_from_dict() → identical fields."""
    rec_orig = _empty_record(n_steps=3, M=3)
    rec_orig.per_step_v2_state = ["uniform", "engaged", "engaged"]
    rec_orig.per_step_v2_signal[:] = [0.1, 0.6, 0.7]
    rec_orig.exclusion_T = 5

    payload = rec_orig.to_dict()
    rec_restored = episode_record_from_dict(payload)
    assert rec_restored.n_steps == rec_orig.n_steps
    assert rec_restored.M == rec_orig.M
    assert rec_restored.per_step_v2_state == rec_orig.per_step_v2_state
    np.testing.assert_array_equal(
        rec_restored.per_step_consec_suspect, rec_orig.per_step_consec_suspect
    )
    assert rec_restored.exclusion_T == 5


def test_load_episode_from_json_full_runner_path(tmp_path):
    """Full Runner.run() → JSON dump → load_episode_from_json → aggregate."""
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
    from symbolu_robotics.bcvf_autonomous.analysis import (
        load_episode_from_json,
    )

    diag_path = tmp_path / "fleet_episode.json"
    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1, max_steps=8,
            road=make_straight_road(length=80.0),
            obstacles=[], seed=2,
        ),
        mppi=MPPIConfig(num_rollouts=64, horizon=10, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=2,
        trust_diagnostics_enabled=True,
        trust_diagnostics_path=str(diag_path),
        v2_enabled=True,
        v2_engage_threshold=0.5,
        v2_disengage_threshold=0.2,
    )
    Runner(cfg).run()

    rec, meta = load_episode_from_json(diag_path)
    assert meta["seed"] == 2
    assert rec.n_steps > 0

    fleet = aggregate_fleet(
        [rec], episode_ids=["t1"], classifications=["no_collision"]
    )
    assert fleet.n_episodes == 1
    assert fleet.classification_counts == {"no_collision": 1}


def test_load_episode_from_json_rejects_missing_diagnostics_key(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"seed": 7}))
    from symbolu_robotics.bcvf_autonomous.analysis import (
        load_episode_from_json,
    )
    with pytest.raises(ValueError):
        load_episode_from_json(p)


# --------------------------------------------------------------------------- #
# Audit fix: episode_record_from_dict must fail loudly on corrupt input
# --------------------------------------------------------------------------- #


def test_episode_record_from_dict_rejects_missing_keys():
    """The pre-fix behavior silently produced all-zero records on
    incomplete payloads — a SOTIF anti-pattern. The fix demands every
    required key be present."""
    with pytest.raises(ValueError, match="missing required keys"):
        episode_record_from_dict({"n_steps": 50, "M": 4, "aggregation": "mean"})


def test_episode_record_from_dict_rejects_shape_mismatch():
    rec = _empty_record(n_steps=5, M=3)
    payload = rec.to_dict()
    # Sabotage the per_step_weights shape.
    payload["per_step_weights"] = [[0.0] * 3] * 4   # (4, 3) ≠ (5, 3)
    with pytest.raises(ValueError, match="per_step_weights shape"):
        episode_record_from_dict(payload)


def test_episode_record_from_dict_rejects_v2_state_length_mismatch():
    rec = _empty_record(n_steps=5, M=3)
    payload = rec.to_dict()
    payload["per_step_v2_state"] = ["uniform"] * 4  # length 4 ≠ n_steps 5
    with pytest.raises(ValueError, match="per_step_v2_state length"):
        episode_record_from_dict(payload)


def test_episode_record_from_dict_rejects_negative_dimensions():
    rec = _empty_record(n_steps=3, M=3)
    payload = rec.to_dict()
    payload["n_steps"] = -1
    with pytest.raises(ValueError):
        episode_record_from_dict(payload)


def test_episode_record_from_dict_rejects_non_dict_input():
    with pytest.raises(ValueError):
        episode_record_from_dict("not a dict")  # type: ignore[arg-type]


def test_episode_record_from_dict_round_trips_after_validation():
    """A clean payload produced by to_dict() must still round-trip after
    the validation gates are added."""
    rec = _empty_record(n_steps=3, M=3)
    rec.per_step_v2_state = ["uniform", "engaged", "engaged"]
    rec.per_step_v2_signal[:] = [0.1, 0.6, 0.7]
    rec.exclusion_T = 5

    payload = rec.to_dict()
    rec_restored = episode_record_from_dict(payload)
    assert rec_restored.n_steps == 3
    assert rec_restored.exclusion_T == 5
    np.testing.assert_array_equal(
        rec_restored.per_step_v2_signal, rec.per_step_v2_signal
    )


# --------------------------------------------------------------------------- #
# Audit fix: weight_drop / max_abs_weight_delta on ArgmaxFlip
# --------------------------------------------------------------------------- #


def test_argmax_flip_weight_drop_on_clean_handover():
    rec = _empty_record(n_steps=2, M=3)
    rec.per_step_weights[0] = [1.0, 0.0, 0.0]
    rec.per_step_weights[1] = [0.0, 1.0, 0.0]
    flips = find_argmax_flips(rec, "ep")
    assert len(flips) == 1
    assert flips[0].weight_drop == pytest.approx(1.0)
    assert flips[0].max_abs_weight_delta == pytest.approx(1.0)


def test_argmax_flip_weight_drop_on_marginal_chatter():
    rec = _empty_record(n_steps=2, M=3)
    rec.per_step_weights[0] = [0.51, 0.49, 0.0]
    rec.per_step_weights[1] = [0.49, 0.51, 0.0]
    flips = find_argmax_flips(rec, "ep")
    assert len(flips) == 1
    # Predictor 0 lost 0.51 - 0.49 = 0.02 — small drop = chatter.
    assert flips[0].weight_drop == pytest.approx(0.02)
    assert flips[0].max_abs_weight_delta == pytest.approx(0.02)


def test_argmax_flip_to_dict_includes_weight_drop():
    rec = _empty_record(n_steps=2, M=3)
    rec.per_step_weights[0] = [1.0, 0.0, 0.0]
    rec.per_step_weights[1] = [0.0, 1.0, 0.0]
    flips = find_argmax_flips(rec, "ep")
    payload = flips[0].to_dict()
    assert "weight_drop" in payload
    assert "max_abs_weight_delta" in payload


# --------------------------------------------------------------------------- #
# Audit fix: per-episode metadata propagated onto events
# --------------------------------------------------------------------------- #


def test_summarize_episode_decorates_events_with_metadata():
    rec = _empty_record(n_steps=3, M=3)
    rec.per_step_weights[0] = [1.0, 0.0, 0.0]
    rec.per_step_weights[1] = [0.0, 1.0, 0.0]
    rec.per_step_weights[2] = [0.0, 0.0, 1.0]
    rec.per_step_v2_state = ["uniform", "engaged", "uniform"]
    rec.exclusion_T = 5
    rec.per_step_consec_suspect = np.zeros((3, 3), dtype=np.int64)
    rec.per_step_consec_suspect[:, 1] = [3, 4, 4]

    summary = summarize_episode(
        rec, episode_id="trip42", classification="no_collision",
        metadata={"vehicle_id": "VIN-X", "scenario": "highway"},
    )
    for ev in summary.argmax_flips:
        assert ev.metadata == {
            "vehicle_id": "VIN-X", "scenario": "highway"
        }
    for ev in summary.v2_state_flips:
        assert ev.metadata["vehicle_id"] == "VIN-X"
    for nv in summary.near_vetoes:
        assert nv.metadata["scenario"] == "highway"


# --------------------------------------------------------------------------- #
# Audit fix: aggregate_fleet stops double-detecting events
# --------------------------------------------------------------------------- #


def test_aggregate_fleet_reuses_cached_events_no_double_detection(monkeypatch):
    """The pre-fix aggregator called find_near_vetoes / find_v2_state_flips
    once inside summarize_episode and then again inside the aggregator
    loop — 2x the detector cost on every record. The fix reuses the
    cached lists. Verify by counting calls."""
    from symbolu_robotics.bcvf_autonomous.analysis import (
        episode as episode_module,
    )

    call_counts = {"argmax": 0, "v2": 0, "near_veto": 0}
    real_argmax = episode_module.find_argmax_flips
    real_v2 = episode_module.find_v2_state_flips
    real_nv = episode_module.find_near_vetoes

    def counted_argmax(*args, **kwargs):
        call_counts["argmax"] += 1
        return real_argmax(*args, **kwargs)

    def counted_v2(*args, **kwargs):
        call_counts["v2"] += 1
        return real_v2(*args, **kwargs)

    def counted_nv(*args, **kwargs):
        call_counts["near_veto"] += 1
        return real_nv(*args, **kwargs)

    monkeypatch.setattr(episode_module, "find_argmax_flips", counted_argmax)
    monkeypatch.setattr(episode_module, "find_v2_state_flips", counted_v2)
    monkeypatch.setattr(episode_module, "find_near_vetoes", counted_nv)

    records = [_empty_record(n_steps=5, M=3) for _ in range(4)]
    aggregate_fleet(records)
    # Each detector must run exactly once per episode.
    assert call_counts == {"argmax": 4, "v2": 4, "near_veto": 4}


def test_aggregate_fleet_propagates_metadata_to_event_lists():
    rec = _empty_record(n_steps=3, M=3)
    rec.exclusion_T = 5
    rec.per_step_consec_suspect = np.zeros((3, 3), dtype=np.int64)
    rec.per_step_consec_suspect[:, 0] = [4, 4, 4]
    fleet = aggregate_fleet(
        [rec],
        episode_ids=["e1"],
        classifications=["nominal"],
        metadata=[{"vehicle_id": "VIN-A", "scenario": "urban"}],
    )
    assert len(fleet.near_vetoes) == 1
    assert fleet.near_vetoes[0].metadata == {
        "vehicle_id": "VIN-A", "scenario": "urban"
    }


# --------------------------------------------------------------------------- #
# Integration — exclusion counters captured through real planner
# --------------------------------------------------------------------------- #


def test_consec_counters_captured_through_real_episode():
    """End-to-end check that the exclusion-counter pipe (TrustWeightResult
    → TrustStepRecord → TrustShapedEpisodeRecord) carries data when
    exclusion is enabled in a real planning loop."""
    from symbolu_robotics.bcvf_autonomous import (
        MPPIConfig,
        MPPIPlanner,
        PerfCostConfig,
        create_predictor_set,
        make_straight_road,
    )
    predictors = create_predictor_set(seed=0)
    road = make_straight_road(length=80.0)
    planner = MPPIPlanner(
        MPPIConfig(num_rollouts=32, horizon=8),
        PerfCostConfig(), predictors, road, [],
    )
    planner.set_seed(0)
    planner.set_exclusion(enabled=True, r=1.5, T_exclude=5, T_reinstate=5)
    planner.set_trust_diagnostics_enabled(True)
    for _ in range(4):
        planner.plan()
    diag = planner.get_trust_diagnostics()
    assert diag is not None
    assert diag.exclusion_T == 5
    assert diag.per_step_consec_suspect.shape == (4, len(predictors))
    # Exclusion was enabled the whole episode — no -1 sentinels.
    assert (diag.per_step_consec_suspect >= 0).all()


# --------------------------------------------------------------------------- #
# Fleet report writers — CSV + Markdown frozen artifacts
# --------------------------------------------------------------------------- #


def _fleet_with_n_episodes(n: int = 3) -> FleetSummary:
    """Build an aggregate_fleet over n hand-built records."""
    records = []
    classifications = []
    ids = []
    for i in range(n):
        rec = _empty_record(n_steps=10, M=3)
        records.append(rec)
        classifications.append("collision" if i == 0 else "no_collision")
        ids.append(f"trip_{i}")
    return aggregate_fleet(records, ids, classifications)


def test_fleet_summary_to_csv_writes_header_and_one_row_per_episode(tmp_path):
    fleet = _fleet_with_n_episodes(3)
    out = fleet.to_csv(tmp_path / "fleet.csv")
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4   # header + 3 episodes
    header = lines[0].split(",")
    expected = [
        "episode_id", "classification", "n_steps", "M",
        "n_argmax_flips", "argmax_flip_rate",
        "n_v2_state_flips", "n_near_vetoes",
        "fraction_engaged", "deadband_fired_rate",
        "mean_bcvf_total", "max_bcvf_total",
        "excluded_ever_count",
    ]
    assert header == expected


def test_fleet_summary_to_csv_round_trips_through_csv_reader(tmp_path):
    """The CSV must parse cleanly through stdlib csv.DictReader — a
    SOTIF audit script reading via pandas / Excel must not trip on
    quoting or escaping."""
    import csv as _csv
    fleet = _fleet_with_n_episodes(3)
    out = fleet.to_csv(tmp_path / "fleet.csv")
    with open(out, "r", encoding="utf-8", newline="") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 3
    classifications = sorted(r["classification"] for r in rows)
    assert classifications == ["collision", "no_collision", "no_collision"]
    # n_steps round-trips as a string; cast and check.
    assert all(int(r["n_steps"]) == 10 for r in rows)


def test_fleet_summary_to_csv_emits_blank_for_none_fraction_engaged(tmp_path):
    """V2-disabled episodes have fraction_engaged=None — render as
    empty string in CSV (not "None" or "nan"), so a downstream
    parser sees a missing value, not a literal."""
    fleet = _fleet_with_n_episodes(2)
    out = fleet.to_csv(tmp_path / "fleet.csv")
    body = out.read_text(encoding="utf-8").splitlines()[1:]
    for line in body:
        cols = line.split(",")
        # fraction_engaged is column 8 (0-indexed).
        assert cols[8] == "", f"expected empty fraction_engaged, got {cols[8]!r}"


def test_fleet_summary_to_markdown_report_has_required_sections(tmp_path):
    from datetime import datetime, timezone
    fleet = _fleet_with_n_episodes(3)
    out = fleet.to_markdown_report(
        tmp_path / "fleet_report.md",
        label="nightly_2026-05-04",
        generated_at=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
    )
    md = out.read_text(encoding="utf-8")
    for section in (
        "# BCVF Fleet Summary",
        "## Headline aggregates",
        "## Classification breakdown",
        "## Per-predictor exclusion incidence",
        "## Near-veto roster",
        "## V2 state-flip roster",
        "## Per-episode index",
        "## Methodology",
    ):
        assert section in md, f"missing section: {section}"
    # Label and timestamp present in the header.
    assert "nightly_2026-05-04" in md
    assert "2026-05-04T12:00:00" in md


def test_fleet_summary_markdown_renders_classification_table(tmp_path):
    fleet = _fleet_with_n_episodes(3)
    out = fleet.to_markdown_report(tmp_path / "fleet_report.md")
    md = out.read_text(encoding="utf-8")
    # 1 collision + 2 no_collision out of the 3 hand-built episodes.
    assert "| `collision` | 1 |" in md
    assert "| `no_collision` | 2 |" in md


def test_fleet_summary_markdown_handles_empty_rosters(tmp_path):
    """When no near-vetoes / V2 flips were observed, the writer emits
    an explicit "No ... events observed." sentinel rather than an
    empty section — auditors see a deliberate negative result, not
    an apparent omission."""
    fleet = _fleet_with_n_episodes(2)
    out = fleet.to_markdown_report(tmp_path / "fleet_report.md")
    md = out.read_text(encoding="utf-8")
    assert "_No near-veto events observed._" in md
    assert "_No V2 state-flip events observed._" in md


def test_fleet_summary_markdown_render_is_deterministic():
    from datetime import datetime, timezone
    from symbolu_robotics.bcvf_autonomous.analysis import render_fleet_markdown
    fleet = _fleet_with_n_episodes(3)
    ts = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
    a = render_fleet_markdown(fleet, generated_at=ts)
    b = render_fleet_markdown(fleet, generated_at=ts)
    assert a == b


def test_fleet_summary_to_csv_creates_parent_directories(tmp_path):
    fleet = _fleet_with_n_episodes(2)
    nested = tmp_path / "audits" / "2026-05" / "nightly"
    out = fleet.to_csv(nested / "fleet.csv")
    assert out.exists()
