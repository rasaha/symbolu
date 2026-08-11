"""Normalization tests (section 19.2)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical import (
    Measurement, NormalizationMethod, NormalizationPolicy, Unit, normalize_signal,
)
from ugence_cloud_scaling_controller.canonical.normalization import NormalizationError


def _policy(**kw):
    base = dict(policy_id="p", method_by_signal={}, thresholds={})
    base.update(kw)
    return NormalizationPolicy(**base)


def test_ratio_passthrough():
    p = _policy(method_by_signal={"error_rate": NormalizationMethod.RATIO_PASSTHROUGH})
    ns = normalize_signal("error_rate", Measurement(0.2, Unit.RATE), p)
    assert ns.normalized_value == 0.2
    assert ns.raw_value == 0.2 and ns.raw_unit == "rate" and ns.method == "ratio_passthrough"


def test_percent_to_ratio():
    p = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    ns = normalize_signal("cpu", Measurement(82.0, Unit.PERCENT), p)
    assert ns.normalized_value == pytest.approx(0.82)


def test_latency_ms_and_s_threshold():
    p = _policy(method_by_signal={"latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD},
                thresholds={"latency_p99": 1000.0})
    ns = normalize_signal("latency_p99", Measurement(810.0, Unit.MILLISECONDS), p)
    assert ns.normalized_value == pytest.approx(0.81)
    assert ns.threshold == 1000.0

    p2 = _policy(method_by_signal={"latency_p99": NormalizationMethod.LATENCY_S_TO_THRESHOLD},
                 thresholds={"latency_p99": 2.0})
    ns2 = normalize_signal("latency_p99", Measurement(1.0, Unit.SECONDS), p2)
    assert ns2.normalized_value == pytest.approx(0.5)


def test_queue_to_capacity_baseline():
    p = _policy(method_by_signal={"queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY},
                thresholds={"queue_depth": 100.0})
    ns = normalize_signal("queue_depth", Measurement(70, Unit.COUNT), p)
    assert ns.normalized_value == pytest.approx(0.7)


def test_explicit_clamping_recorded():
    p = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO}, clamp=True)
    ns = normalize_signal("cpu", Measurement(100.0, Unit.PERCENT), p)
    assert ns.normalized_value == 1.0 and ns.clamped is False
    # value that would exceed 1.0 via a threshold method
    p2 = _policy(method_by_signal={"latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD},
                 thresholds={"latency_p99": 100.0}, clamp=True)
    ns2 = normalize_signal("latency_p99", Measurement(500.0, Unit.MILLISECONDS), p2)
    assert ns2.normalized_value == 1.0 and ns2.clamped is True


def test_no_clamping_out_of_range_fails_closed():
    p = _policy(method_by_signal={"latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD},
                thresholds={"latency_p99": 100.0}, clamp=False)
    with pytest.raises(NormalizationError):
        normalize_signal("latency_p99", Measurement(500.0, Unit.MILLISECONDS), p)


def test_zero_and_negative_threshold_rejected():
    with pytest.raises(NormalizationError):
        _policy(method_by_signal={"q": NormalizationMethod.QUEUE_TO_CAPACITY}, thresholds={"q": 0.0})
    with pytest.raises(NormalizationError):
        _policy(method_by_signal={"q": NormalizationMethod.QUEUE_TO_CAPACITY}, thresholds={"q": -5.0})


def test_missing_threshold_never_invented():
    p = _policy(method_by_signal={"queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY})
    with pytest.raises(NormalizationError):
        normalize_signal("queue_depth", Measurement(70, Unit.COUNT), p)


def test_unsupported_unit_for_method():
    p = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    with pytest.raises(NormalizationError):
        normalize_signal("cpu", Measurement(0.8, Unit.RATIO), p)


def test_unconfigured_signal_fails_closed():
    p = _policy(method_by_signal={})
    with pytest.raises(NormalizationError):
        normalize_signal("cpu", Measurement(50.0, Unit.PERCENT), p)


def test_contradictory_clamp_bounds_rejected():
    with pytest.raises(NormalizationError):
        _policy(method_by_signal={}, clamp=True, clamp_low=1.0, clamp_high=0.0)


def test_policy_identity_stable():
    a = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    b = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    assert a.digest() == b.digest()
    c = _policy(method_by_signal={"cpu": NormalizationMethod.RATIO_PASSTHROUGH})
    assert a.digest() != c.digest()


def test_deterministic_normalization_and_raw_preserved():
    p = _policy(method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    m = Measurement(63.0, Unit.PERCENT)
    a = normalize_signal("cpu", m, p)
    b = normalize_signal("cpu", m, p)
    assert a == b
    assert a.raw_value == 63.0 and a.method == "percent_to_ratio"
