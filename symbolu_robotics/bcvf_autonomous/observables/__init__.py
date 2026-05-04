"""BCVF Autonomous observable framework — public API.

An observable is a witness function that reads the predictor
trajectory tensor for one planning tick and produces a scalar. The
probe harness runs an observable across many ticks (or episodes)
and measures how well its scalar predicts the chosen outcome
label.

Polarity convention follows the BCVF LLM framework:

  SAFETY_CORRELATED  — AUC ≥ 0.60 vs the configured label.
  UNCORRELATED       — 0.45 ≤ AUC < 0.60.
  ANTI_CORRELATED    — AUC < 0.45 (signal with the wrong sign).
  NULL               — fewer than 40 datapoints.

Usage:

    from symbolu_robotics.bcvf_autonomous.observables import (
        BCVFPerStepMaxObservable, probe_observable,
    )

    obs = BCVFPerStepMaxObservable()
    samples = [(trajectories_tick_0, collision_label_0, None), ...]
    report = probe_observable(obs, samples)
    print(report.classification, report.auc, report.recommendation)
"""

from __future__ import annotations

from .agreement import PredictorAgreementObservable
from .base import (
    Observable,
    ObservableValue,
    ProbeDatapoint,
    ProbeReport,
    classify_observable,
    recommendation_for,
    validate_trajectory_tensor,
)
from .bcvf_per_step import (
    BCVFPerStepMaxObservable,
    BCVFPredictorPerStepMaxObservable,
)
from .coherence import CoherenceAnchoredBCVFObservable
from .entropy import (
    EnsembleHeadingEntropyObservable,
    EnsembleSpreadObservable,
)
from .kernel_per_step import (
    BCVFPerStepBreakdown,
    compute_bcvf_per_step,
    stencil_align_to_signal,
)
from .probe import probe_observable, probe_observables
from .uncertainty_gated import UncertaintyGatedBCVFPerStepMaxObservable

__all__ = [
    "BCVFPerStepBreakdown",
    "BCVFPerStepMaxObservable",
    "BCVFPredictorPerStepMaxObservable",
    "CoherenceAnchoredBCVFObservable",
    "EnsembleHeadingEntropyObservable",
    "EnsembleSpreadObservable",
    "Observable",
    "ObservableValue",
    "PredictorAgreementObservable",
    "ProbeDatapoint",
    "ProbeReport",
    "UncertaintyGatedBCVFPerStepMaxObservable",
    "classify_observable",
    "compute_bcvf_per_step",
    "probe_observable",
    "probe_observables",
    "recommendation_for",
    "stencil_align_to_signal",
    "validate_trajectory_tensor",
]
