"""Deterministic MOCK_TEST_ONLY dataset library.

Named regimes that encode a KNOWN ground truth so each machinery branch can be
exercised. This is stub/fixture data for branch + integrity testing — NOT a biometric
dataset. Per MOCK_DATA_REGIMES.md, the point is to verify code paths, not to prove any
method works, and algorithms are NOT tuned to recover every regime perfectly.

Every produced record/fixture carries data_origin = MOCK_TEST_ONLY, so the verdict
layer can only ever emit *_PATH_VERIFIED / *_NO_SCIENTIFIC_VERDICT from it.

Families:
  * cohort      — feature-record cohorts (identity / coupling / confound / artifact regimes)
  * bcvf        — two-estimator rows (z, sigma) for BCVF branches
  * fusion      — per-modality score rows for fusion branches
  * confidence  — (score, label) fixtures for calibration branches
  * temporal    — score streams with a known change point for takeover branches
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

import numpy as np

from cyber_security.behavioral_biometrics.version import ORIGIN_MOCK, REAL_MARKER

_D = 6                      # marginal feature dimension per modality
_STATS = ("xcorr_max_abs", "xcorr_zero", "correlogram_peak", "cca_mean_corr")

COHORT_REGIMES = ("NO_SIGNAL", "KEYBOARD_ONLY_SIGNAL", "POINTER_ONLY_SIGNAL",
                  "MULTIMODAL_MARGINAL_SIGNAL", "COUPLING_ONLY_SIGNAL",
                  "COUPLING_PLUS_MARGINAL_SIGNAL", "DEVICE_CONFOUND", "TASK_CONFOUND",
                  "SAMPLING_ARTIFACT", "SPARSE_ACTIVITY")
BCVF_REGIMES = ("BCVF_HELPFUL", "BCVF_REDUNDANT", "BCVF_HARMFUL")
FUSION_REGIMES = ("FUSION_HELPFUL", "FUSION_REDUNDANT")
CONFIDENCE_REGIMES = ("CONFIDENCE_WELL_CALIBRATED", "CONFIDENCE_MISCALIBRATED")
TEMPORAL_REGIMES = ("ABRUPT_TAKEOVER", "SLOW_TAKEOVER", "LEGITIMATE_DRIFT")

ALL_REGIMES = (COHORT_REGIMES + BCVF_REGIMES + FUSION_REGIMES + CONFIDENCE_REGIMES
               + TEMPORAL_REGIMES)


def _seed(regime: str, seed: int) -> int:
    return int(hashlib.sha256(f"{regime}|{seed}".encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# feature-record cohorts
# ---------------------------------------------------------------------------

def _record(part, sid, device, task, role, cond, kbd, ptr, cr, cs, cc, *,
            kbd_avail=1.0, ptr_avail=1.0, n_events=320.0) -> Dict[str, Any]:
    marg = {}
    if kbd_avail:
        marg.update({f"kbd.f{i}": float(kbd[i]) for i in range(_D)})
    if ptr_avail:
        marg.update({f"ptr.f{i}": float(ptr[i]) for i in range(_D)})
    # cr/cs/cc are length-4 vectors (one independent value per coupling statistic)
    cr, cs, cc = np.atleast_1d(cr), np.atleast_1d(cs), np.atleast_1d(cc)
    cpl = {"coupling_available": 1.0}
    for i, st in enumerate(_STATS):
        cpl[st] = float(cr[i])
        cpl[st + "__shuf"] = float(cs[i])
        cpl[st + "__ctxm"] = float(cc[i])
    cpl["resid_vs_shuf"] = float(np.mean(cr - cs))
    cpl["resid_vs_ctxm"] = float(np.mean(cr - cc))
    quality = {"q.kbd_available": kbd_avail, "q.ptr_available": ptr_avail,
               "q.touch_available": 0.0, "q.motion_available": 0.0, "q.n_events": n_events,
               "q.span_s": 32.0}
    meta = {"participant_pseudonym": part, "session_id": sid, "device_id": device,
            "task_id": task, "trial_id": sid, "role": role, "condition": cond,
            "data_origin": ORIGIN_MOCK, "data_provenance": REAL_MARKER}
    return {"marginal": marg, "coupling": cpl, "quality": quality, "meta": meta}


_COHORT_CFG = {
    #                       kbd  ptr  cpl  dev  task couplingCtrlCarriesSignal sparse
    "NO_SIGNAL":            (0.0, 0.0, 0.0, 0.0, 0.0, False, False),
    "KEYBOARD_ONLY_SIGNAL": (1.6, 0.0, 0.0, 0.0, 0.0, False, False),
    "POINTER_ONLY_SIGNAL":  (0.0, 1.6, 0.0, 0.0, 0.0, False, False),
    "MULTIMODAL_MARGINAL_SIGNAL": (1.3, 1.3, 0.0, 0.0, 0.0, False, False),
    "COUPLING_ONLY_SIGNAL": (0.0, 0.0, 1.8, 0.0, 0.0, False, False),
    "COUPLING_PLUS_MARGINAL_SIGNAL": (1.2, 1.2, 1.5, 0.0, 0.0, False, False),
    "DEVICE_CONFOUND":      (0.2, 0.2, 0.0, 1.8, 0.0, False, False),
    "TASK_CONFOUND":        (0.2, 0.2, 0.0, 0.0, 1.8, False, False),
    "SAMPLING_ARTIFACT":    (0.0, 0.0, 1.8, 0.0, 0.0, True, False),
    "SPARSE_ACTIVITY":      (1.3, 1.3, 0.0, 0.0, 0.0, False, True),
}


def make_cohort(regime: str, *, n_participants: int = 12, sessions_per: int = 4,
                seed: int = 7, second_device: bool = True) -> Dict[str, Any]:
    kbd_s, ptr_s, cpl_s, dev_s, task_s, ctrl_signal, sparse = _COHORT_CFG[regime]
    rng = np.random.default_rng(_seed(regime, seed))
    parts = [f"mockP{i:02d}" for i in range(n_participants)]
    # per-user / per-device / per-task latent centers
    ukbd = {p: rng.normal(0, 1, _D) for p in parts}
    uptr = {p: rng.normal(0, 1, _D) for p in parts}
    ucpl = {p: rng.normal(0.0, 1.0, 4) for p in parts}   # 4-dim coupling identity
    devices = {p: [f"dev_{i:02d}_a", f"dev_{i:02d}_b"] for i, p in enumerate(parts)}
    dcenter = {d: rng.normal(0, 1, _D) for p in parts for d in devices[p]}
    tasks = ["taskA", "taskB"]
    tcenter = {t: rng.normal(0, 1, _D) for t in tasks}
    records: List[Dict[str, Any]] = []

    def vec(base_user, device, task, scale_u, scale_d, scale_t):
        v = scale_u * base_user + scale_d * dcenter[device] + scale_t * tcenter[task]
        return v + rng.normal(0, 0.5, _D)

    for pi, p in enumerate(parts):
        dev_list = devices[p][:2] if second_device else devices[p][:1]
        for s in range(sessions_per):
            device = dev_list[0] if (s < sessions_per - 1 or not second_device) else dev_list[1]
            task = tasks[s % 2] if regime == "TASK_CONFOUND" else "taskA"
            role = "enrollment" if s == 0 else "verification"
            kbd = vec(ukbd[p], device, task, kbd_s, dev_s, task_s)
            ptr = vec(uptr[p], device, task, ptr_s, dev_s, task_s)
            cr = cpl_s * ucpl[p] + rng.normal(0, 0.15, 4)          # real coupling (4-dim)
            cs = (cpl_s * ucpl[p] if ctrl_signal else 0.0) + rng.normal(0, 0.15, 4)  # shuffled ctrl
            cc = (cpl_s * ucpl[p] * 0.2) + rng.normal(0, 0.15, 4)  # context-matched ctrl
            n_ev = 120.0 if sparse else 320.0
            records.append(_record(p, f"{p}_s{s}", device, task, role, "genuine",
                                   kbd, ptr, cr, cs, cc, n_events=n_ev))
        # same-task same-device live impostor (a different actor labeled with target id)
        actor = parts[(pi + 1) % n_participants]
        kbd = vec(ukbd[actor], dev_list[0], "taskA", kbd_s, dev_s, task_s)
        ptr = vec(uptr[actor], dev_list[0], "taskA", ptr_s, dev_s, task_s)
        cr = cpl_s * ucpl[actor] + rng.normal(0, 0.15, 4)
        cs = (cpl_s * ucpl[actor] if ctrl_signal else 0.0) + rng.normal(0, 0.15, 4)
        cc = cpl_s * ucpl[actor] * 0.2 + rng.normal(0, 0.15, 4)
        records.append(_record(p, f"{p}_imp", dev_list[0], "taskA", "verification",
                               "live_impostor", kbd, ptr, cr, cs, cc))
    return {"kind": "cohort", "regime": regime, "origin": ORIGIN_MOCK, "records": records,
            "ground_truth": {"kbd": kbd_s, "ptr": ptr_s, "coupling": cpl_s,
                             "device_confound": dev_s, "task_confound": task_s,
                             "control_carries_signal": ctrl_signal}}


# ---------------------------------------------------------------------------
# BCVF two-estimator rows
# ---------------------------------------------------------------------------

def make_bcvf(regime: str, *, n: int = 400, seed: int = 7) -> Dict[str, Any]:
    rng = np.random.default_rng(_seed(regime, seed))
    labels = (rng.random(n) < 0.5).astype(int)
    groups = rng.integers(0, 12, n)
    # two estimators of the SAME latent identity (structurally distinct: kbd vs ptr)
    base = np.where(labels == 1, 1.0, -1.0)
    z1 = 0.8 * base + rng.normal(0, 0.9, n)
    z2 = 0.8 * base + rng.normal(0, 0.9, n)
    s1 = np.abs(rng.normal(0.9, 0.15, n))
    s2 = np.abs(rng.normal(0.9, 0.15, n))
    if regime == "BCVF_HELPFUL":
        # weaker joint estimators, but genuine users are highly CONSISTENT (small
        # |z1-z2|) while impostors disagree strongly -> disagreement adds real info.
        z1 = 0.5 * base + rng.normal(0, 0.9, n)
        z2 = z1 - np.where(labels == 1, rng.normal(0, 0.2, n), rng.normal(0, 2.4, n))
    elif regime == "BCVF_REDUNDANT":
        # disagreement carries no extra info beyond the (already strong) joint
        z1 = 1.5 * base + rng.normal(0, 0.6, n)
        z2 = 1.5 * base + rng.normal(0, 0.6, n)
    elif regime == "BCVF_HARMFUL":
        # disagreement is pure noise that, if used, dilutes the joint signal
        z2 = z1 + rng.normal(0, 2.0, n)
    return {"kind": "bcvf", "regime": regime, "origin": ORIGIN_MOCK,
            "rows": {"z1": z1.tolist(), "z2": z2.tolist(), "s1": s1.tolist(),
                     "s2": s2.tolist(), "labels": labels.tolist(), "groups": groups.tolist()}}


# ---------------------------------------------------------------------------
# fusion score rows
# ---------------------------------------------------------------------------

def make_fusion(regime: str, *, n: int = 800, seed: int = 7) -> Dict[str, Any]:
    rng = np.random.default_rng(_seed(regime, seed))
    labels = (rng.random(n) < 0.5).astype(int)
    groups = rng.integers(0, 24, n)
    base = np.where(labels == 1, 1.0, -1.0)
    if regime == "FUSION_HELPFUL":
        kbd = 0.55 * base + rng.normal(0, 1.0, n)    # each weak + INDEPENDENT noise
        ptr = 0.55 * base + rng.normal(0, 1.0, n)
    else:  # FUSION_REDUNDANT: shared noise -> fusion ~ best single
        shared = rng.normal(0, 1.0, n)
        kbd = 0.9 * base + shared + rng.normal(0, 0.2, n)
        ptr = 0.9 * base + shared + rng.normal(0, 0.2, n)
    q_kbd = np.abs(rng.normal(0.9, 0.1, n))
    q_ptr = np.abs(rng.normal(0.9, 0.1, n))
    return {"kind": "fusion", "regime": regime, "origin": ORIGIN_MOCK,
            "rows": {"kbd": kbd.tolist(), "ptr": ptr.tolist(), "q_kbd": q_kbd.tolist(),
                     "q_ptr": q_ptr.tolist(), "labels": labels.tolist(), "groups": groups.tolist()}}


# ---------------------------------------------------------------------------
# confidence (score, label) fixtures
# ---------------------------------------------------------------------------

def make_confidence(regime: str, *, n: int = 600, seed: int = 7) -> Dict[str, Any]:
    """The calibration split is CHRONOLOGICAL (first half fits, second half tests).
    WELL_CALIBRATED is stationary; MISCALIBRATED drifts to over-confidence in the test
    half so a calibrator fit on the first half under-corrects (held-out miscalibration)."""
    rng = np.random.default_rng(_seed(regime, seed))
    p_true = rng.beta(0.7, 0.7, n)                      # true P(genuine)
    labels = (rng.random(n) < p_true).astype(int)
    scores = p_true.copy()
    if regime == "CONFIDENCE_MISCALIBRATED":
        # held-out half drifts to CONSTANT over-confidence over UNINFORMATIVE labels:
        # no calibrator fit on the (informative) first half can rescue the test half.
        half = n // 2
        scores[half:] = 0.92
        labels[half:] = (rng.random(n - half) < 0.5).astype(int)
    return {"kind": "confidence", "regime": regime, "origin": ORIGIN_MOCK,
            "rows": {"scores": scores.tolist(), "labels": labels.tolist()}}


# ---------------------------------------------------------------------------
# temporal score streams
# ---------------------------------------------------------------------------

def make_temporal(regime: str, *, length: int = 200, onset: int = 120, seed: int = 7) -> Dict[str, Any]:
    rng = np.random.default_rng(_seed(regime, seed))
    x = rng.normal(0.0, 0.3, length)  # genuine baseline (higher = more genuine)
    change = None
    if regime == "ABRUPT_TAKEOVER":
        x[onset:] -= 3.0; change = onset
    elif regime == "SLOW_TAKEOVER":
        ramp = np.linspace(0, -3.0, length - onset); x[onset:] += ramp; change = onset
    elif regime == "LEGITIMATE_DRIFT":
        x += np.linspace(0, -1.0, length)  # gradual benign drift, no takeover
        change = None
    return {"kind": "temporal", "regime": regime, "origin": ORIGIN_MOCK,
            "stream": x.tolist(), "true_change": change, "onset": onset}


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

def generate(regime: str, *, seed: int = 7, **kw) -> Dict[str, Any]:
    if regime in COHORT_REGIMES:
        return make_cohort(regime, seed=seed, **kw)
    if regime in BCVF_REGIMES:
        return make_bcvf(regime, seed=seed, **kw)
    if regime in FUSION_REGIMES:
        return make_fusion(regime, seed=seed, **kw)
    if regime in CONFIDENCE_REGIMES:
        return make_confidence(regime, seed=seed, **kw)
    if regime in TEMPORAL_REGIMES:
        return make_temporal(regime, seed=seed, **kw)
    raise KeyError(f"unknown regime {regime!r}")
