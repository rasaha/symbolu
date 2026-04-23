"""§11 probe harness — run an observable against a benchmark and
measure correlation with correctness.

Key methodological property: the probe runs BEFORE any Rahu
attractor is built. It answers only the Ketu question ("does this
observable correlate with truth?"). If the probe returns
UNCORRELATED or ANTI_CORRELATED, building a decoder on top of the
observable is waste at best and active harm at worst.

Polarity normalization: every observable declares
`higher_means_more_suspicious` (a boolean). The probe internally
flips labels so the reported AUC is uniformly "higher AUC = more
truth-predictive" regardless of the observable's polarity choice.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

import numpy as np

from symbolu_bcvf_llm.benchmark.dataset import Benchmark

from .base import (
    Observable,
    ObservableValue,
    ProbeDatapoint,
    ProbeReport,
    _pearson_r,
    _rankdata,
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

    For each (question_id, choice_id):
      - construct fresh sources via benchmark.make_sources(question)
      - compute observable.observe(sources, prompt_tokens, choice_tokens)
      - record (is_correct = choice_id == question.correct_index, observable_value)

    Returns a ProbeReport with Pearson r, Spearman ρ, AUC, class-conditional
    means, classification, and recommendation text.

    Args:
        observable: Observable Protocol conformant.
        benchmark: Any §6.2 Benchmark. MockBenchmark works without torch.
        max_questions: cap on questions processed. Default = all.
        retain_datapoints: keep per-(Q, C) records on the report. Set False
            for very large benchmarks if memory is a concern.
    """
    questions = list(benchmark.questions)
    if max_questions is not None:
        questions = questions[: max_questions]
    N = len(questions)

    scalars: List[float] = []
    labels: List[int] = []
    datapoints: List[ProbeDatapoint] = []

    for q_idx, question in enumerate(questions):
        for c_idx, choice_tokens in enumerate(question.choice_tokens):
            sources = benchmark.make_sources(question)
            value = observable.observe(
                sources=sources,
                prompt_tokens=list(question.prompt_tokens),
                choice_tokens=list(choice_tokens),
            )
            is_correct = (c_idx == question.correct_index)
            scalars.append(value.scalar)
            labels.append(1 if is_correct else 0)
            if retain_datapoints:
                datapoints.append(ProbeDatapoint(
                    question_id=q_idx,
                    choice_id=c_idx,
                    is_correct=is_correct,
                    observable_value=value,
                ))

    scalars_np = np.asarray(scalars, dtype=np.float64)
    labels_np = np.asarray(labels, dtype=np.float64)

    # Polarity handling — probe wants AUC to mean "higher = better predictor".
    # If `higher_means_more_suspicious`, then correct examples should have
    # LOWER scalar → invert scores so AUC stays interpretable uniformly.
    if getattr(observable, "higher_means_more_suspicious", False):
        scores_for_auc = -scalars_np
        scalars_for_corr = -scalars_np
    else:
        scores_for_auc = scalars_np
        scalars_for_corr = scalars_np

    pearson = _pearson_r(scalars_for_corr, labels_np)
    spearman = _spearman_rho(scalars_for_corr, labels_np)
    auc = _roc_auc(scores_for_auc, labels_np.astype(bool))

    correct_scalars = scalars_np[labels_np == 1.0]
    wrong_scalars = scalars_np[labels_np == 0.0]
    mean_correct = float(correct_scalars.mean()) if correct_scalars.size else 0.0
    mean_wrong = float(wrong_scalars.mean()) if wrong_scalars.size else 0.0
    std_overall = float(scalars_np.std()) if scalars_np.size else 0.0

    classification = classify_observable(auc, n_datapoints=len(scalars))
    recommendation = recommendation_for(classification, auc)

    return ProbeReport(
        observable_name=getattr(observable, "name", type(observable).__name__),
        higher_means_more_suspicious=bool(
            getattr(observable, "higher_means_more_suspicious", False)
        ),
        n_questions=N,
        n_choices=int(len(scalars_np)),
        n_datapoints=len(scalars),
        pearson_r=pearson,
        spearman_rho=spearman,
        auc=auc,
        mean_scalar_when_correct=mean_correct,
        mean_scalar_when_wrong=mean_wrong,
        std_scalar_overall=std_overall,
        classification=classification,
        recommendation=recommendation,
        datapoints=datapoints if retain_datapoints else [],
    )


def probe_observables_parallel(
    observables: Sequence[Observable],
    benchmark: Benchmark,
    max_questions: Optional[int] = None,
    retain_datapoints: bool = False,
) -> Dict[str, ProbeReport]:
    """Run multiple observables against the same benchmark in a single
    pass — avoids the N × K `make_sources()` cost from probing one at
    a time.

    For each (question, choice) pair, constructs the sources ONCE and
    dispatches all observables against the same source triple. Fresh
    sources are constructed per-choice (matching the benchmark harness).

    Returns: {observable_name: ProbeReport}.
    """
    questions = list(benchmark.questions)
    if max_questions is not None:
        questions = questions[: max_questions]
    N = len(questions)

    per_obs_scalars: Dict[str, List[float]] = {o.name: [] for o in observables}
    per_obs_datapoints: Dict[str, List[ProbeDatapoint]] = {
        o.name: [] for o in observables
    }
    labels: List[int] = []

    for q_idx, question in enumerate(questions):
        for c_idx, choice_tokens in enumerate(question.choice_tokens):
            is_correct = (c_idx == question.correct_index)
            labels.append(1 if is_correct else 0)
            for obs in observables:
                # IMPORTANT: Observables may mutate source state via
                # teacher-forced operations. To preserve independence
                # between observables in the same (Q, C) pass, construct
                # a fresh source triple for EACH observable. This is
                # slower but correct.
                sources = benchmark.make_sources(question)
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
        scalars_np = np.asarray(per_obs_scalars[obs.name], dtype=np.float64)
        polarity = bool(
            getattr(obs, "higher_means_more_suspicious", False)
        )
        scores_for_auc = -scalars_np if polarity else scalars_np
        scalars_for_corr = -scalars_np if polarity else scalars_np

        pearson = _pearson_r(scalars_for_corr, labels_np)
        spearman = _spearman_rho(scalars_for_corr, labels_np)
        auc = _roc_auc(scores_for_auc, labels_np.astype(bool))
        correct = scalars_np[labels_np == 1.0]
        wrong = scalars_np[labels_np == 0.0]
        classification = classify_observable(auc, n_datapoints=len(scalars_np))
        reports[obs.name] = ProbeReport(
            observable_name=obs.name,
            higher_means_more_suspicious=polarity,
            n_questions=N,
            n_choices=int(len(scalars_np)),
            n_datapoints=len(scalars_np),
            pearson_r=pearson,
            spearman_rho=spearman,
            auc=auc,
            mean_scalar_when_correct=float(correct.mean()) if correct.size else 0.0,
            mean_scalar_when_wrong=float(wrong.mean()) if wrong.size else 0.0,
            std_scalar_overall=float(scalars_np.std()) if scalars_np.size else 0.0,
            classification=classification,
            recommendation=recommendation_for(classification, auc),
            datapoints=per_obs_datapoints[obs.name] if retain_datapoints else [],
        )
    return reports
