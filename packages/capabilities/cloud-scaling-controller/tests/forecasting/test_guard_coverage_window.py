"""Isolating tests for the guard sweep — `forecasting/window.py`.

Written for phase 2 of the shared-engine adoption. The input window is the leakage
boundary: it decides which observations a forecaster is allowed to see, in which value
space, and under which normalization authority. Its gates are the ones that keep a
forecast honest about what it was computed from — a window built from the wrong space, or
normalized under a policy that does not apply to these observations, produces a forecast
whose units mean something other than what the evidence says they mean.

Each test isolates one gate, asserting the typed half of the refusal — `WindowError`, or
for the normalization gates the `NormalizationApplicabilityError.reason` label the service
maps to an abstention. `reason` is a typed field, not a message: the three normalization
gates all raise the same class, so the label is the only thing that attributes a kill to
one of them rather than another.
"""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacityState,
    NormalizationPolicy,
)
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    ForecastValueSpace,
)
from ugence_cloud_scaling_controller.forecasting.window import (
    NormalizationApplicabilityError,
    WindowError,
    build_input_window,
)

H1 = ForecastHorizon(60.0)
NPOL = fx.cpu_norm_policy()


def _series(values=(10.0, 20.0, 30.0)):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(list(values)))


def _replica_series():
    states = [
        CanonicalCapacityState(subject=fx.subject(), observed_at=fx.at(60.0 * i),
                               capacity=CapacityState(running_replicas=4 + i))
        for i in range(3)
    ]
    return CanonicalCapacitySeries.build(states)


def _build(series=None, target=ForecastTarget.CPU_UTILIZATION, **kw):
    s = series or _series()
    return build_input_window(s, target, s.end_event_time, H1, **kw)


# ===================================================================================== #
# the configuration objects a window is built under
# ===================================================================================== #


def test_a_horizon_whose_length_is_a_bool_is_refused():
    """`True` is an `int`, and it is also `> 0`, so the positivity check one line down
    accepts it: only the type half of this gate stands between a caller and a
    one-second horizon labelled as whatever they meant."""

    with pytest.raises(WindowError):
        ForecastHorizon(True)


@pytest.mark.parametrize(
    "override",
    [
        {"lookback_seconds": True},
        {"expected_cadence_seconds": True},
    ],
)
def test_a_feature_config_interval_that_is_a_bool_is_refused(override):
    """The shared loop over the two strictly-positive intervals. A bool passes `> 0`, so
    a neutralised gate turns a lookback window into one second — and the forecast is then
    computed from an empty history that the evidence still describes as an hour of it."""

    with pytest.raises(WindowError):
        FeatureConfig(**override)


def test_a_cadence_tolerance_that_is_negative_is_refused():
    """A separate gate from the two above because zero is admissible here: an exact
    cadence requirement is a legitimate configuration, a negative tolerance is not."""

    with pytest.raises(WindowError):
        FeatureConfig(cadence_tolerance_seconds=-1.0)


# ===================================================================================== #
# type gates on the window builder
# ===================================================================================== #


def test_a_series_that_is_not_a_canonical_series_is_refused():
    with pytest.raises(WindowError):
        build_input_window("not a series", ForecastTarget.CPU_UTILIZATION, fx.T0, H1)


def test_a_target_that_is_not_a_forecast_target_is_refused():
    """`ForecastTarget` is a `str` enum, so the bare string reaches every comparison in
    the extractor and silently matches nothing — an empty window rather than a refusal."""

    with pytest.raises(WindowError):
        _build(target="cpu_utilization")


def test_a_horizon_that_is_not_a_forecast_horizon_is_refused():
    s = _series()
    with pytest.raises(WindowError):
        build_input_window(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, 60.0)


def test_a_cutoff_that_is_not_a_datetime_is_refused():
    """The cutoff is the leakage boundary itself: everything at or before it may be seen
    and nothing after it may. A string cutoff is a boundary nothing can be compared to."""

    s = _series()
    with pytest.raises(WindowError):
        build_input_window(s, ForecastTarget.CPU_UTILIZATION, "2026-01-01", H1)


def test_a_forecast_space_that_is_not_a_value_space_is_refused():
    """Also a `str` enum: without the gate `forecast_space is NORMALIZED` is False for the
    equal string, so a NORMALIZED request would quietly produce a raw window whose
    evidence claims it was normalized."""

    with pytest.raises(WindowError):
        _build(forecast_space="normalized")


# ===================================================================================== #
# normalization applicability — one class, three typed reasons
# ===================================================================================== #


def test_normalizing_a_target_that_has_no_normalization_method_is_refused():
    """RUNNING_REPLICAS is projected without conversion and has no method at all. Probes
    both the `do_normalize` block admission and the missing-signal gate inside it:
    neutralise either and the request produces an empty window instead of a refusal,
    because the per-sample normalization path finds no Measurement to convert."""

    with pytest.raises(NormalizationApplicabilityError) as exc:
        _build(_replica_series(), ForecastTarget.RUNNING_REPLICAS,
               normalization_policy=NPOL,
               forecast_space=ForecastValueSpace.NORMALIZED)
    assert exc.value.reason == "unsupported_target"


def test_normalizing_without_a_policy_at_all_is_refused():
    """Without the gate the next line reads `.method_by_signal` off `None`."""

    with pytest.raises(NormalizationApplicabilityError) as exc:
        _build(normalization_policy=None, forecast_space=ForecastValueSpace.NORMALIZED)
    assert exc.value.reason == "missing_normalization_policy"


def test_normalizing_under_a_policy_with_no_method_for_this_signal_is_refused():
    """The typed reason is what attributes this kill. Neutralised, the per-sample path
    still fails — `normalize_signal` refuses a signal it has no method for — but it
    reports `inconsistent_unit`, which the service maps to a different abstention than
    the one the operator needs to see. The gate exists to name the failure correctly, so
    only the `reason` label distinguishes the two."""

    empty_policy = NormalizationPolicy(policy_id="empty-p1", method_by_signal={})
    with pytest.raises(NormalizationApplicabilityError) as exc:
        _build(normalization_policy=empty_policy,
               forecast_space=ForecastValueSpace.NORMALIZED)
    assert exc.value.reason == "missing_normalization_policy"
