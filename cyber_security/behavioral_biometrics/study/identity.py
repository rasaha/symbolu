"""Identity-verification study runner.

Enrollment templates from training sessions; genuine held-out + same-task impostor
scoring; full metric suite with participant-clustered bootstrap CIs. Reuses the
train-only prototype scorer in ``baselines`` (identifiers are never features). Returns
per-user and aggregate results.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import baselines, splits
from cyber_security.behavioral_biometrics.study import arms, metrics
from cyber_security.behavioral_biometrics.study.effects import DEFAULT, StudyEffects


def run_arm(records: List[Dict[str, Any]], plan: splits.SplitPlan,
            arm: str, *, model: str = "prototype", cfg: StudyEffects = DEFAULT) -> Dict[str, Any]:
    builder = arm if callable(arm) else arms.builder_for(arm)
    res = baselines.evaluate_identity(records, plan, builder, model=model)
    if not res.get("usable"):
        return {"arm": arm if isinstance(arm, str) else "custom", "usable": False,
                "reason": res.get("reason")}
    scores = np.array(res["scores"])
    labels = np.array(res["labels"])
    groups = np.array(res["groups"])
    m = metrics.summary(scores, labels, cfg.effects.fixed_far)
    m["auc_ci"] = metrics.clustered_bootstrap_ci(
        scores, labels, groups, metric="auc", iters=cfg.bootstrap_iters,
        alpha=cfg.effects.ci_alpha, seed=cfg.seed)
    return {"arm": arm if isinstance(arm, str) else "custom", "usable": True,
            "n_features": res["n_features"], "metrics": m,
            "per_user": _per_user(scores, labels, groups),
            "scores": res["scores"], "labels": res["labels"], "groups": res["groups"]}


def _per_user(scores, labels, groups) -> Dict[str, Any]:
    out = {}
    for g in np.unique(groups):
        mask = groups == g
        yl = labels[mask]
        if len(set(yl.tolist())) < 2:
            out[str(g)] = {"auc": None, "note": "insufficient_labels"}
        else:
            out[str(g)] = {"auc": metrics.auc(scores[mask], yl),
                           "n_genuine": int((yl == 1).sum()), "n_impostor": int((yl == 0).sum())}
    return out


def run_ablation(records: List[Dict[str, Any]], plan: splits.SplitPlan,
                 arm_list: Optional[List[str]] = None, *, cfg: StudyEffects = DEFAULT
                 ) -> Dict[str, Any]:
    """Run every available simple arm on ONE split (fair: same records/split/model)."""
    avail_mod = set(arms.available_modalities(records))
    todo = arm_list or [a for a in arms.SIMPLE_ARMS
                        if a not in ("K", "P", "T", "M") or a in avail_mod]
    results = {}
    for a in todo:
        results[a] = run_arm(records, plan, a, cfg=cfg)
    return results


def standard_splits(records: List[Dict[str, Any]], *, seed: int = 0) -> Dict[str, splits.SplitPlan]:
    """The frozen split battery for the identity study."""
    return {
        "session_disjoint": splits.session_disjoint(records, seed=seed),
        "same_task_same_device": splits.live_impostor_only(records),
        "task_disjoint": splits.task_disjoint(records),
        "device_disjoint": splits.device_instance(records),
        "user_disjoint_transfer": splits.participant_disjoint(records, seed=seed),
    }
