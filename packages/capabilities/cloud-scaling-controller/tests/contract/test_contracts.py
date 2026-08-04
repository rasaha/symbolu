"""Contract tests for the public boundary (ScalingObservation / ScalingRecommendation)."""

from __future__ import annotations

import json
import math

import pytest

from ugence_cloud_scaling_controller import (
    CloudScalingController,
    ScalingObservation,
    ScalingRecommendation,
    ContractError,
    SCHEMA_VERSION,
)
from ugence_cloud_scaling_controller.contracts import normalize_observation


def _ctrl():
    return CloudScalingController()


def test_valid_observation():
    obs = ScalingObservation(
        metrics={"cpu": 0.8, "memory": 0.7, "latency_p99": 0.6,
                 "error_rate": 0.1, "queue_depth": 0.5},
        current_replicas=5,
        phase="peak",
    )
    rec = _ctrl().recommend(obs)
    assert isinstance(rec, ScalingRecommendation)
    assert rec.schema_version == SCHEMA_VERSION
    assert rec.current_replicas == 5
    assert rec.recommended_replicas == 5 + rec.replica_delta


def test_missing_optional_metrics_are_allowed():
    # Only some known signals present; missing ones are simply not counted.
    rec = _ctrl().recommend(ScalingObservation(metrics={"cpu": 0.9}, current_replicas=3))
    assert rec.recommendation  # produces a decision string
    assert "cpu" in rec.metrics_snapshot


def test_unknown_metrics_accepted_and_do_not_drive_decision():
    # Unknown metric keys must not raise, must be preserved in the snapshot, and must
    # not participate in the weighted pressure groups. They cannot flip the discrete
    # decision for a clearly-decided case. (They may marginally enter variance-based
    # damping like any numeric signal — see docs/BOUNDARIES.md — so exact action_score
    # equality is not asserted.)
    base = _ctrl().recommend(
        ScalingObservation(metrics={"cpu": 0.9, "memory": 0.8}, current_replicas=4)
    )
    withunknown = _ctrl().recommend(
        ScalingObservation(
            metrics={"cpu": 0.9, "memory": 0.8, "made_up_signal": 0.5}, current_replicas=4
        )
    )
    assert "made_up_signal" in withunknown.metrics_snapshot
    assert base.recommendation == withunknown.recommendation
    assert base.replica_delta == withunknown.replica_delta


def test_invalid_metric_type_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": "high"}, current_replicas=3))
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": True}, current_replicas=3))
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={5: 0.5}, current_replicas=3))


def test_nan_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": float("nan")}, current_replicas=3))


def test_infinity_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": math.inf}, current_replicas=3))
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": -math.inf}, current_replicas=3))


def test_negative_replicas_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": 0.5}, current_replicas=-1))


def test_zero_replicas_allowed_and_normalized():
    # Zero is accepted at the boundary; the algorithm treats the effective floor as >= 1.
    rec = _ctrl().recommend(ScalingObservation(metrics={"cpu": 0.5}, current_replicas=0))
    assert rec.current_replicas == 0
    assert isinstance(rec.recommended_replicas, int)


def test_invalid_phase_type_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(ScalingObservation(metrics={"cpu": 0.5}, current_replicas=3, phase=123))


def test_unknown_phase_string_accepted():
    # Unknown phase strings are accepted and handled as the default phase downstream.
    rec = _ctrl().recommend(
        ScalingObservation(metrics={"cpu": 0.5}, current_replicas=3, phase="not_a_real_phase")
    )
    assert rec.recommendation


def test_negative_restarts_fails_closed():
    with pytest.raises(ContractError):
        normalize_observation(
            ScalingObservation(metrics={"cpu": 0.5}, current_replicas=3, recent_pod_restarts=-2)
        )


def test_correlation_id_preserved():
    rec = _ctrl().recommend(
        ScalingObservation(metrics={"cpu": 0.5}, current_replicas=3, correlation_id="abc-123")
    )
    assert rec.correlation_id == "abc-123"


def test_json_round_trip():
    rec = _ctrl().recommend(
        ScalingObservation(metrics={"cpu": 0.9, "memory": 0.8}, current_replicas=4,
                           correlation_id="rt-1")
    )
    text = rec.to_json()
    parsed = json.loads(text)
    assert parsed["correlation_id"] == "rt-1"
    assert parsed["schema_version"] == SCHEMA_VERSION
    # Deterministic ordering: to_json is stable across calls.
    assert rec.to_json() == text
    # Keys are sorted.
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_stable_schema_version():
    assert SCHEMA_VERSION == "1.0"
    rec = _ctrl().recommend(ScalingObservation(metrics={"cpu": 0.5}, current_replicas=2))
    assert rec.schema_version == "1.0"


def test_advisory_only_invariants():
    rec = _ctrl().recommend(ScalingObservation(metrics={"cpu": 0.95}, current_replicas=4))
    assert rec.advisory_only is True
    assert rec.actuation_performed is False
    assert rec.to_dict()["advisory_only"] is True
    assert rec.to_dict()["actuation_performed"] is False


def test_from_dict_rejects_unknown_top_level_field():
    with pytest.raises(ContractError):
        ScalingObservation.from_dict(
            {"metrics": {"cpu": 0.5}, "current_replicas": 3, "bogus": 1}
        )


def test_from_dict_requires_metrics_and_replicas():
    with pytest.raises(ContractError):
        ScalingObservation.from_dict({"current_replicas": 3})
    with pytest.raises(ContractError):
        ScalingObservation.from_dict({"metrics": {"cpu": 0.5}})


def test_recommend_accepts_plain_mapping():
    rec = _ctrl().recommend({"metrics": {"cpu": 0.9}, "current_replicas": 3})
    assert isinstance(rec, ScalingRecommendation)
