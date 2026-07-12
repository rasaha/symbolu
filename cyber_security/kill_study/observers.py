"""Fast/slow observers, the equalized guard layer, and the shared consumer.

The guarded observer (`run_observer(..., guarded=True)`) applies the update
gate, verified-anchor bound, and cumulative-displacement limit. Arms H and I
consume the *same* guarded observer trace and the *same* consumer, so the
detector-core score is the only factor that differs between them.

The consumer maps a per-step standardized core score (see calibration.py) to
challenge decisions: it applies a k-sigma deadband, persistence (m-of-K), and
hysteresis. Non-guarded arms use the immediate variant (threshold on the
standardized score, no persistence/deadband).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import StudyConfig
from .trajectories import TrajectoryEvent


@dataclass
class ObserverTrace:
    m_fast: np.ndarray       # (H, D)
    m_slow: np.ndarray       # (H, D)
    d: np.ndarray            # (H, D) = m_fast - m_slow
    identity: np.ndarray     # (H,)   = ||m_fast - mu_u||
    gate_open: np.ndarray    # (H,) bool
    template_update_amount: float  # sum ||delta m_slow||


def run_observer(
    event: TrajectoryEvent, cfg: StudyConfig, guarded: bool
) -> ObserverTrace:
    """Run the fast/slow observers over an event.

    When ``guarded`` the slow template is governed by the equalized guard:
    update only when the pre-update disagreement is under the gate, subject to
    a cumulative-displacement budget and a hard verified-anchor bound.
    """
    af = cfg.observer.alpha_fast
    as_ = cfg.observer.alpha_slow
    g = cfg.guard
    z = event.z
    mask = event.mask
    mu_u = event.mu_u
    h, dim = z.shape

    # Seed both observers from the first observed sample.
    first = z[0] if mask[0] else mu_u.copy()
    m_fast = first.astype(np.float64).copy()
    m_slow = first.astype(np.float64).copy()

    m_fast_tr = np.zeros((h, dim), dtype=np.float64)
    m_slow_tr = np.zeros((h, dim), dtype=np.float64)
    d_tr = np.zeros((h, dim), dtype=np.float64)
    ident = np.zeros(h, dtype=np.float64)
    gate_open = np.zeros(h, dtype=bool)
    cum_disp = 0.0
    update_amount = 0.0

    for t in range(h):
        if mask[t]:
            zt = z[t]
            m_fast = (1.0 - af) * m_fast + af * zt
            pre_d = m_fast - m_slow
            if not guarded:
                delta = as_ * (zt - m_slow)
                m_slow = m_slow + delta
                update_amount += float(np.linalg.norm(delta))
                gate_open[t] = True
            else:
                gate_ok = float(np.linalg.norm(pre_d)) < g.gate_threshold
                if gate_ok:
                    delta = as_ * (zt - m_slow)
                    step = float(np.linalg.norm(delta))
                    if cum_disp + step <= g.cumulative_disp_limit:
                        m_slow = m_slow + delta
                        cum_disp += step
                        update_amount += step
                        gate_open[t] = True
                    # else: cumulative budget spent -> freeze
                # anchor bound: project the slow template back into the ball
                off = m_slow - mu_u
                r = float(np.linalg.norm(off))
                if r > g.anchor_radius:
                    m_slow = mu_u + off * (g.anchor_radius / r)
        # missing step: hold both observers (predict = last estimate)

        m_fast_tr[t] = m_fast
        m_slow_tr[t] = m_slow
        d_tr[t] = m_fast - m_slow
        ident[t] = float(np.linalg.norm(m_fast - mu_u))

    return ObserverTrace(
        m_fast=m_fast_tr,
        m_slow=m_slow_tr,
        d=d_tr,
        identity=ident,
        gate_open=gate_open,
        template_update_amount=update_amount,
    )


def challenge_step_for_threshold(
    s_norm: np.ndarray, threshold: float, guarded: bool, cfg: StudyConfig
) -> Optional[int]:
    """First challenge step at ``threshold``; None if never challenged.

    Non-guarded: immediate — first t with ``s_norm > threshold``.
    Guarded: k-sigma deadband + persistence (m-of-K). Both H and I use this
    identical path.
    """
    if not guarded:
        idx = np.nonzero(s_norm > threshold)[0]
        return int(idx[0]) if idx.size else None

    g = cfg.guard
    sd = s_norm - g.deadband_k                 # deadband
    elevated = sd > threshold
    k, m = g.persistence_k, g.persistence_m
    n = s_norm.shape[0]
    for t in range(n):
        lo = max(0, t - k + 1)
        if int(np.count_nonzero(elevated[lo : t + 1])) >= m:
            return t
    return None


def challenge_rate(
    s_norm: np.ndarray, threshold: float, guarded: bool, cfg: StudyConfig
) -> float:
    """Fraction of steps in an alarm state (challenge burden / flicker proxy).

    Guarded uses hysteresis for the sustained-alarm state; non-guarded counts
    raw threshold crossings.
    """
    n = s_norm.shape[0]
    if n == 0:
        return 0.0
    if not guarded:
        return float(np.count_nonzero(s_norm > threshold)) / n

    g = cfg.guard
    sd = s_norm - g.deadband_k
    # hysteresis: turn on above (threshold+hyst_on-band), off below hyst_off
    on_thr = threshold
    off_thr = threshold - (g.hyst_on - g.hyst_off)
    alarm = False
    count = 0
    for t in range(n):
        if not alarm and sd[t] > on_thr:
            alarm = True
        elif alarm and sd[t] < off_thr:
            alarm = False
        if alarm:
            count += 1
    return count / n
