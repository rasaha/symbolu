#!/usr/bin/env python3
"""Deterministic predictor-fault corpus (Part 4 §held-out fault families).

Generates SE(2) predictor-trajectory bundles ``(M, H, 3)`` with columns
``[x, y, theta]`` for 14 fault families plus a nominal baseline. Every bundle
is fully seeded and reproducible; nothing here is random at call time given a
seed.

Design goals (why this is separate from the kernel's own
``characterization/traces.py``):

  * The kernel's characterization set has 8 families; the milestone requires
    14. We reproduce the overlapping ones INDEPENDENTLY so the benchmark does
    not inherit the kernel's own generator assumptions, and add the missing
    ones (stuck, delayed, stale, correlated/common-mode, precise-biased,
    noisy-unbiased, calibration-drift, abrupt-jump, slow-bias).
  * Each bundle carries ground-truth a *safety* system needs — not just "which
    predictor is the outlier" but "is there a physically harmful state error,
    and when did it start" — so we can score detection recall, delay, and
    (critically) whether a fault is HARM-BEARING yet BCVF-INVISIBLE.

Ground-truth fields on every bundle:
  trajectories   (M, H, 3)
  truth_label    int | None    index of the faulty predictor (None = nominal
                               or common-mode with no single culprit)
  onset_tick     int | None    first tick the fault is active (for delay)
  fault_active   bool          is there a real fault a safety layer must catch?
  harm_class     str           harmful_state_error | benign | common_mode
  bcvf_visible   bool          does the fault, by BCVF's 2nd-order invariance,
                               produce a non-transient kernel signal at all?
  valid_masks    (M, H) bool | None   per-tick validity (freshness/missing)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

HARM_STATE = "harmful_state_error"
HARM_BENIGN = "benign"
HARM_COMMON = "common_mode"


@dataclass
class FaultBundle:
    family: str
    trajectories: np.ndarray  # (M, H, 3)
    truth_label: Optional[int]
    onset_tick: Optional[int]
    fault_active: bool
    harm_class: str
    bcvf_visible: bool
    valid_masks: Optional[np.ndarray] = None  # (M, H) bool
    metadata: Dict = field(default_factory=dict)


def _nominal(M: int, H: int, dt: float, v: float, seed: int,
             sigma: float = 0.01) -> np.ndarray:
    """M predictors tracking the same straight constant-velocity path."""
    rng = np.random.default_rng(seed)
    t = np.arange(H) * dt
    base = np.zeros((H, 3), dtype=np.float64)
    base[:, 0] = v * t  # x = v t
    trajs = np.repeat(base[None, :, :], M, axis=0)
    trajs += rng.normal(0.0, sigma, size=trajs.shape)
    return trajs


# --- Family generators. Each returns a FaultBundle. -----------------------

def f_gaussian_noise(M, H, dt, v, seed, sigma=0.05):
    trajs = _nominal(M, H, dt, v, seed, sigma=sigma)
    return FaultBundle("gaussian_noise", trajs, None, None, False, HARM_BENIGN,
                       bcvf_visible=False, metadata={"sigma": sigma})


def f_constant_bias(M, H, dt, v, seed, bias=0.5, target=1):
    trajs = _nominal(M, H, dt, v, seed)
    trajs[target, :, 1] += bias  # persistent lateral (y) offset
    # Harmful: robot's position estimate is permanently wrong by `bias` metres.
    # BCVF-invisible: constant offset -> zero 2nd difference (Lemma 1).
    return FaultBundle("constant_bias", trajs, target, 0, True, HARM_STATE,
                       bcvf_visible=False, metadata={"bias": bias})


def f_slow_bias(M, H, dt, v, seed, rate=0.02, target=1, onset=10):
    trajs = _nominal(M, H, dt, v, seed)
    t = np.arange(H)
    ramp = np.clip(t - onset, 0, None) * rate
    trajs[target, :, 1] += ramp  # slowly growing lateral bias (near-linear)
    # Harmful and mostly BCVF-invisible: a linear ramp has ~zero 2nd diff
    # except a one-tick transient at onset.
    return FaultBundle("slow_bias", trajs, target, onset, True, HARM_STATE,
                       bcvf_visible=False, metadata={"rate": rate})


def f_linear_drift(M, H, dt, v, seed, rate=0.05, target=1):
    trajs = _nominal(M, H, dt, v, seed)
    t = np.arange(H)
    trajs[target, :, 1] += rate * t  # constant-velocity divergence
    return FaultBundle("linear_drift", trajs, target, 0, True, HARM_STATE,
                       bcvf_visible=False, metadata={"rate": rate})


def f_accelerating(M, H, dt, v, seed, accel=0.5, target=1, onset=5):
    trajs = _nominal(M, H, dt, v, seed)
    t = np.arange(H) * dt
    ramp = np.where(np.arange(H) >= onset, 0.5 * accel * (t - onset * dt) ** 2, 0.0)
    trajs[target, :, 1] += ramp
    # Harmful AND BCVF-visible: quadratic divergence has non-zero 2nd diff.
    return FaultBundle("accelerating", trajs, target, onset, True, HARM_STATE,
                       bcvf_visible=True, metadata={"accel": accel})


def f_abrupt_jump(M, H, dt, v, seed, jump=0.8, target=1, onset=25):
    trajs = _nominal(M, H, dt, v, seed)
    trajs[target, onset:, 1] += jump  # step change
    # Harmful; BCVF sees only a ONE-TICK transient spike at the jump edge,
    # then invariant (constant offset thereafter).
    return FaultBundle("abrupt_jump", trajs, target, onset, True, HARM_STATE,
                       bcvf_visible=True, metadata={"jump": jump, "transient_only": True})


def f_stuck_sensor(M, H, dt, v, seed, onset=15, target=1):
    trajs = _nominal(M, H, dt, v, seed)
    trajs[target, onset:, :] = trajs[target, onset, :]  # freeze at onset value
    # Harmful; while others move at constant velocity the disagreement grows
    # LINEARLY -> BCVF 2nd-order invariant after the onset transient.
    return FaultBundle("stuck_sensor", trajs, target, onset, True, HARM_STATE,
                       bcvf_visible=False, metadata={"note": "freeze -> linear disagreement"})


def f_delayed_predictor(M, H, dt, v, seed, lag=6, target=1):
    trajs = _nominal(M, H, dt, v, seed)
    src = trajs[target].copy()
    trajs[target, lag:, :] = src[:-lag, :]
    trajs[target, :lag, :] = src[0, :]
    # A pure time lag of a constant-velocity path = constant spatial offset ->
    # harmful (lags reality) but BCVF-invariant.
    return FaultBundle("delayed_predictor", trajs, target, 0, True, HARM_STATE,
                       bcvf_visible=False, metadata={"lag": lag})


def f_stale_predictor(M, H, dt, v, seed, onset=20, target=2):
    trajs = _nominal(M, H, dt, v, seed)
    trajs[target, onset:, :] = trajs[target, onset, :]  # stops updating
    masks = np.ones((M, H), dtype=bool)
    masks[target, onset:] = False  # freshness signal available to a good detector
    return FaultBundle("stale_predictor", trajs, target, onset, True, HARM_STATE,
                       bcvf_visible=False, valid_masks=masks,
                       metadata={"note": "freshness observable via valid_masks"})


def f_correlated_failure(M, H, dt, v, seed, bias=0.5, targets=(1, 2)):
    trajs = _nominal(M, H, dt, v, seed)
    for tgt in targets:
        trajs[tgt, :, 1] += bias  # same bias on 2 predictors (common-mode pair)
    # Two predictors share a fault: majority/consensus is corrupted. No single
    # culprit -> truth_label None. BCVF may mis-attribute to the honest one.
    return FaultBundle("correlated_failure", trajs, None, 0, True, HARM_STATE,
                       bcvf_visible=False, metadata={"targets": list(targets)})


def f_all_wrong(M, H, dt, v, seed, drift=0.05):
    trajs = _nominal(M, H, dt, v, seed)
    t = np.arange(H)
    for m in range(M):
        trajs[m, :, 1] += drift * t  # every predictor drifts identically
    # All predictors agree with each other but disagree with REALITY. Zero
    # cross-predictor disagreement -> undetectable by ANY disagreement-only
    # method (BCVF or consensus-residual). A good detector must ABSTAIN.
    return FaultBundle("all_wrong", trajs, None, 0, True, HARM_COMMON,
                       bcvf_visible=False, metadata={"note": "no cross-disagreement"})


def f_precise_biased(M, H, dt, v, seed, bias=0.4, target=1):
    trajs = _nominal(M, H, dt, v, seed, sigma=0.05)
    trajs[target] = _nominal(1, H, dt, v, seed + 99, sigma=0.005)[0]  # very low noise
    trajs[target, :, 1] += bias  # but constant lateral bias
    # The most "confident-looking" predictor is systematically wrong. Harmful,
    # BCVF-invariant (constant offset).
    return FaultBundle("precise_biased", trajs, target, 0, True, HARM_STATE,
                       bcvf_visible=False, metadata={"bias": bias})


def f_noisy_unbiased(M, H, dt, v, seed, sigma=0.15, target=1):
    trajs = _nominal(M, H, dt, v, seed)
    rng = np.random.default_rng(seed + 7)
    trajs[target] += rng.normal(0.0, sigma, size=trajs[target].shape)  # zero-mean
    # NOT a fault: high-variance but unbiased. A safety system must NOT flag it
    # (false-alarm test). But its high spread can trip naive detectors.
    return FaultBundle("noisy_unbiased", trajs, None, None, False, HARM_BENIGN,
                       bcvf_visible=True, metadata={"sigma": sigma,
                                                    "note": "benign; false-alarm probe"})


def f_calibration_drift(M, H, dt, v, seed, target=1, onset=20):
    trajs = _nominal(M, H, dt, v, seed, sigma=0.02)
    rng = np.random.default_rng(seed + 13)
    growth = np.clip(np.arange(H) - onset, 0, None) / max(1, (H - onset))
    extra = rng.normal(0.0, 1.0, size=(H, 3)) * (0.2 * growth)[:, None]
    trajs[target] += extra  # variance grows over time; mean stays ~0
    # Uncertainty calibration degrades but the estimate stays unbiased -> a
    # method that ignores reported uncertainty cannot distinguish this from a
    # real fault. Classified benign-but-uncertain.
    return FaultBundle("calibration_drift", trajs, None, onset, False, HARM_BENIGN,
                       bcvf_visible=True, metadata={"note": "variance grows, mean unbiased"})


FAMILIES = {
    "gaussian_noise": f_gaussian_noise,
    "constant_bias": f_constant_bias,
    "slow_bias": f_slow_bias,
    "linear_drift": f_linear_drift,
    "accelerating": f_accelerating,
    "abrupt_jump": f_abrupt_jump,
    "stuck_sensor": f_stuck_sensor,
    "delayed_predictor": f_delayed_predictor,
    "stale_predictor": f_stale_predictor,
    "correlated_failure": f_correlated_failure,
    "all_wrong": f_all_wrong,
    "precise_biased": f_precise_biased,
    "noisy_unbiased": f_noisy_unbiased,
    "calibration_drift": f_calibration_drift,
}

# Held-out split: TUNE families are for any threshold selection; TEST families
# are evaluation-only. No family appears in both. Thresholds are frozen in the
# preregistration BEFORE the TEST families are scored.
TUNE_FAMILIES = ["gaussian_noise", "constant_bias", "linear_drift",
                 "accelerating", "noisy_unbiased"]
TEST_FAMILIES = ["slow_bias", "abrupt_jump", "stuck_sensor", "delayed_predictor",
                 "stale_predictor", "correlated_failure", "all_wrong",
                 "precise_biased", "calibration_drift"]


def generate(family: str, M: int = 3, H: int = 50, dt: float = 0.1,
             base_velocity: float = 5.0, seed: int = 0, **params) -> FaultBundle:
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; known={sorted(FAMILIES)}")
    return FAMILIES[family](M, H, dt, base_velocity, seed, **params)


def corpus(families: List[str], seeds: int = 20, **kw) -> List[FaultBundle]:
    out = []
    for fam in families:
        for s in range(seeds):
            out.append(generate(fam, seed=s, **kw))
    return out


if __name__ == "__main__":
    # Smoke: every family generates with the declared shape + labels.
    for fam in FAMILIES:
        b = generate(fam, seed=0)
        assert b.trajectories.shape == (3, 50, 3), (fam, b.trajectories.shape)
        assert np.all(np.isfinite(b.trajectories)), fam
        print(f"{fam:20s} truth={str(b.truth_label):>4} onset={str(b.onset_tick):>4} "
              f"fault={int(b.fault_active)} harm={b.harm_class:20s} "
              f"bcvf_visible={int(b.bcvf_visible)}")
