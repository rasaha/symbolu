"""Synthetic end-to-end replay for the four-arm evaluation (no telemetry).

These fixtures exist to prove the evaluation can reach **any** of its permitted conclusions
from data alone — H winning, N winning, T killing H's incremental value, or nothing clearing
its gates — and that the causal machinery rejects the contaminations that would otherwise
manufacture a win.

Nothing here ratifies a third baseline. A synthetic pass makes the replay executable in
principle; only the authorized replay on representative data can ratify anything.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

import fc_helpers as fx
import synthetic_scenarios as S
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    CalibrationResiduals,
    CanonicalCapacitySeries,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    HarmonicPhaseForecaster,
    PrequentialResidualBank,
    ReplayCalibrationProvider,
    ResidualEntry,
    build_input_window,
    cutoff_sequence_digest,
    validate_calibration,
)
from ugence_cloud_scaling_controller.forecasting.evaluation import EvaluationStatus
from ugence_cloud_scaling_controller.forecasting.evidence import (
    FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED,
)
from ugence_cloud_scaling_controller.forecasting.uncertainty import UncertaintyError

T0 = S.T0


# ------------------------------------------------------------ 1-4: outcome-neutral arms
@pytest.fixture(scope="module")
def outcomes():
    """Paired MAE per arm for the four decisive data shapes (computed once)."""
    out = {}
    shapes = {
        "harmonic_plus_trend": S.harmonic_with_trend(),
        "exact_seasonality": S.exact_repeating([10.0 + (i % 7) * 3.0 for i in range(60)]),
        "trend_only": S.trend_only(),
        "non_periodic": S.non_periodic(),
    }
    for name, fn in shapes.items():
        states = S.build_states(fn)
        cutoffs = S.aligned_cutoffs(states)
        results = S.run_all_arms(states, cutoffs)
        out[name] = (S.paired_mae(results), S.paired_count(results))
    return out


def test_1_harmonic_plus_trend_lets_h_win(outcomes):
    mae, paired = outcomes["harmonic_plus_trend"]
    assert paired >= 10
    assert mae["H"] <= 0.90 * mae["P"]
    assert mae["H"] <= 0.95 * mae["T"]
    assert mae["H"] <= 0.97 * mae["N"]


def test_2_exact_seasonality_lets_n_tie_or_beat_h(outcomes):
    """The control that can retire the candidate must actually be able to."""
    mae, paired = outcomes["exact_seasonality"]
    assert paired >= 10
    assert mae["N"] <= mae["H"]
    assert not (mae["H"] <= 0.97 * mae["N"])


def test_3_trend_only_kills_h_incremental_value(outcomes):
    """H may not be credited for a win its own trend term produced."""
    mae, paired = outcomes["trend_only"]
    assert paired >= 10
    assert mae["T"] == pytest.approx(mae["H"], abs=1e-9)
    assert not (mae["H"] <= 0.95 * mae["T"])


def test_4_non_periodic_data_fails_h_gates(outcomes):
    mae, paired = outcomes["non_periodic"]
    assert paired >= 10
    assert not (mae["H"] <= 0.95 * mae["T"])


def test_outcome_neutrality_every_conclusion_is_reachable(outcomes):
    """H, N, T and 'no candidate' must each be attainable from data alone."""
    h_wins = outcomes["harmonic_plus_trend"][0]
    n_wins = outcomes["exact_seasonality"][0]
    t_kills = outcomes["trend_only"][0]
    none_wins = outcomes["non_periodic"][0]
    assert h_wins["H"] < min(h_wins["P"], h_wins["T"], h_wins["N"])
    assert n_wins["N"] < min(n_wins["P"], n_wins["T"], n_wins["H"])
    assert t_kills["T"] <= t_kills["H"]
    assert not (none_wins["H"] <= 0.95 * none_wins["T"])


# ------------------------------------------------- 5-10: sampling structure and abstentions
def _h_only(states, cutoffs):
    return S.run_arm(states, cutoffs, HarmonicPhaseForecaster(S.SCALED_H))


def _few_cutoffs(states, n=3):
    return S.aligned_cutoffs(states, stride=1800.0)[:n]


def test_5_irregular_but_resolvable_sampling_still_forecasts():
    """Jitter within the ratified gap bounds must not be treated as unresolvable."""
    base = S.harmonic_with_trend()

    def jittered(t: datetime) -> float:
        return base(t)

    # Drop one sample every 10 minutes: gaps become 120 s, exactly at the p95 ceiling.
    states = S.build_states(jittered, drop_indices=tuple(range(9, 601, 10)))
    result = _h_only(states, _few_cutoffs(states))
    assert any(ev.forecast.status == "forecast" for ev in result.evidences)


def test_6_insufficient_cycle_coverage_is_reported_end_to_end():
    states = S.build_states(S.harmonic_with_trend(), periods=10)
    # Cut the history to a single period before the first cutoff.
    short = [s for s in states if s.observed_at <= T0 + timedelta(seconds=S.PERIOD)]
    cutoffs = [short[-1].observed_at]
    result = _h_only(short, cutoffs)
    assert S.abstention_reasons(result) == {"insufficient_cycle_coverage": 1}


def test_7_excessive_p95_gap_is_reported_end_to_end():
    states = S.build_states(S.harmonic_with_trend(), cadence=300.0)
    result = _h_only(states, _few_cutoffs(states, 2))
    assert set(S.abstention_reasons(result)) <= {"period_not_resolvable",
                                                 "insufficient_cycle_coverage"}
    assert "period_not_resolvable" in S.abstention_reasons(result)


def test_8_excessive_maximum_gap_is_reported_end_to_end():
    # A 17-minute outage: one phase bin lost (coverage still passes), max-gap rule fires.
    states = S.build_states(S.harmonic_with_trend(), drop_indices=tuple(range(430, 446)))
    result = _h_only(states, _few_cutoffs(states, 2))
    assert "period_not_resolvable" in S.abstention_reasons(result)


def test_9_deficient_phase_bin_coverage_is_reported_end_to_end():
    states = S.build_states(
        S.harmonic_with_trend(),
        keep=lambda t: (t.timestamp() % S.PERIOD) < S.PERIOD / 3,
    )
    result = _h_only(states, _few_cutoffs(states, 2))
    assert "insufficient_cycle_coverage" in S.abstention_reasons(result)


def test_10_rank_and_conditioning_failure_declines():
    """Every sample at one phase cannot identify a harmonic, however much data there is."""
    states = S.build_states(lambda t: 50.0, cadence=S.PERIOD, periods=60)
    f = HarmonicPhaseForecaster({**S.SCALED_H, "max_p95_gap_seconds": 1e9,
                                 "max_gap_seconds": 1e9, "min_occupied_bins": 1,
                                 "min_days_with_coverage": 1})
    times = [s.observed_at for s in states]
    assert f.resolvability_failure(times) is None
    assert f.predict_from(times, [50.0] * len(times), times[-1] + timedelta(seconds=60)) is None

    # Sampling rules passed, so the decline must be attributed to rank/conditioning.
    series = CanonicalCapacitySeries.build(states)
    window = build_input_window(
        series, ForecastTarget.CPU_UTILIZATION, states[-1].observed_at,
        ForecastHorizon(60.0),
        FeatureConfig(lookback_seconds=61 * S.PERIOD, expected_cadence_seconds=S.PERIOD),
    )
    assert f.point_estimate(window) is None
    assert f.decline_reason(window) is AbstentionReason.PERIOD_NOT_RESOLVABLE


# ------------------------------------------------------------- 11: regime breaks retained
def test_11_regime_break_is_retained_not_excluded():
    """No regime-break exclusion exists (ruling 1): the hard origins stay in the run."""
    break_at = T0 + timedelta(seconds=8 * S.PERIOD)
    base = S.harmonic_with_trend(level=30.0)
    shifted = S.with_level_shift(base, break_at, delta=20.0)
    states = S.build_states(shifted)
    cutoffs = S.aligned_cutoffs(states, stride=1800.0)
    spanning = [c for c in cutoffs if break_at - timedelta(seconds=S.LOOKBACK) <= c]
    assert spanning, "the fixture must contain cutoffs whose window spans the break"

    results = S.run_all_arms(states, cutoffs)
    evaluated = {
        r.forecast_cutoff
        for r in results["H"].records
        if r.status is EvaluationStatus.EVALUATED
    }
    # Every origin whose window spans the break is still scored — none is dropped.
    assert set(spanning) & evaluated == set(spanning) & {
        r.forecast_cutoff for r in results["P"].records
        if r.status is EvaluationStatus.EVALUATED
    }
    assert len(evaluated) >= 4

    # And the break really is hard: H's error over the break exceeds its clean-data error.
    clean = S.paired_mae(S.run_all_arms(S.build_states(base), cutoffs))
    broken = S.paired_mae(results)
    assert broken["H"] > clean["H"]


# ------------------------------------- 12-13: contaminated / mis-bound calibration rejected
def _bank_states_and_cutoffs():
    states = S.build_states(S.harmonic_with_trend())
    return states, S.aligned_cutoffs(states)


def test_12_future_contaminated_calibration_is_rejected():
    """The negative control: a residual that resolves after the cutoff must never be used.

    Contamination of this kind *narrows* intervals and flatters coverage — the failure mode
    that looks like success — so the bank filters on the actual's observability, not on the
    origin alone.
    """
    bank = PrequentialResidualBank(bank_cap=672)
    cutoff = T0 + timedelta(seconds=7 * S.PERIOD)
    # Honest residuals: large spread, resolved well before the cutoff.
    for i in range(1, 9):
        bank.admit(ResidualEntry(origin=cutoff - timedelta(seconds=900 * (i + 1)),
                                 actual_event_time=cutoff - timedelta(seconds=900 * i),
                                 value=(-1.0) ** i * 10.0 * i))
    honest = bank.eligible_at(cutoff)
    # A "perfect" future residual that would shrink the interval if admitted.
    bank.admit(ResidualEntry(origin=cutoff - timedelta(seconds=60),
                             actual_event_time=cutoff + timedelta(seconds=86400),
                             value=0.0))
    after = bank.eligible_at(cutoff)
    assert [e.value for e in after] == [e.value for e in honest]
    assert all(e.actual_event_time <= cutoff for e in after)


def test_12b_contaminated_calibration_object_cannot_be_constructed():
    cutoff = T0 + timedelta(seconds=7 * S.PERIOD)
    with pytest.raises(UncertaintyError):
        CalibrationResiduals(
            subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION, horizon_seconds=900.0,
            arm_model_id="harmonic_phase", evaluation_cutoff=cutoff,
            values=(1.0, 2.0, 3.0, 4.0, 5.0),
            earliest_origin=cutoff - timedelta(seconds=900),
            latest_origin=cutoff + timedelta(seconds=900),  # resolves in the future
            bank_cap=672, config_digest="sha256:cfg", cutoff_sequence_digest="sha256:seq",
        )


def test_13_cross_binding_calibration_is_rejected_end_to_end():
    cutoff = T0 + timedelta(seconds=7 * S.PERIOD)
    cal = CalibrationResiduals(
        subject=fx.subject(), target=ForecastTarget.CPU_UTILIZATION, horizon_seconds=900.0,
        arm_model_id="seasonal_naive",  # residuals from a different arm
        evaluation_cutoff=cutoff, values=(1.0, -1.0, 2.0, -2.0, 0.5),
        earliest_origin=cutoff - timedelta(seconds=3600),
        latest_origin=cutoff - timedelta(seconds=900),
        bank_cap=672, config_digest="sha256:cfg", cutoff_sequence_digest="sha256:seq",
    )
    with pytest.raises(UncertaintyError):
        validate_calibration(cal, subject=fx.subject(),
                             target=ForecastTarget.CPU_UTILIZATION,
                             horizon=ForecastHorizon(900.0),
                             arm_model_id="harmonic_phase", cutoff=cutoff,
                             config=S.BANK_CONFIG)


def test_13b_provider_keeps_arms_separate_in_a_real_replay():
    states, cutoffs = _bank_states_and_cutoffs()
    provider = ReplayCalibrationProvider(
        config=S.BANK_CONFIG, cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
        require_calibration_origin=False,
    )
    S.run_arm(states, cutoffs, HarmonicPhaseForecaster(S.SCALED_H),
              provider=provider, uncertainty_config=S.BANK_CONFIG)
    keys = list(provider.bank_sizes())
    assert keys and all(k[3] == "harmonic_phase" for k in keys)


# --------------------------------------------------------------- 14: replay determinism
def test_14_repeated_runs_produce_identical_digests_and_records():
    states, cutoffs = _bank_states_and_cutoffs()

    def once():
        provider = ReplayCalibrationProvider(
            config=S.BANK_CONFIG, cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
            require_calibration_origin=False,
        )
        res = S.run_arm(states, cutoffs, HarmonicPhaseForecaster(S.SCALED_H),
                        provider=provider, uncertainty_config=S.BANK_CONFIG)
        return ([e.digest() for e in res.evidences],
                [r.digest() for r in res.records],
                res.aggregate.digest(),
                provider.bank_sizes())

    assert once() == once()


def test_cutoff_sequence_digest_binds_the_schedule():
    _, cutoffs = _bank_states_and_cutoffs()
    assert cutoff_sequence_digest(cutoffs) != cutoff_sequence_digest(cutoffs[:-1])


# ------------------------------------------------ bounded 49-period chronology integration
PERIODS_TOTAL = 49
BURN_IN_END = 7
CALIBRATION_END = 14
BLOCK_PERIODS = 7


@pytest.fixture(scope="module")
def chronology():
    """One bounded integration fixture: the 49-day chronology, at the scaled period.

    A 'day' here is the scaled 3600-second period, so the whole 49-day / 7-day-burn-in /
    7-day-calibration / five-scoring-block structure is exercised at a few thousand samples
    instead of seventy thousand. This proves the chronology and the plumbing; it is not the
    production-sized matrix and does not pretend to be.
    """
    states = S.build_states(S.harmonic_with_trend(slope=0.0002), periods=PERIODS_TOTAL)
    # Four cutoffs per period inside the calibration block and the five scoring blocks.
    cutoffs = []
    t = T0 + timedelta(seconds=BURN_IN_END * S.PERIOD)
    end = T0 + timedelta(seconds=PERIODS_TOTAL * S.PERIOD)
    while t < end:
        cutoffs.append(t)
        t = t + timedelta(seconds=S.PERIOD)
    provider = ReplayCalibrationProvider(
        config=S.BANK_CONFIG, cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
        require_calibration_origin=False,
    )
    result = S.run_arm(states, cutoffs, HarmonicPhaseForecaster(S.SCALED_H),
                       provider=provider, uncertainty_config=S.BANK_CONFIG)
    return states, cutoffs, result, provider


def test_chronology_has_the_ratified_shape(chronology):
    states, cutoffs, _, _ = chronology
    span = (states[-1].observed_at - states[0].observed_at).total_seconds()
    assert span == PERIODS_TOTAL * S.PERIOD
    assert cutoffs[0] == T0 + timedelta(seconds=BURN_IN_END * S.PERIOD)


def test_no_origin_before_the_burn_in_boundary_is_scored(chronology):
    _, _, result, _ = chronology
    boundary = T0 + timedelta(seconds=BURN_IN_END * S.PERIOD)
    for r in result.records:
        assert r.forecast_cutoff >= boundary


def test_five_scoring_blocks_are_each_populated(chronology):
    _, _, result, _ = chronology
    scored = [r for r in result.records if r.status is EvaluationStatus.EVALUATED]
    blocks = {}
    for r in scored:
        offset = (r.forecast_cutoff - T0).total_seconds() / S.PERIOD
        if offset < CALIBRATION_END:
            continue
        blocks.setdefault(int((offset - CALIBRATION_END) // BLOCK_PERIODS), []).append(r)
    assert sorted(blocks) == [0, 1, 2, 3, 4]
    assert all(len(v) >= 1 for v in blocks.values())


def test_calibration_block_records_are_separable_from_gating_records(chronology):
    _, _, result, _ = chronology
    calibration_end = T0 + timedelta(seconds=CALIBRATION_END * S.PERIOD)
    calibration = [r for r in result.records if r.forecast_cutoff < calibration_end]
    gating = [r for r in result.records if r.forecast_cutoff >= calibration_end]
    assert calibration and gating
    assert not (set(r.forecast_cutoff for r in calibration)
                & set(r.forecast_cutoff for r in gating))


def test_bank_fills_and_stays_within_its_cap(chronology):
    _, _, _, provider = chronology
    sizes = list(provider.bank_sizes().values())
    assert sizes and all(0 < n <= provider.bank_cap for n in sizes)


def test_calibrated_evidence_appears_once_the_bank_is_warm(chronology):
    _, _, result, _ = chronology
    schemas = [e.evidence_schema_version for e in result.evidences]
    assert FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED in schemas
    first_calibrated = schemas.index(FORECAST_EVIDENCE_SCHEMA_VERSION_CALIBRATED)
    # The bank cannot be warm at the very first origin.
    assert first_calibrated > 0


def test_chronology_is_deterministic(chronology):
    states, cutoffs, result, _ = chronology
    provider2 = ReplayCalibrationProvider(
        config=S.BANK_CONFIG, cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
        require_calibration_origin=False,
    )
    again = S.run_arm(states, cutoffs, HarmonicPhaseForecaster(S.SCALED_H),
                      provider=provider2, uncertainty_config=S.BANK_CONFIG)
    assert [e.digest() for e in again.evidences] == [e.digest() for e in result.evidences]
    assert again.aggregate.digest() == result.aggregate.digest()
