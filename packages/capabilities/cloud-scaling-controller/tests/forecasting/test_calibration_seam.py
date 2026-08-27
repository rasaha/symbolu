"""Conformance tests for the typed causal calibration seam (seam design §8, tests 3-14).

The seam lets a replay supply uncertainty residuals from a causal prequential bank instead of
the shipped in-window collection. These tests exist to make the *dangerous* cases fail: a bank
that peeks at the future, one bound to a neighbouring arm or another tenant, one that quietly
overrides the frozen configuration, or one that leaves the shipped path perturbed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CalibrationResiduals,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    PrequentialResidualBank,
    ReplayCalibrationProvider,
    ResidualEntry,
    UncertaintyConfig,
    UncertaintyMethod,
    cutoff_sequence_digest,
    forecast_with_evidence,
    is_calibration_origin,
    run_replay_evaluation,
    validate_calibration,
)
from ugence_cloud_scaling_controller.forecasting.evidence import (
    FORECAST_EVIDENCE_SCHEMA_VERSION,
    FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED,
    ForecastServiceError,
)
from ugence_cloud_scaling_controller.forecasting.uncertainty import UncertaintyError

T0 = fx.T0
HZ = ForecastHorizon(60.0)
BANK_CFG = UncertaintyConfig(
    method=UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK,
    requested_coverage=0.8,
    min_calibration_samples=3,
    match_tolerance_seconds=5.0,
)


def _series(values, cadence=60.0, subj=None):
    states = fx.cpu_series_states(values, cadence_seconds=cadence, subj=subj)
    return states, CanonicalCapacitySeries.build(states)


def _calib(subject, *, values=(1.0, -2.0, 3.0, -1.5), cutoff=None, target=ForecastTarget.CPU_UTILIZATION,
           horizon_seconds=60.0, arm="persistence", cap=672,
           earliest=None, latest=None):
    cutoff = cutoff or (T0 + timedelta(seconds=600))
    earliest = earliest or (cutoff - timedelta(seconds=1800))
    latest = latest or (cutoff - timedelta(seconds=900))
    return CalibrationResiduals(
        subject=subject, target=target, horizon_seconds=horizon_seconds, arm_model_id=arm,
        evaluation_cutoff=cutoff, values=tuple(values),
        earliest_origin=earliest, latest_origin=latest,
        bank_cap=cap, config_digest="sha256:cfg", cutoff_sequence_digest="sha256:seq",
    )


# --------------------------------------------------------------------------- shape / digest
def test_calibration_digest_covers_values_and_binding():
    s = fx.subject()
    base = _calib(s)
    assert base.digest() == _calib(s).digest()
    assert base.digest() != _calib(s, values=(1.0, -2.0, 3.0, -1.6)).digest()
    assert base.digest() != _calib(s, arm="harmonic_phase").digest()
    assert base.digest() != _calib(s, target=ForecastTarget.QUEUE_DEPTH).digest()
    assert base.digest() != _calib(s, horizon_seconds=900.0).digest()
    assert base.digest() != _calib(fx.subject(workload_id="wl-2")).digest()


def test_calibration_is_immutable_and_rejects_lists():
    with pytest.raises(UncertaintyError):
        CalibrationResiduals(
            subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION, horizon_seconds=60.0,
            arm_model_id="persistence", evaluation_cutoff=T0 + timedelta(seconds=600),
            values=[1.0, 2.0], earliest_origin=T0, latest_origin=T0 + timedelta(seconds=60),
            bank_cap=672, config_digest="sha256:cfg", cutoff_sequence_digest="sha256:seq",
        )


def test_calibration_rejects_non_finite_and_oversize():
    s = fx.subject()
    with pytest.raises(UncertaintyError):
        _calib(s, values=(1.0, float("nan")))
    with pytest.raises(UncertaintyError):
        _calib(s, values=(1.0, 2.0, 3.0), cap=2)


def test_calibration_rejects_origin_at_or_after_cutoff():
    """6. Causality — an origin that has not resolved by the cutoff cannot be calibration."""
    s = fx.subject()
    cutoff = T0 + timedelta(seconds=600)
    with pytest.raises(UncertaintyError):
        _calib(s, cutoff=cutoff, earliest=cutoff - timedelta(seconds=60), latest=cutoff)
    with pytest.raises(UncertaintyError):
        _calib(s, cutoff=cutoff, earliest=cutoff, latest=cutoff + timedelta(seconds=60))


# ------------------------------------------------------------------------------- binding (7)
@pytest.mark.parametrize("mutation", [
    {"arm": "seasonal_naive"},
    {"target": ForecastTarget.QUEUE_DEPTH},
    {"horizon_seconds": 900.0},
])
def test_cross_binding_calibration_is_rejected(mutation):
    s = fx.subject()
    cutoff = T0 + timedelta(seconds=600)
    cal = _calib(s, cutoff=cutoff, **mutation)
    with pytest.raises(UncertaintyError):
        validate_calibration(cal, subject=s, target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                             arm_model_id="persistence", cutoff=cutoff, config=BANK_CFG)


def test_cross_subject_calibration_is_rejected():
    cutoff = T0 + timedelta(seconds=600)
    cal = _calib(fx.subject(workload_id="wl-other"), cutoff=cutoff)
    with pytest.raises(UncertaintyError):
        validate_calibration(cal, subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION,
                             horizon=HZ, arm_model_id="persistence", cutoff=cutoff, config=BANK_CFG)


def test_cutoff_mismatch_is_rejected():
    s = fx.subject()
    cal = _calib(s, cutoff=T0 + timedelta(seconds=600))
    with pytest.raises(UncertaintyError):
        validate_calibration(cal, subject=s, target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                             arm_model_id="persistence", cutoff=T0 + timedelta(seconds=1200),
                             config=BANK_CFG)


# ------------------------------------------------------------------------ config authority (9)
def test_calibration_cannot_be_used_under_the_legacy_method():
    s = fx.subject()
    cutoff = T0 + timedelta(seconds=600)
    cal = _calib(s, cutoff=cutoff)
    with pytest.raises(UncertaintyError):
        validate_calibration(cal, subject=s, target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                             arm_model_id="persistence", cutoff=cutoff,
                             config=UncertaintyConfig())


def test_config_values_come_from_config_not_calibration():
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    s = series.subject
    cal = _calib(s, cutoff=cutoff, values=(1.0, -1.0, 2.0, -2.0, 0.5))
    strict = UncertaintyConfig(method=UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK,
                               requested_coverage=0.5, min_calibration_samples=99,
                               match_tolerance_seconds=5.0)
    ev = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                                PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                uncertainty_config=strict, calibration=cal)
    # min_calibration_samples=99 is honoured despite 5 supplied residuals: the config wins.
    assert ev.forecast.status == "abstained"
    assert ev.forecast.abstention_reason.value == "insufficient_calibration_history"


# ------------------------------------------------------- evidence binding + schema versioning
def _calibrated_evidence():
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    cal = _calib(series.subject, cutoff=cutoff, values=(1.0, -1.0, 2.0, -2.0, 0.5))
    ev = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                                PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                uncertainty_config=BANK_CFG, calibration=cal)
    return ev, cal


def test_calibrated_evidence_carries_matching_digests_and_new_schema():
    ev, cal = _calibrated_evidence()
    assert ev.evidence_schema_version == FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED
    assert ev.calibration_input_digest == cal.digest()
    assert ev.forecast.uncertainty.calibration_input_digest == cal.digest()
    assert ev.to_canonical_dict()["calibration_input_digest"] == cal.digest()
    assert ev.forecast.uncertainty.method == "empirical_prequential_residual_bank"


def test_mismatched_evidence_and_interval_digests_fail_closed():
    ev, _ = _calibrated_evidence()
    from dataclasses import replace
    with pytest.raises(ForecastServiceError):
        replace(ev, calibration_input_digest="sha256:different")


def test_calibrated_field_forbidden_on_legacy_schema_version():
    ev, _ = _calibrated_evidence()
    from dataclasses import replace
    with pytest.raises(ForecastServiceError):
        replace(ev, evidence_schema_version=FORECAST_EVIDENCE_SCHEMA_VERSION)


def test_unsupported_schema_version_fails_closed():
    ev, _ = _calibrated_evidence()
    from dataclasses import replace
    with pytest.raises(ForecastServiceError):
        replace(ev, evidence_schema_version="capacity-forecast-evidence-99")


# ----------------------------------------------------------------- no-provider invariance (3)
def test_no_calibration_leaves_evidence_byte_identical():
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    cfg = UncertaintyConfig(min_calibration_samples=2, match_tolerance_seconds=5.0)
    a = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                               PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                               uncertainty_config=cfg)
    b = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                               PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                               uncertainty_config=cfg, calibration=None)
    assert a.digest() == b.digest()
    assert a.evidence_schema_version == FORECAST_EVIDENCE_SCHEMA_VERSION
    assert a.calibration_input_digest is None
    assert "calibration_input_digest" not in a.to_canonical_dict()


def test_no_provider_replay_is_unchanged():
    states, _ = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    kw = dict(normalization_policy=fx.cpu_norm_policy(),
              uncertainty_config=UncertaintyConfig(min_calibration_samples=2,
                                                   match_tolerance_seconds=5.0))
    a = run_replay_evaluation(states, ForecastTarget.CPU_UTILIZATION, HZ,
                              PersistenceForecaster(), **kw)
    b = run_replay_evaluation(states, ForecastTarget.CPU_UTILIZATION, HZ,
                              PersistenceForecaster(), calibration_provider=None, **kw)
    assert [e.digest() for e in a.evidences] == [e.digest() for e in b.evidences]
    assert a.aggregate.digest() == b.aggregate.digest()


# --------------------------------------------------------------- point invariance (5) & mixing (4)
def test_point_estimate_is_identical_with_and_without_calibration():
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    plain = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                                   PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                   uncertainty_config=UncertaintyConfig(min_calibration_samples=2,
                                                                        match_tolerance_seconds=5.0))
    cal_ev, _ = _calibrated_evidence()
    assert plain.forecast.point_estimate == cal_ev.forecast.point_estimate == 15.0


def test_supplied_residuals_are_not_mixed_with_in_window_collection():
    """4. Provider isolation — the interval must come only from the supplied collection."""
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    values = (1.0, -1.0, 2.0, -2.0, 0.5)
    cal = _calib(series.subject, cutoff=cutoff, values=values)
    ev = forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                                PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                uncertainty_config=BANK_CFG, calibration=cal)
    iv = ev.forecast.uncertainty
    assert iv.calibration_sample_count == len(values)
    # Endpoints reproduce the supplied residuals exactly (point + empirical quantiles).
    from ugence_cloud_scaling_controller.forecasting import interval_from_residuals
    direct = interval_from_residuals(ev.forecast.point_estimate, values, BANK_CFG,
                                     calibration_input_digest=cal.digest())
    assert (iv.lower, iv.upper) == (direct.lower, direct.upper)


def test_rolling_origin_is_not_called_when_calibration_is_supplied(monkeypatch):
    import ugence_cloud_scaling_controller.forecasting.evidence as EV

    def _boom(*a, **k):  # pragma: no cover - must not run
        raise AssertionError("compute_uncertainty must not run on the calibrated path")

    monkeypatch.setattr(EV, "compute_uncertainty", _boom)
    ev, _ = _calibrated_evidence()
    assert ev.forecast.uncertainty.available


# ------------------------------------------------------------------------ bank order/cap (8)
def _entry(origin_s, actual_s, value):
    return ResidualEntry(origin=T0 + timedelta(seconds=origin_s),
                         actual_event_time=T0 + timedelta(seconds=actual_s), value=value)


def test_bank_eviction_is_oldest_origin_first():
    bank = PrequentialResidualBank(bank_cap=3)
    for i in range(6):
        bank.admit(_entry(i * 900, i * 900 + 60, float(i)))
    got = bank.eligible_at(T0 + timedelta(seconds=10_000))
    assert [e.value for e in got] == [3.0, 4.0, 5.0]


def test_bank_result_is_independent_of_insertion_order():
    a = PrequentialResidualBank(bank_cap=10)
    b = PrequentialResidualBank(bank_cap=10)
    entries = [_entry(i * 900, i * 900 + 60, float(i)) for i in range(5)]
    for e in entries:
        a.admit(e)
    for e in reversed(entries):
        b.admit(e)
    at = T0 + timedelta(seconds=10_000)
    assert [e.value for e in a.eligible_at(at)] == [e.value for e in b.eligible_at(at)]


def test_bank_colliding_origins_are_broken_deterministically():
    bank = PrequentialResidualBank(bank_cap=10)
    bank.admit(_entry(900, 1000, 5.0))
    bank.admit(_entry(900, 960, 7.0))
    got = bank.eligible_at(T0 + timedelta(seconds=5000))
    assert [(e.actual_event_time.second, e.value) for e in got] == [(0, 7.0), (40, 5.0)]


def test_bank_excludes_unobservable_actuals():
    """13. Negative control — a residual whose actual is still in the future is excluded."""
    bank = PrequentialResidualBank(bank_cap=10)
    bank.admit(_entry(900, 1800, 1.0))    # resolved by t=1800
    bank.admit(_entry(1200, 100_000, 2.0))  # resolves far in the future
    got = bank.eligible_at(T0 + timedelta(seconds=3600))
    assert [e.value for e in got] == [1.0]


def test_bank_excludes_origins_at_or_after_the_cutoff():
    bank = PrequentialResidualBank(bank_cap=10)
    bank.admit(_entry(900, 960, 1.0))
    bank.admit(_entry(3600, 3660, 2.0))
    assert [e.value for e in bank.eligible_at(T0 + timedelta(seconds=3600))] == [1.0]


def test_residual_entry_requires_actual_after_origin():
    with pytest.raises(UncertaintyError):
        _entry(900, 900, 1.0)
    with pytest.raises(UncertaintyError):
        _entry(900, 800, 1.0)


def test_calibration_origin_schedule_is_quarter_hourly():
    assert is_calibration_origin(datetime(2026, 1, 1, 3, 15, 0, tzinfo=timezone.utc))
    assert is_calibration_origin(datetime(2026, 1, 1, 3, 45, 0, tzinfo=timezone.utc))
    assert not is_calibration_origin(datetime(2026, 1, 1, 3, 16, 0, tzinfo=timezone.utc))
    assert not is_calibration_origin(datetime(2026, 1, 1, 3, 15, 30, tzinfo=timezone.utc))


# ------------------------------------------------------------------ provider / fairness (14)
def _provider(cutoffs, cap=672):
    return ReplayCalibrationProvider(config=BANK_CFG,
                                     cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
                                     bank_cap=cap, require_calibration_origin=False)


def test_provider_declines_off_schedule_origins_when_required():
    p = ReplayCalibrationProvider(config=BANK_CFG, cutoff_sequence_digest="sha256:seq")
    kw = dict(subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
              arm_model_id="persistence", actual_event_time=T0 + timedelta(seconds=1000),
              residual=1.0)
    assert p.observe(origin=datetime(2026, 1, 1, 0, 15, 0, tzinfo=timezone.utc), **kw) is True
    assert p.observe(origin=datetime(2026, 1, 1, 0, 16, 0, tzinfo=timezone.utc), **kw) is False


def test_provider_never_shares_residuals_across_arms():
    p = _provider([T0])
    common = dict(subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                  actual_event_time=T0 + timedelta(seconds=120), residual=4.0)
    p.observe(arm_model_id="persistence", origin=T0 + timedelta(seconds=60), **common)
    at = T0 + timedelta(seconds=600)
    assert p.calibration_for(fx.subject(), ForecastTarget.CPU_UTILIZATION, HZ, "persistence", at) is not None
    assert p.calibration_for(fx.subject(), ForecastTarget.CPU_UTILIZATION, HZ, "harmonic_phase", at) is None


def test_provider_calibration_round_trips_validation():
    p = _provider([T0])
    s = fx.subject()
    for i in range(4):
        p.observe(subject=s, target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                  arm_model_id="persistence", origin=T0 + timedelta(seconds=60 * (i + 1)),
                  actual_event_time=T0 + timedelta(seconds=60 * (i + 1) + 30), residual=float(i))
    at = T0 + timedelta(seconds=600)
    cal = p.calibration_for(s, ForecastTarget.CPU_UTILIZATION, HZ, "persistence", at)
    assert cal.count == 4 and cal.bank_cap == 672
    assert validate_calibration(cal, subject=s, target=ForecastTarget.CPU_UTILIZATION, horizon=HZ,
                                arm_model_id="persistence", cutoff=at, config=BANK_CFG) == cal.digest()


def test_cutoff_sequence_digest_is_order_sensitive_and_deterministic():
    a = [T0, T0 + timedelta(seconds=900), T0 + timedelta(seconds=1800)]
    assert cutoff_sequence_digest(a) == cutoff_sequence_digest(list(a))
    assert cutoff_sequence_digest(a) != cutoff_sequence_digest(list(reversed(a)))


# ------------------------------------------------------------------ replay determinism (11)
def _replay_with_provider(states, cutoffs):
    p = _provider(cutoffs)
    return run_replay_evaluation(
        states, ForecastTarget.CPU_UTILIZATION, HZ, PersistenceForecaster(),
        normalization_policy=fx.cpu_norm_policy(), cutoffs=cutoffs, uncertainty_config=BANK_CFG,
        calibration_provider=p,
    ), p


def test_replay_with_provider_is_deterministic_and_causal():
    states, _ = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0, 14.5, 16.0])
    cutoffs = [s.observed_at for s in states]
    r1, p1 = _replay_with_provider(states, cutoffs)
    r2, p2 = _replay_with_provider(states, cutoffs)
    assert [e.digest() for e in r1.evidences] == [e.digest() for e in r2.evidences]
    assert r1.aggregate.digest() == r2.aggregate.digest()
    assert p1.bank_sizes() == p2.bank_sizes()

    # The first cutoffs cannot be calibrated: no residual has resolved yet.
    schemas = [e.evidence_schema_version for e in r1.evidences]
    assert schemas[0] == FORECAST_EVIDENCE_SCHEMA_VERSION
    assert FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED in schemas


def test_bank_never_calibrates_its_own_origin():
    states, _ = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0, 14.5, 16.0])
    cutoffs = [s.observed_at for s in states]
    result, provider = _replay_with_provider(states, cutoffs)
    for ev in result.evidences:
        cal = provider.calibration_for(ev.forecast.subject, ev.forecast.target, HZ,
                                       "persistence", ev.forecast.forecast_cutoff)
        if cal is not None:
            assert cal.latest_origin < ev.forecast.forecast_cutoff


# ------------------------------------------------------- adversarial: config/method mismatch
def _zero_width_calibration(series, cutoff, arm="persistence"):
    """Residuals that would collapse the interval to zero width if wrongly admitted."""
    return _calib(series.subject, cutoff=cutoff, values=(0.0,) * 5, arm=arm)


@pytest.mark.parametrize("method", [UncertaintyMethod.EMPIRICAL_ROLLING_ORIGIN_RESIDUAL,
                                    UncertaintyMethod.NONE])
def test_supplied_calibration_is_refused_unless_the_config_declares_the_bank(method):
    """A bank may not be smuggled in under a config that asked for something else.

    The residuals here are all zero, so admitting them would report a zero-width interval —
    maximum apparent confidence from calibration the configuration never authorised.
    """
    states, series = _series([10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.5, 15.0])
    cutoff = states[-1].observed_at
    cfg = UncertaintyConfig(method=method, min_calibration_samples=2,
                            match_tolerance_seconds=5.0)
    with pytest.raises(UncertaintyError):
        forecast_with_evidence(series, ForecastTarget.CPU_UTILIZATION, cutoff, HZ,
                               PersistenceForecaster(),
                               normalization_policy=fx.cpu_norm_policy(),
                               uncertainty_config=cfg,
                               calibration=_zero_width_calibration(series, cutoff))
