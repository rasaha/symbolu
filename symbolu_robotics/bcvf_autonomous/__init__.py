"""BCVF for Autonomous Systems.

Second-order cross-model coherence regularizer for multi-model predictive
control. See ``DESIGN.md`` for the full specification.

Public API through Phase 3 (math kernel + trace characterization +
4-predictor framework + simulator + MPPI planner + runner):

    from symbolu_robotics.bcvf_autonomous import (
        # Phase 1 — math kernel
        BCVFConfig, BCVFResult, CostOrder,
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
        # Phase 3A — simulator
        Road, Obstacle, SimConfig, SimState, Simulator,
        make_straight_road, make_curved_road, make_urban_road,
        # Phase 3B — MPPI planner
        MPPIConfig, MPPIResult, MPPIPlanner,
        PerfCostConfig, compute_perf_cost,
        # Phase 3C — runner
        RunConfig, RunResult, EpisodeDiagnostics,
        Runner, load_config, benchmark_planner,
    )
"""

from symbolu_robotics.bcvf_autonomous.core import (
    BCVFConfig,
    BCVFResult,
    CostOrder,
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
from symbolu_robotics.bcvf_autonomous.simulator import (
    Obstacle,
    Road,
    SimConfig,
    SimState,
    Simulator,
    make_curved_road,
    make_straight_road,
    make_urban_road,
)
from symbolu_robotics.bcvf_autonomous.mppi_planner import (
    MPPIConfig,
    MPPIPlanner,
    MPPIResult,
    PerfCostConfig,
    compute_perf_cost,
)
from symbolu_robotics.bcvf_autonomous.runner import (
    EpisodeDiagnostics,
    RunConfig,
    RunResult,
    Runner,
    benchmark_planner,
    load_config,
)
from symbolu_robotics.bcvf_autonomous.scenarios import (
    SCENARIOS,
    ScenarioConfig,
    get_scenario,
    list_scenarios,
    scenario_to_run_config,
)
from symbolu_robotics.bcvf_autonomous.metrics import (
    AggregateMetrics,
    ComparisonResult,
    EpisodeMetrics,
    build_summary_table,
    compare_collision_rates,
    compare_continuous_metric,
    compare_recovery_rates,
    compute_aggregate_metrics,
    compute_alignment_diagnostic,
    compute_early_warning_time,
    compute_episode_metrics,
    fisher_exact_2x2,
    mcnemar_exact,
    welch_t_test,
    wilson_ci,
)
from symbolu_robotics.bcvf_autonomous.run_experiments import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRunner,
    VARIANT_IDS,
)
from symbolu_robotics.bcvf_autonomous.observables import (
    BCVFPerStepBreakdown,
    BCVFPerStepMaxObservable,
    BCVFPredictorPerStepMaxObservable,
    CoherenceAnchoredBCVFObservable,
    EnsembleHeadingEntropyObservable,
    EnsembleSpreadObservable,
    Observable,
    ObservableValue,
    PredictorAgreementObservable,
    ProbeDatapoint,
    ProbeReport,
    UncertaintyGatedBCVFPerStepMaxObservable,
    classify_observable,
    compute_bcvf_per_step,
    probe_observable,
    probe_observables,
    recommendation_for,
)
from symbolu_robotics.bcvf_autonomous.trust import (
    ConsumerState,
    ConsumerV2Config,
    TrustWeightComputer,
    TrustWeightResult,
)
from symbolu_robotics.bcvf_autonomous.trust_diagnostics import (
    RolloutAggregation,
    TrustDiagnosticsRecorder,
    TrustShapedEpisodeRecord,
    TrustStepRecord,
)
from symbolu_robotics.bcvf_autonomous.characterization import (
    AlignmentAggregate,
    AlignmentMetrics,
    CellResult,
    TraceBundle,
    aggregate_alignment,
    compute_alignment_metrics,
    family_pass_rate,
    pick_winner_tuple,
    run_ablation_grid,
    run_primary_grid,
    run_sensitivity_grid,
    summarize_grid,
)
from symbolu_robotics.bcvf_autonomous.characterization import (
    generate_trace as generate_trace_bundle,
)

__version__ = "0.4.0"

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
    # simulator (Phase 3A)
    "Road",
    "Obstacle",
    "SimConfig",
    "SimState",
    "Simulator",
    "make_straight_road",
    "make_curved_road",
    "make_urban_road",
    # planner (Phase 3B)
    "MPPIConfig",
    "MPPIResult",
    "MPPIPlanner",
    "PerfCostConfig",
    "compute_perf_cost",
    "CostOrder",
    # runner (Phase 3C)
    "RunConfig",
    "RunResult",
    "EpisodeDiagnostics",
    "Runner",
    "load_config",
    "benchmark_planner",
    # scenarios (Phase 4A)
    "ScenarioConfig",
    "SCENARIOS",
    "get_scenario",
    "list_scenarios",
    "scenario_to_run_config",
    # metrics (Phase 4B)
    "EpisodeMetrics",
    "AggregateMetrics",
    "ComparisonResult",
    "compute_episode_metrics",
    "compute_aggregate_metrics",
    "compute_alignment_diagnostic",
    "compute_early_warning_time",
    "compare_collision_rates",
    "compare_continuous_metric",
    "compare_recovery_rates",
    "build_summary_table",
    "wilson_ci",
    "welch_t_test",
    "fisher_exact_2x2",
    "mcnemar_exact",
    # experiments (Phase 4C)
    "ExperimentConfig",
    "ExperimentResult",
    "ExperimentRunner",
    "VARIANT_IDS",
    # observables
    "BCVFPerStepBreakdown",
    "BCVFPerStepMaxObservable",
    "BCVFPredictorPerStepMaxObservable",
    "CoherenceAnchoredBCVFObservable",
    "EnsembleHeadingEntropyObservable",
    "EnsembleSpreadObservable",
    "Observable",
    "ObservableValue",
    "PredictorAgreementObservable",
    "ProbeDatapoint",
    "ProbeReport",
    "UncertaintyGatedBCVFPerStepMaxObservable",
    "classify_observable",
    "compute_bcvf_per_step",
    "probe_observable",
    "probe_observables",
    "recommendation_for",
    # trust + V2 consumer
    "ConsumerState",
    "ConsumerV2Config",
    "TrustWeightComputer",
    "TrustWeightResult",
    # trust diagnostics
    "RolloutAggregation",
    "TrustDiagnosticsRecorder",
    "TrustShapedEpisodeRecord",
    "TrustStepRecord",
    # characterization sweep
    "AlignmentAggregate",
    "AlignmentMetrics",
    "CellResult",
    "TraceBundle",
    "aggregate_alignment",
    "compute_alignment_metrics",
    "family_pass_rate",
    "generate_trace_bundle",
    "pick_winner_tuple",
    "run_ablation_grid",
    "run_primary_grid",
    "run_sensitivity_grid",
    "summarize_grid",
]
