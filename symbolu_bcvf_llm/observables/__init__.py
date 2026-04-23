"""§11 Ketu observable framework — public API.

A Ketu (observable) is a witness function that reads the sources'
behavior on a (question, choice) pair and produces a scalar. It
does NOT act — it only reports. Separating the Ketu observable
from the Rahu attractor is the design discipline §10.V1 showed is
essential.

The probe harness runs an observable against a benchmark and
measures how well its scalar predicts correctness. Four classifications:

  TRUTH_CORRELATED  — AUC > 0.60. Observable is signal.
  UNCORRELATED      — 0.45 < AUC < 0.55. Observable is noise.
  ANTI_CORRELATED   — AUC < 0.40. Observable has signal with the
                      wrong sign — would help if flipped.
  NULL              — too few data points for a verdict.

Usage:

    from symbolu_bcvf_llm.observables import (
        BCVFTotalCostObservable, probe_observable,
    )
    from symbolu_bcvf_llm.benchmark import MockBenchmark

    bench = MockBenchmark(num_questions=24)
    report = probe_observable(BCVFTotalCostObservable(), bench)
    print(report.classification, report.auc, report.recommendation)

The probe runs before any attractor (softmin, veto, etc.) is
built — that's the point. An observable with AUC ≈ 0.5 is not
worth building a decoder around; an anti-correlated observable
would actively hurt the decoder.
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
from .entropy import Source0EntropyObservable
from .probe import probe_observable, probe_observables_parallel

__all__ = [
    "BCVFSourceZeroCostObservable",
    "BCVFTotalCostObservable",
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
