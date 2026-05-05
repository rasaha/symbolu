"""Behavioural tests for the calibration management framework.

The framework is the §9-row-#6 industry-features-roadmap pick.
These tests pin the load-bearing contracts:

* :class:`CalibrationSet` is hash-identified, kernel-version-
  validated, JSON-serialisable.
* Every embedded config dict is reconstruction-validated at
  construction (a malformed config can't ride into the bundle).
* :func:`load_calibration_set` rejects: missing path, invalid
  JSON, missing required fields, bad digest, kernel-version
  mismatch (unless explicitly allowed).
* The digest is canonical-JSON-stable: same content in →
  same digest out.
* :class:`CalibrationDriftDetector` walks
  :attr:`expected_metrics` against a
  :class:`WindowedFleetSummary`; emits typed
  :class:`CalibrationDriftAlert` per range violation.
* Round-trip survives JSON write / read.
* The bundle composes with all 8 typed configs (BCVFConfig +
  ConsumerV2Config + BicycleConfig + RealTimeBudget +
  DDSQoSProfile + SafetyStateMachineConfig + per-predictor
  FailureConfig + the expected-metrics map).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous._version import __version__
from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_autonomous.predictors.base import (
    BicycleConfig,
    FailureConfig,
)
from symbolu_robotics.bcvf_autonomous.realtime.budget import RealTimeBudget
from symbolu_robotics.bcvf_autonomous.ros2 import DDSQoSProfile
from symbolu_robotics.bcvf_autonomous.safety_state.machine import (
    SafetyStateMachineConfig,
)
from symbolu_robotics.bcvf_autonomous.trust import ConsumerV2Config
from symbolu_robotics.bcvf_autonomous.calibration import (
    CalibrationDigestError,
    CalibrationDriftAlert,
    CalibrationDriftDetector,
    CalibrationSet,
    CalibrationSetError,
    CalibrationVersionError,
    build_calibration_set,
    load_calibration_set,
    render_calibration_set_text,
    save_calibration_set,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _build(**overrides) -> CalibrationSet:
    base = dict(
        calibration_id="oem-test-fleet-A-v1",
        bcvf_config=BCVFConfig(),
        consumer_v2_config=ConsumerV2Config(),
        bicycle_config=BicycleConfig(),
        realtime_budget=RealTimeBudget(),
        dds_qos_profile=DDSQoSProfile(),
        safety_state_config=SafetyStateMachineConfig(),
        per_predictor_failure_thresholds={"M1": FailureConfig()},
        expected_metrics={
            "argmax_flips_per_step.p95": {"min": 0.0, "max": 0.05},
        },
        metadata={"fleet": "A"},
        kernel_version=__version__,
        created_at="2026-05-05T12:00:00+00:00",
    )
    base.update(overrides)
    return build_calibration_set(**base)


# --------------------------------------------------------------------------- #
# CalibrationSet construction + validation
# --------------------------------------------------------------------------- #


def test_build_calibration_set_succeeds_with_defaults():
    cs = _build()
    assert cs.calibration_id == "oem-test-fleet-A-v1"
    assert cs.kernel_version == __version__
    assert cs.matches_running_kernel is True
    assert cs.digest  # non-empty


def test_calibration_set_digest_is_64_char_sha256():
    cs = _build()
    assert len(cs.digest) == 64  # SHA-256 hex
    int(cs.digest, 16)  # all hex characters


def test_two_bundles_with_same_content_have_same_digest():
    a = _build()
    b = _build()
    assert a.digest == b.digest


def test_changing_calibration_id_changes_digest():
    a = _build()
    b = _build(calibration_id="oem-test-fleet-B-v1")
    assert a.digest != b.digest


def test_changing_a_nested_config_field_changes_digest():
    a = _build()
    bcvf_modified = BCVFConfig(lambda_c=2.0)  # default is 1.0
    b = _build(bcvf_config=bcvf_modified)
    assert a.digest != b.digest


def test_construction_rejects_empty_calibration_id():
    with pytest.raises(CalibrationSetError, match="calibration_id"):
        _build(calibration_id="")


def test_construction_rejects_whitespace_only_calibration_id():
    with pytest.raises(CalibrationSetError, match="non-whitespace"):
        _build(calibration_id="   ")


def test_construction_rejects_non_semver_kernel_version():
    with pytest.raises(CalibrationSetError, match="semver"):
        _build(kernel_version="not-a-version")


def test_construction_rejects_non_iso_8601_created_at():
    with pytest.raises(CalibrationSetError, match="ISO 8601"):
        _build(created_at="yesterday")


# --------------------------------------------------------------------------- #
# Embedded-config validation
# --------------------------------------------------------------------------- #


def test_construction_rejects_malformed_bcvf_config_dict():
    """A bcvf_config dict missing a required key fails at
    construction — the bundle can't smuggle a malformed config
    past the validator."""
    with pytest.raises(CalibrationSetError, match="bcvf_config"):
        CalibrationSet(
            calibration_id="x",
            kernel_version=__version__,
            created_at="2026-05-05T12:00:00+00:00",
            bcvf_config={"lambda_c": 1.0},  # missing every other field
            consumer_v2_config={
                "enabled": False, "engage_threshold": 0.5,
                "disengage_threshold": 0.2, "T_engage": 3, "T_disengage": 5,
            },
            bicycle_config={
                "wheelbase": 2.7, "max_steering": 0.6,
                "max_velocity": 15.0, "max_acceleration": 3.0, "dt": 0.1,
            },
            realtime_budget=RealTimeBudget().to_dict(),
            dds_qos_profile=DDSQoSProfile().to_dict(),
            safety_state_config={
                "rolling_window_ticks": 200,
                "near_veto_consec_floor": 3,
                "near_veto_rate_threshold": 0.10,
                "bcvf_active_threshold": 0.05,
                "bcvf_active_rate_threshold": 0.50,
                "exclusion_persistence_ticks": 5,
                "failsafe_excluded_predictor_count": 2,
                "t_recovery_ticks": 100,
            },
            per_predictor_failure_thresholds={},
            expected_metrics={},
        )


def test_construction_rejects_unknown_cost_order():
    """An invalid CostOrder name in the bcvf_config dict fails
    reconstruction at the embedded-validator gate."""
    bcvf_dict = {
        "lambda_c": 1.0, "gate_threshold": 0.05, "gate_beta": 400.0,
        "huber_delta": 0.5, "lever_arm": 0.0,
        "weight_matrix": np.eye(3).tolist(),
        "use_anchor_pairing": False, "anchor_index": 0, "dt": 0.1,
        "cost_order": "BOGUS_ORDER",
    }
    with pytest.raises(CalibrationSetError):
        CalibrationSet(
            calibration_id="x",
            kernel_version=__version__,
            created_at="2026-05-05T12:00:00+00:00",
            bcvf_config=bcvf_dict,
            consumer_v2_config=ConsumerV2Config().__dict__,  # passes
            bicycle_config=BicycleConfig().__dict__,
            realtime_budget=RealTimeBudget().to_dict(),
            dds_qos_profile=DDSQoSProfile().to_dict(),
            safety_state_config={
                "rolling_window_ticks": 200,
                "near_veto_consec_floor": 3,
                "near_veto_rate_threshold": 0.10,
                "bcvf_active_threshold": 0.05,
                "bcvf_active_rate_threshold": 0.50,
                "exclusion_persistence_ticks": 5,
                "failsafe_excluded_predictor_count": 2,
                "t_recovery_ticks": 100,
            },
            per_predictor_failure_thresholds={},
            expected_metrics={},
        )


def test_construction_rejects_expected_metric_with_inverted_bounds():
    with pytest.raises(CalibrationSetError, match="min .* max"):
        _build(expected_metrics={
            "argmax_flips_per_step.p95": {"min": 0.5, "max": 0.0},
        })


def test_construction_rejects_expected_metric_missing_min_or_max():
    with pytest.raises(CalibrationSetError, match="min.*max"):
        _build(expected_metrics={"some_metric": {"min": 0.0}})


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #


def test_to_dict_then_from_dict_round_trips():
    cs = _build()
    d = cs.to_dict()
    cs2 = CalibrationSet.from_dict(d)
    assert cs2.calibration_id == cs.calibration_id
    assert cs2.kernel_version == cs.kernel_version
    assert cs2.digest == cs.digest


def test_from_dict_rejects_non_dict_input():
    with pytest.raises(CalibrationSetError, match="dict"):
        CalibrationSet.from_dict([1, 2, 3])  # type: ignore[arg-type]


def test_from_dict_rejects_missing_required_fields():
    cs = _build()
    payload = cs.to_dict()
    del payload["calibration_id"]
    with pytest.raises(CalibrationSetError, match="missing required fields"):
        CalibrationSet.from_dict(payload)


def test_from_dict_rejects_tampered_digest():
    cs = _build()
    payload = cs.to_dict()
    payload["digest"] = "0" * 64  # valid hex but wrong digest
    with pytest.raises(CalibrationDigestError, match="digest mismatch"):
        CalibrationSet.from_dict(payload)


def test_from_dict_rejects_tampered_field_with_correct_digest_recompute():
    """A hand-edit to a config field must surface as a digest
    mismatch — the digest discipline's whole point."""
    cs = _build()
    payload = cs.to_dict()
    payload["bcvf_config"]["lambda_c"] = 999.0  # tamper
    # digest unchanged → should be detected as a mismatch on load.
    with pytest.raises(CalibrationDigestError):
        CalibrationSet.from_dict(payload)


def test_from_dict_with_verify_digest_false_skips_digest_check():
    """A diagnostic-only load that explicitly opts out of
    digest verification should accept a tampered bundle —
    used for forensics on a corrupted artifact."""
    cs = _build()
    payload = cs.to_dict()
    payload["digest"] = "0" * 64
    # Should not raise — verify_digest=False explicitly skips.
    bundle = CalibrationSet.from_dict(payload, verify_digest=False)
    assert bundle.digest == "0" * 64


# --------------------------------------------------------------------------- #
# I/O — save / load + canonical JSON
# --------------------------------------------------------------------------- #


def test_save_and_load_round_trips(tmp_path):
    cs = _build()
    out = tmp_path / "calibration.json"
    save_calibration_set(cs, out)
    cs2 = load_calibration_set(out)
    assert cs2.digest == cs.digest


def test_load_rejects_missing_path(tmp_path):
    with pytest.raises(CalibrationSetError, match="not found"):
        load_calibration_set(tmp_path / "does_not_exist.json")


def test_load_rejects_invalid_json(tmp_path):
    out = tmp_path / "bad.json"
    out.write_text("not { valid json", encoding="utf-8")
    with pytest.raises(CalibrationSetError, match="JSON"):
        load_calibration_set(out)


def test_load_rejects_kernel_version_drift_by_default(tmp_path):
    cs = _build(kernel_version="0.0.1-old")
    out = tmp_path / "old.json"
    save_calibration_set(cs, out)
    with pytest.raises(CalibrationVersionError, match="kernel_version"):
        load_calibration_set(out)


def test_load_allows_kernel_version_drift_when_explicit(tmp_path):
    cs = _build(kernel_version="0.0.1-old")
    out = tmp_path / "old.json"
    save_calibration_set(cs, out)
    bundle = load_calibration_set(out, allow_version_drift=True)
    assert bundle.kernel_version == "0.0.1-old"
    assert bundle.matches_running_kernel is False


def test_render_text_is_deterministic():
    cs = _build()
    a = render_calibration_set_text(cs)
    b = render_calibration_set_text(cs)
    assert a == b


def test_render_text_uses_canonical_serialisation():
    cs = _build()
    text = render_calibration_set_text(cs)
    assert text.endswith("\n")
    parsed = json.loads(text)
    # Sorted top-level keys: bcvf_config comes before kernel_version.
    assert text.index('"bcvf_config"') < text.index('"kernel_version"')


# --------------------------------------------------------------------------- #
# Drift detector
# --------------------------------------------------------------------------- #


def _stub_windowed_summary(metric_value: float, n_episodes: int = 5):
    """Build a minimal stub WindowedFleetSummary with the given
    p95 metric value. We mock the to_dict surface the detector
    walks rather than spinning up the full StreamingFleetMonitor."""
    class _Stub:
        def to_dict(self):
            return {
                "fleet": {
                    "argmax_flips_per_step": {
                        "p50": 0.0, "p95": float(metric_value),
                        "p99": float(metric_value),
                    },
                },
                "n_observed_in_window": int(n_episodes),
            }
    return _Stub()


def test_drift_detector_in_range_emits_no_alerts():
    cs = _build(expected_metrics={
        "argmax_flips_per_step.p95": {"min": 0.0, "max": 0.10},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_stub_windowed_summary(metric_value=0.05))
    assert alerts == ()


def test_drift_detector_above_range_emits_above_alert():
    cs = _build(expected_metrics={
        "argmax_flips_per_step.p95": {"min": 0.0, "max": 0.10},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_stub_windowed_summary(metric_value=0.25))
    assert len(alerts) == 1
    a = alerts[0]
    assert a.metric == "argmax_flips_per_step.p95"
    assert a.observed_value == 0.25
    assert a.expected_max == 0.10
    assert a.direction == "above"
    assert a.calibration_id == cs.calibration_id


def test_drift_detector_below_range_emits_below_alert():
    cs = _build(expected_metrics={
        "argmax_flips_per_step.p95": {"min": 0.10, "max": 0.50},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_stub_windowed_summary(metric_value=0.05))
    assert len(alerts) == 1
    assert alerts[0].direction == "below"


def test_drift_detector_with_no_expected_metrics_emits_no_alerts():
    cs = _build(expected_metrics={})
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_stub_windowed_summary(metric_value=99.9))
    assert alerts == ()


def test_drift_detector_skips_missing_metric_silently():
    """A metric path that resolves to None (legitimately
    missing — e.g. v2_engaged_fraction when V2 was off) is
    skipped, not reported as a drift signal."""
    class _Stub:
        def to_dict(self):
            return {
                "fleet": {"v2_engaged_fraction": None},
                "n_observed_in_window": 10,
            }
    cs = _build(expected_metrics={
        "v2_engaged_fraction": {"min": 0.5, "max": 1.0},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_Stub())
    assert alerts == ()


def test_drift_detector_raises_on_typo_metric_path():
    """A metric path that doesn't resolve at all (typo / dropped
    segment) raises KeyError — same loud-failure discipline
    StreamingFleetMonitor enforces for typo'd AlertRule.metric."""
    cs = _build(expected_metrics={
        "fleet.does_not_exist.p95": {"min": 0.0, "max": 0.1},
    })
    det = CalibrationDriftDetector(cs)
    with pytest.raises(KeyError, match="does_not_exist"):
        det.evaluate(_stub_windowed_summary(metric_value=0.05))


def test_drift_detector_alert_serialises_to_dict():
    cs = _build(expected_metrics={
        "argmax_flips_per_step.p95": {"min": 0.0, "max": 0.10},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(_stub_windowed_summary(
        metric_value=0.25, n_episodes=42,
    ))
    d = alerts[0].to_dict()
    assert d["metric"] == "argmax_flips_per_step.p95"
    assert d["observed_value"] == 0.25
    assert d["expected_min"] == 0.0
    assert d["expected_max"] == 0.10
    assert d["direction"] == "above"
    assert d["calibration_id"] == cs.calibration_id
    assert d["n_episodes_in_window"] == 42


def test_drift_detector_rejects_non_calibration_input():
    with pytest.raises(CalibrationSetError, match="CalibrationSet"):
        CalibrationDriftDetector("not a calibration")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Composition with real WindowedFleetSummary
# --------------------------------------------------------------------------- #


def test_drift_detector_walks_real_windowed_fleet_summary():
    """Composition test: the detector accepts the actual
    WindowedFleetSummary the StreamingFleetMonitor produces.
    Pinned so a future refactor of the to_dict shape doesn't
    silently break the detector path."""
    from datetime import timedelta
    import numpy as np
    from symbolu_robotics.bcvf_autonomous.analysis import (
        StreamingFleetMonitor,
    )
    from symbolu_robotics.bcvf_autonomous.trust_diagnostics import (
        RolloutAggregation,
        TrustShapedEpisodeRecord,
    )

    monitor = StreamingFleetMonitor()
    T, M = 5, 3
    record = TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.zeros((T, M)),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.zeros(T),
        per_step_deadband_active_count=np.zeros(T, dtype=np.int64),
        per_step_deadband_fired=np.zeros(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_v2_state=[""] * T,
        per_step_v2_signal=np.zeros(T),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
        per_step_consec_ok=np.zeros((T, M), dtype=np.int64),
    )
    monitor.observe_episode(record, episode_id="ep_1", classification="quiet")
    windowed = monitor.summary(window=timedelta(hours=24))

    # Quiet episode — argmax_flips_per_step.p95 should be 0.0.
    cs = _build(expected_metrics={
        "argmax_flips_per_step.p95": {"min": -0.01, "max": 0.5},
    })
    det = CalibrationDriftDetector(cs)
    alerts = det.evaluate(windowed)
    assert alerts == ()  # quiet episode is in-range


# --------------------------------------------------------------------------- #
# Snapshot / canonical JSON shape
# --------------------------------------------------------------------------- #


def test_canonical_to_dict_includes_all_top_level_fields():
    """Pin the bundle JSON shape so a regression that adds a
    default field, drops one, or reorders surfaces loud."""
    cs = _build()
    d = cs.to_dict()
    expected = {
        "calibration_id",
        "kernel_version",
        "created_at",
        "bcvf_config",
        "consumer_v2_config",
        "bicycle_config",
        "realtime_budget",
        "dds_qos_profile",
        "safety_state_config",
        "per_predictor_failure_thresholds",
        "expected_metrics",
        "metadata",
        "digest",
    }
    assert set(d.keys()) == expected
