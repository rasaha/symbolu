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
    # --- amendment A1: time-varying noise estimate (None = A0 whole-episode)
    noise_forgetting: Optional[float] = None  # lambda in (0,1); None -> A0 behaviour
    noise_warmup: int = 6             # causal MAD warm-up over first fresh diffs
    noise_clip: float = 9.0           # clip e^2 at clip * s^2 (robust to one jump)
    # --- amendment A3: coloured-noise state (False = A1 behaviour)
    coloured_noise: bool = False      # augment state with an AR(1) noise component
    phi_max: float = 0.9              # clip on the causal AR(1) coefficient estimate
    rho_forgetting: float = 0.95      # forgetting for the variance / lag-1 autocov


# Frozen A1 configuration — the TUNE-only sweep's choice
# (results/llt_kalman_tune_A1.json: 486 configs, 198 survivors, min strict-tick
# delay 8.28 on TUNE, ties to larger cusum_h then bias_z, first in grid order).
# Frozen BEFORE any evaluation seed was scored. The A0 defaults above are NOT
# modified so the committed A0 rows stay reproducible.
A1_CONFIG = LLTKalmanConfig(
    q_level_ratio=0.01, q_slope_ratio=0.003, cusum_k=2.0, cusum_h=12.0,
    bias_z=4.0, bias_min_m=0.20, bias_sustain=4,
    noise_forgetting=0.9, noise_warmup=6, noise_clip=9.0)

# Frozen A3 configuration (set after the TUNE-only sweep in
# results/llt_kalman_tune_A3.json; None until frozen).
A3_CONFIG: Optional[LLTKalmanConfig] = None


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


def forgetting_obs_noise(r: np.ndarray, fresh: np.ndarray,
                         cfg: LLTKalmanConfig) -> np.ndarray:
    """Amendment A1: causal, exponentially forgetting robust noise std, (H,).

    Warm-up: causal MAD over the first ``noise_warmup`` fresh first
    differences (the A0 estimator restricted to the prefix). Thereafter
    ``s_t^2 = lam * s_{t-1}^2 + (1 - lam) * clip(e_t^2, 0, clip * s_{t-1}^2)``
    where ``e_t = (dr_t - m_t) / sqrt(2)`` and ``m_t`` is an EWMA of the first
    differences (removes a constant drift increment). Clipping makes one
    jump inflate ``s`` by at most ``clip`` in variance for one step, so an
    abrupt fault is not laundered into "noise". Ticks before the first fresh
    difference carry the warm-up value; non-fresh ticks hold the last value.
    """
    lam = float(cfg.noise_forgetting)
    H = r.shape[0]
    idx = np.flatnonzero(fresh)
    out = np.full(H, cfg.scale_floor, dtype=np.float64)
    if idx.size < 2:
        return out
    dr = np.diff(r[idx])                     # fresh-to-fresh first differences
    k = min(cfg.noise_warmup, dr.size)
    warm = dr[:k]
    mad = float(np.median(np.abs(warm - np.median(warm))))
    s2 = max(1.4826 * mad / np.sqrt(2.0), cfg.scale_floor) ** 2
    m = float(np.median(warm))
    # warm-up value applies to every tick up to and including the k-th diff
    out[: idx[min(k, idx.size - 1)] + 1] = np.sqrt(s2)
    for j in range(k, dr.size):
        m = lam * m + (1.0 - lam) * float(dr[j])
        e2 = ((float(dr[j]) - m) ** 2) / 2.0
        s2 = lam * s2 + (1.0 - lam) * min(e2, cfg.noise_clip * s2)
        s2 = max(s2, cfg.scale_floor ** 2)
        lo, hi = idx[j] + 1, (idx[j + 1] + 1 if j + 1 < idx.size else H)
        out[lo:hi] = np.sqrt(s2)
    return out


def coloured_noise_params(r: np.ndarray, fresh: np.ndarray,
                          cfg: LLTKalmanConfig):
    """Amendment A3: causal per-axis (sigma_n^2[t], phi[t]) of the residual noise.

    IMPLEMENTATION DEVIATION (logged in the preregistration A3 outcome): the
    preregistered text estimated phi from the *innovations*; a filter that
    models the coloured state whitens its own innovations, so phi is not
    identifiable from them.  The estimate therefore uses FIRST DIFFERENCES of
    the residual (as A1 does for the noise scale), decided on TUNE data before
    any evaluation seed was scored.  A constant offset is invisible to
    differences and a linear drift's constant mean is cancelled by the
    mean-corrected moments.

    For pure AR(1) noise, Corr(dn_t, dn_{t-1}) = -(1-phi)/2 and
    Var(dn) = 2 sigma_n^2 (1-phi), hence phi = 1 + 2 rho_d (clipped to
    [0, phi_max]) and sigma_n^2 = Var(dn) / (2 (1-phi)).  White noise gives
    rho_d = -1/2 -> phi = 0 and sigma_n^2 = Var(dn)/2, i.e. exactly A1.  An
    additive white component biases phi downward (conservative on colour);
    a three-moment AR(1)+white solve was tried and rejected because the lag-2
    autocovariance is not causally estimable at these window lengths.

    Moments are forgetting means (``rho_forgetting``) of dr, dr^2 and
    dr_t*dr_{t-1}: gamma(0) = E[dr^2] - m^2, gamma(1) = E[dr dr_prev] - m^2.
    Each squared increment is clipped at ``noise_clip`` * gamma(0) (A1's
    clip).  ``scale_floor`` is applied ONLY to the emitted sigma_n^2, never
    inside the ratio.
    """
    rho = float(cfg.rho_forgetting)
    H = r.shape[0]
    floor2 = cfg.scale_floor ** 2
    sig2 = np.full(H, floor2, dtype=np.float64)
    phi = np.zeros(H, dtype=np.float64)
    idx = np.flatnonzero(fresh)
    if idx.size < 2:
        return sig2, phi
    dr = np.diff(r[idx])
    k = min(cfg.noise_warmup, dr.size)
    warm = dr[:k]
    m = float(np.mean(warm))
    mad = float(np.median(np.abs(warm - np.median(warm))))
    g0_warm = max((1.4826 * mad) ** 2, 1e-12)
    q = g0_warm + m * m                       # E[dr^2]
    a = m * m - 0.5 * g0_warm                 # E[dr dr_prev]; white-noise prior
    dr_prev: Optional[float] = None

    def _emit(lo, hi, m_, q_, a_):
        g0 = max(q_ - m_ * m_, 1e-12)
        rho_d = (a_ - m_ * m_) / g0
        ph = min(max(1.0 + 2.0 * rho_d, 0.0), cfg.phi_max)
        sig2[lo:hi] = max(g0 / (2.0 * (1.0 - ph)), floor2)
        phi[lo:hi] = ph

    _emit(0, idx[min(k, idx.size - 1)] + 1, m, q, a)
    for j in range(k, dr.size):
        x = float(dr[j])
        g0 = max(q - m * m, 1e-12)
        cap = m * m + cfg.noise_clip * g0
        m = rho * m + (1.0 - rho) * x
        q = rho * q + (1.0 - rho) * min(x * x, cap)
        if dr_prev is not None and idx[j] == idx[j - 1] + 1:     # consecutive ticks only
            a = rho * a + (1.0 - rho) * min(max(x * dr_prev, -cap), cap)
        dr_prev = x
        lo, hi = idx[j] + 1, (idx[j + 1] + 1 if j + 1 < idx.size else H)
        _emit(lo, hi, m, q, a)
    return sig2, phi


def llt_filter_axis_coloured(r: np.ndarray, fresh: np.ndarray, sig2: np.ndarray,
                             phi: np.ndarray, cfg: LLTKalmanConfig) -> AxisFilterTrace:
    """Amendment A3: LLT Kalman with an AR(1) coloured-noise state.

    State ``[level, slope, c]``, ``F=[[1,1,0],[0,1,0],[0,0,phi_t]]``,
    ``H=[1,0,1]``, ``Q=diag(q_level_ratio*sig2, q_slope_ratio*sig2,
    sig2*(1-phi^2))``, ``R=scale_floor^2`` (as preregistered).  Slow
    correlated wander is
    absorbed by ``c`` (stationary variance sig2), so the *level* posterior
    variance is calibrated under coloured noise and the bias test reads a
    level that excludes the coloured excursion.
    """
    H = r.shape[0]
    Hm = np.array([1.0, 0.0, 1.0])
    I3 = np.eye(3)
    R = cfg.scale_floor ** 2
    first = np.flatnonzero(fresh)
    x = np.array([float(r[first[0]]) if first.size else 0.0, 0.0, 0.0])
    P = np.diag([cfg.p0_ratio * sig2[0], cfg.p0_ratio * sig2[0], sig2[0]])
    level = np.zeros(H)
    level_var = np.zeros(H)
    nis = np.full(H, np.nan)
    for t in range(H):
        s2, ph = float(sig2[t]), float(phi[t])
        F = np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, ph]])
        Q = np.diag([cfg.q_level_ratio * s2, cfg.q_slope_ratio * s2, s2 * (1.0 - ph * ph)])
        xp = F @ x
        Pp = F @ P @ F.T + Q
        if fresh[t]:
            y = float(r[t]) - float(Hm @ xp)
            S = float(Hm @ Pp @ Hm) + R
            K = (Pp @ Hm) / S
            x = xp + K * y
            P = (I3 - np.outer(K, Hm)) @ Pp
            nis[t] = (y * y) / S
        else:
            x, P = xp, Pp
        level[t] = x[0]
        level_var[t] = P[0, 0]
    return AxisFilterTrace(level=level, level_var=level_var, nis=nis)


def llt_filter_axis(r: np.ndarray, fresh: np.ndarray, R,
                    cfg: LLTKalmanConfig) -> AxisFilterTrace:
    """Local-linear-trend Kalman filter on one residual axis.

    State ``[level, slope]``; ``F=[[1,1],[0,1]]``, ``H=[1,0]``. A constant
    slope (legitimate or faulty linear drift) is absorbed into the slope
    state so innovations are white under it, while the *level* state tracks
    the current offset — which is what the bias channel reads.

    ``R`` is either a scalar (A0: one observation variance per episode) or an
    ``(H,)`` array of per-tick variances (A1). ``Q`` is a ratio of the current
    ``R_t`` so the filter stays scale-free.
    """
    H = r.shape[0]
    R_t = np.broadcast_to(np.asarray(R, dtype=np.float64), (H,))
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    I2 = np.eye(2)

    # initialise at the first fresh observation (or 0 if none), zero slope
    first = np.flatnonzero(fresh)
    x = np.array([float(r[first[0]]) if first.size else 0.0, 0.0])
    P = I2 * (cfg.p0_ratio * R_t[0])

    level = np.zeros(H)
    level_var = np.zeros(H)
    nis = np.full(H, np.nan)
    for t in range(H):
        Rt = float(R_t[t])
        Q = np.array([[cfg.q_level_ratio * Rt, 0.0], [0.0, cfg.q_slope_ratio * Rt]])
        xp = F @ x
        Pp = F @ P @ F.T + Q
        if fresh[t]:
            y = float(r[t]) - xp[0]
            S = Pp[0, 0] + Rt
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
                if cfg.coloured_noise:                # A3: coloured-noise state
                    sig2, phi = coloured_noise_params(signed[m, :, a], fresh, cfg)
                    traces.append(llt_filter_axis_coloured(signed[m, :, a], fresh,
                                                           sig2, phi, cfg))
                    continue
                if cfg.noise_forgetting is None:      # A0: one R per episode
                    sigma = _robust_obs_noise(signed[m, :, a], fresh, cfg.scale_floor)
                    R = sigma * sigma
                else:                                 # A1: per-tick R_t
                    R = forgetting_obs_noise(signed[m, :, a], fresh, cfg) ** 2
                traces.append(llt_filter_axis(signed[m, :, a], fresh, R, cfg))

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
