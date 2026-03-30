"""12-parameter controller configuration for cloud infrastructure.

Adapted from ExperientialControllerConfig (minimal_controller.py:42-77).
Loss weights (lambda_temporal/coherence/latent) replaced with signal weights.
Gain defaults reduced for conservative cloud scaling.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# Canonical metric group definitions — shared between controller, coherence,
# and pipeline to avoid duplication.
INFRA_KEYS: Tuple[str, ...] = ("cpu", "memory")
APP_KEYS: Tuple[str, ...] = ("latency_p99", "error_rate")
BUSINESS_KEYS: Tuple[str, ...] = ("queue_depth",)


@dataclass
class InfraControllerConfig:
    """12-parameter cloud controller configuration.

    Every parameter maps to an ablation-validated CG parameter.
    """

    # --- Signal weights (3) --- replaces lambda_temporal/coherence/latent
    w_infra: float = 0.4        # Infrastructure signal weight (CPU, mem, disk)
    w_app: float = 0.4          # Application signal weight (latency, errors)
    w_business: float = 0.2     # Business signal weight (queue depth, conversions)

    # --- Plasticity gate (3) --- same as CG
    k_r: float = 2.0            # Resistance openness scaling
    k_m: float = 2.0            # Misalignment suppression scaling
    b_p: float = -1.0           # Bias floor (sigmoid(-1) = 0.27, gate never fully closes)

    # --- Adaptive gain (3) --- conservative for cloud
    G_base: float = 1.0         # Base gain (CG uses 3.0, cloud is more conservative)
    G_min: float = 0.0          # Minimum gain (0 = allow "do nothing")
    G_max: float = 3.0          # Maximum gain (3x max scaling factor)

    # --- Damping (2) --- same as CG
    k_dv: float = 1.0           # Metric variance sensitivity
    k_dc: float = 0.5           # Coherence instability sensitivity

    # --- Identity (1) --- same as CG
    alpha_base: float = 0.01    # Identity EMA learning rate

    # --- Auxiliary (not in core 12) ---
    replay_buffer_size: int = 256
    replay_ttl: int = 200       # Cycles before entries expire
    identity_dim: int = 5       # Dimension of baseline state vector (matches 5 MVP metrics)

    # --- Operational ---
    cycle_interval_seconds: float = 15.0   # How often to evaluate
    warmup_steps: int = 100                # Cycles for initial controller warmup
    damping_warmup_steps: int = 50         # Cycles to hold d=1.0 after startup (let EMAs stabilize)
    consolidation_interval: int = 240      # Cycles between identity updates (~1 hour at 15s)
    replay_interval: int = 100             # Cycles between replay sampling

    # --- Action thresholds ---
    action_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "no_action": 0.05,
        "recommend": 0.2,
        "scale_1": 0.5,
        "scale_2": 1.0,
    })

    # --- Safety bounds ---
    max_scale_out_ratio: float = 0.5   # Max +50% replicas per action
    max_scale_in_ratio: float = 0.25   # Max -25% replicas per action
    min_replicas: int = 1              # Never scale below this

    def validate(self) -> List[str]:
        """Check parameter ranges and return warnings for risky values.

        Returns:
            List of warning strings. Empty if all parameters are within
            safe ranges.
        """
        warnings = []

        # Plasticity gate — extreme k_r can paralyze the controller
        if self.k_r > 5.0:
            warnings.append(
                f"k_r={self.k_r} is very high (>5.0); plasticity gate may "
                f"become insensitive to resistance changes"
            )
        if self.b_p < -2.0:
            warnings.append(
                f"b_p={self.b_p} is very low (<-2.0); sigmoid floor drops "
                f"below 0.12, controller may be overly suppressed"
            )

        # Identity — fast EMA causes baseline to chase signal
        if self.alpha_base > 0.05:
            warnings.append(
                f"alpha_base={self.alpha_base} is very high (>0.05); identity "
                f"baseline will chase demand and suppress deviation signal"
            )

        # Damping — high k_dv over-suppresses action in noisy environments
        if self.k_dv > 3.0:
            warnings.append(
                f"k_dv={self.k_dv} is very high (>3.0); damping will "
                f"heavily suppress action during any metric variance"
            )

        # Gain — zero G_base means no action ever
        if self.G_base <= 0.0:
            warnings.append(
                f"G_base={self.G_base} is zero or negative; controller "
                f"will never produce a scaling action"
            )
        if self.G_max < self.G_base:
            warnings.append(
                f"G_max={self.G_max} < G_base={self.G_base}; gain will "
                f"be clamped below its base value"
            )

        # Signal weights — should sum to ~1.0
        total_w = self.w_infra + self.w_app + self.w_business
        if total_w < 0.5 or total_w > 2.0:
            warnings.append(
                f"Signal weights sum to {total_w:.2f}; expected ~1.0"
            )

        # Warmup — too short means controller acts on uncalibrated data
        if self.warmup_steps < 10:
            warnings.append(
                f"warmup_steps={self.warmup_steps} is very short (<10); "
                f"controller will act before EMAs stabilize"
            )

        return warnings
