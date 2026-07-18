"""Deterministic synthetic trajectory families for the kill study.

Every event is a vector process ``z_t`` in R^D. Legitimate families drift
along a benign axis (never toward the attacker prototype); attack families
move the true source toward the attacker prototype ``mu_a`` along the attack
axis. All randomness is derived from an explicit integer seed.

No human data. "user" / "attacker" are synthetic vector processes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import StudyConfig


# Fixed geometry: attack axis and (orthogonal) benign-drift axis.
def _axes(dim: int) -> tuple[np.ndarray, np.ndarray]:
    attack_axis = np.zeros(dim, dtype=np.float64)
    attack_axis[0] = 1.0
    benign_axis = np.zeros(dim, dtype=np.float64)
    benign_axis[min(1, dim - 1)] = 1.0
    return attack_axis, benign_axis


def smootherstep(x: np.ndarray) -> np.ndarray:
    """Ken Perlin's smootherstep, C2-continuous on [0, 1]."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


@dataclass
class TrajectoryEvent:
    name: str
    z: np.ndarray            # (H, D) observed embedding; NaN where missing
    mask: np.ndarray         # (H,) True where observed
    is_attack: bool
    onset: int               # takeover/disturbance onset; -1 if none
    mu_u: np.ndarray         # (D,) user prototype
    mu_a: Optional[np.ndarray]   # (D,) attacker prototype (None for legit)
    v_attack: Optional[np.ndarray]  # (D,) unit attack direction (None for legit)
    params: dict


def _apply_missing(
    z: np.ndarray, missing_rate: float, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    h = z.shape[0]
    mask = np.ones(h, dtype=bool)
    if missing_rate > 0.0:
        drop = rng.random(h) < missing_rate
        drop[0] = False  # always observe the first step
        mask = ~drop
        z = z.copy()
        z[~mask] = np.nan
    return z, mask


def _unguarded_disagreement(
    z: np.ndarray, mask: np.ndarray, cfg: StudyConfig
) -> np.ndarray:
    """Fast/slow EMA disagreement used only to make family 10 detector-aware.

    Mirrors observers.py's unguarded path (gate always on). Kept local to
    avoid an import cycle; observers.py is the authoritative version.
    """
    af, as_ = cfg.observer.alpha_fast, cfg.observer.alpha_slow
    h, d = z.shape
    m_fast = z[0].copy()
    m_slow = z[0].copy()
    dis = np.zeros((h, d), dtype=np.float64)
    for t in range(h):
        if mask[t]:
            zt = z[t]
            m_fast = (1 - af) * m_fast + af * zt
            m_slow = (1 - as_) * m_slow + as_ * zt
        dis[t] = m_fast - m_slow
    return dis


def _peak_second_diff(dis: np.ndarray) -> float:
    if dis.shape[0] < 3:
        return 0.0
    a = dis[2:] - 2.0 * dis[1:-1] + dis[:-2]
    return float(np.linalg.norm(a, axis=-1).max())


def generate(
    family: str,
    seed: int,
    cfg: StudyConfig,
    sigma: float,
    separation: float,
    ramp_duration: float,
    missing_rate: float,
) -> TrajectoryEvent:
    """Generate one deterministic event for ``family`` at ``seed``."""
    rng = np.random.default_rng(seed)
    dim = cfg.embed_dim
    h = cfg.horizon
    onset = cfg.onset
    attack_axis, benign_axis = _axes(dim)
    mu_u = np.zeros(dim, dtype=np.float64)
    mu_a = separation * attack_axis
    t = np.arange(h, dtype=np.float64)
    noise = rng.normal(0.0, sigma, size=(h, dim))

    is_attack = False
    ev_onset = -1
    ev_mu_a: Optional[np.ndarray] = None
    ev_v: Optional[np.ndarray] = None

    if family == "F01_stable":
        signal = np.tile(mu_u, (h, 1))

    elif family == "F02_constant_offset":
        offset = 1.2 * benign_axis  # bounded, benign, < anchor_radius
        signal = np.tile(mu_u + offset, (h, 1))

    elif family == "F03_linear_drift":
        end = 1.5  # bounded benign endpoint
        signal = np.outer(end * (t / (h - 1)), benign_axis) + mu_u

    elif family == "F04_smooth_nonlinear_drift":
        amp = 1.2
        base = np.outer(amp * smootherstep(t / (h - 1)), benign_axis)
        wobble = np.outer(0.15 * np.sin(2.0 * np.pi * t / 90.0), benign_axis)
        signal = mu_u + base + wobble

    elif family == "F05_abrupt_device_switch":
        jump = 1.4 * benign_axis  # benign but abrupt (false-positive stressor)
        step = (t >= onset).astype(np.float64)
        signal = mu_u + np.outer(step, jump)

    elif family == "F06_abrupt_takeover":
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        step = (t >= onset).astype(np.float64)
        signal = mu_u + np.outer(step, mu_a - mu_u)

    elif family == "F07_slow_linear_takeover":
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        frac = np.clip((t - onset) / max(ramp_duration, 1.0), 0.0, 1.0)
        signal = mu_u + np.outer(frac, mu_a - mu_u)

    elif family == "F08_smooth_low_curvature_takeover":
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        frac = smootherstep((t - onset) / max(ramp_duration, 1.0))
        signal = mu_u + np.outer(frac, mu_a - mu_u)

    elif family == "F09_gate_aware_poisoning":
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        # Constant velocity tuned to keep steady-state ||d|| just under the gate.
        af, as_ = cfg.observer.alpha_fast, cfg.observer.alpha_slow
        lag = abs((1 - af) / af - (1 - as_) / as_)
        v_edge = 0.95 * cfg.guard.gate_threshold / max(lag, 1e-6)
        disp = v_edge * np.clip(t - onset, 0.0, None)
        disp = np.minimum(disp, separation)  # cannot exceed the attacker prototype
        signal = mu_u + np.outer(disp, attack_axis)

    elif family == "F10_detector_aware_optimized":
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        # Search a smoothness parameter to MINIMISE peak ||Delta^2 d|| while
        # still reaching mu_a. This constructs the worst case for the
        # second-order detector (adversary-first).
        best = None
        for width_mult in (1.0, 1.5, 2.0, 3.0, 4.0):
            dur = min(ramp_duration * width_mult, float(h - onset - 1))
            frac = smootherstep((t - onset) / max(dur, 1.0))
            cand = mu_u + np.outer(frac, mu_a - mu_u)
            # observe under nominal (fully-present) sampling for the search
            full_mask = np.ones(h, dtype=bool)
            dis = _unguarded_disagreement(cand + 0.0, full_mask, cfg)
            peak = _peak_second_diff(dis)
            if best is None or peak < best[0]:
                best = (peak, cand)
        signal = best[1]

    elif family == "F11_replay_low_noise":
        # Impostor replays captured user telemetry: matches mu_u, abnormally
        # clean. No liveness channel exists -> expected to defeat all arms.
        is_attack = True
        ev_onset = 0
        ev_mu_a, ev_v = mu_u.copy(), attack_axis
        signal = np.tile(mu_u, (h, 1))
        noise = rng.normal(0.0, sigma / 10.0, size=(h, dim))

    elif family == "F12_sparse_missing_evidence":
        # Slow linear takeover under forced heavy missingness.
        is_attack = True
        ev_onset = onset
        ev_mu_a, ev_v = mu_a, attack_axis
        frac = np.clip((t - onset) / max(ramp_duration, 1.0), 0.0, 1.0)
        signal = mu_u + np.outer(frac, mu_a - mu_u)
        missing_rate = max(missing_rate, 0.3)

    else:
        raise ValueError(f"unknown family {family!r}")

    z = signal + noise
    z, mask = _apply_missing(z, missing_rate, rng)

    return TrajectoryEvent(
        name=family,
        z=z,
        mask=mask,
        is_attack=is_attack,
        onset=ev_onset,
        mu_u=mu_u,
        mu_a=ev_mu_a,
        v_attack=ev_v,
        params={
            "seed": seed,
            "sigma": sigma,
            "separation": separation,
            "ramp_duration": ramp_duration,
            "missing_rate": missing_rate,
        },
    )
