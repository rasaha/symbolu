"""Tests for bcvf_autonomous.run_experiments — DESIGN.md §4C.10."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_autonomous.mppi_planner import MPPIConfig, PerfCostConfig
from symbolu_robotics.bcvf_autonomous.predictors.base import BicycleConfig
from symbolu_robotics.bcvf_autonomous.run_experiments import (
    ExperimentConfig,
    ExperimentRunner,
    VARIANT_DIRNAMES,
    _variant_to_configs,
    main,
)


def _fast_tuning():
    bcvf = BCVFConfig(
        lambda_c=1.0,
        gate_threshold=0.2,
        gate_beta=100.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )
    mppi = MPPIConfig(
        num_rollouts=16,
        horizon=10,
        noise_std=np.array([1.5, 0.2]),
        velocity_bounds=(0.5, 8.0),
        bcvf_config=bcvf,
    )
    return bcvf, mppi, PerfCostConfig(), BicycleConfig()


def _fast_config(output_dir: Path, **overrides) -> ExperimentConfig:
    bcvf, mppi, perf, bicycle = _fast_tuning()
    cfg = ExperimentConfig(
        scenarios=["S1_normal_driving"],
        ablation_variants=["A0", "A3"],
        lambda_c_sweep_values=[],
        runs_per_config=2,
        base_seed=42,
        output_dir=str(output_dir),
        base_bcvf=bcvf,
        base_mppi=mppi,
        base_perf=perf,
        base_bicycle=bicycle,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    # Shrink scenarios' max_steps indirectly by a tiny horizon+rollouts.
    return cfg


# --- variant translation ---


def test_ablation_variant_configs() -> None:
    bcvf, mppi, _, _ = _fast_tuning()
    a0_b, a0_m = _variant_to_configs("A0", bcvf, mppi)
    a1_b, _ = _variant_to_configs("A1", bcvf, mppi)
    a2_b, _ = _variant_to_configs("A2", bcvf, mppi)
    a3_b, _ = _variant_to_configs("A3", bcvf, mppi)
    assert a0_m.lambda_c == 0.0
    assert a1_b.cost_order == CostOrder.ZEROTH
    assert a2_b.cost_order == CostOrder.FIRST
    assert a3_b.cost_order == CostOrder.SECOND
    assert a3_b.lambda_c == 1.0
    # Lambda override for sweep.
    _, swept = _variant_to_configs("A3", bcvf, mppi, lambda_c_override=5.0)
    assert swept.lambda_c == 5.0


def test_invalid_variant_raises() -> None:
    bcvf, mppi, _, _ = _fast_tuning()
    with pytest.raises(ValueError):
        _variant_to_configs("XYZ", bcvf, mppi)


# --- orchestrator integration ---


def test_scenario_subset(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path, scenarios=["S1_normal_driving"])
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS

    # Use smaller max_steps by monkey-patching the scenario (kept minimal here).
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        result = ExperimentRunner(cfg).run_all()
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200
    assert set(k[0] for k in result.ablation_results.keys()) == {"S1_normal_driving"}


def test_variant_subset(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path, ablation_variants=["A0", "A3"])
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        result = ExperimentRunner(cfg).run_all()
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200
    variants = {VARIANT_DIRNAMES[v] for v in cfg.ablation_variants}
    assert set(k[1] for k in result.ablation_results.keys()) == variants


def test_result_persistence(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path)
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        ExperimentRunner(cfg).run_all()
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200

    run_file = tmp_path / "ablation" / "S1_normal_driving" / "A0_baseline" / "run_000.json"
    assert run_file.exists()
    with open(run_file) as f:
        payload = json.load(f)
    assert "ground_truth_trajectory" in payload
    assert (tmp_path / "summary_table.json").exists()
    assert (tmp_path / "comparisons.json").exists()
    assert (tmp_path / "experiment_config.json").exists()


def test_resumption(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path, runs_per_config=3)
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        # First pass: run all 3.
        ExperimentRunner(cfg).run_all()
        run_dir = tmp_path / "ablation" / "S1_normal_driving" / "A0_baseline"
        assert (run_dir / "run_000.json").exists()

        # Modify run_000 payload so we can detect it was skipped.
        with open(run_dir / "run_000.json") as f:
            payload = json.load(f)
        payload["marker"] = "from_first_pass"
        with open(run_dir / "run_000.json", "w") as f:
            json.dump(payload, f)

        # Second pass: should skip run_000 (already on disk).
        ExperimentRunner(cfg).run_all()
        with open(run_dir / "run_000.json") as f:
            payload2 = json.load(f)
        assert payload2.get("marker") == "from_first_pass"
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200


def test_seed_produces_different_runs(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path, runs_per_config=2)
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        ExperimentRunner(cfg).run_all()
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200
    r0 = tmp_path / "ablation" / "S1_normal_driving" / "A0_baseline" / "run_000.json"
    r1 = tmp_path / "ablation" / "S1_normal_driving" / "A0_baseline" / "run_001.json"
    with open(r0) as f:
        p0 = json.load(f)
    with open(r1) as f:
        p1 = json.load(f)
    assert p0["ground_truth_trajectory"] != p1["ground_truth_trajectory"]


def test_experiment_config_saved(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path)
    cfg.base_mppi.horizon = 5
    cfg.base_mppi.num_rollouts = 8
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    SCENARIOS["S1_normal_driving"].max_steps = 5
    try:
        ExperimentRunner(cfg).run_all()
    finally:
        SCENARIOS["S1_normal_driving"].max_steps = 200
    with open(tmp_path / "experiment_config.json") as f:
        saved = json.load(f)
    assert saved["scenarios"] == cfg.scenarios
    assert saved["runs_per_config"] == cfg.runs_per_config


# --- CLI ---


def test_cli_quick_mode(tmp_path: Path, monkeypatch) -> None:
    # Reduce per-run cost via monkey-patching scenario max_steps.
    from symbolu_robotics.bcvf_autonomous.scenarios import SCENARIOS
    original = {}
    for name in ("S1_normal_driving", "S6_glass_corridor"):
        original[name] = SCENARIOS[name].max_steps
        SCENARIOS[name].max_steps = 5
    try:
        argv = [
            "--quick", "--output", str(tmp_path),
            "--scenarios", "S1_normal_driving",  # single scenario for speed
            "--variants", "A0",
            "--runs", "2",
        ]
        rc = main(argv)
        assert rc == 0
        assert (tmp_path / "summary_table.json").exists()
    finally:
        for name, ms in original.items():
            SCENARIOS[name].max_steps = ms
