"""Phase 4A — failure scenarios (DESIGN.md §4A).

Scenarios are data only — they combine a road geometry, obstacle layout,
failure injection, and expected behavior into a :class:`ScenarioConfig`
dataclass that ``scenario_to_run_config`` translates into a ``RunConfig``
consumable by :class:`~symbolu_robotics.bcvf_autonomous.runner.Runner`.

Per DESIGN §4A.6 the scenario does **not** carry BCVF / MPPI / perf
tuning parameters — the caller supplies those so the same scenario can
run under every ablation variant and every ``lambda_c`` value.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

from .core import BCVFConfig
from .mppi_planner import MPPIConfig, PerfCostConfig
from .predictors.base import BicycleConfig, FailureConfig
from .runner import RunConfig
from .simulator import (
    Obstacle,
    Road,
    SimConfig,
    make_curved_road,
    make_straight_road,
    make_urban_road,
)


@dataclass
class ScenarioConfig:
    """Complete definition of one test scenario (DESIGN.md §4A.3)."""

    name: str
    description: str
    road_type: str = "straight"
    road_length: float = 200.0
    road_radius: float = 100.0
    road_arc_degrees: float = 90.0
    obstacles: List[Dict[str, float]] = field(default_factory=list)
    failures: Dict[str, FailureConfig] = field(default_factory=dict)
    max_steps: int = 200
    initial_velocity: float = 8.0
    gnss_failure_type: Optional[str] = None  # override M4 failure_type if set
    # V2 Option B1 (scenario-specific anchor): when set, overrides the
    # default MPPIConfig.anchor at scenario_to_run_config time. Use the
    # failing predictor as the anchor so the baseline planner is driven
    # by the model whose failure is being injected — this is what makes
    # the §4C.13 gate-2 A0-vs-A3 contrast producible. Leave as ``None``
    # to preserve the default anchor from the caller's MPPIConfig.
    anchor: Optional[str] = None
    # V2 follow-up (gate-2 enablement): per-scenario MPPI rollout horizon.
    # Default ``base_mppi.horizon`` is too short for the in-rollout failure
    # bias to integrate enough 2nd-order signal at the gate threshold. A
    # scenario can opt into a longer horizon when its failure dynamics
    # need more integration time. ``None`` preserves the caller's default.
    mppi_horizon: Optional[int] = None

    # Directional expectations (not hard assertions).
    expect_bcvf_activation: bool = False
    expect_collision_baseline: bool = False
    expect_collision_bcvf: bool = False


# --- Scenario catalog (§4A.4) ---


S1_NORMAL = ScenarioConfig(
    name="S1_normal_driving",
    description=(
        "Highway driving at 8 m/s, all sensors nominal. No failures, "
        "no obstacles. Measures false positive rate and baseline path "
        "efficiency."
    ),
    road_type="straight",
    road_length=200.0,
    obstacles=[],
    failures={},
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=False,
    expect_collision_baseline=False,
    expect_collision_bcvf=False,
)


S2_GPS_MULTIPATH = ScenarioConfig(
    name="S2_gps_multipath",
    description=(
        "GPS multipath in urban canyon: M4 position jumps of 2-5m with "
        "increasing frequency. Other models unaffected."
    ),
    road_type="straight",
    road_length=200.0,
    obstacles=[{"x": 100.0, "y": 3.0, "radius": 0.5}],
    failures={
        "M4": FailureConfig(
            active=True, onset_time=3.0, severity=0.8, ramp_duration=2.0
        )
    },
    gnss_failure_type="multipath",
    anchor="M4",  # V2 B1: baseline uses failing predictor as J_perf reference
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,
    expect_collision_bcvf=False,
)


S3_MAP_ERROR = ScenarioConfig(
    name="S3_map_error",
    description=(
        "Construction zone: road layout differs from HD map. M4 diverges "
        "laterally with quadratically growing offset. Primary gate-2 "
        "scenario — failure injects in the lane-deviation-relevant axis "
        "(lateral), so anchor=M4 misroutes the baseline planner."
    ),
    road_type="straight",
    road_length=200.0,
    # V2 follow-up: barrier line moved from x=120-140 to x=60-80 so the
    # 20s episode at current MPPI tuning (~3.5 m/s) actually reaches it.
    # Same barrier shape (3 obstacles, 10 m apart, lateral offset growing).
    obstacles=[
        {"x": 60.0, "y": 0.0, "radius": 1.5},
        {"x": 70.0, "y": 0.5, "radius": 1.5},
        {"x": 80.0, "y": 1.0, "radius": 1.5},
    ],
    failures={
        "M4": FailureConfig(
            active=True, onset_time=5.0, severity=1.0, ramp_duration=5.0
        )
    },
    gnss_failure_type="map_error",
    anchor="M4",  # V2 B1
    # V2 follow-up: 2s rollout horizon (H=20) is too short for the
    # accelerating lateral bias to push BCVF above the gate threshold.
    # 5s horizon gives the failure 2.5x the integration time.
    mppi_horizon=50,
    max_steps=400,  # V2 follow-up: 40-s episode so vehicle reaches the 60-80m obstacle band
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,
    expect_collision_bcvf=False,
)


S4_CAMERA_DEGRADATION = ScenarioConfig(
    name="S4_camera_degradation",
    description=(
        "Weather degrades progressively: M3 (VO) noise inflates then "
        "tracking is lost. Other models unaffected. Tests graceful "
        "transition."
    ),
    road_type="curved",
    road_length=200.0,
    road_radius=80.0,
    obstacles=[],
    failures={
        "M3": FailureConfig(
            active=True, onset_time=2.0, severity=1.0, ramp_duration=10.0
        )
    },
    anchor="M3",  # V2 B1
    max_steps=200,
    initial_velocity=6.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=False,
    expect_collision_bcvf=False,
)


S5_CONSTANT_BIAS = ScenarioConfig(
    name="S5_constant_bias",
    description=(
        "Lemma 1 validation. M4 injected with a constant 0.5m x bias "
        "throughout; constant disagreement must produce zero J_BCVF "
        "(the invariance that differentiates 2nd-order from 0th-order)."
    ),
    road_type="straight",
    road_length=200.0,
    obstacles=[],
    failures={
        "M4": FailureConfig(
            active=True, onset_time=0.0, severity=1.0, ramp_duration=0.0
        )
    },
    gnss_failure_type="constant_bias",
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=False,
    expect_collision_baseline=False,
    expect_collision_bcvf=False,
)


S3_MAP_ERROR_ACCEL = ScenarioConfig(
    name="S3_map_error_accel",
    description=(
        "Accelerating-failure variant of S3. Same geometry/anchor/horizon "
        "as S3 but M4's lateral drift grows quadratically in absolute "
        "time (per-step increment ~elapsed^2). Keeps the 2nd-order BCVF "
        "signal alive throughout the misrouting phase, giving A3 a fair "
        "chance to separate from A0 on the closed-loop metrics."
    ),
    road_type="straight",
    road_length=200.0,
    obstacles=[
        {"x": 60.0, "y": 0.0, "radius": 1.5},
        {"x": 70.0, "y": 0.5, "radius": 1.5},
        {"x": 80.0, "y": 1.0, "radius": 1.5},
    ],
    failures={
        "M4": FailureConfig(
            active=True, onset_time=5.0, severity=1.0, ramp_duration=5.0
        )
    },
    gnss_failure_type="map_error_accel",
    anchor="M4",
    mppi_horizon=50,
    max_steps=400,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,
    expect_collision_bcvf=False,
)


S6_GLASS_CORRIDOR = ScenarioConfig(
    name="S6_glass_corridor",
    description=(
        "LiDAR glass corridor: M2 state estimate drifts quadratically as "
        "scans pass through glass. The canonical BCVF activation case."
    ),
    road_type="straight",
    road_length=200.0,
    obstacles=[{"x": 130.0, "y": 2.5, "radius": 0.5}],
    failures={
        "M2": FailureConfig(
            active=True, onset_time=5.0, severity=1.0, ramp_duration=3.0
        )
    },
    anchor="M2",  # V2 B1
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,
    expect_collision_bcvf=False,
)


SCENARIOS: Dict[str, ScenarioConfig] = {
    "S1_normal_driving": S1_NORMAL,
    "S2_gps_multipath": S2_GPS_MULTIPATH,
    "S3_map_error": S3_MAP_ERROR,
    "S3_map_error_accel": S3_MAP_ERROR_ACCEL,
    "S4_camera_degradation": S4_CAMERA_DEGRADATION,
    "S5_constant_bias": S5_CONSTANT_BIAS,
    "S6_glass_corridor": S6_GLASS_CORRIDOR,
}


def get_scenario(name: str) -> ScenarioConfig:
    """Look up a scenario by name. Raises ``KeyError`` if not found."""
    return SCENARIOS[name]


def list_scenarios() -> List[str]:
    """Return all scenario names in registration order."""
    return list(SCENARIOS.keys())


# --- Translation to RunConfig (§4A.6) ---


def _build_road(scenario: ScenarioConfig) -> Road:
    if scenario.road_type == "straight":
        return make_straight_road(length=scenario.road_length)
    if scenario.road_type == "curved":
        return make_curved_road(
            radius=scenario.road_radius, arc_degrees=scenario.road_arc_degrees
        )
    if scenario.road_type == "urban":
        return make_urban_road()
    raise ValueError(f"unknown road_type {scenario.road_type!r}")


def scenario_to_run_config(
    scenario: ScenarioConfig,
    bcvf_config: BCVFConfig,
    mppi_config: MPPIConfig,
    perf_config: PerfCostConfig,
    bicycle_config: BicycleConfig,
    seed: int = 42,
) -> RunConfig:
    """Translate ``scenario`` + tuning into a :class:`RunConfig`."""
    road = _build_road(scenario)
    obstacles = [Obstacle(**o) for o in scenario.obstacles]

    sim = SimConfig(
        dt=mppi_config.dt,
        max_steps=scenario.max_steps,
        bicycle=bicycle_config,
        road=road,
        obstacles=obstacles,
        seed=seed,
    )

    # Scenario anchor, if set, overrides the caller's MPPIConfig.anchor.
    # This is the V2 Option B1 entry point: a scenario selects which
    # predictor the planner trusts for J_perf, independent of which
    # variant (A0/A1/A2/A3) is being run.
    mppi_out = replace(mppi_config)
    if scenario.anchor is not None:
        mppi_out = replace(mppi_out, anchor=scenario.anchor)
    # Scenario MPPI horizon, if set, overrides the caller's default. Used
    # by gate-2 scenarios whose accelerating failure needs a longer
    # rollout to push BCVF cost above the gate threshold.
    if scenario.mppi_horizon is not None:
        mppi_out = replace(mppi_out, horizon=scenario.mppi_horizon)

    return RunConfig(
        sim=sim,
        mppi=mppi_out,
        perf=replace(perf_config),
        bcvf=replace(bcvf_config),
        bicycle=replace(bicycle_config),
        seed=seed,
        failures={k: replace(v) for k, v in scenario.failures.items()},
        gnss_failure_type=scenario.gnss_failure_type or "multipath",
    )
