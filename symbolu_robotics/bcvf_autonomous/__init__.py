"""BCVF for Autonomous Systems.

Second-order cross-model coherence regularizer for multi-model predictive
control. See ``DESIGN.md`` for the full specification.

Phase 1 public API (math kernel only — no predictors or planner yet):

    from symbolu_robotics.bcvf_autonomous import (
        BCVFConfig,
        BCVFResult,
        compute_bcvf_cost,
        compute_bcvf_cost_batch,
        SE2Pose,
        body_frame_error,
        wrap_angle,
    )
"""

from symbolu_robotics.bcvf_autonomous.core import (
    BCVFConfig,
    BCVFResult,
    compute_bcvf_cost,
    compute_bcvf_cost_batch,
    compute_disagreement,
    compute_disagreement_acceleration,
    compute_disagreement_velocity,
    pseudo_huber,
    smooth_gate,
)
from symbolu_robotics.bcvf_autonomous.manifold import (
    SE2Pose,
    body_frame_error,
    body_frame_error_trajectory,
    compose,
    inverse,
    log_map,
    wrap_angle,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # core
    "BCVFConfig",
    "BCVFResult",
    "compute_bcvf_cost",
    "compute_bcvf_cost_batch",
    "compute_disagreement",
    "compute_disagreement_velocity",
    "compute_disagreement_acceleration",
    "smooth_gate",
    "pseudo_huber",
    # manifold
    "SE2Pose",
    "wrap_angle",
    "compose",
    "inverse",
    "log_map",
    "body_frame_error",
    "body_frame_error_trajectory",
]
