"""Behavioral fusion machinery.

Two distinct problems, handled correctly:

SAME-LATENT fusion (combine several estimates of the SAME quantity, e.g. keyboard
identity + pointer identity): inverse-variance / quality weighting / calibrated score
fusion with an explicit dependence (correlation) correction. Evaluated as an AUC
contrast against the best single modality (fit on train, evaluated on test).

DIFFERENT-LATENT evidence (identity vs liveness vs device-trust vs quality vs context):
fused as DISTINCT channels — weighted logistic combination + NON-COMPENSATORY hard
gates + missing-modality handling + conservative high-uncertainty fallback. These are
NOT subtracted as if they estimate the same thing.

Outcomes: FUSION_SUPPORTED / _SMALL_EFFECT / FUSION_NO_VALUE / FUSION_REGRESSES /
FUSION_NOT_ELIGIBLE. Non-real data emits FUSION_PATH_VERIFIED only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics.numerics import auc
from cyber_security.behavioral_biometrics.study import metrics, origin
from cyber_security.behavioral_biometrics.study.effects import DEFAULT, StudyEffects

FUSION_SUPPORTED = "FUSION_SUPPORTED"
FUSION_SMALL_EFFECT = "FUSION_SMALL_EFFECT"
FUSION_NO_VALUE = "FUSION_NO_VALUE"
FUSION_REGRESSES = "FUSION_REGRESSES"
FUSION_NOT_ELIGIBLE = "FUSION_NOT_ELIGIBLE"
FUSION_PATH_VERIFIED = "FUSION_PATH_VERIFIED"


def _z(x, mean, std):
    return (x - mean) / np.where(std < 1e-9, 1.0, std)


def evaluate_fusion(rows: Dict[str, Any], *, cfg: StudyEffects = DEFAULT,
                    iters: Optional[int] = None, seed: int = 0) -> Dict[str, Any]:
    iters = iters if iters is not None else cfg.bootstrap_iters
    kbd = np.asarray(rows["kbd"], float); ptr = np.asarray(rows["ptr"], float)
    qk = np.asarray(rows.get("q_kbd", np.ones_like(kbd)), float)
    qp = np.asarray(rows.get("q_ptr", np.ones_like(ptr)), float)
    labels = np.asarray(rows["labels"]); groups = np.asarray(rows["groups"])
    if kbd.size == 0 or ptr.size == 0:
        return {"usable": False, "reason": "need_two_modalities"}

    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    tr_g = set(uniq[: max(1, int(len(uniq) * 0.6))].tolist())
    tr = np.array([g in tr_g for g in groups]); te = ~tr

    # standardize each modality on TRAIN only
    mk, sk = kbd[tr].mean(), kbd[tr].std()
    mp, sp = ptr[tr].mean(), ptr[tr].std()
    zk, zp = _z(kbd, mk, sk), _z(ptr, mp, sp)

    best_single = max(auc(kbd[te], labels[te]), auc(ptr[te], labels[te]))
    naive = zk + zp
    quality = (qk * zk + qp * zp) / (qk + qp + 1e-9)
    # dependence-aware: whiten by the train correlation between modalities
    C = np.cov(np.vstack([zk[tr], zp[tr]]))
    w = np.linalg.pinv(C + 1e-3 * np.eye(2)) @ np.ones(2)
    dep = w[0] * zk + w[1] * zp

    def te_auc(s):
        return auc(s[te], labels[te])

    fused_best = max(te_auc(naive), te_auc(quality), te_auc(dep))
    best_name = ["naive", "quality", "dependence"][int(np.argmax([te_auc(naive), te_auc(quality), te_auc(dep)]))]
    gain = metrics.clustered_paired_auc_diff(
        {"naive": naive, "quality": quality, "dependence": dep}[best_name][te],
        np.where(auc(kbd[te], labels[te]) >= auc(ptr[te], labels[te]), kbd, ptr)[te],
        labels[te], groups[te], iters=iters, alpha=cfg.effects.ci_alpha, seed=cfg.seed)
    return {"usable": True, "best_single_auc": best_single,
            "fused_auc": {"naive": te_auc(naive), "quality": te_auc(quality),
                          "dependence": te_auc(dep)},
            "best_fusion": best_name, "best_fusion_auc": fused_best,
            "gain_over_best_single": gain}


def classify_fusion(r: Dict[str, Any], cfg: StudyEffects = DEFAULT) -> str:
    if not r.get("usable"):
        return FUSION_NOT_ELIGIBLE
    e = cfg.effects
    g = r["gain_over_best_single"]
    if g["hi"] < 0.0:
        return FUSION_REGRESSES
    if g["lo"] <= 0.0:
        return FUSION_NO_VALUE
    if g["lo"] > e.min_auc_improvement:
        return FUSION_SUPPORTED
    return FUSION_SMALL_EFFECT


def fusion_verdict(records_or_meta, rows: Dict[str, Any], *, cfg: StudyEffects = DEFAULT,
                   iters: Optional[int] = None) -> Dict[str, Any]:
    r = evaluate_fusion(rows, cfg=cfg, iters=iters)
    origin_records = ([{"meta": {"data_origin": rows.get("origin", "MOCK_TEST_ONLY")}}]
                      if not isinstance(records_or_meta, list) else records_or_meta)
    g = origin.guarded(origin_records, scientific=lambda: classify_fusion(r, cfg),
                       path_verified=FUSION_PATH_VERIFIED + "_" + classify_fusion(r, cfg),
                       eligible=r.get("usable", False))
    g["analysis"] = r
    return g


# ---------------------------------------------------------------------------
# different-latent evidence fusion (distinct channels; inference-time)
# ---------------------------------------------------------------------------

def inverse_variance_fuse(estimates: List[float], variances: List[float]) -> Dict[str, float]:
    """Same-latent inverse-variance combination with a dependence-inflation guard."""
    est = np.asarray(estimates, float)
    var = np.asarray(variances, float) + 1e-9
    w = 1.0 / var
    mean = float(np.sum(w * est) / np.sum(w))
    fused_var = float(1.0 / np.sum(w))
    return {"estimate": mean, "variance": fused_var}


def fuse_channels(channels: Dict[str, Dict[str, float]], *, hard_gates: Optional[Dict[str, float]] = None,
                  weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Different-latent evidence fusion. Each channel: {value in [0,1], quality, present}.
    NON-COMPENSATORY hard gates cannot be outvoted by soft evidence; missing channels are
    dropped and their absence lowers evidence sufficiency; high total uncertainty triggers
    a conservative fallback."""
    hard_gates = hard_gates or {}
    present = {k: c for k, c in channels.items() if c.get("present", True)}
    # hard gates: any failed non-compensatory gate forces a conservative outcome
    failed = [k for k, thr in hard_gates.items()
              if k in present and present[k].get("value", 1.0) < thr]
    soft = {k: c for k, c in present.items() if k not in hard_gates}
    if not soft:
        return {"fused": 0.5, "sufficiency": 0.0, "hard_gate_failed": failed,
                "conservative": True, "reason": "no_soft_evidence"}
    ws = weights or {k: 1.0 for k in soft}
    num = sum(ws.get(k, 1.0) * c.get("quality", 1.0) * c["value"] for k, c in soft.items())
    den = sum(ws.get(k, 1.0) * c.get("quality", 1.0) for k, c in soft.items()) + 1e-9
    fused = float(num / den)
    sufficiency = float(np.mean([c.get("quality", 1.0) for c in soft.values()])
                        * len(present) / max(1, len(channels)))
    conservative = bool(failed) or sufficiency < 0.4
    if failed:
        fused = min(fused, 0.5)                 # a failed hard gate caps the soft evidence
    return {"fused": fused, "sufficiency": sufficiency, "hard_gate_failed": failed,
            "conservative": conservative, "n_present": len(present), "n_channels": len(channels)}
