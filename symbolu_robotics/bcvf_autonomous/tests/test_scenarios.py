"""Tests for bcvf_autonomous.scenarios — DESIGN.md §4A.8."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig
from symbolu_robotics.bcvf_autonomous.mppi_planner import MPPIConfig, PerfCostConfig
from symbolu_robotics.bcvf_autonomous.predictors.base import BicycleConfig
from symbolu_robotics.bcvf_autonomous.scenarios import (
    SCENARIOS,
    ScenarioConfig,
    get_scenario,
    list_scenarios,
    scenario_to_run_config,
)


def _tuning():
    return (
        BCVFConfig(weight_matrix=np.ones(3)),
        MPPIConfig(num_rollouts=8, horizon=5),
        PerfCostConfig(),
        BicycleConfig(),
    )


def test_all_scenarios_loadable() -> None:
    for name in list_scenarios():
        s = get_scenario(name)
        assert isinstance(s, ScenarioConfig)
        assert s.name == name


def test_scenario_to_run_config() -> None:
    bcvf, mppi, perf, bicycle = _tuning()
    cfg = scenario_to_run_config(SCENARIOS["S6_glass_corridor"], bcvf, mppi, perf, bicycle)
    assert cfg.sim.max_steps == SCENARIOS["S6_glass_corridor"].max_steps
    assert len(cfg.sim.obstacles) == 1
    assert "M2" in cfg.failures
    assert cfg.failures["M2"].active


def test_s1_no_failures() -> None:
    assert SCENARIOS["S1_normal_driving"].failures == {}


def test_s2_m4_failure() -> None:
    s = SCENARIOS["S2_gps_multipath"]
    assert "M4" in s.failures
    assert s.failures["M4"].onset_time == 3.0


def test_s5_constant_bias_flag() -> None:
    s = SCENARIOS["S5_constant_bias"]
    assert s.gnss_failure_type == "constant_bias"


def test_scenario_registry_complete() -> None:
    names = list_scenarios()
    assert len(names) == 6
    assert len(set(names)) == 6


def test_scenario_separation_by_tuning() -> None:
    """Same scenario + two lambda_c values -> two distinct RunConfigs."""
    bcvf_a = BCVFConfig(lambda_c=0.0, weight_matrix=np.ones(3))
    bcvf_b = BCVFConfig(lambda_c=5.0, weight_matrix=np.ones(3))
    _, mppi, perf, bicycle = _tuning()
    cfg_a = scenario_to_run_config(SCENARIOS["S6_glass_corridor"], bcvf_a, mppi, perf, bicycle)
    cfg_b = scenario_to_run_config(SCENARIOS["S6_glass_corridor"], bcvf_b, mppi, perf, bicycle)
    assert cfg_a.bcvf.lambda_c == 0.0
    assert cfg_b.bcvf.lambda_c == 5.0


def test_gnss_failure_type_routed_to_runner() -> None:
    from symbolu_robotics.bcvf_autonomous.runner import Runner

    # S5 uses constant_bias; verify the predictor receives it.
    bcvf, mppi, perf, bicycle = _tuning()
    cfg = scenario_to_run_config(SCENARIOS["S5_constant_bias"], bcvf, mppi, perf, bicycle)
    cfg.sim.max_steps = 5  # shortcut for fast test
    cfg.mppi.num_rollouts = 8
    cfg.mppi.horizon = 5
    cfg.mppi.velocity_bounds = (0.5, 8.0)
    assert cfg.gnss_failure_type == "constant_bias"
    # Running it must not raise despite the non-default failure type.
    _ = Runner(cfg).run()


# --- V2 Option B1: scenario-specific anchor plumbing ---


def test_scenario_anchor_default_is_none() -> None:
    """A scenario without an explicit anchor leaves the field None so the
    caller's MPPIConfig.anchor passes through unchanged (regression)."""
    assert SCENARIOS["S1_normal_driving"].anchor is None
    assert SCENARIOS["S5_constant_bias"].anchor is None


def test_failure_scenarios_pin_anchor_to_failing_predictor() -> None:
    """Fault-injection scenarios pin anchor = failing predictor so the
    baseline planner is actually driven by the model whose failure is
    being injected (the V2 B1 unblock)."""
    assert SCENARIOS["S2_gps_multipath"].anchor == "M4"
    assert SCENARIOS["S3_map_error"].anchor == "M4"
    assert SCENARIOS["S4_camera_degradation"].anchor == "M3"
    assert SCENARIOS["S6_glass_corridor"].anchor == "M2"


def test_scenario_anchor_reaches_mppi_config() -> None:
    """The scenario anchor must appear in the final RunConfig.mppi.anchor —
    this is the one plumbing path that matters for gate-2 validation."""
    bcvf, mppi, perf, bicycle = _tuning()
    # Caller config defaults to "M1"; scenario override must win.
    assert mppi.anchor == "M1"

    cfg_s6 = scenario_to_run_config(SCENARIOS["S6_glass_corridor"], bcvf, mppi, perf, bicycle)
    assert cfg_s6.mppi.anchor == "M2"

    cfg_s3 = scenario_to_run_config(SCENARIOS["S3_map_error"], bcvf, mppi, perf, bicycle)
    assert cfg_s3.mppi.anchor == "M4"


def test_no_anchor_preserves_caller_default() -> None:
    """When the scenario does not specify an anchor, the caller's
    MPPIConfig.anchor is preserved (regression guard)."""
    bcvf, mppi, perf, bicycle = _tuning()
    mppi_custom = replace_mppi_anchor(mppi, "M3")
    cfg_s1 = scenario_to_run_config(
        SCENARIOS["S1_normal_driving"], bcvf, mppi_custom, perf, bicycle
    )
    assert cfg_s1.mppi.anchor == "M3"  # caller default flows through


def replace_mppi_anchor(mppi, anchor):
    from dataclasses import replace
    return replace(mppi, anchor=anchor)


# --- V2 follow-up: per-scenario MPPI horizon ---


def test_scenario_mppi_horizon_default_is_none_for_other_scenarios() -> None:
    """All non-S3 scenarios leave mppi_horizon as None (caller default
    flows through). Regression guard against accidental scope creep."""
    for name in (
        "S1_normal_driving",
        "S2_gps_multipath",
        "S4_camera_degradation",
        "S5_constant_bias",
        "S6_glass_corridor",
    ):
        assert SCENARIOS[name].mppi_horizon is None, name


def test_s3_has_extended_horizon() -> None:
    assert SCENARIOS["S3_map_error"].mppi_horizon == 50


def test_s3_obstacles_in_reach_band() -> None:
    """S3 obstacles relocated to the 60-80 m band so the 20s episode at
    current pacing actually reaches them."""
    xs = sorted(o["x"] for o in SCENARIOS["S3_map_error"].obstacles)
    assert xs == [60.0, 70.0, 80.0]


def test_scenario_horizon_reaches_mppi_config() -> None:
    bcvf, mppi, perf, bicycle = _tuning()
    assert mppi.horizon == 5  # caller default from _tuning()
    cfg_s3 = scenario_to_run_config(SCENARIOS["S3_map_error"], bcvf, mppi, perf, bicycle)
    assert cfg_s3.mppi.horizon == 50  # scenario override wins
    cfg_s1 = scenario_to_run_config(SCENARIOS["S1_normal_driving"], bcvf, mppi, perf, bicycle)
    assert cfg_s1.mppi.horizon == 5  # no override -> caller default preserved


def test_scenario_anchor_used_by_planner_at_runtime() -> None:
    """End-to-end behavioral: build a Runner from a scenario with a
    non-default anchor and verify the instantiated MPPIPlanner uses that
    predictor for its anchor-mode rollouts. We reach into the planner's
    config because there is no public introspection hook; if that ever
    breaks, the test signals the observable surface has shifted."""
    from symbolu_robotics.bcvf_autonomous.predictors import create_predictor_set
    from symbolu_robotics.bcvf_autonomous.mppi_planner import MPPIPlanner
    from symbolu_robotics.bcvf_autonomous.simulator import make_straight_road

    bcvf, mppi, perf, bicycle = _tuning()
    cfg = scenario_to_run_config(
        SCENARIOS["S6_glass_corridor"], bcvf, mppi, perf, bicycle
    )
    predictors = create_predictor_set(bicycle_config=cfg.bicycle, seed=cfg.seed)
    road = make_straight_road(length=100.0)
    planner = MPPIPlanner(cfg.mppi, cfg.perf, predictors, road, cfg.sim.obstacles)
    assert planner.config.anchor == "M2"
    assert planner.predictors[planner.config.anchor].model_id == "M2"
