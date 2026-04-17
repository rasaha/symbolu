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
