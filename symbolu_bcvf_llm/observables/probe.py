"""Run an observable against a benchmark and measure correlation with correctness.

Polarity normalization: every observable declares
`higher_means_more_suspicious` (a boolean). The probe internally flips
labels so the reported AUC is uniformly "higher AUC = more truth-
predictive" regardless of the observable's polarity choice.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.benchmark.dataset import Benchmark

from .base import (
    Observable,
    ObservableValue,
    ProbeDatapoint,
    ProbeReport,
    _pearson_r,
    _roc_auc,
    _spearman_rho,
    classify_observable,
    recommendation_for,
)


def probe_observable(
    observable: Observable,
    benchmark: Benchmark,
    max_questions: Optional[int] = None,
    retain_datapoints: bool = True,
) -> ProbeReport:
    """Run `observable` on every (question, choice) pair and build a report.

    Equivalent to `probe_observables_parallel([observable], ...)` —
    kept as a thin convenience wrapper for single-observable callers.
    """
    reports = probe_observables_parallel(
        [observable],
        benchmark,
        max_questions=max_questions,
        retain_datapoints=retain_datapoints,
    )
    return reports[observable.name]


def probe_observables_parallel(
    observables: Sequence[Observable],
    benchmark: Benchmark,
    max_questions: Optional[int] = None,
    retain_datapoints: bool = False,
) -> Dict[str, ProbeReport]:
    """Probe multiple observables against the same benchmark in one pass.

    Constructs the source triple ONCE per (question, choice) and
    dispatches every observable against it. Observables that mutate
    source state must opt out by setting `requires_isolated_sources =
    True` on their class — those receive a fresh source triple each.

    Returns: {observable_name: ProbeReport}.
    """
    questions = list(benchmark.questions)
    if max_questions is not None:
        questions = questions[:max_questions]
    n_questions = len(questions)

    per_obs_scalars: Dict[str, List[float]] = {o.name: [] for o in observables}
    per_obs_datapoints: Dict[str, List[ProbeDatapoint]] = {
        o.name: [] for o in observables
    }
    labels: List[int] = []

    for q_idx, question in enumerate(questions):
        for c_idx, choice_tokens in enumerate(question.choice_tokens):
            is_correct = (c_idx == question.correct_index)
            labels.append(1 if is_correct else 0)
            shared_sources = benchmark.make_sources(question)
            for obs in observables:
                if getattr(obs, "requires_isolated_sources", False):
                    sources = benchmark.make_sources(question)
                else:
                    sources = shared_sources
                value = obs.observe(
                    sources=sources,
                    prompt_tokens=list(question.prompt_tokens),
                    choice_tokens=list(choice_tokens),
                )
                per_obs_scalars[obs.name].append(value.scalar)
                if retain_datapoints:
                    per_obs_datapoints[obs.name].append(ProbeDatapoint(
                        question_id=q_idx,
                        choice_id=c_idx,
                        is_correct=is_correct,
                        observable_value=value,
                    ))

    labels_np = np.asarray(labels, dtype=np.float64)
    reports: Dict[str, ProbeReport] = {}
    for obs in observables:
        reports[obs.name] = _build_report(
            obs,
            scalars=np.asarray(per_obs_scalars[obs.name], dtype=np.float64),
            labels_np=labels_np,
            n_questions=n_questions,
            datapoints=per_obs_datapoints[obs.name] if retain_datapoints else [],
        )
    return reports


def _build_report(
    obs: Observable,
    *,
    scalars: np.ndarray,
    labels_np: np.ndarray,
    n_questions: int,
    datapoints: List[ProbeDatapoint],
) -> ProbeReport:
    # AUC and rank correlations are computed against scalars normalized to
    # "higher = more truth-predictive", so suspicion-polarity observables
    # have their scalars negated before scoring.
    polarity = bool(obs.higher_means_more_suspicious)
    normalized = -scalars if polarity else scalars

    pearson = _pearson_r(normalized, labels_np)
    spearman = _spearman_rho(normalized, labels_np)
    auc = _roc_auc(normalized, labels_np.astype(bool))

    correct = scalars[labels_np == 1.0]
    wrong = scalars[labels_np == 0.0]
    classification = classify_observable(auc, n_datapoints=len(scalars))
    return ProbeReport(
        observable_name=obs.name,
        higher_means_more_suspicious=polarity,
        n_questions=n_questions,
        n_datapoints=len(scalars),
        pearson_r=pearson,
        spearman_rho=spearman,
        auc=auc,
        mean_scalar_when_correct=float(correct.mean()) if correct.size else 0.0,
        mean_scalar_when_wrong=float(wrong.mean()) if wrong.size else 0.0,
        std_scalar_overall=float(scalars.std()) if scalars.size else 0.0,
        classification=classification,
        recommendation=recommendation_for(classification, auc),
        datapoints=datapoints,
    )
