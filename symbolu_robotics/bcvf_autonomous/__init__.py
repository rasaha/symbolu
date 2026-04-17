"""BCVF for Autonomous Systems.

Second-order cross-model coherence regularizer for multi-model predictive
control. See ``DESIGN.md`` for the full specification.

Public API through Phase 2 (math kernel + disagreement characterization
+ 4-predictor framework — MPPI planner lands in Phase 3):

    from symbolu_robotics.bcvf_autonomous import (
        # Phase 1 — math kernel
        BCVFConfig, BCVFResult,
        compute_bcvf_cost, compute_bcvf_cost_batch,
        SE2Pose, body_frame_error, wrap_angle,
        # Phase 1.5 — trace families and sensitivity sweep
        TraceResult, generate_trace, analyze_trace,
        run_all_traces, parameter_sensitivity_report,
        # Phase 2 — predictor framework
        BasePredictor, BicycleConfig, PredictorState,
        FailureConfig, ControlInput,
        IMUOdometry, LidarSLAM, VisualOdometry, GNSSMap,
        create_predictor_set,
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
from symbolu_robotics.bcvf_autonomous.predictors import (
    BasePredictor,
    BicycleConfig,
    ControlInput,
    FailureConfig,
    GNSSMap,
    IMUOdometry,
    LidarSLAM,
    PredictorState,
    VisualOdometry,
    create_predictor_set,
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

__version__ = "0.2.0"

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
    # predictors (Phase 2)
    "BasePredictor",
    "BicycleConfig",
    "PredictorState",
    "FailureConfig",
    "ControlInput",
    "IMUOdometry",
    "LidarSLAM",
    "VisualOdometry",
    "GNSSMap",
    "create_predictor_set",
]
