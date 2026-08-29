"""Synthetic stream families for the phase_temporal_collector experiment.

All parameters here are fixed by PREREGISTRATION.md and its amendments.
Streams are generated from an explicit numpy Generator so every arm trains and
evaluates on identical data.

Amendment 2 additions: `mode` replaces the heldout flag ("train" | "heldout" |
"extrap"), the informational `freq_drift` family (test-only), and per-stream
event-onset tracks returned for dense supervision. The gated families, pools,
cutoffs, and targets are unchanged.
"""
from __future__ import annotations

import numpy as np

T = 256
H = 8
CUTOFFS = (128, 192, 240)
FAMILIES = ("periodic", "drifting", "phase_shift", "irregular", "rare_event",
            "freq_drift")
TRAIN_FAMILIES = FAMILIES[:5]
FORECAST_FAMILIES = ("periodic", "drifting", "phase_shift", "irregular")

TRAIN_POOLS = [(6.0, 12.0), (20.0, 36.0), (64.0, 96.0)]
HELDOUT_POOLS = [(14.0, 18.0), (44.0, 56.0)]
EXTRAP_POOLS = [(108.0, 140.0)]  # Amendment 2, informational split only
RARE_POOLS = {"train": (64.0, 96.0), "heldout": (44.0, 56.0),
              "extrap": (108.0, 140.0)}

# Fixed harmonic clock bank: K=8 periods, log-spaced 4 -> 128 (a priori).
CLOCK_PERIODS = tuple(float(p) for p in 4.0 * (128.0 / 4.0) ** (np.arange(8) / 7.0))

NOISE_FRAC = 0.05


def _draw_period(rng: np.random.Generator, mode: str) -> float:
    pools = {"train": TRAIN_POOLS, "heldout": HELDOUT_POOLS,
             "extrap": EXTRAP_POOLS}[mode]
    lo, hi = pools[rng.integers(len(pools))]
    return float(rng.uniform(lo, hi))


def _sample_stream(rng: np.random.Generator, family: str, mode: str):
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
            p = _draw_period(rng, mode)
            a = rng.uniform(0.5, 1.5)
            amp_sum += a
            x += a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += rng.normal(0, NOISE_FRAC * amp_sum, size=T)
    elif family == "drifting":
        p = _draw_period(rng, mode)
        a = rng.uniform(0.5, 1.5)
        x = a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += np.cumsum(rng.normal(0, 0.02, size=T))          # random walk
        x += rng.uniform(-0.005, 0.005) * tau                # slow slope
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "phase_shift":
        p = _draw_period(rng, mode)
        a = rng.uniform(0.5, 1.5)
        phi = np.full(T, rng.uniform(0, 2 * np.pi))
        n_jumps = int(rng.integers(1, 3))
        for cp in sorted(rng.uniform(40, 220, size=n_jumps)):
            phi[tau >= cp] += rng.uniform(0.5 * np.pi, 1.5 * np.pi)
        x = a * np.sin(2 * np.pi * tau / p + phi)
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "irregular":
        p = _draw_period(rng, mode)
        a = rng.uniform(0.5, 1.5)
        x = a * np.sin(2 * np.pi * tau / p + rng.uniform(0, 2 * np.pi))
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    elif family == "rare_event":
        lo, hi = RARE_POOLS[mode]
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
    elif family == "freq_drift":
        # Test-only (Amendment 2): period drifts linearly by up to +/-30%.
        p0 = _draw_period(rng, "train")
        p1 = p0 * rng.uniform(0.7, 1.3)
        a = rng.uniform(0.5, 1.5)
        frac = tau / tau[-1]
        inst_p = p0 + (p1 - p0) * frac
        theta = np.cumsum(2 * np.pi * dt / inst_p) + rng.uniform(0, 2 * np.pi)
        x = a * np.sin(theta)
        x += rng.normal(0, NOISE_FRAC * a, size=T)
    else:
        raise ValueError(family)
    return x.astype(np.float32), dt.astype(np.float32), tau.astype(np.float32), onsets


def make_batch(rng: np.random.Generator, n_streams: int, mode: str,
               families=TRAIN_FAMILIES):
    """Generate a batch of streams with per-cutoff targets at the frozen CUTOFFS.

    Returns a dict of float32 numpy arrays:
      x, dt, tau, onsets: [n, T]; family_idx: [n]; y: [n, C, H]; event: [n, C];
      future_off: [n, C, H] (tau offsets of the H targets past each cutoff).
    `onsets` is all-zero for non-rare families; dense-supervision targets are
    derived from x/tau/onsets by the harness.
    """
    n = n_streams
    C = len(CUTOFFS)
    xs = np.zeros((n, T), np.float32)
    dts = np.zeros((n, T), np.float32)
    taus = np.zeros((n, T), np.float32)
    ons = np.zeros((n, T), np.float32)
    fam = np.zeros(n, np.int64)
    y = np.zeros((n, C, H), np.float32)
    ev = np.zeros((n, C), np.float32)
    fut = np.zeros((n, C, H), np.float32)
    for i in range(n):
        f = families[rng.integers(len(families))]
        x, dt, tau, onsets = _sample_stream(rng, f, mode)
        xs[i], dts[i], taus[i] = x, dt, tau
        if onsets is not None:
            ons[i] = onsets
        fam[i] = FAMILIES.index(f)
        for c, tc in enumerate(CUTOFFS):
            y[i, c] = x[tc:tc + H]
            fut[i, c] = tau[tc:tc + H] - tau[tc - 1]
            if onsets is not None:
                ev[i, c] = float(onsets[tc:tc + H].max())
    return {"x": xs, "dt": dts, "tau": taus, "onsets": ons, "family": fam,
            "y": y, "event": ev, "future_off": fut}
