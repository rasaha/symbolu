"""Deterministic token tracks for all arms (PREREGISTRATION.md definitions).

Everything here is causal: the track value gathered for a query at bin t is
the state after consuming bin t-1. Seasonal medians use train days only.
Development code must gather only t < 960; the held-out evaluator is the only
consumer of later positions.
"""
from __future__ import annotations

import math

import numpy as np

BINS = 1344
BINS_PER_DAY = 96
TRAIN_END, DEV_END = 768, 960
HORIZONS = (1, 4, 12)  # 15 / 60 / 180 minutes
STAT_GAMMAS = (0.9, 0.98, 0.995)
HARM_PERIODS = (4, 8, 16, 32, 48, 96)  # 1,2,4,8,12,24 h — intraday+daily only
N_RETRIEVAL_ANOM = 4
LOOKBACK_V2 = 288  # 72 h (Spike Retrieval 2)
FEAT = 6


def bin_series(minutes: np.ndarray) -> np.ndarray:
    return minutes.reshape(minutes.shape[0], BINS, 15).sum(axis=2)


def targets(bins: np.ndarray) -> np.ndarray:
    """[F, BINS, 3] log1p sums over the next H bins starting at t (nan if
    the window exceeds the trace)."""
    F = bins.shape[0]
    out = np.full((F, BINS, len(HORIZONS)), np.nan, np.float32)
    csum = np.concatenate([np.zeros((F, 1)), bins.cumsum(axis=1)], axis=1)
    for hi, H in enumerate(HORIZONS):
        last = BINS - H
        out[:, :last + 1, hi] = np.log1p(csum[:, H:] - csum[:, :-H])[:, :last + 1]
    return out


def baseline_preds(bins: np.ndarray) -> dict:
    """persistence / seasonal_naive predictions, [F, BINS, 3] (nan = invalid)."""
    F = bins.shape[0]
    csum = np.concatenate([np.zeros((F, 1)), bins.cumsum(axis=1)], axis=1)
    pers = np.full((F, BINS, 3), np.nan, np.float32)
    seas = np.full((F, BINS, 3), np.nan, np.float32)
    for hi, H in enumerate(HORIZONS):
        for t in range(BINS_PER_DAY, BINS - max(HORIZONS) + 1):
            pers[:, t, hi] = np.log1p(csum[:, t] - csum[:, t - H])
            s = t - BINS_PER_DAY
            seas[:, t, hi] = np.log1p(csum[:, s + H] - csum[:, s])
    return {"persistence": pers, "seasonal_naive": seas}


def stats_tokens(bins: np.ndarray) -> np.ndarray:
    """[F, BINS, 3, 6]; slot t holds the state after consuming bin t-1."""
    F = bins.shape[0]
    x = np.log1p(bins).astype(np.float64)
    out = np.zeros((F, BINS, len(STAT_GAMMAS), FEAT), np.float32)
    for gi, g in enumerate(STAT_GAMMAS):
        m = np.zeros(F)
        s2 = np.zeros(F)
        tr = np.zeros(F)
        w = np.zeros(F)
        prev = np.zeros(F)
        for t in range(BINS):
            if t > 0:
                cov = np.maximum(w, 1e-9)
                mean = m / cov
                var = np.maximum(s2 / cov - mean ** 2, 0)
                out[:, t, gi] = np.stack(
                    [mean, var, tr / cov, prev, w * (1 - g),
                     np.full(F, gi - 1.0)], axis=-1)
            m = g * m + x[:, t]
            s2 = g * s2 + x[:, t] ** 2
            tr = g * tr + (x[:, t] - prev)
            w = g * w + 1.0
            prev = x[:, t]
    return out


def harmonic_tokens(bins: np.ndarray) -> np.ndarray:
    """[F, BINS, 6, 6]; fixed clock bank, decay horizon 4 periods; slot t is
    the state after bin t-1, with the clock angle evaluated at t."""
    F = bins.shape[0]
    x = np.log1p(bins).astype(np.float64)
    out = np.zeros((F, BINS, len(HARM_PERIODS), FEAT), np.float32)
    for pi, P in enumerate(HARM_PERIODS):
        g = math.exp(-1.0 / (4.0 * P))
        sr = np.zeros(F)
        si = np.zeros(F)
        a = np.zeros(F)
        for t in range(BINS):
            ang = 2 * math.pi * t / P
            if t > 0:
                mag = np.sqrt(sr ** 2 + si ** 2) / np.maximum(a, 1e-9)
                th = np.arctan2(si, sr)
                out[:, t, pi] = np.stack(
                    [mag, np.cos(th), np.sin(th),
                     np.full(F, math.cos(ang)), np.full(F, math.sin(ang)),
                     np.full(F, math.log(P) / 5.0)], axis=-1)
            sr = g * sr + x[:, t] * math.cos(ang)
            si = g * si - x[:, t] * math.sin(ang)
            a = g * a + 1.0
    return out


def seasonal_median(bins: np.ndarray) -> np.ndarray:
    """[F, 96] per-bin-of-day median of log1p over TRAIN days only (frozen)."""
    train = np.log1p(bins[:, :TRAIN_END]).reshape(bins.shape[0], 8, BINS_PER_DAY)
    return np.median(train, axis=1)


def retrieval_tracks(minutes: np.ndarray, bins: np.ndarray,
                     seas_med: np.ndarray) -> dict:
    """Per-bin ingredients for the 6-token retrieval budget."""
    F = bins.shape[0]
    mp = minutes.reshape(F, BINS, 15).astype(np.float64)
    rec = np.stack([np.log1p(mp.mean(2)), np.log1p(mp.max(2)),
                    np.log1p(mp.std(2)), np.log1p(mp[:, :, -1])],
                   axis=-1).astype(np.float32)          # [F, BINS, 4]
    lb = np.log1p(bins).astype(np.float32)
    bod = np.arange(BINS) % BINS_PER_DAY
    anom = np.abs(lb - seas_med[:, bod]).astype(np.float32)  # [F, BINS]
    return {"rec": rec, "lb": lb, "anom": anom, "bod": bod}


def retrieval_tokens(tracks: dict, f_idx: np.ndarray, t_idx: np.ndarray) -> np.ndarray:
    """[B, 6, 6] retrieval tokens for query pairs (f, t): 2 recency + 4 anomaly."""
    B = len(f_idx)
    out = np.zeros((B, 2 + N_RETRIEVAL_ANOM, FEAT), np.float32)
    rec, lb, anom, bod = (tracks["rec"], tracks["lb"], tracks["anom"],
                          tracks["bod"])
    for b, (f, t) in enumerate(zip(f_idx, t_idx)):
        for j, tb in enumerate((t - 1, t - 2)):
            out[b, j] = [rec[f, tb, 0], rec[f, tb, 1], rec[f, tb, 2],
                         rec[f, tb, 3], -(j + 1) / 4.0, 1.0]
        w0 = t - BINS_PER_DAY
        window = anom[f, w0:t]
        top = np.argsort(window)[::-1][:N_RETRIEVAL_ANOM]
        for j, off in enumerate(top):
            tb = w0 + int(off)
            th = 2 * math.pi * bod[tb] / BINS_PER_DAY
            out[b, 2 + j] = [lb[f, tb], anom[f, tb], math.cos(th),
                             math.sin(th), (tb - t) / BINS_PER_DAY,
                             rec[f, tb, 1]]
    return out


def query_features(t_idx: np.ndarray) -> np.ndarray:
    th = 2 * math.pi * (t_idx % BINS_PER_DAY) / BINS_PER_DAY
    return np.stack([np.cos(th), np.sin(th), np.ones(len(t_idx))],
                    axis=-1).astype(np.float32)


def retrieval_tracks_v2(minutes: np.ndarray, bins: np.ndarray,
                        seas_med: np.ndarray) -> dict:
    """Spike Retrieval 2 ingredients: signed anomaly scores (surge vs drought)
    alongside the unchanged recency stats."""
    base = retrieval_tracks(minutes, bins, seas_med)
    bod = base["bod"]
    signed = (base["lb"] - seas_med[:, bod]).astype(np.float32)
    return {**base, "signed": signed}


def retrieval_tokens_v2(tracks: dict, f_idx: np.ndarray,
                        t_idx: np.ndarray) -> np.ndarray:
    """[B, 6, 6]: 2 unchanged recency tokens + 4 redesigned anomaly tokens
    (top-4 by |signed score| in a 288-bin lookback, time-ordered, with
    time-since-previous-anomaly and the last inter-anomaly gap)."""
    B = len(f_idx)
    out = np.zeros((B, 2 + N_RETRIEVAL_ANOM, FEAT), np.float32)
    rec, lb, signed = tracks["rec"], tracks["lb"], tracks["signed"]
    for b, (f, t) in enumerate(zip(f_idx, t_idx)):
        for j, tb in enumerate((t - 1, t - 2)):
            out[b, j] = [rec[f, tb, 0], rec[f, tb, 1], rec[f, tb, 2],
                         rec[f, tb, 3], -(j + 1) / 4.0, 1.0]
        w0 = max(t - LOOKBACK_V2, 0)
        window = np.abs(signed[f, w0:t])
        top = np.sort(np.argsort(window)[::-1][:N_RETRIEVAL_ANOM]) + w0
        last_gap = (top[-1] - top[-2]) / BINS_PER_DAY if len(top) >= 2 else 3.0
        for j, tb in enumerate(top):
            prev_gap = ((tb - top[j - 1]) / BINS_PER_DAY if j > 0 else 3.0)
            out[b, 2 + j] = [lb[f, tb], signed[f, tb],
                             (tb - t) / BINS_PER_DAY, prev_gap, last_gap,
                             rec[f, tb, 1]]
    return out
