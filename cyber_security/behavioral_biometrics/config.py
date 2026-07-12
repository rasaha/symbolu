"""Frozen configuration: instrumentation thresholds, practical effect sizes, and
minimum real-data sample requirements.

Everything mechanical reads from here so a run manifest captures the full
configuration. Thresholds are FROZEN before pilot analysis (see
INSTRUMENTATION_THRESHOLDS.md). Nothing here reads a clock, RNG, or network.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict


@dataclass(frozen=True)
class InstrumentationThresholds:
    """Timing-quality gates. A session is only INSTRUMENTATION_READY if it clears
    all of these; DEGRADED if it clears the ``_degraded`` bounds; else NOT_READY.

    Times are in milliseconds unless noted. These are deliberately lenient enough
    for commodity hardware yet strict enough to keep unusable sessions out of
    identity analysis."""

    # event loss / integrity
    max_drop_rate: float = 0.02            # <=2% dropped events (ready)
    max_drop_rate_degraded: float = 0.10
    max_duplicate_rate: float = 0.005
    max_duplicate_rate_degraded: float = 0.02
    max_reorder_rate: float = 0.005
    max_reorder_rate_degraded: float = 0.02

    # timing quality
    max_jitter_ms: float = 12.0            # median absolute deviation of inter-arrival
    max_jitter_ms_degraded: float = 35.0
    max_source_to_receipt_ms: float = 25.0  # median source->collector latency
    max_source_to_receipt_ms_degraded: float = 75.0
    max_quantization_ms: float = 16.0      # inferred timestamp grid (e.g. 60Hz==16.7ms)
    max_quantization_ms_degraded: float = 34.0
    max_clock_drift_ppm: float = 500.0     # monotonic-vs-source drift
    max_clock_drift_ppm_degraded: float = 2000.0

    # coverage / activity
    min_session_seconds: float = 20.0
    min_session_seconds_degraded: float = 10.0
    min_events: int = 200
    min_events_degraded: int = 80
    min_active_fraction: float = 0.35      # fraction of time with activity
    min_active_fraction_degraded: float = 0.15
    max_collector_overhead_ms: float = 5.0  # per-event receipt processing budget
    max_collector_overhead_ms_degraded: float = 15.0


@dataclass(frozen=True)
class PracticalEffectThresholds:
    """Preregistered minimum PRACTICAL effects. Significance alone never yields a
    positive verdict; if a CI is favorable but the point effect is below threshold,
    a *small-effect* outcome is emitted."""

    min_auc_improvement: float = 0.03          # paired AUC gain to credit a signal
    min_detection_at_far_gain: float = 0.05    # gain in TPR at fixed FAR
    fixed_far: float = 0.05
    max_false_challenge_increase: float = 0.02  # coupling must not inflate challenges
    min_within_between_separation: float = 0.10  # normalized (between-within)/pooled
    min_marginal_auc: float = 0.60             # marginal identity must clear chance+margin
    ci_alpha: float = 0.05                      # two-sided CI level for bootstrap


@dataclass(frozen=True)
class MinimumSampleRequirements:
    """Real-data minimums checked BEFORE any positive identity/coupling verdict is
    available. Below these, verdicts return *INSUFFICIENT_DATA*, never a positive."""

    min_participants: int = 10
    min_sessions_per_participant: int = 3
    min_days_span: int = 2
    min_ready_sessions_per_participant: int = 2
    min_genuine_trials: int = 40
    min_impostor_trials: int = 20
    min_usable_windows_per_session: int = 8


@dataclass(frozen=True)
class FeatureConfig:
    """Deterministic feature-pipeline knobs (versioned via EXTRACTOR_VERSION)."""

    window_seconds: float = 5.0
    window_stride_seconds: float = 2.5
    resample_hz: float = 50.0              # continuous-signal resampling for coupling
    coupling_max_lag_ms: float = 500.0
    coupling_lag_step_ms: float = 20.0
    digraph_min_count: int = 3             # min occurrences to keep a digraph timing
    ridge: float = 1e-3                    # covariance regularization (Mahalanobis/CCA)
    shuffle_seed: int = 20260712           # deterministic control-shuffle seed base


@dataclass(frozen=True)
class BiometricConfig:
    instrumentation: InstrumentationThresholds = field(default_factory=InstrumentationThresholds)
    effects: PracticalEffectThresholds = field(default_factory=PracticalEffectThresholds)
    minimums: MinimumSampleRequirements = field(default_factory=MinimumSampleRequirements)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    bootstrap_iters: int = 2000
    master_seed: int = 20260712

    def to_dict(self) -> Dict:
        return asdict(self)


DEFAULT = BiometricConfig()
