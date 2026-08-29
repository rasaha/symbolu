"""Event-labelled synthetic streams for the HarmonicEventCollector experiment.

All numbers are fixed by PREREGISTRATION.md. Each stream carries ground-truth
event onsets (index, family). Stage A streams (T=4096) test eventization;
Stage B streams (T=768) add causal structure between events for the reasoning
task.
"""
from __future__ import annotations

import numpy as np

EVENT_FAMILIES = ("periodic_deviation", "phase_shift", "regime_change",
                  "quasi_periodic_event", "rare_aperiodic")
T_A = 4096
T_B = 768
BASE_POOLS = [(6.0, 12.0), (20.0, 36.0), (64.0, 96.0)]
MIN_SEP = 32
EDGE = 64

# Per-family onset match tolerance (PREREGISTRATION.md table).
TOLERANCE = {"periodic_deviation": 8, "phase_shift": 24, "regime_change": 24,
             "quasi_periodic_event": 8, "rare_aperiodic": 8}


def _base_period(rng):
    lo, hi = BASE_POOLS[rng.integers(len(BASE_POOLS))]
    return float(rng.uniform(lo, hi))


def _pick_onsets(rng, n, taken, T):
    """n onset indices in [EDGE, T-EDGE], >= MIN_SEP from everything in taken."""
    out = []
    for _ in range(200):
        if len(out) == n:
            break
        c = int(rng.integers(EDGE, T - EDGE))
        if all(abs(c - o) >= MIN_SEP for o in taken + out):
            out.append(c)
    return out


def _spike(x, onset, amp, T):
    span = np.arange(onset, min(onset + 6, T))
    x[span] += amp * np.exp(-(span - onset) / 2.0)


def gen_stream(rng: np.random.Generator, T: int, quasi_period_range,
               n_deviation, n_phase_shift, n_regime, n_rare, couple: bool):
    """Build one labelled stream. Returns (x, labels) with labels a list of
    (onset_index, family_name)."""
    P0 = _base_period(rng)
    A0 = float(rng.uniform(0.7, 1.3))
    labels = []

    # Persistent-change schedules (phase jumps, regime changes).
    taken = []
    ps_onsets = _pick_onsets(rng, n_phase_shift, taken, T)
    taken += ps_onsets
    rg_onsets = _pick_onsets(rng, n_regime, taken, T)
    taken += rg_onsets

    period = np.full(T, P0)
    amp = np.full(T, A0)
    phase_add = np.zeros(T)
    for o in ps_onsets:
        phase_add[o:] += rng.uniform(0.5 * np.pi, 1.5 * np.pi)
        labels.append((o, "phase_shift"))
    for o in rg_onsets:
        kind = rng.integers(3)
        if kind == 0:
            period[o:] = period[o:] * rng.uniform(1.3, 1.8)
        elif kind == 1:
            amp[o:] = amp[o:] * rng.uniform(0.4, 0.6)
        else:
            amp[o:] = 0.1 * A0  # oscillation collapse
        labels.append((o, "regime_change"))
    theta = np.cumsum(2 * np.pi / period) + rng.uniform(0, 2 * np.pi) + phase_add
    x = amp * np.sin(theta)

    # Quasi-periodic spike train.
    pe = rng.uniform(*quasi_period_range)
    t0 = rng.uniform(EDGE, EDGE + pe)
    while t0 < T - EDGE:
        o = int(t0)
        if all(abs(o - q) >= MIN_SEP for q, _ in labels):
            _spike(x, o, 2.5 * rng.uniform(0.8, 1.2), T)
            labels.append((o, "quasi_periodic_event"))
        t0 += pe * rng.uniform(0.9, 1.1)
    taken = [o for o, _ in labels]

    # One-off periodic deviations: bump near a cycle peak, shifted +/-0.25 P.
    for o in _pick_onsets(rng, n_deviation, taken, T):
        p_here = period[o]
        center = o + int(p_here / 8)
        width = max(1.0, p_here / 8)
        span = np.arange(max(0, center - int(4 * width)),
                         min(T, center + int(4 * width) + 1))
        x[span] += (rng.choice([-1.0, 1.0]) * rng.uniform(0.8, 1.2) * A0
                    * np.exp(-((span - center) ** 2) / (2 * width ** 2)))
        labels.append((o, "periodic_deviation"))
        taken.append(o)

    # Rare aperiodic transients (+ optional causal coupling for Stage B).
    rare_onsets = _pick_onsets(rng, n_rare, taken, T)
    if couple:
        for o in ps_onsets + rg_onsets:
            if rng.uniform() < 0.8:
                c = o + int(rng.integers(20, 61))
                if c < T - EDGE and all(abs(c - q) >= MIN_SEP for q in taken + rare_onsets):
                    rare_onsets.append(c)
    for o in rare_onsets:
        w = rng.uniform(4, 10)
        a = rng.choice([-1.0, 1.0]) * rng.uniform(1.5, 3.0)
        span = np.arange(o, min(o + int(4 * w), T))
        x[span] += a * np.exp(-(span - o) / w)
        labels.append((o, "rare_aperiodic"))

    # Distractors: Student-t noise (df=5) and a slow random-walk drift.
    x += rng.standard_t(5, size=T) * 0.05 * A0
    x += np.cumsum(rng.normal(0, 0.01, size=T))
    labels.sort()
    return x.astype(np.float32), labels


def gen_stage_a(rng: np.random.Generator):
    return gen_stream(rng, T_A, quasi_period_range=(256.0, 384.0),
                      n_deviation=int(rng.integers(2, 5)),
                      n_phase_shift=int(rng.integers(1, 3)),
                      n_regime=int(rng.integers(1, 3)),
                      n_rare=int(rng.integers(1, 4)), couple=False)


def gen_stage_b(rng: np.random.Generator):
    return gen_stream(rng, T_B, quasi_period_range=(96.0, 160.0),
                      n_deviation=int(rng.integers(1, 3)),
                      n_phase_shift=int(rng.integers(0, 2)),
                      n_regime=int(rng.integers(1, 2)),
                      n_rare=int(rng.integers(0, 2)), couple=True)


def onset_track(labels, T: int) -> np.ndarray:
    tr = np.zeros(T, np.float32)
    for o, _ in labels:
        tr[o] = 1.0
    return tr
