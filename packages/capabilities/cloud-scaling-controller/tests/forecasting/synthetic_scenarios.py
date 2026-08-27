"""Deterministic synthetic scenarios for the four-arm replay (no telemetry, no randomness).

Everything here is generated from closed-form expressions of the timestamp, so a scenario is
reproducible bit-for-bit and a fixture can be reasoned about rather than trusted.

**Scaled period.** Unit scenarios use a 3600-second period as a stand-in for the ratified
86,400-second day, with the phase-bin thresholds scaled to match. The estimator is
period-agnostic (a dedicated test pins that at the real period), and the scaling keeps a
full multi-period window at a few hundred samples instead of ten thousand.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    AdmissionPolicy,
    CanonicalCapacitySeries,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    HarmonicPhaseForecaster,
    LinearTrendForecaster,
    PersistenceForecaster,
    ReplayCalibrationProvider,
    SeasonalNaiveForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    cutoff_sequence_digest,
    run_replay_evaluation,
)
from ugence_cloud_scaling_controller.forecasting.evaluation import EvaluationStatus

T0 = fx.T0
PERIOD = 3600.0
CADENCE = 60.0
LOOKBACK = 7 * PERIOD
STRIDE = 900.0

#: Scaled analogue of the ratified resolvability configuration (run manifest §6).
SCALED_H = {
    "period_seconds": PERIOD,
    "min_cycle_span_seconds": LOOKBACK - CADENCE,
    "phase_bins": 12,
    "min_occupied_bins": 11,
    "min_days_with_coverage": 6,
    "lookback_days": 7,
}

#: Every arm receives byte-identical skeleton configuration. Only the forecaster differs.
FEATURE_CONFIG = FeatureConfig(
    feature_version="synthetic-eval-v1",
    lookback_seconds=LOOKBACK,
    expected_cadence_seconds=CADENCE,
)
ADMISSION_POLICY = AdmissionPolicy(
    policy_id="synthetic-eval",
    require_regular_cadence=False,
    max_staleness_seconds=None,
    max_missing_fraction=0.9,
)
UNCERTAINTY_NONE = UncertaintyConfig(method=UncertaintyMethod.NONE)
BANK_CONFIG = UncertaintyConfig(
    method=UncertaintyMethod.EMPIRICAL_PREQUENTIAL_RESIDUAL_BANK,
    requested_coverage=0.8,
    min_calibration_samples=5,
    match_tolerance_seconds=5.0,
    calibration_window_id="synthetic-bank-v1",
)


def phase(t: datetime, period: float = PERIOD) -> float:
    return 2.0 * math.pi * ((t.timestamp() % period) / period)


# ------------------------------------------------------------------------ value generators
def harmonic_with_trend(level=50.0, slope=0.0005, amp_cos=10.0, amp_sin=4.0):
    def f(t: datetime) -> float:
        return (level + slope * (t.timestamp() - T0.timestamp())
                + amp_cos * math.cos(phase(t)) + amp_sin * math.sin(phase(t)))
    return f


def exact_repeating(step_values: Sequence[float]):
    """A period-exact repeating pattern: seasonal-naive is exactly right by construction."""
    def f(t: datetime) -> float:
        slot = int((t.timestamp() % PERIOD) // CADENCE)
        return float(step_values[slot % len(step_values)])
    return f


def trend_only(level=20.0, slope=0.002):
    def f(t: datetime) -> float:
        return level + slope * (t.timestamp() - T0.timestamp())
    return f


def non_periodic(level=40.0):
    """Deterministic but aperiodic: a logistic map driven by the sample index."""
    def f(t: datetime) -> float:
        i = int((t.timestamp() - T0.timestamp()) // CADENCE)
        x = 0.37
        for _ in range(1 + (i % 13)):
            x = 3.99 * x * (1.0 - x)
        return level + 25.0 * x
    return f


def with_level_shift(base: Callable[[datetime], float], at: datetime, delta: float):
    """A regime break: retained, never excluded (run manifest §7.1)."""
    def f(t: datetime) -> float:
        return base(t) + (delta if t >= at else 0.0)
    return f


# ------------------------------------------------------------------------------ series
def build_states(
    value_fn: Callable[[datetime], float],
    *,
    periods: int = 10,
    cadence: float = CADENCE,
    drop_indices: Sequence[int] = (),
    keep: Optional[Callable[[datetime], bool]] = None,
):
    states = []
    n = int(periods * PERIOD / cadence) + 1
    dropped = set(drop_indices)
    for i in range(n):
        if i in dropped:
            continue
        t = T0 + timedelta(seconds=cadence * i)
        if keep is not None and not keep(t):
            continue
        states.append(fx.cpu_state(t, value_fn(t)))
    return states


def aligned_cutoffs(states, *, first_period: int = 7, stride: float = STRIDE) -> List[datetime]:
    """UTC-aligned cutoffs from the first fully-covered period onward."""
    start = T0 + timedelta(seconds=first_period * PERIOD)
    end = states[-1].observed_at
    out = []
    t = start
    while t <= end:
        out.append(t)
        t = t + timedelta(seconds=stride)
    return out


# --------------------------------------------------------------------------- the four arms
def arms() -> Dict[str, object]:
    """P, T, N, H — constructed fresh so no state can leak between arms or runs."""
    return {
        "P": PersistenceForecaster(),
        "T": LinearTrendForecaster({"min_history": 3}),
        "N": SeasonalNaiveForecaster({"period_seconds": PERIOD, "match_tolerance_seconds": 5.0}),
        "H": HarmonicPhaseForecaster(SCALED_H),
    }


def run_arm(states, cutoffs, forecaster, horizon_seconds=900.0, *, provider=None,
            uncertainty_config=UNCERTAINTY_NONE):
    return run_replay_evaluation(
        states,
        ForecastTarget.CPU_UTILIZATION,
        ForecastHorizon(horizon_seconds),
        forecaster,
        normalization_policy=fx.cpu_norm_policy(),
        cutoffs=cutoffs,
        feature_config=FEATURE_CONFIG,
        uncertainty_config=uncertainty_config,
        admission_policy=ADMISSION_POLICY,
        match_tolerance_seconds=5.0,
        calibration_provider=provider,
    )


def run_all_arms(states, cutoffs, horizon_seconds=900.0, *, with_bank=False):
    """Run the four arms over identical inputs; return per-arm replay results."""
    results = {}
    for name, f in arms().items():
        provider = None
        cfg = UNCERTAINTY_NONE
        if with_bank:
            cfg = BANK_CONFIG
            provider = ReplayCalibrationProvider(
                config=BANK_CONFIG,
                cutoff_sequence_digest=cutoff_sequence_digest(cutoffs),
                require_calibration_origin=False,
            )
        results[name] = run_arm(states, cutoffs, f, horizon_seconds,
                                provider=provider, uncertainty_config=cfg)
    return results


# ------------------------------------------------------------------- four-arm paired scoring
def paired_mae(results: Dict[str, object]) -> Dict[str, float]:
    """MAE per arm over cutoffs where **all four** arms produced an EVALUATED record.

    Unpaired scoring would let a heavily-abstaining arm win by declining the hard origins,
    which is exactly the failure mode the run manifest's paired-set rule exists to prevent.
    """
    scored: Dict[str, Dict[datetime, float]] = {}
    for name, res in results.items():
        scored[name] = {
            r.forecast_cutoff: r.absolute_error
            for r in res.records
            if r.status is EvaluationStatus.EVALUATED and r.absolute_error is not None
        }
    common = set.intersection(*(set(v) for v in scored.values())) if scored else set()
    if not common:
        return {}
    return {name: sum(scored[name][c] for c in common) / len(common) for name in scored}


def paired_count(results: Dict[str, object]) -> int:
    scored = [
        {r.forecast_cutoff for r in res.records if r.status is EvaluationStatus.EVALUATED}
        for res in results.values()
    ]
    return len(set.intersection(*scored)) if scored else 0


def abstention_reasons(result) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for ev in result.evidences:
        if ev.forecast.status == "abstained":
            key = ev.forecast.abstention_reason.value
            out[key] = out.get(key, 0) + 1
    return out
