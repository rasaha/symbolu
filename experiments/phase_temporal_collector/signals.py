"""Synthetic stream families for the phase_temporal_collector experiment.

All parameters here are fixed by PREREGISTRATION.md. Streams are generated from
an explicit numpy Generator so every arm trains and evaluates on identical data.
"""
from __future__ import annotations

import numpy as np

T = 256
H = 8
CUTOFFS = (128, 192, 240)
FAMILIES = ("periodic", "drifting", "phase_shift", "irregular", "rare_event")
FORECAST_FAMILIES = ("periodic", "drifting", "phase_shift", "irregular")

TRAIN_POOLS = [(6.0, 12.0), (20.0, 36.0), (64.0, 96.0)]
HELDOUT_POOLS = [(14.0, 18.0), (44.0, 56.0)]
RARE_TRAIN_POOL = (64.0, 96.0)
RARE_HELDOUT_POOL = (44.0, 56.0)

# Fixed harmonic clock bank: K=8 periods, log-spaced 4 -> 128 (a priori).
CLOCK_PERIODS = tuple(float(p) for p in 4.0 * (128.0 / 4.0) ** (np.arange(8) / 7.0))

NOISE_FRAC = 0.05


def _draw_period(rng: np.random.Generator, heldout: bool) -> float:
    pools = HELDOUT_POOLS if heldout else TRAIN_POOLS
    lo, hi = pools[rng.integers(len(pools))]
    return float(rng.uniform(lo, hi))


def _sample_stream(rng: np.random.Generator, family: str, heldout: bool):
    """Return (x[T], dt[T], tau[T], event_onset[T] or None)."""
    dt = np.ones(T)
    onsets = None
    if family == "irregular":
        dt = 0.5 + rng.exponential(1.0, size=T)
    tau = np.cumsum(dt)

    if family == "periodic":
        x = np.zeros(T)
        amp_sum = 0.0
        for _ in range(2):
            p = _draw_period(rng, heldout)
            a = rng.uniform(0.5, 1.5)
            amp_sum += a
            x += a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += rng.normal(0, NOISE_FRAC * amp_sum, size=T)
    elif family == "drifting":
        p = _draw_period(rng, heldout)
        a = rng.uniform(0.5, 1.5)
        x = a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += np.cumsum(rng.normal(0, 0.02, size=T))          # random walk
        x += rng.uniform(-0.005, 0.005) * tau                # slow slope
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "phase_shift":
        p = _draw_period(rng, heldout)
        a = rng.uniform(0.5, 1.5)
        phi = np.full(T, rng.uniform(0, 2 * np.pi))
        n_jumps = int(rng.integers(1, 3))
        for cp in sorted(rng.uniform(40, 220, size=n_jumps)):
            phi[tau >= cp] += rng.uniform(0.5 * np.pi, 1.5 * np.pi)
        x = a * np.sin(2 * np.pi * tau / p + phi)
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "irregular":
        p = _draw_period(rng, heldout)
        a = rng.uniform(0.5, 1.5)
        x = a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "rare_event":
        lo, hi = RARE_HELDOUT_POOL if heldout else RARE_TRAIN_POOL
        pe = rng.uniform(lo, hi)
        x = rng.normal(0, 0.1, size=T)
        onsets = np.zeros(T, dtype=np.float64)
        t0 = rng.uniform(0, pe)
        spike_times = []
        while t0 < tau[-1] + 1:
            spike_times.append(t0)
            t0 += pe * rng.uniform(0.9, 1.1)
        amp = 2.5 * rng.uniform(0.8, 1.2)
        for st in spike_times:
            idx = np.searchsorted(tau, st)
            if idx >= T:
                continue
            onsets[idx] = 1.0
            span = np.arange(idx, min(idx + 6, T))
            x[span] += amp * np.exp(-(tau[span] - tau[idx]) / 2.0)
    else:
        raise ValueError(family)
    return x.astype(np.float32), dt.astype(np.float32), tau.astype(np.float32), onsets


def make_batch(rng: np.random.Generator, n_streams: int, heldout: bool,
               families=FAMILIES):
    """Generate a batch of streams; each stream yields len(CUTOFFS) examples.

    Returns a dict of float32 numpy arrays:
      x, dt, tau: [n, T]; family_idx: [n]; y: [n, C, H]; event: [n, C];
      future_off: [n, C, H] (tau offsets of the H targets past each cutoff).
    """
    n = n_streams
    C = len(CUTOFFS)
    xs = np.zeros((n, T), np.float32)
    dts = np.zeros((n, T), np.float32)
    taus = np.zeros((n, T), np.float32)
    fam = np.zeros(n, np.int64)
    y = np.zeros((n, C, H), np.float32)
    ev = np.zeros((n, C), np.float32)
    fut = np.zeros((n, C, H), np.float32)
    for i in range(n):
        f = families[rng.integers(len(families))]
        x, dt, tau, onsets = _sample_stream(rng, f, heldout)
        xs[i], dts[i], taus[i] = x, dt, tau
        fam[i] = FAMILIES.index(f)
        for c, tc in enumerate(CUTOFFS):
            y[i, c] = x[tc:tc + H]
            fut[i, c] = tau[tc:tc + H] - tau[tc - 1]
            if onsets is not None:
                ev[i, c] = float(onsets[tc:tc + H].max())
    return {"x": xs, "dt": dts, "tau": taus, "family": fam,
            "y": y, "event": ev, "future_off": fut}
