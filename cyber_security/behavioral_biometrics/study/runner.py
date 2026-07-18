"""End-to-end study orchestration.

Runs the complete machinery on a cohort of feature records (mock or, later, real):
eligibility → leakage-safe splits → train-only fits → modality/marginal baselines →
coupling(USE) → BCVF → fusion → confidence calibration (held-out) → paired contrasts →
practical thresholds → machine-readable report → claim lock by origin.

On non-real data every scientific verdict is replaced by a *_PATH_VERIFIED test outcome
and the report carries the TEST-DATA banner.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import splits
from cyber_security.behavioral_biometrics.study import (
    arms,
    bcvf,
    confidence,
    effects,
    fusion,
    identity,
    metrics,
    origin,
    report,
    temporal,
    use_eval,
)
from cyber_security.behavioral_biometrics.study.effects import StudyEffects


def _standardize(v):
    v = np.asarray(v, float)
    s = v.std()
    return (v - v.mean()) / s if s > 1e-9 else v - v.mean()


def _estimator_and_fusion_rows(records, plan, cfg):
    """Derive keyboard/pointer identity estimators (for BCVF) and per-modality score
    rows (for fusion) from the same split. Uncertainty is a documented proxy."""
    K = identity.run_arm(records, plan, "K", cfg=cfg)
    P = identity.run_arm(records, plan, "P", cfg=cfg)
    if not (K.get("usable") and P.get("usable")):
        return None, None, {"K": K.get("usable", False), "P": P.get("usable", False)}
    z1 = _standardize(K["scores"]); z2 = _standardize(P["scores"])
    labels = K["labels"]; groups = K["groups"]
    n = len(z1)
    bcvf_rows = {"z1": z1.tolist(), "z2": z2.tolist(),
                 "s1": np.ones(n).tolist(), "s2": np.ones(n).tolist(),
                 "labels": labels, "groups": groups}
    fusion_rows = {"kbd": K["scores"], "ptr": P["scores"],
                   "q_kbd": np.ones(n).tolist(), "q_ptr": np.ones(n).tolist(),
                   "labels": labels, "groups": groups}
    return bcvf_rows, fusion_rows, {"K_auc": K["metrics"]["auc"], "P_auc": P["metrics"]["auc"]}


def _eligibility(records, cfg: StudyEffects) -> Dict[str, Any]:
    by_p: Dict[str, int] = {}
    genuine = impostor = 0
    for r in records:
        m = r["meta"]
        by_p[m["participant_pseudonym"]] = by_p.get(m["participant_pseudonym"], 0) + 1
        if m.get("condition") == "live_impostor":
            impostor += 1
        else:
            genuine += 1
    mn = cfg.minimums
    checks = {
        "participants": (len(by_p), mn.min_participants, len(by_p) >= mn.min_participants),
        "sessions_per_participant": (min(by_p.values()) if by_p else 0,
                                     mn.min_sessions_per_participant,
                                     (min(by_p.values()) if by_p else 0) >= mn.min_sessions_per_participant),
        "genuine_trials": (genuine, mn.min_genuine_trials, genuine >= mn.min_genuine_trials),
        "impostor_trials": (impostor, mn.min_impostor_trials, impostor >= mn.min_impostor_trials),
    }
    return {"met": all(c[2] for c in checks.values()),
            "checks": {k: {"value": v[0], "required": v[1], "ok": v[2]} for k, v in checks.items()}}


def run_study(records: List[Dict[str, Any]], *, cfg: StudyEffects = effects.DEFAULT,
              iters: Optional[int] = None, temporal_fixture: Optional[Dict[str, Any]] = None,
              config: Optional[Dict[str, Any]] = None, seed: int = 0) -> Dict[str, Any]:
    iters = iters if iters is not None else cfg.bootstrap_iters
    lock = origin.claim_lock(records)
    sections: Dict[str, Any] = {"prereg": config or {}, "claim_lock": lock,
                                "eligibility": _eligibility(records, cfg)}

    plan = splits.session_disjoint(records, seed=seed)
    sections["leakage_check"] = splits.check_leakage(plan, records)

    # marginal / multimodal / coupling arms (fair ablation on one split)
    ablation = identity.run_ablation(records, plan, cfg=cfg)
    sections["identity_ablation"] = {a: (r["metrics"] if r.get("usable") else r)
                                     for a, r in ablation.items()}

    # coupling / USE
    sections["use"] = use_eval.use_verdict(records, cfg=cfg, iters=iters)

    # BCVF + fusion (derived estimators)
    bcvf_rows, fusion_rows, est_info = _estimator_and_fusion_rows(records, plan, cfg)
    sections["estimators"] = est_info
    if bcvf_rows is not None:
        sections["bcvf"] = bcvf.bcvf_verdict(records, bcvf_rows, cfg=cfg, iters=iters)
        sections["fusion"] = fusion.fusion_verdict(records, fusion_rows, cfg=cfg, iters=iters)
    else:
        sections["bcvf"] = {"verdict": bcvf.BCVF_NOT_ELIGIBLE, "note": "estimators unusable"}
        sections["fusion"] = {"verdict": fusion.FUSION_NOT_ELIGIBLE, "note": "estimators unusable"}

    # confidence calibration on the MM arm (held-out)
    mm = ablation.get("MM", {})
    if mm.get("usable"):
        probs = 1.0 / (1.0 + np.exp(-_standardize(mm["scores"])))
        sections["confidence"] = confidence.confidence_verdict(records, probs, mm["labels"], cfg=cfg)
    else:
        sections["confidence"] = {"verdict": confidence.CONFIDENCE_NOT_ELIGIBLE}

    # confound gates
    sections["confounds"] = _confounds(records, cfg)

    # temporal (optional; diagnostic only)
    if temporal_fixture is not None:
        sections["temporal"] = temporal.temporal_verdict(records, temporal_fixture)

    return report.assemble(records, sections, cfg)


def _confounds(records, cfg) -> Dict[str, Any]:
    out = {}
    dev = splits.device_instance(records)
    if dev.enroll:
        r = identity.run_arm(records, dev, "MM", cfg=cfg)
        out["device_disjoint_mm_auc"] = r["metrics"]["auc"] if r.get("usable") else None
    else:
        out["device_disjoint"] = "not_assessable"
    task = splits.task_disjoint(records)
    if task.enroll:
        r = identity.run_arm(records, task, "MM", cfg=cfg)
        out["task_disjoint_mm_auc"] = r["metrics"]["auc"] if r.get("usable") else None
    else:
        out["task_disjoint"] = "not_assessable"
    return out
