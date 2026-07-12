"""Deterministic configuration for the BCVF-Bio adversarial synthetic kill study.

All numeric knobs live here so a single run manifest can capture the full
configuration. Nothing in this study reads a clock, a global RNG, or the
network; every random draw is derived from an explicit integer seed.

Scope: synthetic falsification only. No human data, no biometric claim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

# Fixed structural constants (not swept).
EMBED_DIM: int = 2          # behavioural embedding dimension (>=2 so D_parallel/D_perp exist)
HORIZON: int = 200          # timesteps per event
ONSET: int = 80             # nominal takeover / disturbance onset step
DT: float = 1.0             # arbitrary time unit


@dataclass(frozen=True)
class GuardParams:
    """The equalized protection layer shared byte-for-byte by arms H and I."""

    anchor_radius: float = 2.0          # ||m_slow - mu_u|| hard bound
    gate_threshold: float = 0.9         # update slow only when ||d|| < this
    cumulative_disp_limit: float = 6.0  # cap on total ||delta m_slow|| per event
    deadband_k: float = 2.0             # k-sigma significance gate (EMA-centered)
    ema_center_alpha: float = 0.05      # EMA rate for centering the core score
    hyst_on: float = 3.0                # normalized alarm-on threshold (z-units)
    hyst_off: float = 1.5               # normalized alarm-off threshold (z-units)
    persistence_k: int = 5              # window length K
    persistence_m: int = 3              # require m-of-K elevated windows


@dataclass(frozen=True)
class ObserverParams:
    alpha_fast: float = 0.30
    alpha_slow: float = 0.02


@dataclass(frozen=True)
class DetectorParams:
    # CUSUM
    cusum_kappa: float = 0.25           # slack (drift-tolerance) per step
    # BCVF composite weights
    w_identity: float = 1.0
    w_disagree: float = 1.0
    w_accel: float = 1.0
    bcvf_gate_threshold: float = 0.3    # gate on ||d|| for the second-order term
    bcvf_gate_beta: float = 40.0
    huber_delta: float = 0.5
    # LLT Kalman (local linear trend)
    llt_q_level: float = 1e-4           # process noise on level
    llt_q_slope: float = 1e-5           # process noise on slope
    llt_r_obs: float = 0.09             # observation noise (matched to nominal sigma^2)


@dataclass(frozen=True)
class DamagePolicy:
    """Fixed, preregistered, front-loaded attacker action policy.

    Worst case for a detector: the highest-value action is available in the
    first window after takeover, so slow detection is maximally costly. The
    policy is identical for every arm and never tuned.
    """

    horizon: int = 40                   # steps over which damage accrues post-onset
    peak: float = 1.0                   # weight at onset
    floor: float = 0.1                  # weight far after onset

    def weight(self, steps_since_onset: int) -> float:
        if steps_since_onset < 0:
            return 0.0
        if steps_since_onset >= self.horizon:
            return self.floor
        frac = steps_since_onset / float(self.horizon)
        return self.peak + (self.floor - self.peak) * frac


# --- Sweep grids: dev and held-out occupy DISJOINT ranges ---
# Thresholds are tuned on DEV_GRID; every reported number is on EVAL_GRID.

DEV_GRID: Dict[str, List[float]] = {
    "sigma": [0.25, 0.35],
    "separation": [3.0, 4.0],
    "ramp_duration": [90.0],
    "missing_rate": [0.0],
}

EVAL_GRID: Dict[str, List[float]] = {
    "sigma": [0.30, 0.45],           # 0.45 unseen in dev
    "separation": [3.5, 5.0],        # 5.0 unseen in dev
    "ramp_duration": [70.0, 110.0],  # both unseen in dev
    "missing_rate": [0.0, 0.3],
}

# Preregistered FAR budget for DET summarisation and operating-point tuning.
FAR_BUDGET: float = 0.05             # target false-challenge rate per legit event
DET_FIXED_FAR: float = 0.05          # detection-at-fixed-FAR operating point

# Threshold sweep for the DET frontier (normalized z-score units).
THRESHOLD_SWEEP: Tuple[float, ...] = tuple(
    round(0.5 * i, 4) for i in range(0, 25)   # 0.0 .. 12.0, 25 points
)

# Statistics
N_BOOT: int = 2000
BOOT_SEED: int = 20260712

# Seed layout: dev and eval seed pools are disjoint.
DEV_SEED_BASE: int = 0
EVAL_SEED_BASE: int = 1_000_000


@dataclass(frozen=True)
class StudyConfig:
    guard: GuardParams = field(default_factory=GuardParams)
    observer: ObserverParams = field(default_factory=ObserverParams)
    detector: DetectorParams = field(default_factory=DetectorParams)
    damage: DamagePolicy = field(default_factory=DamagePolicy)
    embed_dim: int = EMBED_DIM
    horizon: int = HORIZON
    onset: int = ONSET
    dt: float = DT
    dev_seeds_per_cell: int = 8
    eval_seeds_per_cell: int = 16

    def to_dict(self) -> dict:
        return {
            "guard": asdict(self.guard),
            "observer": asdict(self.observer),
            "detector": asdict(self.detector),
            "damage": {k: v for k, v in asdict(self.damage).items()},
            "embed_dim": self.embed_dim,
            "horizon": self.horizon,
            "onset": self.onset,
            "dt": self.dt,
            "dev_seeds_per_cell": self.dev_seeds_per_cell,
            "eval_seeds_per_cell": self.eval_seeds_per_cell,
            "dev_grid": DEV_GRID,
            "eval_grid": EVAL_GRID,
            "far_budget": FAR_BUDGET,
            "det_fixed_far": DET_FIXED_FAR,
            "threshold_sweep": list(THRESHOLD_SWEEP),
            "n_boot": N_BOOT,
            "boot_seed": BOOT_SEED,
        }


# Family registry -------------------------------------------------------------

LEGIT_FAMILIES: Tuple[str, ...] = (
    "F01_stable",
    "F02_constant_offset",
    "F03_linear_drift",
    "F04_smooth_nonlinear_drift",
    "F05_abrupt_device_switch",
)

ATTACK_FAMILIES: Tuple[str, ...] = (
    "F06_abrupt_takeover",
    "F07_slow_linear_takeover",
    "F08_smooth_low_curvature_takeover",
    "F09_gate_aware_poisoning",
    "F10_detector_aware_optimized",
    "F11_replay_low_noise",
    "F12_sparse_missing_evidence",
)

# The adaptive-attack set that gates SECOND_ORDER_ADDS_SECURITY_VALUE.
ADAPTIVE_ATTACK_FAMILIES: Tuple[str, ...] = (
    "F07_slow_linear_takeover",
    "F08_smooth_low_curvature_takeover",
    "F09_gate_aware_poisoning",
    "F10_detector_aware_optimized",
)

# Legitimate-drift families that gate FRICTION_ONLY.
DRIFT_FRICTION_FAMILIES: Tuple[str, ...] = (
    "F02_constant_offset",
    "F03_linear_drift",
    "F04_smooth_nonlinear_drift",
)

ALL_FAMILIES: Tuple[str, ...] = LEGIT_FAMILIES + ATTACK_FAMILIES
