"""HarmonicEventCollector V2: V1's detector plus exactly the two preregistered
corrections (PREREGISTRATION.md):

1. Protected reference updates — the seasonal reference reads a parallel
   clean history in which samples whose residual exceeds 3x the robust scale
   are imputed with the expected value, for at most `protect` consecutive
   samples (then observations are adopted so persistent changes heal).
2. Sequential accumulated evidence — V1's surprise-CUSUM plus a new signed
   CUSUM on the seasonal envelope log-ratio (`ecus`) for slow-reveal
   amplitude/regime changes.

Stream generation, scoring, the StatChangeDetector baseline, and the edge/
refractory machinery are imported UNCHANGED from V1. Classical mechanism; not
Phase; nothing imported from symbolu/lightweight_phase/.
"""
from __future__ import annotations

import math

import numpy as np

from experiments.harmonic_event_collector.detectors import (
    CLOCK_PERIODS, EPS, WARMUP, _edge_candidates)

FLAG_SIGMA = 3.0  # fixed disturbance flag threshold (not fitted)

HEC_V2_GRID = {"res": (3.0, 4.0, 5.0), "mag": (0.6, 9.9), "ang": (0.8, 9.9),
               "env": (0.35, 0.5, 0.7), "cus": (6.0, 10.0, 99.0),
               "ecus": (4.0, 7.0, 99.0), "refractory": (12, 16, 24)}
PROTECT_GRID = (8, 16, 32)


def hec_channels_v2(x: np.ndarray, protect: int) -> dict:
    """One causal pass, bounded state. Identical to V1's hec_channels except
    for the two preregistered corrections (clean history `xc`, `ecus`)."""
    T = len(x)
    K = len(CLOCK_PERIODS)
    g = np.array([math.exp(-1.0 / (4.0 * P)) for P in CLOCK_PERIODS])
    g_slow = np.array([math.exp(-1.0 / (16.0 * P)) for P in CLOCK_PERIODS])
    w = 2 * np.pi / np.array(CLOCK_PERIODS)
    S = np.zeros(K, complex)
    A = np.zeros(K)
    S2 = np.zeros(K, complex)
    A2 = np.zeros(K)
    nu = np.zeros(K)
    prev_ang = np.zeros(K)
    mean = x[0]
    rvar = 0.01
    p_ref = None
    envf = envr = 0.1
    hcs = 0.0
    ecp = ecn = 0.0
    protect_count = 0
    xc = np.copy(x)  # clean history (correction 1)
    res = np.zeros(T)
    magc = np.zeros(T)
    angc = np.zeros(T)
    envc = np.zeros(T)
    cusc = np.zeros(T)
    ecusc = np.zeros(T)
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
                refv = (1 - fr) * xc[lo] + fr * xc[lo + 1]
                c = float(np.mean(np.abs(xc[idx.astype(int)] - refv)))
                if best_c is None or c < best_c:
                    best_c, best_l = c, L
            p_ref = float(np.clip(0.7 * p_ref + 0.3 * best_l, 4.0, 200.0))
        p_est = p_ref
        phat[t] = p_est
        refs = []
        for m_lag in (1, 2, 3):
            lag = m_lag * p_est
            if t - lag >= 1:
                lo = int(math.floor(t - lag))
                frac = (t - lag) - lo
                refs.append((1 - frac) * xc[lo] + frac * xc[min(lo + 1, T - 1)])
        x_hat = float(np.median(refs)) if refs else mean
        recon[t] = x_hat
        r = x[t] - x_hat
        # Correction 1: protected clean history with bounded adoption budget.
        if abs(r) > FLAG_SIGMA * math.sqrt(max(rvar, EPS)) and protect_count < protect:
            xc[t] = x_hat
            protect_count += 1
        else:
            xc[t] = x[t]
            if abs(r) <= FLAG_SIGMA * math.sqrt(max(rvar, EPS)):
                protect_count = 0
        envf = envf + (abs(x[t] - mean) - envf) / 8.0
        envr = envr + (abs(x_hat - mean) - envr) / 8.0
        if t >= 8:
            res[t] = abs(r) / math.sqrt(max(rvar, EPS))
            el = math.log((envf + 0.02) / (envr + 0.02))
            envc[t] = abs(el)
            hcs = min(max(0.0, hcs + res[t] - 1.2), 30.0)
            if hcs >= 30.0:
                hcs = 0.0
            cusc[t] = hcs
            # Correction 2: signed CUSUM on the envelope log-ratio.
            ecp = min(max(0.0, ecp + el - 0.05), 30.0)
            ecn = min(max(0.0, ecn - el - 0.05), 30.0)
            if max(ecp, ecn) >= 30.0:
                ecp = ecn = 0.0
            ecusc[t] = max(ecp, ecn)
            dmag = np.abs(np.abs(c_fast) - np.abs(c_slow))
            magc[t] = (dmag / max(np.abs(c_slow).max(), 0.05)).max()
            if np.abs(c_fast[k_star]) > 0.1:
                angc[t] = abs(float(np.angle(c_fast[k_star]
                                             * np.conj(c_slow[k_star]))))
        mags[t] = np.abs(c_fast)
        angs[t] = np.angle(c_fast)
        ph = np.exp(1j * w * t)
        demod = x[t] * np.conj(ph)  # accumulators read raw x, exactly as in V1
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
        lr = 0.01 if abs(r) < 3.0 * math.sqrt(max(rvar, EPS)) else 0.001
        rvar = (1 - lr) * rvar + lr * r * r
    return {"res": res, "mag": magc, "ang": angc, "env": envc, "cus": cusc,
            "ecus": ecusc, "mags": mags, "angs": angs, "recon": recon,
            "phat": phat}


def emit_v2(channels: dict, config: dict) -> list[int]:
    """V1 edge/refractory machinery over the V2 channel set."""
    trig = (_edge_candidates(channels["res"], config["res"])
            | _edge_candidates(channels["mag"], config["mag"])
            | _edge_candidates(channels["ang"], config["ang"])
            | _edge_candidates(channels["env"], config["env"])
            | _edge_candidates(channels["cus"], config["cus"])
            | _edge_candidates(channels["ecus"], config["ecus"]))
    trig[:WARMUP] = False
    out = []
    last = -10 ** 9
    for t in np.flatnonzero(trig):
        if t - last >= config["refractory"]:
            out.append(int(t))
            last = t
    return out
