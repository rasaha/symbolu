"""Streaming detectors for Stage A: StatChangeDetector (baseline) and
HarmonicEventCollector (under test).

Both are two-phase for efficiency: `*_channels(x)` computes threshold-free
per-sample statistics in one causal pass (bounded state, streaming by
construction); `emit(channels, config)` applies frozen thresholds + refractory
to produce emitted events. Thresholds are fit ONLY on training streams and
frozen before the single held-out evaluation (PREREGISTRATION.md).

The collector is a classical fixed-frequency mechanism; it is not Phase and
imports nothing from symbolu/lightweight_phase/.
"""
from __future__ import annotations

import math
from itertools import product

import numpy as np

# Fixed clock bank: identical to phase_temporal_collector (K=8, log-spaced 4->128).
CLOCK_PERIODS = tuple(float(p) for p in 4.0 * (128.0 / 4.0) ** (np.arange(8) / 7.0))
WARMUP = 64
EPS = 1e-6


def stat_channels(x: np.ndarray) -> dict:
    """Baseline: multi-timescale z-scores + CUSUM of the standardized residual."""
    T = len(x)
    zs = np.zeros((2, T))
    cusum = np.zeros(T)
    for gi, g in enumerate((0.9, 0.98)):
        m = x[0]
        v = 1.0
        cp = cn = 0.0
        for t in range(1, T):
            std = math.sqrt(max(v, EPS))
            z = (x[t] - m) / std
            zs[gi, t] = abs(z)
            if gi == 1:  # CUSUM on the slower timescale
                cp = max(0.0, cp + z - 0.5)
                cn = max(0.0, cn - z - 0.5)
                cusum[t] = max(cp, cn)
                if cusum[t] > 20:  # cap + reset so one change = one excursion
                    cp = cn = 0.0
            m = g * m + (1 - g) * x[t]
            v = g * v + (1 - g) * (x[t] - m) ** 2
    return {"z": zs.max(axis=0), "cusum": cusum}


def hec_channels(x: np.ndarray) -> dict:
    """HarmonicEventCollector statistics (one causal pass, bounded state).

    The clock bank (decayed complex accumulators S_P, counts A_P) selects the
    dominant period and refines it with the accumulator's own rotation rate
    (w_eff = w_P + nu_P). The expected value is the classical seasonal
    reference at that refined period -- the median of the values one, two and
    three estimated periods ago (median makes a one-off past event unable to
    echo into a false residual one period later). Channels:
      res:  |x - expected| / robust decayed residual std   (surprise)
      mag:  max over clocks of fast-vs-slow normalized magnitude change
      ang:  fast-vs-slow angle change of the dominant clock (radians)
    Per-clock magnitude/angle tracks and the period estimate are returned for
    event profiles. Classical mechanism throughout; nothing is learned.
    """
    T = len(x)
    K = len(CLOCK_PERIODS)
    g = np.array([math.exp(-1.0 / (4.0 * P)) for P in CLOCK_PERIODS])
    g_slow = np.array([math.exp(-1.0 / (16.0 * P)) for P in CLOCK_PERIODS])
    w = 2 * np.pi / np.array(CLOCK_PERIODS)
    S = np.zeros(K, complex)
    A = np.zeros(K)
    S2 = np.zeros(K, complex)
    A2 = np.zeros(K)
    nu = np.zeros(K)          # per-clock residual rotation rate (rad/sample)
    prev_ang = np.zeros(K)
    mean = x[0]
    rvar = 0.01
    p_ref = None
    envf = envr = 0.1
    hcs = 0.0
    res = np.zeros(T)
    envc = np.zeros(T)
    cusc = np.zeros(T)
    magc = np.zeros(T)
    angc = np.zeros(T)
    mags = np.zeros((T, K))
    angs = np.zeros((T, K))
    phat = np.zeros(T)
    recon = np.zeros(T)
    for t in range(T):
        c_fast = S / np.maximum(A, EPS)
        c_slow = S2 / np.maximum(A2, EPS)
        k_star = int(np.argmax(np.abs(c_fast)))
        w_eff = max(w[k_star] + nu[k_star], 2 * np.pi / 200.0)
        p_clock = float(np.clip(2 * np.pi / w_eff, 4.0, 200.0))
        # Classical local refinement (pitch-tracking style): every 8 samples,
        # nudge the period toward the lag that minimizes the mean absolute
        # seasonal difference over the recent window. Sharpens the reference
        # far beyond what the coarse clock bank + rotation rate give alone.
        if p_ref is None or abs(p_clock - p_ref) > 0.25 * p_ref:
            p_ref = p_clock
        if t % 8 == 0 and t > 2 * p_ref + 28:
            best_l, best_c = p_ref, None
            for dl in (-0.06, -0.03, -0.015, 0.0, 0.015, 0.03, 0.06):
                L = p_ref * (1 + dl)
                idx = t - np.arange(24, dtype=float)
                ref_pos = idx - L
                lo = np.floor(ref_pos).astype(int)
                fr = ref_pos - lo
                refv = (1 - fr) * x[lo] + fr * x[lo + 1]
                c = float(np.mean(np.abs(x[idx.astype(int)] - refv)))
                if best_c is None or c < best_c:
                    best_c, best_l = c, L
            p_ref = float(np.clip(0.7 * p_ref + 0.3 * best_l, 4.0, 200.0))
        p_est = p_ref
        phat[t] = p_est
        # Seasonal expectation: median of interpolated references at lags
        # p_est, 2 p_est, 3 p_est (whichever exist).
        refs = []
        for m_lag in (1, 2, 3):
            lag = m_lag * p_est
            if t - lag >= 1:
                lo = int(math.floor(t - lag))
                frac = (t - lag) - lo
                refs.append((1 - frac) * x[lo] + frac * x[min(lo + 1, T - 1)])
        x_hat = float(np.median(refs)) if refs else mean
        recon[t] = x_hat
        r = x[t] - x_hat
        envf = envf + (abs(x[t] - mean) - envf) / 8.0
        envr = envr + (abs(x_hat - mean) - envr) / 8.0
        if t >= 8:
            res[t] = abs(r) / math.sqrt(max(rvar, EPS))
            # Seasonal envelope ratio: the reference keeps the pre-change
            # envelope for ~1-3 periods, so amplitude regime changes show up
            # within ~2 EMA horizons; envelope dips of the sinusoid cancel.
            envc[t] = abs(math.log((envf + 0.02) / (envr + 0.02)))
            # CUSUM of the seasonal surprise: slow-reveal changes (e.g. a
            # period shift whose residual grows gradually) integrate past a
            # threshold quickly even when no single sample is extreme.
            hcs = min(max(0.0, hcs + res[t] - 1.2), 30.0)
            if hcs >= 30.0:
                hcs = 0.0
            cusc[t] = hcs
            dmag = np.abs(np.abs(c_fast) - np.abs(c_slow))
            magc[t] = (dmag / max(np.abs(c_slow).max(), 0.05)).max()
            if np.abs(c_fast[k_star]) > 0.1:  # angle is noise when weak
                angc[t] = abs(float(np.angle(c_fast[k_star]
                                             * np.conj(c_slow[k_star]))))
        mags[t] = np.abs(c_fast)
        angs[t] = np.angle(c_fast)
        # state update (bounded: K complex + K real per bank, plus mean/var)
        ph = np.exp(1j * w * t)
        demod = x[t] * np.conj(ph)
        S = g * S + demod
        A = g * A + 1.0
        S2 = g_slow * S2 + demod
        A2 = g_slow * A2 + 1.0
        ang_now = np.angle(S)
        d_ang = np.angle(np.exp(1j * (ang_now - prev_ang)))
        prev_ang = ang_now
        upd = np.abs(c_fast) > 0.03
        nu[upd] = 0.98 * nu[upd] + 0.02 * d_ang[upd]
        mean = 0.99 * mean + 0.01 * x[t]
        # Robust variance: barely adapt to outlier residuals so events do not
        # inflate the noise floor and mask later events.
        lr = 0.01 if abs(r) < 3.0 * math.sqrt(max(rvar, EPS)) else 0.001
        rvar = (1 - lr) * rvar + lr * r * r
    return {"res": res, "mag": magc, "ang": angc, "env": envc, "cus": cusc,
            "mags": mags, "angs": angs, "recon": recon, "phat": phat}


STAT_GRID = {"z": (3.0, 4.0, 5.0, 6.0, 8.0), "cusum": (4.0, 6.0, 8.0, 10.0),
             "refractory": (16, 24, 32)}
HEC_GRID = {"res": (3.0, 4.0, 5.0, 6.0), "mag": (0.6, 9.9),
            "ang": (0.8, 1.2, 9.9), "env": (0.35, 0.5, 0.7),
            "cus": (6.0, 10.0, 14.0, 99.0), "refractory": (12, 16, 24)}


def grid_configs(grid: dict):
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in product(*(grid[k] for k in keys))]


QUIET_WIN = 16
QUIET_FRAC = 0.5


def _edge_candidates(ch: np.ndarray, th: float) -> np.ndarray:
    """Onset-triggering: fire where the channel exceeds th AND was mostly quiet
    (below th/2) over the preceding window — a persistent elevation after a
    real change emits once at its onset, not continuously at the refractory
    rate."""
    above = ch > th
    soft = (ch > 0.5 * th).astype(np.float64)
    frac = np.convolve(soft, np.ones(QUIET_WIN), mode="full")[:len(ch)] / QUIET_WIN
    quiet = np.roll(frac, 1) <= QUIET_FRAC
    quiet[0] = True
    return above & quiet


def emit(channels: dict, config: dict) -> list[int]:
    """Apply frozen thresholds + edge triggering + refractory."""
    if "z" in config:  # stat detector
        trig = (_edge_candidates(channels["z"], config["z"])
                | _edge_candidates(channels["cusum"], config["cusum"]))
    else:
        trig = (_edge_candidates(channels["res"], config["res"])
                | _edge_candidates(channels["mag"], config["mag"])
                | _edge_candidates(channels["ang"], config["ang"])
                | _edge_candidates(channels["env"], config["env"])
                | _edge_candidates(channels["cus"], config["cus"]))
    trig[:WARMUP] = False
    out = []
    last = -10 ** 9
    for t in np.flatnonzero(trig):
        if t - last >= config["refractory"]:
            out.append(int(t))
            last = t
    return out


def score_events(emitted: list[int], labels, tolerance: dict):
    """Greedy one-to-one matching within per-family tolerance.

    Family-agnostic: a ground-truth event is recalled if ANY emitted event lies
    within its family's tolerance (the E-GATE tests detection, not family
    classification). Returns (per-family [hit, total], n_matched_emitted).
    """
    fam_counts = {}
    used = set()
    matched = 0
    for onset, fam in labels:
        tol = tolerance[fam]
        hit = 0
        best = None
        for i, e in enumerate(emitted):
            if i in used and best is None:
                continue
            if abs(e - onset) <= tol and i not in used:
                best = i
                break
        if best is not None:
            used.add(best)
            hit = 1
            matched += 1
        h, n = fam_counts.get(fam, (0, 0))
        fam_counts[fam] = (h + hit, n + 1)
    return fam_counts, matched
