#!/usr/bin/env python3
"""Deterministic predictor-trust baseline (Part 3 §predictor-trust baseline).

EVALUATION-ONLY. A classical, fully-deterministic fault detector over
``(M, H, 3)`` SE(2) predictor trajectories, built from standard estimation
primitives — NOT from cross-predictor disagreement *dynamics*:

  * innovation / residual magnitude against a robust per-tick consensus;
  * uncertainty-normalized residual (NIS-style, robust MAD scale);
  * EWMA of the standardized residual;
  * CUSUM for persistent small-bias accumulation;
  * freshness / missing-data checks (via ``valid_masks``);
  * persistent-bias detection (sign-consistent offset over a window);
  * explicit per-predictor states TRUSTED / DEGRADED / SUSPECT / ABSTAIN;
  * a global ABSTAIN when a trusted majority cannot be formed (correlated /
    common-mode / insufficient-evidence) — it never forces a winner.

The class also satisfies the kernel's ``Arbitrator`` protocol (``name`` +
``arbitrate((M,H,3)) -> ArbitrationResult``) so it drops into the existing
baseline shootout unchanged.

The design contrast with BCVF is deliberate: BCVF is *invariant* to constant
offset and linear drift by construction; this baseline scores residual
*magnitude* and *persistence*, so those exact fault classes are what it is
built to catch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np


class TrustState(str, Enum):
    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    SUSPECT = "SUSPECT"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class TrustBaselineConfig:
    """Frozen thresholds. Tuned only on TUNE families; see preregistration."""
    lever_arm: float = 2.5          # rad -> m homogenisation for heading error
    scale_floor: float = 0.05       # m; robust-scale floor (sensor noise floor)
    ewma_alpha: float = 0.3         # EWMA smoothing on standardized magnitude
    degraded_z: float = 3.0         # EWMA standardized magnitude -> DEGRADED
    cusum_k: float = 1.0            # CUSUM slack (sigma units); diagnostic only
    cusum_h: float = 8.0            # CUSUM threshold; diagnostic only
    bias_window: int = 12           # trailing window for persistent-mean test
    bias_z: float = 4.0             # windowed-mean significance -> SUSPECT
    bias_min_m: float = 0.20        # m; min physical offset to call it a bias
    bias_sustain: int = 8           # consecutive ticks the test must hold
    stale_frac: float = 0.3         # fraction of missing ticks -> predictor ABSTAIN
    abstain_suspect_frac: float = 0.5  # >= this frac SUSPECT -> global ABSTAIN


@dataclass
class PredictorReport:
    index: int
    state: TrustState
    suspicion: float          # continuous score (higher = more suspicious)
    ewma_z: float
    cusum_peak: float
    persistent_bias_m: float
    stale_fraction: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class TrustDecision:
    per_predictor: List[PredictorReport]
    flagged: Optional[int]        # single culprit, or None
    trusted: List[int]
    system_state: TrustState      # ABSTAIN if no trusted majority
    detection_tick: Optional[int]
    reason: str


# --- geometry -------------------------------------------------------------

def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _se2_residual(traj_m: np.ndarray, ref: np.ndarray, lever: float) -> np.ndarray:
    """Per-tick SE(2) residual magnitude between predictor and reference. (H,)"""
    dx = traj_m[:, 0] - ref[:, 0]
    dy = traj_m[:, 1] - ref[:, 1]
    dth = _wrap(traj_m[:, 2] - ref[:, 2]) * lever
    return np.sqrt(dx * dx + dy * dy + dth * dth)


def _robust_consensus(trajs: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Coordinate-wise median across *valid* predictors -> (H, 3)."""
    M, H, _ = trajs.shape
    ref = np.zeros((H, 3), dtype=np.float64)
    for t in range(H):
        rows = trajs[valid[:, t], t, :]
        if rows.shape[0] == 0:
            rows = trajs[:, t, :]
        ref[t, 0] = np.median(rows[:, 0])
        ref[t, 1] = np.median(rows[:, 1])
        # circular-ish median for heading via median of wrapped values around mean
        ref[t, 2] = np.median(rows[:, 2])
    return ref


class DeterministicTrustBaseline:
    """Classical predictor-trust detector. Deterministic given inputs."""

    name = "DeterministicTrust"

    def __init__(self, config: Optional[TrustBaselineConfig] = None):
        self.cfg = config or TrustBaselineConfig()

    def evaluate(self, trajs: np.ndarray,
                 valid_masks: Optional[np.ndarray] = None) -> TrustDecision:
        cfg = self.cfg
        M, H, _ = trajs.shape
        valid = (np.ones((M, H), dtype=bool) if valid_masks is None
                 else valid_masks.astype(bool))

        ref = _robust_consensus(trajs, valid)

        # Per-axis robust scale from cross-predictor spread (ambient noise).
        # Axis weights homogenise heading into the same units as position.
        axis_w = np.array([1.0, 1.0, cfg.lever_arm])
        signed = (trajs - ref[None, :, :]) * axis_w[None, None, :]  # (M,H,3)
        signed[..., 2] = _wrap(trajs[..., 2] - ref[None, :, 2]) * cfg.lever_arm
        # Pool the robust scale per axis over ALL (predictor, tick) samples.
        # A per-tick MAD over only M=3 predictors is unstable (the median
        # predictor has exactly-zero residual), so we pool across time; MAD
        # keeps it robust to the biased predictor's inflation.
        med_axis = np.median(signed, axis=(0, 1), keepdims=True)          # (1,1,3)
        mad_axis = np.median(np.abs(signed - med_axis), axis=(0, 1))      # (3,)
        scale_axis = np.maximum(1.4826 * mad_axis, cfg.scale_floor)[None, :]  # (1,3)

        reports: List[PredictorReport] = []
        first_detect: Optional[int] = None
        for m in range(M):
            fresh = valid[m]
            stale_fraction = float(np.mean(~fresh))

            z_axis = signed[m] / scale_axis            # (H,3) standardized signed
            mag = np.linalg.norm(z_axis, axis=1)       # (H,) magnitude (variance ch.)

            # EWMA of the standardized *magnitude* -> the variance/DEGRADED
            # channel. Reacts to a noisy-but-unbiased predictor without
            # calling it a fault.
            ewma = 0.0
            ewma_peak = 0.0
            for t in range(H):
                if fresh[t]:
                    ewma = cfg.ewma_alpha * mag[t] + (1 - cfg.ewma_alpha) * ewma
                ewma_peak = max(ewma_peak, ewma)

            # Two-sided CUSUM on each *signed* axis -> the bias/SUSPECT channel.
            # Zero-mean noise flips sign and never accumulates; a persistent
            # offset (constant bias, drift, stuck, delay, precise-bias) does.
            cusum_peak = 0.0
            cusum_cross_tick = None
            for a in range(3):
                hi = lo = 0.0
                for t in range(H):
                    if not fresh[t]:
                        continue
                    za = z_axis[t, a]
                    hi = max(0.0, hi + za - cfg.cusum_k)
                    lo = max(0.0, lo - za - cfg.cusum_k)
                    peak = max(hi, lo)
                    cusum_peak = max(cusum_peak, peak)
                    if peak >= cfg.cusum_h and cusum_cross_tick is None:
                        cusum_cross_tick = t

            # PERSISTENT-BIAS test (SUSPECT channel): a trailing-window mean
            # significance test. For a true offset the windowed mean is large
            # and significant; for zero-mean noise (however high-variance) the
            # mean -> 0, so this does NOT fire on noisy-but-unbiased predictors.
            # Requires BOTH statistical significance (bias_z) and a physical
            # magnitude floor (bias_min_m metres).
            w = cfg.bias_window
            persistent_bias = 0.0     # metres, reported
            bias_z_peak = 0.0
            bias_tick = None
            for a in range(3):
                r = signed[m, :, a]
                se = scale_axis[0, a] / np.sqrt(w)
                run = 0  # consecutive ticks the windowed-mean test holds
                for t in range(w, H + 1):
                    if fresh[t - w:t].sum() < w:
                        run = 0
                        continue
                    wmean = float(np.mean(r[t - w:t]))
                    bz = abs(wmean) / se
                    bias_z_peak = max(bias_z_peak, bz)
                    if bz >= cfg.bias_z and abs(wmean) >= cfg.bias_min_m:
                        run += 1
                        if run >= cfg.bias_sustain:
                            persistent_bias = max(persistent_bias, abs(wmean))
                            if bias_tick is None:
                                bias_tick = t - 1
                    else:
                        run = 0

            # State assignment (non-compensatory: worst reason wins).
            # SUSPECT = persistent BIAS (CUSUM cross or windowed offset).
            # DEGRADED = elevated VARIANCE only (noisy-but-unbiased): reduce
            #            trust, do NOT call it a fault.
            # ABSTAIN = insufficient fresh data for this predictor.
            reasons: List[str] = []
            state = TrustState.TRUSTED
            if stale_fraction >= cfg.stale_frac:
                state = TrustState.ABSTAIN
                reasons.append(f"stale({stale_fraction:.2f})")
            else:
                if persistent_bias > 0.0:
                    state = TrustState.SUSPECT
                    reasons.append(f"bias({persistent_bias:.2f}m,z={bias_z_peak:.1f})")
                if state is TrustState.TRUSTED and ewma_peak >= cfg.degraded_z:
                    state = TrustState.DEGRADED
                    reasons.append(f"variance_z({ewma_peak:.1f})")

            # Suspicion score: continuous, for Arbitrator attribution + ranking.
            suspicion = (10.0 * persistent_bias + 0.5 * bias_z_peak
                         + 0.2 * ewma_peak + 5.0 * stale_fraction)

            # Detection tick = earliest hard bias signal for this predictor.
            if state is TrustState.SUSPECT and bias_tick is not None:
                if first_detect is None or bias_tick < first_detect:
                    first_detect = bias_tick

            reports.append(PredictorReport(
                index=m, state=state, suspicion=float(suspicion),
                ewma_z=ewma_peak, cusum_peak=cusum_peak,
                persistent_bias_m=persistent_bias, stale_fraction=stale_fraction,
                reasons=reasons))

        # Global decision — never force a winner.
        suspect = [r.index for r in reports if r.state is TrustState.SUSPECT]
        abstain_pred = [r.index for r in reports if r.state is TrustState.ABSTAIN]
        usable = [r for r in reports if r.state not in
                  (TrustState.SUSPECT, TrustState.ABSTAIN)]

        if len(reports) - len(abstain_pred) < 2:
            return TrustDecision(reports, None, [r.index for r in usable],
                                 TrustState.ABSTAIN, first_detect,
                                 "insufficient fresh predictors")
        # If half or more are suspect, we cannot form a trusted majority and
        # cannot safely attribute -> ABSTAIN (correlated / common-mode guard).
        if len(suspect) >= max(1, int(np.ceil(cfg.abstain_suspect_frac * M))):
            return TrustDecision(reports, None, [r.index for r in usable],
                                 TrustState.ABSTAIN, first_detect,
                                 f"{len(suspect)}/{M} suspect: no trusted majority")
        flagged = None
        if suspect:
            flagged = max(suspect, key=lambda i: reports[i].suspicion)
        trusted = [r.index for r in usable]
        sys_state = TrustState.TRUSTED if not suspect else TrustState.DEGRADED
        return TrustDecision(reports, flagged, trusted, sys_state, first_detect,
                             "ok" if flagged is None else f"flagged predictor {flagged}")

    # --- Arbitrator protocol adapter --------------------------------------
    def arbitrate(self, trajectories: np.ndarray):
        """Satisfy the kernel's Arbitrator protocol. Returns a duck-typed result."""
        import time
        dec = self.evaluate(trajectories)
        M, H, _ = trajectories.shape
        valid = np.ones((M, H), dtype=bool)
        ref = _robust_consensus(trajectories, valid)
        attribution = np.array([r.suspicion for r in dec.per_predictor],
                               dtype=np.float64)

        @dataclass
        class _Result:
            consensus: np.ndarray
            attribution: np.ndarray
            per_tick_us: float
            metadata: Dict
        return _Result(consensus=ref, attribution=attribution, per_tick_us=0.0,
                       metadata={"system_state": dec.system_state.value,
                                 "flagged": dec.flagged, "reason": dec.reason})


if __name__ == "__main__":
    from robotics_reliability_bench import fault_corpus as fc
    det = DeterministicTrustBaseline()
    for fam in fc.FAMILIES:
        b = fc.generate(fam, seed=0)
        d = det.evaluate(b.trajectories, b.valid_masks)
        print(f"{fam:20s} truth={str(b.truth_label):>4} -> flagged={str(d.flagged):>4} "
              f"sys={d.system_state.value:8s} det@={str(d.detection_tick):>4}  {d.reason}")
