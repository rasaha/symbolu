"""Frozen practical-effect thresholds + minimum-sample requirements for the study.

Every POSITIVE scientific verdict requires ALL of: sufficient real data, a favorable
confidence interval, an effect above the practical minimum, no critical regression on
friction/calibration, and passed artifact/confound gates. These knobs are frozen here
so they cannot be silently reselected after test results are visible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EffectThresholds:
    fixed_far: float = 0.05
    min_auc_improvement: float = 0.03        # paired AUC gain to credit an arm
    min_tar_gain_at_far: float = 0.05        # detection gain at fixed FAR
    max_false_challenge_regression: float = 0.02   # allowed increase in genuine rejection
    min_marginal_auc: float = 0.60           # marginal identity must clear chance+margin
    min_within_between_sep: float = 0.10
    # confidence / calibration
    min_ece_improvement: float = 0.02
    max_confidence_ece: float = 0.10         # above this == miscalibrated
    # temporal
    min_ttd_reduction: float = 0.10          # fractional reduction in time-to-detection
    min_decision_cost_reduction: float = 0.05
    max_false_challenge_per_hour_regression: float = 0.5
    ci_alpha: float = 0.05


@dataclass(frozen=True)
class MinimumSamples:
    min_participants: int = 10
    min_sessions_per_participant: int = 3
    min_ready_sessions_per_participant: int = 2
    min_genuine_trials: int = 40
    min_impostor_trials: int = 20
    min_calibration_samples: int = 60
    min_days_span: int = 2
    min_events_per_session: int = 200


@dataclass(frozen=True)
class StudyEffects:
    effects: EffectThresholds = field(default_factory=EffectThresholds)
    minimums: MinimumSamples = field(default_factory=MinimumSamples)
    bootstrap_iters: int = 2000
    seed: int = 20260712

    def to_dict(self) -> Dict:
        return asdict(self)


DEFAULT = StudyEffects()
