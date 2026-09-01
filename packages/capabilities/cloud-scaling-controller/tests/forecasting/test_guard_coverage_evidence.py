"""Isolating tests for the guard sweep — `forecasting/evidence.py`.

Written for phase 2 of the shared-engine adoption. This module is the controlled service
path: it turns a series into either a forecast or a *typed abstention*, and binds the
result to an evidence record that discloses every policy digest behind it. Two kinds of
decision point live here, and neutralising either is dangerous in a different way.

The **admission gates** decide forecast-or-abstain. If one stops refusing, the controller
does not fail — it produces a confident forecast from history it had already judged
inadmissible (too short, too stale, too gappy, out of domain), and the abstention that
should have appeared in the evidence never does.

The **posture gates** on `CapacityForecastEvidence` assert that this package is
advisory-only, shadow-only, and executes nothing. They are the machine-readable half of
the boundary the whole controller is built on; a record that could carry
`actuation_performed=True` is a record claiming an authority the package does not have.

Each test isolates one gate, asserting the typed half of the refusal
(`ForecastServiceError`) or the typed `AbstentionReason` — never a message substring. An
abstention is not a refusal, so its tests assert the enum member the gate selects: that is
the attribution, and asserting only "it abstained" would attribute nothing.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacityState,
    Measurement,
    NormalizationMethod,
    NormalizationPolicy,
    Unit,
    WorkloadState,
)
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    AdmissionPolicy,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    ForecastValueSpace,
    PersistenceForecaster,
    forecast_from_observations,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.evidence import (
    CapacityForecastEvidence,
    ForecastServiceError,
)
from ugence_cloud_scaling_controller.forecasting.series import SeriesError

H1 = ForecastHorizon(60.0)
NPOL = fx.cpu_norm_policy()


def _series(values=(10.0, 20.0, 30.0), **kw):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(list(values), **kw))


def _evidence(series=None, **kw):
    s = series or _series()
    kw.setdefault("normalization_policy", NPOL)
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1, PersistenceForecaster(), **kw
    )


def _abstains(reason, series=None, **kw):
    ev = _evidence(series, **kw)
    assert ev.forecast.is_abstained
    assert ev.forecast.abstention_reason is reason
    return ev


# ===================================================================================== #
# AdmissionPolicy — the disclosed thresholds
# ===================================================================================== #


def test_a_policy_without_an_identifier_is_refused():
    """The policy id is what the evidence digest discloses; an empty one makes the
    disclosed thresholds untraceable to a named policy."""

    with pytest.raises(ForecastServiceError):
        AdmissionPolicy(policy_id="")


def test_a_min_history_that_is_a_bool_is_refused():
    """`True` is an `int` in Python: without the bool half of the gate it becomes a
    one-observation minimum, and the strictest admission threshold silently vanishes."""

    with pytest.raises(ForecastServiceError):
        AdmissionPolicy(min_history=True)


def test_a_negative_staleness_bound_is_refused():
    """Probes both halves of the optional-staleness gate: the outer `is not None`
    admission and the range check inside it. Neutralising either admits the negative
    bound, which no observation can ever satisfy — every forecast would abstain as stale
    and the controller would go permanently silent rather than fail loudly."""

    with pytest.raises(ForecastServiceError):
        AdmissionPolicy(max_staleness_seconds=-1.0)


def test_a_missing_fraction_outside_the_unit_interval_is_refused():
    with pytest.raises(ForecastServiceError):
        AdmissionPolicy(max_missing_fraction=1.5)


def test_an_irregular_gap_allowance_that_is_a_bool_is_refused():
    with pytest.raises(ForecastServiceError):
        AdmissionPolicy(max_irregular_gaps=True)


# ===================================================================================== #
# type gates on the service path
# ===================================================================================== #


def test_a_series_that_is_not_a_canonical_series_is_refused():
    with pytest.raises(ForecastServiceError):
        forecast_with_evidence("not a series", ForecastTarget.CPU_UTILIZATION,
                               fx.T0, H1, PersistenceForecaster(), normalization_policy=NPOL)


def test_a_forecaster_that_is_not_a_baseline_forecaster_is_refused():
    s = _series()
    with pytest.raises(ForecastServiceError):
        forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                               "persistence", normalization_policy=NPOL)


def test_a_forecast_space_that_is_not_a_value_space_is_refused():
    s = _series()
    with pytest.raises(ForecastServiceError):
        forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                               PersistenceForecaster(), normalization_policy=NPOL,
                               forecast_space="normalized")


def test_a_normalization_policy_that_is_not_a_policy_is_refused():
    """`None` is admissible here and abstains, so only a non-policy object can probe the
    type gate; without it the next line reads `.method_by_signal` off a string."""

    with pytest.raises(ForecastServiceError):
        _evidence(normalization_policy="cpu-p1")


def test_an_evidence_produced_at_that_is_not_a_datetime_is_refused():
    """The caller-supplied trusted timestamp: it is excluded from the identity digest, so
    nothing downstream would ever notice a string sitting in that field."""

    with pytest.raises(ForecastServiceError):
        _evidence(evidence_produced_at="2026-01-01")


# ===================================================================================== #
# admission gates — each abstains with its own typed reason
# ===================================================================================== #


def test_history_shorter_than_the_effective_minimum_abstains_as_insufficient_history():
    s = _series([10.0, 20.0])
    _abstains(AbstentionReason.INSUFFICIENT_HISTORY, s,
              admission_policy=AdmissionPolicy(min_history=5))


def test_a_target_with_no_normalization_signal_cannot_be_forecast_in_normalized_space():
    """RUNNING_REPLICAS is projected without conversion — it has no normalization method
    at all, so a NORMALIZED request for it is out of scope rather than misconfigured."""

    states = [
        CanonicalCapacityState(subject=fx.subject(), observed_at=fx.at(60.0 * i),
                               capacity=CapacityState(running_replicas=4 + i))
        for i in range(3)
    ]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(
        s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, H1, PersistenceForecaster(),
        normalization_policy=NPOL, forecast_space=ForecastValueSpace.NORMALIZED,
    )
    assert ev.forecast.abstention_reason is AbstentionReason.UNSUPPORTED_TARGET


def _queue_series(values):
    states = [
        CanonicalCapacityState(
            subject=fx.subject(), observed_at=fx.at(60.0 * i),
            workload=WorkloadState(queue_depth=Measurement(float(v), Unit.COUNT)),
        )
        for i, v in enumerate(values)
    ]
    return CanonicalCapacitySeries.build(states)


def test_a_normalization_that_fails_only_on_a_later_sample_abstains_as_inconsistent_unit():
    """The except-arm around the working window. The applicability probe one step earlier
    normalizes only the FIRST sample, so a policy that works there and fails on a later
    one is the only input that reaches this arm. Delete it and a data-quality problem
    escapes the service path as a raw window exception instead of a typed abstention —
    the one outcome this boundary exists to prevent."""

    policy = NormalizationPolicy(
        policy_id="queue-p1",
        method_by_signal={"queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY},
        thresholds={"queue_depth": 2.0},
        clamp=False,  # out-of-range normalization fails closed instead of clamping
    )
    s = _queue_series([1.0, 5.0, 5.0])  # 1/2 = 0.5 admissible; 5/2 = 2.5 is not
    ev = forecast_with_evidence(
        s, ForecastTarget.QUEUE_DEPTH, s.end_event_time, H1, PersistenceForecaster(),
        normalization_policy=policy, forecast_space=ForecastValueSpace.NORMALIZED,
    )
    assert ev.forecast.abstention_reason is AbstentionReason.INCONSISTENT_UNIT


class _NoPointForecaster(PersistenceForecaster):
    """Admissible in every respect, but declines to predict — the case the gate exists
    for. A real forecaster returns None when its own preconditions are unmet."""

    model_id = "no-point-test"

    def _predict(self, event_times, values, forecast_for):
        return None


def test_a_forecaster_that_declines_to_predict_abstains_as_insufficient_history():
    """Without the gate the next line asks `math.isfinite(None)` — a TypeError from the
    arithmetic rather than the typed abstention a caller can act on."""

    s = _series()
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                                _NoPointForecaster(), normalization_policy=NPOL)
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_HISTORY


# ===================================================================================== #
# the advisory/shadow posture — the machine-readable half of the boundary
# ===================================================================================== #


@pytest.mark.parametrize(
    "override",
    [
        {"advisory_only": False},
        {"shadow_only": False},
        {"actuation_performed": True},
        {"authority_class": "EXECUTIVE"},
        {"execution_capability": "DIRECT"},
    ],
)
def test_evidence_cannot_claim_an_authority_this_package_does_not_have(override):
    """One override per posture gate. Each is a *record-level* claim: the evidence is what
    a downstream reader consults to decide whether this package may be trusted to have
    acted, and every one of these fields must read the same way on every record ever
    produced. `advisory_only` and `shadow_only` share a gate, so the two overrides below
    probe its halves separately."""

    ev = _evidence()
    with pytest.raises(ForecastServiceError):
        dataclasses.replace(ev, **override)


def test_the_evidence_dict_carries_the_identity_digest_by_default():
    """`include_digest` is a decision point, not a formatting flag: neutralised, every
    default serialization loses the identity a reader would verify against, and the dict
    still looks complete."""

    ev = _evidence()
    assert ev.to_canonical_dict()["evidence_digest"] == ev.digest()
    assert "evidence_digest" not in ev.to_canonical_dict(include_digest=False)


# ===================================================================================== #
# the observation-admission boundary
# ===================================================================================== #


def _from_obs(observations, **kw):
    kw.setdefault("normalization_policy", NPOL)
    return forecast_from_observations(
        observations, ForecastTarget.CPU_UTILIZATION, fx.at(120.0), H1,
        PersistenceForecaster(), **kw
    )


def test_forecasting_from_no_observations_at_all_is_refused():
    """Not an abstention: there is no series to bind evidence to, so there is nothing to
    disclose. Without the gate the empty series raises a `SeriesError` from one frame
    deeper, which this boundary's contract does not mention."""

    with pytest.raises(ForecastServiceError):
        _from_obs([])


def test_a_series_failure_outside_the_mapped_data_quality_set_is_not_swallowed():
    """The mapping covers data-quality failures only. A naive timestamp is a programming
    error, and turning it into a typed abstention would hide a bug behind a record that
    says the controller merely declined to forecast. Neutralise the gate and it does
    exactly that."""

    naive = datetime(2026, 1, 1, 0, 0, 0)  # no tzinfo
    states = fx.cpu_series_states([10.0, 20.0, 30.0])
    broken = [dataclasses.replace(states[0], observed_at=naive), *states[1:]]
    with pytest.raises(SeriesError):
        _from_obs(broken)


def test_a_mapped_data_quality_failure_becomes_a_typed_abstention():
    """The other side of the same gate: an out-of-order event time IS in the mapped set,
    so it produces evidence rather than an exception."""

    states = fx.cpu_series_states([10.0, 20.0, 30.0])
    out_of_order = [states[0], states[2], states[1]]
    ev = _from_obs(out_of_order)
    assert ev.forecast.abstention_reason is AbstentionReason.INVALID_TIME_ORDER


# ===================================================================================== #
# evidence for the two gates the sweep cannot reach through a supported path
# ===================================================================================== #


def test_a_non_finite_observation_cannot_be_built_at_all():
    """Evidence for the `unreachable-behind-earlier-guard` exclusion of the non-finite
    sweep over `probe.values`. `Measurement.__post_init__` refuses a non-finite value, and
    the replica count is validated as an `int`, so no non-finite number can reach a probe
    window. The comment in the source calls the guard defensive; this measures that."""

    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(Exception) as exc:
            Measurement(bad, Unit.PERCENT)
        assert "finite" in str(exc.value)


def test_an_out_of_domain_observation_cannot_be_built_at_all():
    """Evidence for the `unreachable-behind-earlier-guard` exclusion of the per-sample
    domain sweep. `domain_for` reads the SAME Phase-1 `unit_domain` authority that
    `Measurement` enforces at construction — bounds and integer semantics alike — so a
    raw sample that is out of its domain cannot be constructed in the first place."""

    with pytest.raises(Exception) as too_high:
        Measurement(150.0, Unit.PERCENT)          # upper bound
    assert "100" in str(too_high.value)
    with pytest.raises(Exception) as negative:
        Measurement(-1.0, Unit.PERCENT)           # lower bound
    assert "0" in str(negative.value)
    with pytest.raises(Exception) as fractional:
        Measurement(3.5, Unit.COUNT)              # integer semantics
    assert "integer" in str(fractional.value)
