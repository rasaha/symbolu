"""Legacy parity for the extracted interval formula.

The interval mathematics used to live inline inside ``compute_uncertainty``. It now lives in
the public :func:`interval_from_residuals`, and ``compute_uncertainty`` delegates to it.

``fixtures/legacy_uncertainty_golden.json`` was generated from the module **as it stood
before** the extraction (commit ``2baea64d``). These tests require **exact** equality against
it — no numeric tolerance is claimed or permitted, because the extraction moves the same
operations rather than reformulating them.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    build_input_window,
    compute_uncertainty,
    interval_from_residuals,
    rolling_origin_residuals,
)
from ugence_cloud_scaling_controller.forecasting.uncertainty import UncertaintyError

_GOLDEN = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "legacy_uncertainty_golden.json").read_text()
)
_CASES = _GOLDEN["cases"]

_SERIES = {
    "step": [0.0, 10.0, 5.0, 20.0, 15.0, 30.0],
    "ramp": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "flat": [7.5] * 9,
    "noisy": [12.0, 9.5, 14.25, 8.0, 11.75, 13.5, 7.25, 15.0, 10.5, 12.25],
    "biased": [0.0, 3.0, 7.0, 12.0, 18.0, 25.0, 33.0, 42.0],
    "twopoint": [4.0, 9.0],
}
_CONFIGS = {
    "cov80_min5": dict(requested_coverage=0.8, min_calibration_samples=5, match_tolerance_seconds=5.0),
    "cov50_min2": dict(requested_coverage=0.5, min_calibration_samples=2, match_tolerance_seconds=5.0),
    "cov95_min3": dict(requested_coverage=0.95, min_calibration_samples=3, match_tolerance_seconds=5.0),
    "cov99_min1": dict(requested_coverage=0.99, min_calibration_samples=1, match_tolerance_seconds=5.0),
    "none": dict(method=UncertaintyMethod.NONE, requested_coverage=0.8),
    "pointok": dict(requested_coverage=0.8, min_calibration_samples=50,
                    allow_point_only_when_uncalibrated=True, match_tolerance_seconds=5.0),
}
_FORECASTERS = {"persistence": PersistenceForecaster, "linear_trend": LinearTrendForecaster}


def _window(series_name):
    states = fx.cpu_series_states(_SERIES[series_name], cadence_seconds=60.0)
    s = CanonicalCapacitySeries.build(states)
    return build_input_window(
        s, ForecastTarget.CPU_UTILIZATION, states[-1].observed_at, ForecastHorizon(60.0)
    )


def _ids(case):
    return f"{case['series']}-{case['forecaster']}-{case['config']}-p{case['point']}"


def test_golden_fixture_is_representative():
    """A parity fixture that exercises only one branch would prove nothing."""
    assert len(_CASES) == 216
    reasons = {c["interval"]["unavailable_reason"] for c in _CASES}
    assert reasons == {None, "insufficient_calibration_history", "uncertainty_method_none"}
    assert sum(1 for c in _CASES if c["interval"]["available"]) == 120


@pytest.mark.parametrize("case", _CASES, ids=_ids)
def test_legacy_formula_parity_exact(case):
    """1. compute_uncertainty reproduces frozen pre-extraction output exactly."""
    w = _window(case["series"])
    f = _FORECASTERS[case["forecaster"]]()
    cfg = UncertaintyConfig(**_CONFIGS[case["config"]])

    assert rolling_origin_residuals(w, f, cfg) == case["residuals"]
    iv = compute_uncertainty(w, f, case["point"], cfg)
    assert iv.to_canonical_dict() == case["interval"]


@pytest.mark.parametrize("case", _CASES, ids=_ids)
def test_public_function_parity_exact(case):
    """2. interval_from_residuals given the exact legacy residual sequence agrees exactly."""
    cfg = UncertaintyConfig(**_CONFIGS[case["config"]])
    iv = interval_from_residuals(case["point"], case["residuals"], cfg)
    assert iv.to_canonical_dict() == case["interval"]


def test_legacy_payload_has_no_calibration_digest_key():
    """The new field must not appear in legacy payloads, or every historical digest moves."""
    for case in _CASES:
        assert "calibration_input_digest" not in case["interval"]
    w = _window("noisy")
    iv = compute_uncertainty(w, PersistenceForecaster(), 10.0,
                             UncertaintyConfig(min_calibration_samples=2, match_tolerance_seconds=5.0))
    assert iv.calibration_input_digest is None
    assert "calibration_input_digest" not in iv.to_canonical_dict()


def test_bank_digest_appears_only_when_supplied():
    cfg = UncertaintyConfig(method=UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK,
                            requested_coverage=0.8, min_calibration_samples=3)
    iv = interval_from_residuals(10.0, [1.0, -2.0, 3.0, -4.0], cfg,
                                 calibration_input_digest="sha256:abc")
    assert iv.calibration_input_digest == "sha256:abc"
    assert iv.to_canonical_dict()["calibration_input_digest"] == "sha256:abc"
    assert iv.method == "empirical_prequential_residual_bank"


def test_input_order_does_not_change_the_interval():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=3)
    residuals = [3.5, -1.0, 7.25, 0.0, -4.5]
    a = interval_from_residuals(5.0, residuals, cfg)
    b = interval_from_residuals(5.0, list(reversed(residuals)), cfg)
    assert a == b


def test_caller_sequence_is_not_mutated():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=3)
    residuals = [3.5, -1.0, 7.25, 0.0, -4.5]
    original = list(residuals)
    interval_from_residuals(5.0, residuals, cfg)
    assert residuals == original


def test_immutable_input_is_accepted():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=3)
    iv = interval_from_residuals(5.0, (3.5, -1.0, 7.25, 0.0, -4.5), cfg)
    assert iv.available


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "1.0", None, True])
def test_malformed_residuals_fail_closed(bad):
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=1)
    with pytest.raises(UncertaintyError):
        interval_from_residuals(5.0, [1.0, bad, 2.0], cfg)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "5.0", None, True])
def test_malformed_point_fails_closed(bad):
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=1)
    with pytest.raises(UncertaintyError):
        interval_from_residuals(bad, [1.0, 2.0], cfg)


def test_non_config_fails_closed():
    with pytest.raises(UncertaintyError):
        interval_from_residuals(5.0, [1.0, 2.0], {"requested_coverage": 0.8})


def test_string_residuals_are_not_treated_as_a_sequence():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=1)
    with pytest.raises(UncertaintyError):
        interval_from_residuals(5.0, "123", cfg)


def test_empty_residuals_are_insufficient_not_an_error():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=1)
    iv = interval_from_residuals(5.0, [], cfg)
    assert not iv.available
    assert iv.insufficient_calibration
    assert iv.calibration_sample_count == 0


def test_bad_calibration_digest_fails_closed():
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=1)
    for bad in ("", 123, b"sha256:x"):
        with pytest.raises(UncertaintyError):
            interval_from_residuals(5.0, [1.0, 2.0], cfg, calibration_input_digest=bad)


def test_compute_uncertainty_refuses_bank_method_without_supplied_calibration():
    """A bank-configured run must never silently fall back to in-window collection."""
    w = _window("noisy")
    cfg = UncertaintyConfig(method=UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK,
                            requested_coverage=0.8, min_calibration_samples=3)
    with pytest.raises(UncertaintyError):
        compute_uncertainty(w, PersistenceForecaster(), 10.0, cfg)


def test_existing_enum_values_preserved():
    assert UncertaintyMethod.NONE.value == "none"
    assert UncertaintyMethod.EMPIRICAL_ROLLING_ORIGIN_RESIDUAL.value == "empirical_rolling_origin_residual"
    assert UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK.value == "empirical_prequential_residual_bank"
    assert len(list(UncertaintyMethod)) == 3
