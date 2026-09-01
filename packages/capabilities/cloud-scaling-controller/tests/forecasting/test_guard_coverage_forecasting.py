"""Isolating tests for the guard sweep — the smaller `forecasting/` modules.

Written for phase 2 of the shared-engine adoption. One file rather than six because each
of these modules contributes a handful of gates of the same character. The larger
surfaces have their own files (`test_guard_coverage_evaluation.py`,
`test_guard_coverage_evidence.py`, `test_guard_coverage_window.py`).

Why these matter in one sentence each:

* `forecast` — the record itself. Its status gates are what keep "I predict 30" and "I
  declined to predict" from ever being the same object; its posture gates are the
  machine-readable claim that this package forecasts and never acts.
* `series` — the ordered, single-subject history a forecast is computed from. A
  construction policy that stops validating admits a history assembled under rules
  nobody chose.
* `uncertainty` — the calibration configuration behind every published interval.
* `targets` — the extractor every other module reads observations through.
* `forecasters` / `replay` — the predictor boundary and the leakage-safe harness.

Each test isolates one gate and asserts the typed half of its refusal, never a message
substring.
"""

from __future__ import annotations

import dataclasses

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.forecast import ForecastError
from ugence_cloud_scaling_controller.forecasting.forecasters import ForecasterError
from ugence_cloud_scaling_controller.forecasting.replay import (
    MATCH_NONE,
    ReplayError,
    _match_actual,
    run_replay_evaluation,
)
from ugence_cloud_scaling_controller.forecasting.series import (
    DuplicateTimestampPolicy,
    OrderingPolicy,
    SeriesConstructionPolicy,
    SeriesError,
)
from ugence_cloud_scaling_controller.forecasting.targets import (
    TargetError,
    extract_measurement,
    extract_sample,
)
from ugence_cloud_scaling_controller.forecasting.uncertainty import UncertaintyError

H1 = ForecastHorizon(60.0)
NPOL = fx.cpu_norm_policy()
NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)


def _series(values=(10.0, 20.0, 30.0)):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(list(values)))


def _forecast(values=(10.0, 20.0, 30.0), **kw):
    """A real (non-abstained) forecast. `uncertainty_config` is pinned to NONE because
    the default configuration calibrates an interval and abstains for want of calibration
    history — a legitimate abstention, but not the record these tests need."""
    s = _series(values)
    kw.setdefault("normalization_policy", NPOL)
    kw.setdefault("uncertainty_config", NONE_UC)
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1, PersistenceForecaster(), **kw
    ).forecast


def _abstention():
    fc = _forecast(normalization_policy=None)
    assert fc.is_abstained
    return fc


# ===================================================================================== #
# forecast — the record's posture and its status contract
# ===================================================================================== #


@pytest.mark.parametrize(
    "override",
    [
        {"advisory_only": False},
        {"execution_capability": "DIRECT"},
    ],
)
def test_a_forecast_cannot_claim_an_authority_this_package_does_not_have(override):
    """Two of the five posture gates: the sweep measured only these surviving, so only
    these are probed. A forecast is shadow output — a record that could carry either of
    these values claims the package acted on its own prediction."""

    fc = _forecast()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, **override)


def test_a_status_outside_the_declared_pair_is_refused():
    """There are exactly two outcomes: a forecast or a typed abstention. Neutralised, a
    third status reaches the branch below, takes the `else` (abstained) arm, and a record
    labelled something a reader has never seen is treated as an abstention."""

    fc = _forecast()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, status="maybe")


def test_a_forecast_status_without_a_point_estimate_is_refused():
    """The whole content of a forecast. Without the gate the record says "forecast" and
    carries nothing to forecast with."""

    fc = _forecast()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, point_estimate=None)


def test_a_forecast_status_carrying_an_abstention_reason_is_refused():
    """A record that both predicts and declines to predict; a reader branching on either
    field alone would draw opposite conclusions from the same record."""

    fc = _forecast()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, abstention_reason=AbstentionReason.INSUFFICIENT_HISTORY)


def test_an_abstained_status_carrying_a_point_estimate_is_refused():
    """The dangerous direction of the same contradiction: a caller that reads the point
    estimate without checking the status would act on a number the forecaster explicitly
    declined to stand behind."""

    fc = _abstention()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, point_estimate=30.0)


def test_an_abstained_status_without_a_typed_reason_is_refused():
    """`AbstentionReason` is a `str` enum, so the bare string passes every later equality
    test; only the type gate keeps the reason vocabulary closed."""

    fc = _abstention()
    with pytest.raises(ForecastError):
        dataclasses.replace(fc, abstention_reason="insufficient_history")


# ===================================================================================== #
# series — the history a forecast is computed from
# ===================================================================================== #


def test_a_series_policy_without_an_identifier_is_refused():
    with pytest.raises(SeriesError):
        SeriesConstructionPolicy(policy_id="")


def test_a_series_ordering_that_is_not_an_ordering_policy_is_refused():
    """A `str` enum again: the bare string would compare equal to the member in the
    ordering branch and quietly select whichever arm it spells."""

    with pytest.raises(SeriesError):
        SeriesConstructionPolicy(ordering="require_sorted")


def test_a_duplicate_timestamp_rule_that_is_not_a_policy_is_refused():
    with pytest.raises(SeriesError):
        SeriesConstructionPolicy(duplicate_timestamp="reject")


def test_a_timezone_requirement_that_is_not_a_bool_is_refused():
    """Every non-empty string is truthy, so a neutralised gate leaves the requirement
    looking enabled whatever was passed — including the string "false"."""

    with pytest.raises(SeriesError):
        SeriesConstructionPolicy(require_timezone_aware="yes")


def test_building_a_series_under_something_that_is_not_a_policy_is_refused():
    """`None` is admissible here and selects the default policy, so only a non-policy
    object can probe the gate."""

    with pytest.raises(SeriesError):
        CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0]), "strict")


def test_a_series_carrying_a_non_state_item_is_refused():
    """The first item is a real state, so the sequence looks well-formed at its head; the
    gate materializes and checks the whole of it before building anything."""

    states = fx.cpu_series_states([10.0, 20.0])
    with pytest.raises(SeriesError):
        CanonicalCapacitySeries.build([states[0], {"cpu": 30.0}])


# ===================================================================================== #
# uncertainty — the calibration behind every published interval
# ===================================================================================== #


def test_an_uncertainty_method_that_is_not_a_method_is_refused():
    with pytest.raises(UncertaintyError):
        UncertaintyConfig(method="none")


def test_a_calibration_minimum_that_is_a_bool_is_refused():
    """`True` is an `int` and is `>= 1`, so it passes the range half of the gate: only
    the type half stops a one-sample calibration from producing an interval that looks
    as authoritative as a fifty-sample one."""

    with pytest.raises(UncertaintyError):
        UncertaintyConfig(min_calibration_samples=True)


def test_a_calibration_match_tolerance_that_is_negative_is_refused():
    with pytest.raises(UncertaintyError):
        UncertaintyConfig(match_tolerance_seconds=-1.0)


# ===================================================================================== #
# targets — the extractor every module reads observations through
# ===================================================================================== #


def test_extracting_a_measurement_from_something_that_is_not_a_state_is_refused():
    with pytest.raises(TargetError):
        extract_measurement({"cpu": 50.0}, ForecastTarget.CPU_UTILIZATION)


def test_extracting_a_sample_from_something_that_is_not_a_state_is_refused():
    with pytest.raises(TargetError):
        extract_sample({"cpu": 50.0}, ForecastTarget.CPU_UTILIZATION)


def test_extracting_a_sample_for_something_that_is_not_a_target_is_refused():
    """Without the gate the bare string matches no `is` comparison and the extractor
    returns `None` — indistinguishable from a state that simply lacks the target, which
    the admission gates then read as missingness rather than as a caller error."""

    with pytest.raises(TargetError):
        extract_sample(fx.cpu_state(fx.T0, 50.0), "cpu_utilization")


# ===================================================================================== #
# forecasters and the replay harness
# ===================================================================================== #


def test_a_point_estimate_over_something_that_is_not_a_window_is_refused():
    """The predictor boundary: without the gate the next line reads `.sample_count` off
    whatever was passed."""

    with pytest.raises(ForecasterError):
        PersistenceForecaster().point_estimate([10.0, 20.0, 30.0])


def test_replaying_no_observations_at_all_is_refused():
    """A replay over nothing produces an empty result that looks like a clean run. The
    gate makes the empty input the caller's error rather than a silent success."""

    with pytest.raises(ReplayError):
        run_replay_evaluation([], ForecastTarget.CPU_UTILIZATION, H1,
                              PersistenceForecaster(), normalization_policy=NPOL)


def test_the_matcher_never_returns_an_actual_at_or_before_the_cutoff():
    """Evidence for the `unreachable-behind-earlier-guard` exclusion of the replay loop's
    second leakage guard. The source calls that guard belt-and-suspenders, and this is
    what measures the belt: the matcher's own eligibility rule already skips every
    observation at or before the cutoff, so no candidate the loop could receive can be
    non-future.

    The tolerance here is deliberately wider than the horizon, which is the only way a
    past observation could otherwise fall inside the match window — and the matcher still
    returns nothing."""

    states = fx.cpu_series_states([10.0, 20.0, 30.0])   # t = 0, 60, 120
    cutoff = states[-1].observed_at                      # t = 120
    forecast_for = fx.at(180.0)
    kind, actual = _match_actual(
        states, cutoff, forecast_for,
        tolerance_seconds=600.0,                         # ten times the horizon
        subject=states[0].subject, target=ForecastTarget.CPU_UTILIZATION,
    )
    assert kind == MATCH_NONE
    assert actual is None
