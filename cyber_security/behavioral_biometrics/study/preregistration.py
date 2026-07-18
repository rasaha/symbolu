"""Machine-readable study preregistration template + validation.

Freezes every analysis choice BEFORE test results are visible. No value may be
silently selected after seeing results; ``validate`` checks the required keys are all
present so a run cannot proceed on an under-specified (post-hoc-selectable) config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics.study.effects import DEFAULT

TEMPLATE: Dict[str, Any] = {
    "prereg_version": "bbio-prereg/1.0.0",
    "primary_contrast": "MM_COUPLING_CONTEXT - MM",
    "secondary_contrasts": ["MM_COUPLING_CONTEXT - MM_SHUFFLED",
                            "MM_BCVF - MM_BCVF_NO_DISAGREEMENT",
                            "best_fusion - best_single_modality"],
    "primary_metric": "auc",
    "fixed_far": DEFAULT.effects.fixed_far,
    "effect_thresholds": {
        "min_auc_improvement": DEFAULT.effects.min_auc_improvement,
        "min_tar_gain_at_far": DEFAULT.effects.min_tar_gain_at_far,
        "max_false_challenge_regression": DEFAULT.effects.max_false_challenge_regression,
        "min_marginal_auc": DEFAULT.effects.min_marginal_auc,
        "min_ece_improvement": DEFAULT.effects.min_ece_improvement,
        "max_confidence_ece": DEFAULT.effects.max_confidence_ece,
        "min_ttd_reduction": DEFAULT.effects.min_ttd_reduction,
    },
    "split_protocol": "session_disjoint primary; same_task_same_device, task_disjoint, "
                      "device_disjoint diagnostics; user_disjoint_transfer as a separate claim",
    "eligible_modalities": ["keyboard", "pointer", "touch", "motion"],
    "coupling_representation_selection": (
        "coupling representations are fixed a priori (lagged xcorr, zero-lag xcorr, "
        "event correlogram, windowed CCA); context-conditioning residualizes against "
        "task/UI/device context; no representation is selected after seeing test results"),
    "bcvf_estimator_pair": ["keyboard_identity", "pointer_identity"],
    "bcvf_excludes": ["second_order_delta2_primary_detector", "fast_slow_same_stream_pair",
                      "low_disagreement_means_safe", "smoothness_based_deferral"],
    "fusion_model": "quality-aware + dependence-aware score fusion; non-compensatory hard "
                    "gates for different-latent hard evidence",
    "confidence_calibration_method": "platt (primary); isotonic/histogram reported",
    "bootstrap": {"seed": DEFAULT.seed, "resamples": DEFAULT.bootstrap_iters,
                  "clustered_by": "participant"},
    "exclusion_rules": ["INSTRUMENTATION_NOT_READY sessions excluded (recorded, not dropped)",
                        "non-real origin -> no scientific verdict",
                        "sessions failing quality thresholds excluded from identity analysis"],
    "quality_thresholds": "see INSTRUMENTATION_THRESHOLDS.md (frozen)",
    "minimum_sample_requirements": {
        "min_participants": DEFAULT.minimums.min_participants,
        "min_sessions_per_participant": DEFAULT.minimums.min_sessions_per_participant,
        "min_genuine_trials": DEFAULT.minimums.min_genuine_trials,
        "min_impostor_trials": DEFAULT.minimums.min_impostor_trials,
        "min_calibration_samples": DEFAULT.minimums.min_calibration_samples,
        "min_days_span": DEFAULT.minimums.min_days_span,
    },
}

_REQUIRED = ("primary_contrast", "primary_metric", "fixed_far", "effect_thresholds",
             "split_protocol", "eligible_modalities", "coupling_representation_selection",
             "bcvf_estimator_pair", "fusion_model", "confidence_calibration_method",
             "bootstrap", "exclusion_rules", "quality_thresholds",
             "minimum_sample_requirements")


def default_template() -> Dict[str, Any]:
    return json.loads(json.dumps(TEMPLATE))  # deep copy


def validate(cfg: Dict[str, Any]) -> List[str]:
    problems = [f"missing:{k}" for k in _REQUIRED if k not in cfg]
    if "bootstrap" in cfg and "seed" not in cfg.get("bootstrap", {}):
        problems.append("missing:bootstrap.seed")
    return problems


def load(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def write_template(path: str) -> str:
    Path(path).write_text(json.dumps(TEMPLATE, indent=2))
    return path
