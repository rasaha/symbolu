"""Ketu observable framework — public API.

An observable is a witness function that reads the sources' behavior
on a (question, choice) pair and produces a scalar. The probe harness
runs an observable against a benchmark and measures how well its
scalar predicts correctness. Four classifications:

  TRUTH_CORRELATED  — AUC ≥ 0.60.
  UNCORRELATED      — 0.45 ≤ AUC < 0.60.
  ANTI_CORRELATED   — AUC < 0.45 (signal with the wrong sign).
  NULL              — fewer than 40 datapoints.

Usage:

    from symbolu_bcvf_llm.observables import (
        BCVFTotalCostObservable, probe_observable,
    )
    from symbolu_bcvf_llm.benchmark import MockBenchmark

    bench = MockBenchmark(num_questions=24)
    report = probe_observable(BCVFTotalCostObservable(), bench)
    print(report.classification, report.auc, report.recommendation)
"""

from __future__ import annotations

from .agreement import SourceAgreementObservable
from .base import (
    Observable,
    ObservableValue,
    ProbeDatapoint,
    ProbeReport,
    classify_observable,
)
from .bcvf import (
    BCVFSourceZeroCostObservable,
    BCVFTotalCostObservable,
)
from .bcvf_per_step import (
    BCVFPerStepMaxObservable,
    BCVFSourceZeroPerStepMaxObservable,
)
from .coherence import (
    CoherenceAnchoredBCVFObservable,
    CoherenceAnchoredBCVFPerStepObservable,
)
from .entropy import Source0EntropyObservable
from .probe import probe_observable, probe_observables_parallel

__all__ = [
    "BCVFPerStepMaxObservable",
    "BCVFSourceZeroCostObservable",
    "BCVFSourceZeroPerStepMaxObservable",
    "BCVFTotalCostObservable",
    "CoherenceAnchoredBCVFObservable",
    "CoherenceAnchoredBCVFPerStepObservable",
    "Observable",
    "ObservableValue",
    "ProbeDatapoint",
    "ProbeReport",
    "Source0EntropyObservable",
    "SourceAgreementObservable",
    "classify_observable",
    "probe_observable",
    "probe_observables_parallel",
]
