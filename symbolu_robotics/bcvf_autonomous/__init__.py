"""BCVF for Autonomous Systems.

Second-order cross-model coherence regularizer for multi-model predictive
control. See ``DESIGN.md`` for the full specification.

Public API through Phase 1.5 (math kernel + disagreement signal
characterization — no predictors or planner yet):

    from symbolu_robotics.bcvf_autonomous import (
        BCVFConfig,
        BCVFResult,
        compute_bcvf_cost,
        compute_bcvf_cost_batch,
        SE2Pose,
        body_frame_error,
        wrap_angle,
        # Phase 1.5
        TraceResult,
        generate_trace,
        analyze_trace,
        run_all_traces,
        parameter_sensitivity_report,
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
from symbolu_robotics.bcvf_autonomous.traces import (
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    TRACE_FAMILIES,
    TraceResult,
    analyze_trace,
    generate_trace,
    parameter_sensitivity_report,
    run_all_traces,
)

__version__ = "0.1.5"

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
    # traces (Phase 1.5)
    "TraceResult",
    "TRACE_FAMILIES",
    "NOMINAL_FAMILIES",
    "FAILURE_FAMILIES",
    "generate_trace",
    "analyze_trace",
    "run_all_traces",
    "parameter_sensitivity_report",
]
