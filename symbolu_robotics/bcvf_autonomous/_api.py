"""Public-API stability registry.

Three tiers a downstream integrator can rely on:

* :data:`STABLE_API` — the long-term commitment. Removal requires a
  deprecation cycle (one minor version of advance notice + a
  ``DeprecationWarning`` emitted from the deprecated surface).
  Members are accessed via their canonical submodule path
  (``characterization.run_primary_grid``,
  ``analysis.StreamingFleetMonitor``, ...) and via the top-level
  :mod:`symbolu_robotics.bcvf_autonomous` re-export. Both paths are
  in scope for the commitment.

* :data:`PROVISIONAL_API` — supported, but the signature may change
  in a minor version with a release-note line (no advance notice
  required). Newer surfaces typically start here. The size of this
  set is locked by ``test_api_stability`` so a contributor can't
  accidentally promote / remove a provisional symbol without the
  PR review noticing.

* **Internal** — leading underscore (``_evaluate_thresholds``,
  ``_resolve_metric_path``) or unlisted. No commitment; treat as a
  free-form refactor target.

The registry is a flat tuple of ``"submodule.Symbol"`` strings to
keep the contract human-auditable. The
:func:`resolve_qualified` helper imports the submodule + looks up
the symbol so a renamed module / removed surface fails the test
suite at import time rather than as a silent hole in the
commitment.

The policy in long-form lives in ``API_STABILITY.md`` at the
package root.
"""

from __future__ import annotations

import importlib
from typing import Any, Tuple


# --------------------------------------------------------------------------- #
# Stable surface — long-term commitment
# --------------------------------------------------------------------------- #
# Order: by submodule, then alphabetical within each block. Pinned so
# diffs are diff-readable in PR review.

STABLE_API: Tuple[str, ...] = (
    # Kernel + math primitives
    "core.BCVFConfig",
    "core.BCVFResult",
    "core.CostOrder",
    "core.compute_bcvf_cost",
    "core.compute_bcvf_cost_batch",
    "manifold.SE2Pose",
    "manifold.body_frame_error",
    "manifold.wrap_angle",
    # Predictor framework
    "predictors.base.BasePredictor",
    "predictors.base.BicycleConfig",
    "predictors.base.ControlInput",
    "predictors.base.FailureConfig",
    "predictors.base.PredictorState",
    # MPPI planner
    "mppi_planner.MPPIConfig",
    "mppi_planner.MPPIPlanner",
    "mppi_planner.MPPIResult",
    "mppi_planner.PerfCostConfig",
    # Runner + run config
    "runner.RunConfig",
    "runner.RunResult",
    "runner.Runner",
    # Trust shaping + V2
    "trust.ConsumerV2Config",
    "trust.TrustWeightComputer",
    # Per-tick diagnostic record
    "trust_diagnostics.TrustShapedEpisodeRecord",
    # Fleet analysis — batch + streaming
    "analysis.Alert",
    "analysis.AlertRule",
    "analysis.EpisodeSummary",
    "analysis.FleetSummary",
    "analysis.StreamingFleetMonitor",
    "analysis.WindowedFleetSummary",
    "analysis.aggregate_fleet",
    "analysis.summarize_episode",
    # Characterization — certification grid + stats primitives
    "characterization.CERTIFICATION_FLOOR",
    "characterization.GridSummary",
    "characterization.PerConfigPassStat",
    "characterization.WILSON_Z_95",
    "characterization.run_primary_grid",
    "characterization.summarize_grid",
    "characterization.wilson_ci",
)

# --------------------------------------------------------------------------- #
# Provisional surface — supported, may evolve
# --------------------------------------------------------------------------- #

PROVISIONAL_API: Tuple[str, ...] = (
    # Pilot runner — paired A0 / A3 evaluation
    "pilot.PilotResult",
    "pilot.run_pilot",
    "pilot.one_sided_sign_test",
    # Apples-to-apples baseline shootout
    "baselines.ShootoutResult",
    "baselines.run_shootout",
    # SOTIF / ISO 26262 traceability template
    "safety_case.TraceabilityMatrix",
    "safety_case.build_traceability_matrix",
    "safety_case.render_markdown",
    # Auditor-facing report writers (post-v0.7; layout may evolve as
    # buyers' regulator-pack templates differ)
    "analysis.write_fleet_csv",
    "analysis.write_fleet_markdown",
    "characterization.write_grid_csv",
    "characterization.write_grid_markdown",
    # V2 promotion-decision sweep
    "v2_chatter_sweep.V2PromotionDecisionResult",
    "v2_chatter_sweep.run_v2_promotion_decision",
    # Multi-modal predictor inputs (post-v0.7 — the lift adapter that
    # carries the kernel's Lemma 1 invariance through to lane-frame
    # predictors; see MULTI_MODAL_PREDICTORS_DESIGN.md). Provisional
    # because the geometry-input shape (LaneAnchor) may evolve once
    # an integrator wires their HD-map provider against it.
    "predictors.LaneAnchor",
    "predictors.MultiModalPredictor",
    "predictors.PredictorStateSpace",
    "predictors.lane_frame_to_se2",
    "predictors.se2_to_lane_frame",
    "predictors.unify_to_se2_bundle",
    # Functional-safety state machine (post-v0.7 — the four-state
    # behavioural-contract layer the runtime composes into; see
    # SAFETY_STATE_MACHINE_DESIGN.md). Provisional because the
    # state-graph + ASIL decomposition stay in PROVISIONAL_API
    # until the three §9 ship-when-ready criteria land (three
    # deployment partners exercising in production for one
    # quarter, the characterization grid's state_transition_
    # consistency cell family, and an external auditor review of
    # the §5 ASIL table).
    "safety_state.LEGAL_TRANSITIONS",
    "safety_state.SafetyState",
    "safety_state.SafetyStateMachine",
    "safety_state.SafetyStateMachineConfig",
    "safety_state.StateTransition",
    "safety_state.StateTransitionLog",
    "safety_state.StateTransitionLogEntry",
    "safety_state.IllegalTransitionError",
    "safety_state.SafetyStateMachineError",
    # ROS 2 / DDS integration contract (post-v0.7.x — the §9
    # row-#2 industry-features-roadmap pick; see
    # ROS2_DDS_SBOM_DESIGN.md). Symbols are re-exported via the
    # bcvf_autonomous.ros2 shim because the canonical package
    # (``symbolu_robotics.bcvf_ros2``) is a sibling, not a
    # submodule. Provisional until the five §9 ship-when-ready
    # criteria land (three deployment partners, SBOM accepted
    # into procurement, DDS QoS exercised against RTI/FastDDS,
    # colcon-buildable, external-auditor SBOM validation).
    "ros2.BCVFNode",
    "ros2.BCVFNodeBehaviour",
    "ros2.BCVFNodeConfig",
    "ros2.ConsensusOutputMessage",
    "ros2.DDS_QOS_PROFILE",
    "ros2.DDSQoSProfile",
    "ros2.PredictorTrajectoryMessage",
    "ros2.build_rclpy_qos_profile",
    # CycloneDX SBOM generator (post-v0.7.x; lands paired with
    # the ROS 2 integration contract per ROS2_DDS_SBOM_DESIGN.md
    # §6 — the procurement-gate manifest enumerating runtime
    # dependencies with version + SPDX license).
    "safety_case.sbom.SBOMComponent",
    "safety_case.sbom.generate_cyclonedx_bom",
    "safety_case.sbom.runtime_components",
    "safety_case.sbom.write_cyclonedx_bom",
    # Replay / record-and-replay framework (post-v0.7.x — the §9
    # row-#3 industry-features-roadmap pick; see
    # REPLAY_FRAMEWORK_DESIGN.md). The recall-investigator's
    # bit-identity surface: ReplayBundle ties (RunConfig,
    # recorded TrustShapedEpisodeRecord, package version, episode
    # metadata) into a JSON artifact; replay_bundle runs the
    # bundle's config through the current code and surfaces any
    # divergence with field-level + tick-level localisation.
    # Provisional until the five §9 ship-when-ready criteria
    # land (deployment-partner usage for one quarter, bit-
    # identity replay across a real recall case, Class-A
    # divergence detection across a kernel change, signed bundle
    # integrity field, external auditor sign-off on the bundle
    # JSON shape).
    "replay.BUNDLE_VERSION",
    "replay.ReplayBundle",
    "replay.ReplayBundleError",
    "replay.ReplayBundleVersionError",
    "replay.ReplayResult",
    "replay.build_replay_bundle",
    "replay.compare_replay",
    "replay.load_replay_bundle",
    "replay.replay_bundle",
    "replay.save_replay_bundle",
    # Real-time / no-allocation hot path + p999 budget
    # (post-v0.7.x — the §9 row-#4 industry-features-roadmap
    # pick; see REAL_TIME_BUDGET_DESIGN.md). Typed budget
    # contract (RealTimeBudget) + per-tick observer
    # (LatencyMonitor) with mutually-exclusive tier counters,
    # bounded over-budget audit trail, and percentile-
    # availability discipline (p999/p9999 None below sample-
    # count thresholds). Provisional until the five §9 ship-
    # when-ready criteria land (AUTOSAR-class deployment
    # partner one quarter, real 10⁶-tick load test, C++-port
    # equivalence within 2×, external auditor sign-off,
    # configurable persistence layer).
    "realtime.AllocationTrace",
    "realtime.BudgetSummary",
    "realtime.BudgetViolationError",
    "realtime.LatencyMonitor",
    "realtime.OverBudgetTick",
    "realtime.RealTimeBudget",
    "realtime.RealTimeBudgetError",
    # Calibration parameter management + drift detection
    # (post-v0.7.x — the §9 row-#6 industry-features-roadmap
    # pick; see CALIBRATION_DESIGN.md). Versioned, hash-
    # identified, kernel-version-validated bundle of per-
    # deployment tuning knobs (CalibrationSet) + drift detector
    # (CalibrationDriftDetector) that composes with
    # StreamingFleetMonitor via the same dotted-path metric
    # resolver. Provisional until the five §9 ship-when-ready
    # criteria of CALIBRATION_DESIGN.md land (deployment partner
    # one quarter on a fleet ≥ 10 vehicles, real fleet drift
    # detection across a known mismatch, signed bundle field,
    # external auditor sign-off, expected_metrics schema
    # stabilised across ≥ 3 deployment partners).
    "calibration.CalibrationDigestError",
    "calibration.CalibrationDriftAlert",
    "calibration.CalibrationDriftDetector",
    "calibration.CalibrationSet",
    "calibration.CalibrationSetError",
    "calibration.CalibrationVersionError",
    "calibration.build_calibration_set",
    "calibration.load_calibration_set",
    "calibration.save_calibration_set",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def resolve_qualified(qualified: str) -> Any:
    """Resolve a ``"submodule.Symbol"`` path to the actual object.

    Raises ``ImportError`` if the submodule isn't importable, or
    ``AttributeError`` if the symbol isn't defined on the submodule
    — either failure mode is the signal that the registry has
    drifted from the codebase.
    """
    parts = qualified.split(".")
    if len(parts) < 2:
        raise ValueError(
            f"qualified name must be 'submodule.Symbol'; got {qualified!r}"
        )
    submodule_path = "symbolu_robotics.bcvf_autonomous." + ".".join(parts[:-1])
    symbol = parts[-1]
    module = importlib.import_module(submodule_path)
    if not hasattr(module, symbol):
        raise AttributeError(
            f"{submodule_path}.{symbol} does not resolve — STABLE_API "
            "or PROVISIONAL_API is stale"
        )
    return getattr(module, symbol)


def is_stable(qualified: str) -> bool:
    """``True`` if the qualified path is in :data:`STABLE_API`."""
    return qualified in STABLE_API


def is_provisional(qualified: str) -> bool:
    """``True`` if the qualified path is in :data:`PROVISIONAL_API`."""
    return qualified in PROVISIONAL_API


def stable_top_level_names() -> Tuple[str, ...]:
    """Symbol names (without submodule prefix) that the top-level
    ``bcvf_autonomous`` package must re-export for the stable
    commitment to hold via ``from bcvf_autonomous import X``."""
    return tuple(q.rsplit(".", 1)[1] for q in STABLE_API)
