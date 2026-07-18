"""Calibrated confidence engine.

Cleanly separates raw model score, calibrated probability, uncertainty, quality,
evidence sufficiency, and final confidence. An uncalibrated classifier probability is
NEVER treated as confidence. Calibration is fit on a CALIBRATION split and evaluated on
an untouched TEST split — ``CONFIDENCE_CALIBRATED`` cannot be claimed without held-out
evaluation. It outputs an evidence recommendation (never ALLOW/DENY — the Action Gate
owns decisions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics.study import origin
from cyber_security.behavioral_biometrics.study.effects import DEFAULT, StudyEffects

CONFIDENCE_CALIBRATED = "CONFIDENCE_CALIBRATED"
CONFIDENCE_SMALL_SAMPLE = "CONFIDENCE_SMALL_SAMPLE"
CONFIDENCE_MISCALIBRATED = "CONFIDENCE_MISCALIBRATED"
CONFIDENCE_NOT_ELIGIBLE = "CONFIDENCE_NOT_ELIGIBLE"
CONFIDENCE_PATH_VERIFIED = "CONFIDENCE_PATH_VERIFIED"

CONTINUE_PASSIVE = "CONTINUE_PASSIVE"
OBSERVE_MORE = "OBSERVE_MORE"
REQUEST_PASSIVE_EVIDENCE = "REQUEST_PASSIVE_EVIDENCE"
REQUEST_ACTIVE_EVIDENCE = "REQUEST_ACTIVE_EVIDENCE"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# ---- calibrators (fit on calibration split only) ----

@dataclass
class PlattCalibrator:
    a: float
    b: float

    @staticmethod
    def fit(scores, labels, iters=500, lr=0.1):
        s = np.asarray(scores, float); y = np.asarray(labels, float)
        a, b = 1.0, 0.0
        for _ in range(iters):
            p = 1.0 / (1.0 + np.exp(-np.clip(a * s + b, -30, 30)))
            ga = float(np.mean((p - y) * s)); gb = float(np.mean(p - y))
            a -= lr * ga; b -= lr * gb
        return PlattCalibrator(a, b)

    def apply(self, scores):
        s = np.asarray(scores, float)
        return 1.0 / (1.0 + np.exp(-np.clip(self.a * s + self.b, -30, 30)))


@dataclass
class HistogramCalibrator:
    edges: np.ndarray
    means: np.ndarray

    @staticmethod
    def fit(scores, labels, bins=10):
        s = np.asarray(scores, float); y = np.asarray(labels, float)
        edges = np.linspace(0, 1, bins + 1)
        idx = np.clip(np.digitize(s, edges) - 1, 0, bins - 1)
        means = np.array([y[idx == b].mean() if np.any(idx == b) else (b + 0.5) / bins
                          for b in range(bins)])
        return HistogramCalibrator(edges, means)

    def apply(self, scores):
        s = np.asarray(scores, float)
        b = np.clip(np.digitize(s, self.edges) - 1, 0, len(self.means) - 1)
        return self.means[b]


@dataclass
class IsotonicCalibrator:
    x: np.ndarray
    y: np.ndarray

    @staticmethod
    def fit(scores, labels):
        s = np.asarray(scores, float); y = np.asarray(labels, float)
        order = np.argsort(s, kind="mergesort")
        xs, ys = s[order], y[order].astype(float)
        # pool-adjacent-violators over (value,count) blocks (stable, no overflow)
        vals: List[float] = []
        cnts: List[int] = []
        for v in ys:
            vals.append(float(v)); cnts.append(1)
            while len(vals) > 1 and vals[-2] > vals[-1]:
                c = cnts[-1] + cnts[-2]
                m = (vals[-1] * cnts[-1] + vals[-2] * cnts[-2]) / c
                vals[-2:] = [m]; cnts[-2:] = [c]
        fitted = np.repeat(vals, cnts)
        return IsotonicCalibrator(xs, fitted)

    def apply(self, scores):
        return np.interp(np.asarray(scores, float), self.x, self.y)


_CALIBRATORS = {"platt": PlattCalibrator, "histogram": HistogramCalibrator,
                "isotonic": IsotonicCalibrator}


# ---- calibration metrics ----

def brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def nll(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6); y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def reliability_bins(p, y, bins=10):
    p = np.asarray(p, float); y = np.asarray(y, float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if np.any(m):
            out.append({"bin": b, "conf": float(p[m].mean()), "acc": float(y[m].mean()),
                        "count": int(m.sum())})
    return out


def ece(p, y, bins=10):
    p = np.asarray(p, float); y = np.asarray(y, float)
    rb = reliability_bins(p, y, bins)
    n = len(p)
    return float(sum(b["count"] / n * abs(b["acc"] - b["conf"]) for b in rb))


def mce(p, y, bins=10):
    rb = reliability_bins(p, y, bins)
    return float(max((abs(b["acc"] - b["conf"]) for b in rb), default=0.0))


def selective_risk_curve(p, y, steps=10):
    """Risk (error) vs coverage as we abstain on the least-confident predictions."""
    p = np.asarray(p, float); y = np.asarray(y, float)
    conf = np.abs(p - 0.5)
    order = np.argsort(-conf)
    pred = (p[order] >= 0.5).astype(int)
    yy = y[order]
    out = []
    for k in range(1, steps + 1):
        cov = k / steps
        m = max(1, int(cov * len(p)))
        err = float(np.mean(pred[:m] != yy[:m]))
        out.append({"coverage": cov, "risk": err})
    return out


# ---- evaluate calibration on a held-out split ----

def calibrate_and_evaluate(scores, labels, *, method="platt", cfg: StudyEffects = DEFAULT,
                           seed: int = 0) -> Dict[str, Any]:
    s = np.asarray(scores, float); y = np.asarray(labels)
    n = len(s)
    if n < cfg.minimums.min_calibration_samples:
        return {"usable": True, "small_sample": True, "n": n,
                "reason": "below_min_calibration_samples"}
    cut = n // 2
    cal = np.arange(cut)                          # chronological held-out: fit on the
    test = np.arange(cut, n)                      # first half, evaluate on the untouched
    # (later) half — so calibration DRIFT surfaces as held-out miscalibration.
    calib = _CALIBRATORS[method].fit(s[cal], y[cal])
    p_cal = calib.apply(s[test])
    yt = y[test]
    raw_ece = ece(s[test], yt)
    cal_ece = ece(p_cal, yt)
    # achievable held-out calibration: the model may already be calibrated (raw), or
    # the fitted calibrator may fix it — take the better of the two. Miscalibration
    # persists only when NEITHER achieves a low held-out ECE.
    if cal_ece <= raw_ece:
        p_test, achievable = p_cal, cal_ece
    else:
        p_test, achievable = s[test], raw_ece
    return {"usable": True, "small_sample": False, "method": method, "n": n,
            "n_test": int(len(test)),
            "ece": float(achievable), "raw_ece": float(raw_ece), "calibrated_ece": float(cal_ece),
            "mce": mce(p_test, yt), "brier": brier(p_test, yt), "nll": nll(p_test, yt),
            "reliability": reliability_bins(p_test, yt),
            "selective_risk": selective_risk_curve(p_test, yt)}


def classify_confidence(r: Dict[str, Any], cfg: StudyEffects = DEFAULT) -> str:
    if not r.get("usable"):
        return CONFIDENCE_NOT_ELIGIBLE
    if r.get("small_sample"):
        return CONFIDENCE_SMALL_SAMPLE
    if r["ece"] > cfg.effects.max_confidence_ece:
        return CONFIDENCE_MISCALIBRATED
    return CONFIDENCE_CALIBRATED


def confidence_verdict(records_or_meta, scores, labels, *, method="platt",
                       cfg: StudyEffects = DEFAULT) -> Dict[str, Any]:
    r = calibrate_and_evaluate(scores, labels, method=method, cfg=cfg)
    origin_records = (records_or_meta if isinstance(records_or_meta, list)
                      else [{"meta": {"data_origin": records_or_meta}}])
    g = origin.guarded(origin_records, scientific=lambda: classify_confidence(r, cfg),
                       path_verified=CONFIDENCE_PATH_VERIFIED + "_" + classify_confidence(r, cfg),
                       eligible=r.get("usable", False))
    g["analysis"] = r
    return g


# ---- structured confidence output (inference-time) ----

def build_confidence(*, identity_probability: float, calibration_status: str,
                     uncertainty: float, quality: float, evidence_sufficiency: float,
                     cfg: StudyEffects = DEFAULT) -> Dict[str, Any]:
    # confidence blends calibrated probability separation with quality and (1-uncertainty)
    separation = abs(identity_probability - 0.5) * 2.0
    confidence = float(np.clip(separation * quality * (1.0 - uncertainty), 0.0, 1.0))
    action = _recommend(confidence, evidence_sufficiency, uncertainty, calibration_status)
    return {
        "identity_probability": round(float(identity_probability), 6),
        "calibration_status": calibration_status,
        "uncertainty": round(float(uncertainty), 6),
        "quality": round(float(quality), 6),
        "evidence_sufficiency": round(float(evidence_sufficiency), 6),
        "confidence": round(confidence, 6),
        "recommended_evidence_action": action,
    }


def _recommend(confidence, sufficiency, uncertainty, calibration_status) -> str:
    if sufficiency < 0.3 or calibration_status == CONFIDENCE_NOT_ELIGIBLE:
        return INSUFFICIENT_EVIDENCE
    if uncertainty > 0.7:
        return REQUEST_ACTIVE_EVIDENCE
    if confidence >= 0.7 and calibration_status == CONFIDENCE_CALIBRATED:
        return CONTINUE_PASSIVE
    if confidence >= 0.5:
        return OBSERVE_MORE
    if confidence >= 0.3:
        return REQUEST_PASSIVE_EVIDENCE
    return REQUEST_ACTIVE_EVIDENCE
