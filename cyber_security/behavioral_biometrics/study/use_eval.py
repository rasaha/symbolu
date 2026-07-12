"""USE contribution evaluation — cross-modal coupling as an EVALUATION LABEL, not a
privileged formula.

Primary contrasts (context-conditioned coupling must beat BOTH):
  * MM_COUPLING_CONTEXT − MM            (adds identity info beyond fair marginals)
  * MM_COUPLING_CONTEXT − MM_SHUFFLED   (beyond the shuffled-coupling control)

Diagnostics: raw vs context-conditioned coupling; same-device vs different-device.
The classifier returns one of the six mechanical coupling outcomes; the guarded wrapper
emits only USE_PATH_VERIFIED on non-real data (never a scientific verdict).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import splits
from cyber_security.behavioral_biometrics.study import identity, metrics, origin
from cyber_security.behavioral_biometrics.study.effects import DEFAULT, StudyEffects

USER_SPECIFIC_COUPLING_SUPPORTED = "USER_SPECIFIC_COUPLING_SUPPORTED"
DEVICE_BOUND_COUPLING_ONLY = "DEVICE_BOUND_COUPLING_ONLY"
USER_SPECIFIC_COUPLING_SMALL_EFFECT = "USER_SPECIFIC_COUPLING_SMALL_EFFECT"
HUMANNESS_SIGNAL_ONLY = "HUMANNESS_SIGNAL_ONLY"
SAMPLING_OR_CONTEXT_ARTIFACT = "SAMPLING_OR_CONTEXT_ARTIFACT"
COUPLING_NOT_SUPPORTED = "COUPLING_NOT_SUPPORTED"
USE_PATH_VERIFIED = "USE_PATH_VERIFIED"


def run_use(records: List[Dict[str, Any]], *, cfg: StudyEffects = DEFAULT,
            iters: Optional[int] = None, seed: int = 0) -> Dict[str, Any]:
    iters = iters if iters is not None else cfg.bootstrap_iters
    plan = splits.session_disjoint(records, seed=seed)
    arm_ids = ("MM", "MM_SHUFFLED", "MM_COUPLING", "MM_COUPLING_CONTEXT")
    res = {a: identity.run_arm(records, plan, a, cfg=cfg) for a in arm_ids}
    if not all(res[a].get("usable") for a in arm_ids):
        return {"usable": False, "reason": "arm_unusable"}
    labels = np.array(res["MM"]["labels"])
    groups = np.array(res["MM"]["groups"])

    def diff(a, b):
        return metrics.clustered_paired_auc_diff(
            np.array(res[a]["scores"]), np.array(res[b]["scores"]), labels, groups,
            iters=iters, alpha=cfg.effects.ci_alpha, seed=cfg.seed)

    out = {"usable": True,
           "arm_auc": {a: res[a]["metrics"]["auc"] for a in arm_ids},
           "gain_context_vs_marginal": diff("MM_COUPLING_CONTEXT", "MM"),
           "gain_context_vs_shuffled": diff("MM_COUPLING_CONTEXT", "MM_SHUFFLED"),
           "gain_raw_vs_marginal": diff("MM_COUPLING", "MM"),
           "false_challenge_increase": float(
               (1.0 - res["MM_COUPLING_CONTEXT"]["metrics"]["tar_at_far"])
               - (1.0 - res["MM"]["metrics"]["tar_at_far"]))}
    out["device"] = _device_diagnostic(records, cfg)
    return out


def _device_diagnostic(records, cfg) -> Dict[str, Any]:
    dev_plan = splits.device_instance(records)
    if not dev_plan.enroll:
        return {"assessable": False, "reason": dev_plan.notes or "no_second_device"}
    cross = identity.run_arm(records, dev_plan, "MM_COUPLING_CONTEXT", cfg=cfg)
    return {"assessable": True,
            "cross_device_auc": cross["metrics"]["auc"] if cross.get("usable") else None}


def classify_use(u: Dict[str, Any], cfg: StudyEffects = DEFAULT) -> str:
    if not u.get("usable"):
        return COUPLING_NOT_SUPPORTED
    e = cfg.effects
    g_mm = u["gain_context_vs_marginal"]
    g_shuf = u["gain_context_vs_shuffled"]
    beats_shuffle = g_shuf["lo"] > 0.0
    beats_marginal = g_mm["lo"] > 0.0
    dev = u.get("device", {})
    device_bound = (dev.get("assessable") and dev.get("cross_device_auc") is not None
                    and dev["cross_device_auc"] < e.min_marginal_auc
                    and beats_marginal)

    if not beats_shuffle and not beats_marginal:
        return COUPLING_NOT_SUPPORTED
    if not beats_shuffle:
        return SAMPLING_OR_CONTEXT_ARTIFACT          # gain not beyond the shuffle control
    if not beats_marginal:
        return HUMANNESS_SIGNAL_ONLY                 # coordination real, no identity gain
    if device_bound:
        return DEVICE_BOUND_COUPLING_ONLY
    if g_mm["lo"] > e.min_auc_improvement:
        return USER_SPECIFIC_COUPLING_SUPPORTED
    return USER_SPECIFIC_COUPLING_SMALL_EFFECT


def use_verdict(records: List[Dict[str, Any]], *, cfg: StudyEffects = DEFAULT,
                iters: Optional[int] = None) -> Dict[str, Any]:
    u = run_use(records, cfg=cfg, iters=iters)
    g = origin.guarded(records, scientific=lambda: classify_use(u, cfg),
                       path_verified=USE_PATH_VERIFIED, eligible=u.get("usable", False))
    g["analysis"] = u
    return g
