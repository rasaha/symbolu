#!/usr/bin/env python3
"""LLT-Kalman predictor-trust variant (evaluation-only, cross-domain port).

EVALUATION-ONLY. A second deterministic predictor-trust detector over
``(M, H, 3)`` SE(2) predictor trajectories that keeps the baseline's state
machine (TRUSTED / DEGRADED / SUSPECT / ABSTAIN) and global abstain rules
verbatim, but replaces the baseline's *statistics* with a per-axis
local-linear-trend (LLT) Kalman filter:

  baseline (``predictor_trust_baseline``)      this module
  ------------------------------------------   ------------------------------------
  pooled robust-MAD scale over all predictors  per-predictor, per-axis observation
                                               noise from robust first differences
  EWMA of standardized magnitude (variance)    one-sided CUSUM on the Kalman
                                               normalized-innovation surprise
  trailing-window mean significance (bias)     Kalman level state vs its own
                                               posterior variance (true NIS-style)

The temporal channel mirrors ``cyber_security/kill_study/detectors.py::
llt_cusum_raw`` (state ``[level, slope]``, ``F=[[1,1],[0,1]]``, ``H=[1,0]``,
missing observations -> predict only). That channel is what beat the
second-order BCVF term in the cyber kill study (arm I vs arm H); this module
tests whether the same machinery sharpens the robotics baseline.

Channel-to-state mapping is deliberately identical to the baseline so the two
are comparable under the frozen metric set:

  * SUSPECT  = persistent BIAS: the filtered level is both statistically
               significant (|level| / sqrt(P_level) >= bias_z) and physically
               material (|level| >= bias_min_m) for ``bias_sustain``
               consecutive fresh ticks.  Zero-mean noise, however large,
               has level -> 0 and does NOT fire this channel.
  * DEGRADED = the innovation CUSUM crossed ``cusum_h`` but no bias was
               confirmed (variance / change without a persistent offset).
               Reduces trust; is NOT a fault detection.
  * ABSTAIN  = insufficient fresh data (``stale_frac``).
  * global ABSTAIN when a trusted majority cannot be formed.

Detection tick policy: ``cusum_accelerates_tick`` (default True) lets a CUSUM
crossing on the SAME predictor that is later confirmed SUSPECT count as the
detection tick, exactly the semantics the existing ``FusionDetector`` grants
BCVF. Set it False for the strictly-online tick (bias confirmation only).

Nothing here mutates production code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from robotics_reliability_bench.predictor_trust_baseline import (
    PredictorReport, TrustDecision, TrustState, _robust_consensus, _wrap)


@dataclass(frozen=True)
class LLTKalmanConfig:
    """Frozen thresholds. Tuned only on TUNE families, seeds 0..19; see
    ``results/llt_kalman_tune.json`` and the results note."""
    lever_arm: float = 2.5            # rad -> m homogenisation for heading
    scale_floor: float = 0.05         # m; floor on per-predictor obs-noise std
    q_level_ratio: float = 0.003      # Q_level = ratio * R  (scale-free)
    q_slope_ratio: float = 0.001      # Q_slope = ratio * R  (scale-free)
    p0_ratio: float = 10.0            # P0 = ratio * R * I
    cusum_k: float = 2.0              # slack on surprise magnitude (null ~1.6)
    cusum_h: float = 12.0             # CUSUM threshold -> DEGRADED / early tick
    bias_z: float = 4.0               # |level| / sqrt(P_level) -> significant
    bias_min_m: float = 0.20          # m; min physical offset to call it a bias
    bias_sustain: int = 4             # consecutive fresh ticks the test must hold
    stale_frac: float = 0.3           # fraction missing -> predictor ABSTAIN
    abstain_suspect_frac: float = 0.5 # >= this frac SUSPECT -> global ABSTAIN
    cusum_accelerates_tick: bool = True


@dataclass
class AxisFilterTrace:
    level: np.ndarray        # (H,) posterior level
    level_var: np.ndarray    # (H,) posterior level variance
    nis: np.ndarray          # (H,) squared normalized innovation (nan if not fresh)


def _robust_obs_noise(r: np.ndarray, fresh: np.ndarray, floor: float) -> float:
    """Per-axis observation-noise std from robust first differences.

    Differencing removes a constant offset and turns a linear drift into a
    constant, so MAD(dr - median(dr)) is robust to exactly the fault classes
    we want to detect. Var(dr) = 2 sigma^2 for white noise, hence / sqrt(2).
    """
    idx = np.flatnonzero(fresh)
    if idx.size < 3:
        return floor
    dr = np.diff(r[idx])
    mad = float(np.median(np.abs(dr - np.median(dr))))
    return max(1.4826 * mad / np.sqrt(2.0), floor)


def llt_filter_axis(r: np.ndarray, fresh: np.ndarray, R: float,
                    cfg: LLTKalmanConfig) -> AxisFilterTrace:
    """Local-linear-trend Kalman filter on one residual axis.

    State ``[level, slope]``; ``F=[[1,1],[0,1]]``, ``H=[1,0]``. A constant
    slope (legitimate or faulty linear drift) is absorbed into the slope
    state so innovations are white under it, while the *level* state tracks
    the current offset — which is what the bias channel reads.
    """
    H = r.shape[0]
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    Q = np.array([[cfg.q_level_ratio * R, 0.0], [0.0, cfg.q_slope_ratio * R]])
    I2 = np.eye(2)

    # initialise at the first fresh observation (or 0 if none), zero slope
    first = np.flatnonzero(fresh)
    x = np.array([float(r[first[0]]) if first.size else 0.0, 0.0])
    P = I2 * (cfg.p0_ratio * R)

    level = np.zeros(H)
    level_var = np.zeros(H)
    nis = np.full(H, np.nan)
    for t in range(H):
        xp = F @ x
        Pp = F @ P @ F.T + Q
        if fresh[t]:
            y = float(r[t]) - xp[0]
            S = Pp[0, 0] + R
            K = Pp[:, 0] / S                         # (2,)
            x = xp + K * y
            P = (I2 - np.outer(K, np.array([1.0, 0.0]))) @ Pp
            nis[t] = (y * y) / S
        else:
            x, P = xp, Pp
        level[t] = x[0]
        level_var[t] = P[0, 0]
    return AxisFilterTrace(level=level, level_var=level_var, nis=nis)


class LLTKalmanTrust:
    """LLT-Kalman predictor-trust detector. Deterministic given inputs."""

    name = "LLTKalmanTrust"

    def __init__(self, config: Optional[LLTKalmanConfig] = None):
        self.cfg = config or LLTKalmanConfig()

    def evaluate(self, trajs: np.ndarray,
                 valid_masks: Optional[np.ndarray] = None) -> TrustDecision:
        cfg = self.cfg
        M, H, _ = trajs.shape
        valid = (np.ones((M, H), dtype=bool) if valid_masks is None
                 else valid_masks.astype(bool))

        ref = _robust_consensus(trajs, valid)
        axis_w = np.array([1.0, 1.0, cfg.lever_arm])
        signed = (trajs - ref[None, :, :]) * axis_w[None, None, :]      # (M,H,3)
        signed[..., 2] = _wrap(trajs[..., 2] - ref[None, :, 2]) * cfg.lever_arm

        reports: List[PredictorReport] = []
        first_detect: Optional[int] = None
        for m in range(M):
            fresh = valid[m]
            stale_fraction = float(np.mean(~fresh))

            # --- per-axis LLT Kalman -------------------------------------
            traces: List[AxisFilterTrace] = []
            for a in range(3):
                sigma = _robust_obs_noise(signed[m, :, a], fresh, cfg.scale_floor)
                traces.append(llt_filter_axis(signed[m, :, a], fresh, sigma * sigma, cfg))

            # --- change channel: CUSUM on innovation surprise ------------
            # surprise_t = sqrt(sum_axes NIS_t)  (~ sqrt(chi2_3) under null)
            nis_stack = np.stack([tr.nis for tr in traces], axis=1)     # (H,3)
            surprise = np.sqrt(np.nansum(nis_stack, axis=1))
            cusum = 0.0
            cusum_peak = 0.0
            cusum_cross_tick: Optional[int] = None
            for t in range(H):
                if not fresh[t]:
                    continue
                cusum = max(0.0, cusum + float(surprise[t]) - cfg.cusum_k)
                cusum_peak = max(cusum_peak, cusum)
                if cusum >= cfg.cusum_h and cusum_cross_tick is None:
                    cusum_cross_tick = t

            # --- bias channel: filtered level vs its posterior variance --
            persistent_bias = 0.0
            bias_z_peak = 0.0
            bias_tick: Optional[int] = None
            for a in range(3):
                tr = traces[a]
                run = 0
                for t in range(H):
                    if not fresh[t]:
                        run = 0
                        continue
                    lvl = abs(float(tr.level[t]))
                    z = lvl / np.sqrt(max(float(tr.level_var[t]), 1e-12))
                    bias_z_peak = max(bias_z_peak, z)
                    if z >= cfg.bias_z and lvl >= cfg.bias_min_m:
                        run += 1
                        if run >= cfg.bias_sustain:
                            persistent_bias = max(persistent_bias, lvl)
                            if bias_tick is None:
                                bias_tick = t
                    else:
                        run = 0

            # --- state assignment (identical order to the baseline) -----
            reasons: List[str] = []
            state = TrustState.TRUSTED
            if stale_fraction >= cfg.stale_frac:
                state = TrustState.ABSTAIN
                reasons.append(f"stale({stale_fraction:.2f})")
            else:
                if persistent_bias > 0.0:
                    state = TrustState.SUSPECT
                    reasons.append(f"bias({persistent_bias:.2f}m,z={bias_z_peak:.1f})")
                if state is TrustState.TRUSTED and cusum_peak >= cfg.cusum_h:
                    state = TrustState.DEGRADED
                    reasons.append(f"innovation_cusum({cusum_peak:.1f})")

            suspicion = (10.0 * persistent_bias + 0.5 * bias_z_peak
                         + 0.2 * cusum_peak + 5.0 * stale_fraction)

            # detection tick for a confirmed-SUSPECT predictor
            det_tick: Optional[int] = None
            if state is TrustState.SUSPECT and bias_tick is not None:
                det_tick = bias_tick
                if cfg.cusum_accelerates_tick and cusum_cross_tick is not None:
                    det_tick = min(det_tick, cusum_cross_tick)
                if first_detect is None or det_tick < first_detect:
                    first_detect = det_tick

            reports.append(PredictorReport(
                index=m, state=state, suspicion=float(suspicion),
                ewma_z=float(np.nanmax(surprise) if np.any(fresh) else 0.0),
                cusum_peak=float(cusum_peak),
                persistent_bias_m=float(persistent_bias),
                stale_fraction=stale_fraction,
                reasons=reasons + [f"bias_tick={bias_tick}",
                                   f"cusum_tick={cusum_cross_tick}"]))

        return _global_decision(reports, M, first_detect, cfg)

    # --- Arbitrator protocol adapter --------------------------------------
    def arbitrate(self, trajectories: np.ndarray):
        """Satisfy the kernel's Arbitrator protocol. Returns a duck-typed result."""
        dec = self.evaluate(trajectories)
        M, H, _ = trajectories.shape
        ref = _robust_consensus(trajectories, np.ones((M, H), dtype=bool))
        attribution = np.array([r.suspicion for r in dec.per_predictor], dtype=np.float64)

        @dataclass
        class _Result:
            consensus: np.ndarray
            attribution: np.ndarray
            per_tick_us: float
            metadata: Dict
        return _Result(consensus=ref, attribution=attribution, per_tick_us=0.0,
                       metadata={"system_state": dec.system_state.value,
                                 "flagged": dec.flagged, "reason": dec.reason})


def _global_decision(reports: List[PredictorReport], M: int,
                     first_detect: Optional[int],
                     cfg: LLTKalmanConfig) -> TrustDecision:
    """Global rule — copied verbatim in semantics from the frozen baseline
    (``DeterministicTrustBaseline.evaluate``) so only the statistics differ.
    Never forces a winner."""
    suspect = [r.index for r in reports if r.state is TrustState.SUSPECT]
    abstain_pred = [r.index for r in reports if r.state is TrustState.ABSTAIN]
    usable = [r for r in reports if r.state not in
              (TrustState.SUSPECT, TrustState.ABSTAIN)]

    if len(reports) - len(abstain_pred) < 2:
        return TrustDecision(reports, None, [r.index for r in usable],
                             TrustState.ABSTAIN, first_detect,
                             "insufficient fresh predictors")
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


if __name__ == "__main__":
    from robotics_reliability_bench import fault_corpus as fc
    det = LLTKalmanTrust()
    for fam in fc.FAMILIES:
        b = fc.generate(fam, seed=0)
        d = det.evaluate(b.trajectories, b.valid_masks)
        print(f"{fam:20s} truth={str(b.truth_label):>4} -> flagged={str(d.flagged):>4} "
              f"sys={d.system_state.value:8s} det@={str(d.detection_tick):>4}  {d.reason}")
