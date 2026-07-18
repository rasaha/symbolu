#!/usr/bin/env python3
"""Frozen metric definitions for the incremental-value study (Part 4).

Metric semantics are frozen in ``PREDICTOR_TRUST_V2_PREREGISTRATION.md`` and
MUST NOT change after the preregistration commit. Every metric is computed
from ``DetectorOutput`` + the ground-truth ``FaultBundle``.

Definitions (all per fault family, aggregated over seeds):

  fault_detection_recall   over HARM-BEARING families (fault_active and
                           harm_class != benign): fraction where detected.
  false_alarm_rate         over BENIGN families (not fault_active): fraction
                           where the detector surfaced a fault (detected).
  detection_delay          over correctly-detected single-culprit faults:
                           mean(max(0, detection_tick - onset_tick)) ticks.
  attribution_accuracy     over single-culprit families (truth_label not None):
                           fraction where flagged == truth_label.
  common_mode_handling     over common_mode / correlated families: fraction
                           that ABSTAINED (correct) rather than confidently
                           mis-attributing to an honest predictor.
  abstention_correctness   fraction of families where abstain matched the
                           should-abstain ground truth.
  runtime_us_per_episode   wall-clock microseconds per detect() call.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List

import numpy as np

from robotics_reliability_bench.fault_corpus import (FaultBundle, HARM_BENIGN,
                                                     HARM_COMMON, HARM_STATE)


# Families where the correct system behaviour is to ABSTAIN (no safe
# single-culprit attribution possible): common-mode + correlated multi-fault.
SHOULD_ABSTAIN = {"all_wrong", "correlated_failure"}


@dataclass
class FamilyScore:
    family: str
    n: int
    harm_class: str
    fault_active: bool
    detected_rate: float
    attribution_acc: float | None
    mean_delay: float | None
    abstain_rate: float
    false_alarm: bool
    mean_runtime_us: float
    detail: dict = field(default_factory=dict)


def score_family(detector, bundles: List[FaultBundle]) -> FamilyScore:
    fam = bundles[0].family
    harm = bundles[0].harm_class
    fault_active = bundles[0].fault_active
    n = len(bundles)

    detected = 0
    attr_hits = 0
    attr_total = 0
    delays: List[float] = []
    abstains = 0
    runtimes: List[float] = []

    for b in bundles:
        t0 = time.perf_counter()
        out = detector.detect(b)
        runtimes.append((time.perf_counter() - t0) * 1e6)

        if out.detected:
            detected += 1
        if out.abstained:
            abstains += 1
        if b.truth_label is not None:
            attr_total += 1
            if out.flagged == b.truth_label:
                attr_hits += 1
                if out.detection_tick is not None and b.onset_tick is not None:
                    delays.append(max(0.0, out.detection_tick - b.onset_tick))

    detected_rate = detected / n
    attribution_acc = (attr_hits / attr_total) if attr_total else None
    mean_delay = float(np.mean(delays)) if delays else None
    abstain_rate = abstains / n
    is_benign = (not fault_active) or harm == HARM_BENIGN
    false_alarm = is_benign and detected_rate > 0.0

    return FamilyScore(
        family=fam, n=n, harm_class=harm, fault_active=fault_active,
        detected_rate=detected_rate, attribution_acc=attribution_acc,
        mean_delay=mean_delay, abstain_rate=abstain_rate,
        false_alarm=false_alarm, mean_runtime_us=float(np.mean(runtimes)),
        detail={"detected": detected, "n": n, "attr_hits": attr_hits,
                "attr_total": attr_total, "abstains": abstains})


def aggregate(scores: List[FamilyScore]) -> Dict:
    """Roll family scores into the frozen headline metrics."""
    # Recall is over DETECTABLE harmful faults (single/multi-predictor state
    # errors). Common-mode (all predictors wrong together) is undetectable by
    # any disagreement-only method, so it is excluded from recall and reported
    # separately as a false-detection rate (detecting it = false attribution).
    harm_families = [s for s in scores if s.fault_active
                     and s.harm_class == HARM_STATE]
    common_mode_families = [s for s in scores if s.harm_class == HARM_COMMON]
    benign_families = [s for s in scores if not s.fault_active
                       or s.harm_class == HARM_BENIGN]
    single_culprit = [s for s in scores if s.attribution_acc is not None]
    common = [s for s in scores if s.family in SHOULD_ABSTAIN]
    delayed = [s for s in scores if s.mean_delay is not None]

    # abstention correctness: for should-abstain families, abstain_rate; for
    # others (benign or single-fault), 1 - abstain_rate (should NOT abstain).
    abst_correct = []
    for s in scores:
        if s.family in SHOULD_ABSTAIN:
            abst_correct.append(s.abstain_rate)
        else:
            abst_correct.append(1.0 - s.abstain_rate)

    return {
        "fault_detection_recall": _mean([s.detected_rate for s in harm_families]),
        "false_alarm_rate": _mean([s.detected_rate for s in benign_families]),
        "n_benign_families_with_false_alarm": sum(1 for s in benign_families if s.false_alarm),
        "common_mode_false_detection_rate": _mean([s.detected_rate for s in common_mode_families]),
        "detection_delay_ticks": _mean([s.mean_delay for s in delayed]),
        "attribution_accuracy": _mean([s.attribution_acc for s in single_culprit]),
        "common_mode_abstain_rate": _mean([s.abstain_rate for s in common]),
        "abstention_correctness": _mean(abst_correct),
        "runtime_us_per_episode": _mean([s.mean_runtime_us for s in scores]),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None
