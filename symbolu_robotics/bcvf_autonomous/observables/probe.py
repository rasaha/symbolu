"""Probe harness — score an observable against an outcome label set.

Mirrors ``symbolu_bcvf_llm.observables.probe`` but adapted to
autonomous semantics: a probe iterates over (tick or episode) →
trajectory tensor → outcome label, applies one or more observables,
and reports correlation / AUC against the label.

Pure NumPy. No heavy dependencies. Intended for offline analysis
over a logged corpus of trajectory tensors and outcome labels (e.g.
collision yes/no per episode), not for the hot planning loop.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .base import (
    Observable,
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
    samples: Iterable[
        Tuple[np.ndarray, bool, Optional[np.ndarray]]
    ],
) -> ProbeReport:
    """Score one observable against a labelled corpus.

    Each sample is ``(trajectories, outcome_label, ground_truth_or_None)``.
    The ``outcome_label`` polarity is "True = positive event" — typically
    "True = collision/incident" when probing a higher-means-more-
    suspicious observable, or "True = nominal" when probing a
    higher-means-more-trusted observable. The AUC is computed with the
    labels as-given; sign-conventions are left to the caller.
    """
    datapoints: List[ProbeDatapoint] = []
    scalars: List[float] = []
    labels: List[bool] = []

    for tick_id, sample in enumerate(samples):
        if len(sample) == 2:
            trajectories, label = sample  # type: ignore[misc]
            ground_truth = None
        else:
            trajectories, label, ground_truth = sample
        value = observable.observe(trajectories, ground_truth)
        datapoints.append(
            ProbeDatapoint(
                tick_id=tick_id,
                outcome_label=bool(label),
                observable_value=value,
            )
        )
        scalars.append(value.scalar)
        labels.append(bool(label))

    n = len(datapoints)
    if n == 0:
        return ProbeReport(
            observable_name=getattr(observable, "name", "unknown"),
            higher_means_more_suspicious=getattr(
                observable, "higher_means_more_suspicious", True
            ),
            n_ticks=0,
            pearson_r=0.0,
            spearman_rho=0.0,
            auc=0.5,
            mean_scalar_when_positive=0.0,
            mean_scalar_when_negative=0.0,
            std_scalar_overall=0.0,
            classification="NULL",
            recommendation=recommendation_for("NULL", 0.5),
            datapoints=datapoints,
        )

    s = np.asarray(scalars, dtype=np.float64)
    y = np.asarray(labels, dtype=bool)
    pos = s[y]
    neg = s[~y]

    auc = _roc_auc(s, y)
    pearson = _pearson_r(s, y.astype(np.float64))
    spearman = _spearman_rho(s, y.astype(np.float64))
    classification = classify_observable(auc, n)

    return ProbeReport(
        observable_name=getattr(observable, "name", "unknown"),
        higher_means_more_suspicious=getattr(
            observable, "higher_means_more_suspicious", True
        ),
        n_ticks=n,
        pearson_r=pearson,
        spearman_rho=spearman,
        auc=auc,
        mean_scalar_when_positive=float(pos.mean()) if pos.size > 0 else 0.0,
        mean_scalar_when_negative=float(neg.mean()) if neg.size > 0 else 0.0,
        std_scalar_overall=float(s.std()),
        classification=classification,
        recommendation=recommendation_for(classification, auc),
        datapoints=datapoints,
    )


def probe_observables(
    observables: Sequence[Observable],
    samples: Sequence[Tuple[np.ndarray, bool, Optional[np.ndarray]]],
) -> List[ProbeReport]:
    """Run ``probe_observable`` for each observable on a shared sample list."""
    return [probe_observable(obs, samples) for obs in observables]
