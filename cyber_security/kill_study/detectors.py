"""The nine detector arms (A-I).

Each arm maps an event to a per-step raw core score. A separate Calibration
(calibration.py, fit on DEV-legit) standardizes each arm's raw score onto a
comparable DET axis; ``score()`` applies it. Arms H and I read the *same*
guarded observer trace; only the core score differs. The guard/consumer layer
lives in observers.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

import numpy as np

from .config import StudyConfig
from .observers import ObserverTrace, run_observer
from .trajectories import TrajectoryEvent


@dataclass
class ArmOutput:
    arm: str
    guarded: bool
    s_raw: np.ndarray        # (H,)
    s_norm: np.ndarray       # (H,) causal z-score
    trace: ObserverTrace     # observer states (guarded for H/I)


# --- primitive signal transforms -------------------------------------------


def cusum(r: np.ndarray, kappa: float) -> np.ndarray:
    """One-sided CUSUM: S_t = max(0, S_{t-1} + (r_t - kappa))."""
    out = np.zeros_like(r, dtype=np.float64)
    s = 0.0
    for t in range(r.shape[0]):
        s = max(0.0, s + (float(r[t]) - kappa))
        out[t] = s
    return out


def pseudo_huber(r: np.ndarray, delta: float) -> np.ndarray:
    r = np.asarray(r, dtype=np.float64)
    return (delta * delta) * (np.sqrt(1.0 + (r / delta) ** 2) - 1.0)


def second_difference(d: np.ndarray) -> np.ndarray:
    """||Delta^2 d|| aligned to length H (first two steps padded with 0)."""
    h = d.shape[0]
    out = np.zeros(h, dtype=np.float64)
    if h >= 3:
        a = d[2:] - 2.0 * d[1:-1] + d[:-2]        # (H-2, D)
        out[2:] = np.linalg.norm(a, axis=-1)
    return out


def _gated_second_order(trace: ObserverTrace, cfg: StudyConfig) -> np.ndarray:
    """Gated pseudo-Huber of the second-order disagreement (BCVF core term)."""
    dp = cfg.detector
    dnorm = np.linalg.norm(trace.d, axis=-1)
    arg = np.clip(dp.bcvf_gate_beta * (dnorm - dp.bcvf_gate_threshold), -50.0, 50.0)
    gate = 1.0 / (1.0 + np.exp(-arg))
    accel = second_difference(trace.d)
    return gate * pseudo_huber(accel, dp.huber_delta)


def llt_cusum_raw(event: TrajectoryEvent, cfg: StudyConfig) -> np.ndarray:
    """Local-linear-trend Kalman innovations + CUSUM (per-dim LLT, fused).

    State per dim: [level, slope], F=[[1,1],[0,1]], H=[1,0]. Legitimate linear
    drift is absorbed by the slope state, so innovations are white under
    constant-slope drift; a change of slope or a jump produces surprise that
    CUSUM accumulates. Missing observations -> predict only (no update).
    """
    dp = cfg.detector
    z = event.z
    mask = event.mask
    h, dim = z.shape
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    Qd = np.array([[dp.llt_q_level, 0.0], [0.0, dp.llt_q_slope]])
    Hm = np.array([[1.0, 0.0]])
    R = dp.llt_r_obs

    innov_mag = np.zeros(h, dtype=np.float64)
    # independent filter per dimension
    x = [np.array([z[0, dcol] if mask[0] else 0.0, 0.0]) for dcol in range(dim)]
    P = [np.eye(2) * 1.0 for _ in range(dim)]
    for t in range(h):
        acc = 0.0
        for dcol in range(dim):
            xp = F @ x[dcol]
            Pp = F @ P[dcol] @ F.T + Qd
            if mask[t]:
                y = float(z[t, dcol]) - float((Hm @ xp)[0])
                S = float((Hm @ Pp @ Hm.T)[0, 0]) + R
                K = (Pp @ Hm.T) / S            # (2,1)
                x[dcol] = xp + (K[:, 0] * y)
                P[dcol] = (np.eye(2) - K @ Hm) @ Pp
                acc += (y * y) / S             # squared normalized innovation
            else:
                x[dcol] = xp
                P[dcol] = Pp
        innov_mag[t] = np.sqrt(acc)            # ~ chi-like surprise magnitude
    return cusum(innov_mag, dp.cusum_kappa)


# --- composite channels -----------------------------------------------------
#
# The guarded composite arms H and I are structurally identical: both fuse a
# verified-identity channel, a fast/slow disagreement channel, and a temporal
# change channel. They differ ONLY in the temporal channel — H uses the BCVF
# second-order term, I uses the LLT-Kalman+CUSUM innovation. Each channel is
# z-scored against its own DEV-legit null so the three contribute on equal
# footing and no channel is implicitly up-weighted. This makes H vs I a clean
# attribution test of the second-order term, and gives the LLT+CUSUM baseline
# the SAME identity/disagreement information as BCVF (an identity-blind LLT
# baseline would rig the comparison toward BCVF).


def channel_identity(trace: ObserverTrace) -> np.ndarray:
    return trace.identity.copy()


def channel_disagreement(trace: ObserverTrace) -> np.ndarray:
    return np.linalg.norm(trace.d, axis=-1)


def channel_accel2nd(trace: ObserverTrace, cfg: StudyConfig) -> np.ndarray:
    return _gated_second_order(trace, cfg)


def _cfg_signature(cfg: StudyConfig) -> tuple:
    o, g, d = cfg.observer, cfg.guard, cfg.detector
    return (
        o.alpha_fast, o.alpha_slow,
        g.anchor_radius, g.gate_threshold, g.cumulative_disp_limit,
        d.cusum_kappa, d.bcvf_gate_threshold, d.bcvf_gate_beta, d.huber_delta,
        d.llt_q_level, d.llt_q_slope, d.llt_r_obs,
        cfg.embed_dim, cfg.horizon, cfg.onset,
        cfg.dev_seeds_per_cell,
    )


_CHANNEL_STATS_CACHE: Dict[tuple, Dict[str, tuple]] = {}


def guarded_channel_stats(cfg: StudyConfig) -> Dict[str, tuple]:
    """(mean, std) of each guarded composite channel over DEV-legit events.

    Computed directly from the base channels (never calls the composite arms),
    so there is no circular dependency with the per-arm calibration.
    """
    import itertools

    from .config import ALL_FAMILIES, DEV_GRID, DEV_SEED_BASE, LEGIT_FAMILIES
    from .trajectories import generate

    sig = _cfg_signature(cfg)
    if sig in _CHANNEL_STATS_CACHE:
        return _CHANNEL_STATS_CACHE[sig]

    keys = ("sigma", "separation", "ramp_duration", "missing_rate")
    cells = list(itertools.product(*(DEV_GRID[k] for k in keys)))
    pools: Dict[str, list] = {"identity": [], "disagreement": [],
                              "accel2nd": [], "lltcusum": []}
    for family in LEGIT_FAMILIES:
        true_idx = ALL_FAMILIES.index(family)
        for cell_idx, cell in enumerate(cells):
            sigma, separation, ramp_duration, missing_rate = cell
            for seed_idx in range(cfg.dev_seeds_per_cell):
                seed = (DEV_SEED_BASE + true_idx * 100_000
                        + cell_idx * 1_000 + seed_idx)
                ev = generate(family, seed=seed, cfg=cfg, sigma=sigma,
                              separation=separation, ramp_duration=ramp_duration,
                              missing_rate=missing_rate)
                tr = run_observer(ev, cfg, guarded=True)
                pools["identity"].append(channel_identity(tr))
                pools["disagreement"].append(channel_disagreement(tr))
                pools["accel2nd"].append(channel_accel2nd(tr, cfg))
                pools["lltcusum"].append(llt_cusum_raw(ev, cfg))
    stats = {}
    for name, vals in pools.items():
        allv = np.concatenate(vals)
        stats[name] = (float(np.mean(allv)), float(np.std(allv)))
    _CHANNEL_STATS_CACHE[sig] = stats
    return stats


def _zc(x: np.ndarray, stat: tuple) -> np.ndarray:
    mu, sd = stat
    return (x - mu) / (sd + 1e-9)


# --- arm score builders -----------------------------------------------------


def arm_A(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = tr.identity.copy()
    return ArmOutput("A_static_identity", False, s_raw,
                     s_raw.copy(), tr)


def arm_B(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = np.linalg.norm(tr.d, axis=-1)
    return ArmOutput("B_ewma_disagreement", False, s_raw,
                     s_raw.copy(), tr)


def arm_C(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = cusum(np.linalg.norm(tr.d, axis=-1), cfg.detector.cusum_kappa)
    return ArmOutput("C_cusum_disagreement", False, s_raw,
                     s_raw.copy(), tr)


def arm_D(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = cusum(tr.identity, cfg.detector.cusum_kappa)
    return ArmOutput("D_cusum_identity", False, s_raw,
                     s_raw.copy(), tr)


def arm_E(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = llt_cusum_raw(event, cfg)
    return ArmOutput("E_llt_kalman_cusum", False, s_raw,
                     s_raw.copy(), tr)


def arm_F(event, cfg):
    tr = run_observer(event, cfg, guarded=False)
    s_raw = _gated_second_order(tr, cfg)
    return ArmOutput("F_bcvf_second_order_only", False, s_raw,
                     s_raw.copy(), tr)


def arm_G(event, cfg):
    """BCVF composite (unguarded): z(identity)+z(disagreement)+z(second-order)."""
    tr = run_observer(event, cfg, guarded=False)
    dp = cfg.detector
    st = guarded_channel_stats(cfg)  # shared channel scaling (guarded-null)
    s_raw = (
        dp.w_identity * _zc(channel_identity(tr), st["identity"])
        + dp.w_disagree * _zc(channel_disagreement(tr), st["disagreement"])
        + dp.w_accel * _zc(channel_accel2nd(tr, cfg), st["accel2nd"])
    )
    return ArmOutput("G_bcvf_composite", False, s_raw, s_raw.copy(), tr)


def arm_H(event, cfg):
    """Full guarded BCVF composite: identity + disagreement + SECOND-ORDER.

    Structurally identical to arm I except the temporal channel is the BCVF
    second-order term. Channels are z-scored on the shared guarded-null so the
    three contribute on equal footing.
    """
    tr = run_observer(event, cfg, guarded=True)
    dp = cfg.detector
    st = guarded_channel_stats(cfg)
    s_raw = (
        dp.w_identity * _zc(channel_identity(tr), st["identity"])
        + dp.w_disagree * _zc(channel_disagreement(tr), st["disagreement"])
        + dp.w_accel * _zc(channel_accel2nd(tr, cfg), st["accel2nd"])
    )
    return ArmOutput("H_guarded_bcvf_composite", True, s_raw, s_raw.copy(), tr)


def arm_I(event, cfg):
    """Full guarded LLT-Kalman+CUSUM baseline: identity + disagreement + LLT-CUSUM.

    The fair, guards-equalized strong baseline. Identical to arm H except the
    temporal channel is the LLT-Kalman+CUSUM innovation instead of the BCVF
    second-order term — so H vs I isolates the second-order term alone, and the
    LLT+CUSUM baseline gets the SAME identity/disagreement channels as BCVF.
    It reads the same guarded observer trace, so the poisoning/template metrics
    are equalized by construction. Arm E is the pure (unguarded) LLT+CUSUM.
    """
    tr = run_observer(event, cfg, guarded=True)
    dp = cfg.detector
    st = guarded_channel_stats(cfg)
    s_raw = (
        dp.w_identity * _zc(channel_identity(tr), st["identity"])
        + dp.w_disagree * _zc(channel_disagreement(tr), st["disagreement"])
        + dp.w_accel * _zc(llt_cusum_raw(event, cfg), st["lltcusum"])
    )
    return ArmOutput("I_guarded_llt_kalman_cusum", True, s_raw, s_raw.copy(), tr)


ARMS: Dict[str, Callable[[TrajectoryEvent, StudyConfig], ArmOutput]] = {
    "A": arm_A,
    "B": arm_B,
    "C": arm_C,
    "D": arm_D,
    "E": arm_E,
    "F": arm_F,
    "G": arm_G,
    "H": arm_H,
    "I": arm_I,
}

ARM_ORDER = ("A", "B", "C", "D", "E", "F", "G", "H", "I")


def score(arm_key, event, cfg, calibration=None) -> ArmOutput:
    """Run an arm and standardize its score with ``calibration`` (if given).

    Without a calibration the arm's ``s_norm`` is its raw score (used only by
    the calibration fit pass itself).
    """
    out = ARMS[arm_key](event, cfg)
    if calibration is not None:
        out.s_norm = calibration.transform(arm_key, out.s_raw)
    return out
