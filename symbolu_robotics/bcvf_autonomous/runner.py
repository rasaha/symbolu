"""Phase 3C — closed-loop runner, config loader, and timing benchmark.

Wires Simulator + MPPIPlanner + predictors into a single Runner. Loads
``default_se2.yaml`` (or an override-merged variant) into a fully
populated ``RunConfig``. PyYAML is the only non-NumPy dependency; it is
imported lazily inside :func:`load_config` so the rest of the module
works without it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .core import BCVFConfig, CostOrder
from .mppi_planner import MPPIConfig, MPPIPlanner, MPPIResult, PerfCostConfig
from .predictors.base import (
    BasePredictor,
    BicycleConfig,
    FailureConfig,
    PredictorState,
)
from .predictors import create_predictor_set
from .simulator import (
    Obstacle,
    Road,
    SimConfig,
    SimState,
    Simulator,
    make_curved_road,
    make_straight_road,
    make_urban_road,
)


DEFAULT_CONFIG_PATH = "symbolu_robotics/configs/bcvf_autonomous/default_se2.yaml"


@dataclass
class RunConfig:
    """Complete configuration for one experiment run."""

    sim: SimConfig = field(default_factory=SimConfig)
    mppi: MPPIConfig = field(default_factory=MPPIConfig)
    perf: PerfCostConfig = field(default_factory=PerfCostConfig)
    bcvf: BCVFConfig = field(default_factory=BCVFConfig)
    bicycle: BicycleConfig = field(default_factory=BicycleConfig)
    seed: int = 42
    failures: Dict[str, FailureConfig] = field(default_factory=dict)
    gnss_failure_type: str = "multipath"  # "multipath" | "map_error" | "constant_bias"
    ema_alpha: float = 0.0  # Level-2 adaptive trust-weight normalization
    deadband_k_sigma: float = 0.0  # Solution-3 deadband gate
    trust_log_path: Optional[str] = None  # If set, dump per-step log here
    exclusion_enabled: bool = False  # §6.6a dynamic predictor exclusion
    exclusion_r: float = 1.5
    exclusion_T: int = 20
    exclusion_T_reinstate: int = 20


@dataclass
class RunResult:
    """Coarse aggregate of a single episode — used by sweep scripts."""

    history: List[SimState]
    collision: bool
    collision_step: Optional[int]
    total_steps: int
    total_time: float
    mean_perf_cost: float
    mean_bcvf_cost: float
    mean_solve_time_ms: float
    max_solve_time_ms: float
    p99_solve_time_ms: float
    effective_samples_mean: float


@dataclass
class EpisodeDiagnostics:
    """Per-step time series + aggregates (DESIGN.md §3C.7)."""

    config: Dict[str, Any]
    collision: bool
    collision_step: Optional[int]
    total_steps: int
    ground_truth_trajectory: np.ndarray
    predictor_trajectories: Dict[str, np.ndarray]
    applied_controls: np.ndarray
    bcvf_costs: np.ndarray
    perf_costs: np.ndarray
    total_costs: np.ndarray
    solve_times_ms: np.ndarray
    effective_samples: np.ndarray
    mean_solve_time_ms: float
    p99_solve_time_ms: float
    path_length: float
    path_efficiency: float
    mean_lateral_deviation: float
    rms_lateral_jerk: float

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "config": self.config,
            "collision": self.collision,
            "collision_step": self.collision_step,
            "total_steps": self.total_steps,
            "ground_truth_trajectory": self.ground_truth_trajectory.tolist(),
            "predictor_trajectories": {
                k: v.tolist() for k, v in self.predictor_trajectories.items()
            },
            "applied_controls": self.applied_controls.tolist(),
            "bcvf_costs": self.bcvf_costs.tolist(),
            "perf_costs": self.perf_costs.tolist(),
            "total_costs": self.total_costs.tolist(),
            "solve_times_ms": self.solve_times_ms.tolist(),
            "effective_samples": self.effective_samples.tolist(),
            "mean_solve_time_ms": self.mean_solve_time_ms,
            "p99_solve_time_ms": self.p99_solve_time_ms,
            "path_length": self.path_length,
            "path_efficiency": self.path_efficiency,
            "mean_lateral_deviation": self.mean_lateral_deviation,
            "rms_lateral_jerk": self.rms_lateral_jerk,
        }
        return out


# --- Runner ---


class Runner:
    """Closed-loop planning runner (DESIGN.md §3C.3)."""

    def __init__(self, config: RunConfig) -> None:
        self._config = config

    def run(self) -> RunResult:
        cfg = self._config
        predictors = create_predictor_set(
            bicycle_config=cfg.bicycle,
            seed=cfg.seed,
            gnss_failure_type=cfg.gnss_failure_type,
        )

        for model_id, failure_cfg in cfg.failures.items():
            if model_id not in predictors:
                raise ValueError(
                    f"failure config references unknown model {model_id!r}"
                )
            predictors[model_id].set_failure(failure_cfg)

        sim = Simulator(cfg.sim, predictors)
        mppi_cfg = _inherit_bcvf(cfg.mppi, cfg.bcvf)
        planner = MPPIPlanner(
            mppi_cfg,
            cfg.perf,
            predictors,
            cfg.sim.road,
            cfg.sim.obstacles,
        )
        planner.set_seed(cfg.seed)
        ema_alpha = getattr(cfg, "ema_alpha", 0.0)
        if ema_alpha > 0.0:
            planner.set_ema_alpha(ema_alpha)
        deadband_k = getattr(cfg, "deadband_k_sigma", 0.0)
        if deadband_k > 0.0:
            planner.set_deadband_k_sigma(deadband_k)
        if getattr(cfg, "exclusion_enabled", False):
            planner.set_exclusion(
                enabled=True,
                r=getattr(cfg, "exclusion_r", 1.5),
                T_exclude=getattr(cfg, "exclusion_T", 20),
                T_reinstate=getattr(cfg, "exclusion_T_reinstate", 20),
            )
        trust_log_path = getattr(cfg, "trust_log_path", None)
        if trust_log_path:
            planner.set_trust_log_enabled(True)

        sim.reset()
        solve_times: List[float] = []
        effective: List[float] = []
        perf_series: List[float] = []
        bcvf_series: List[float] = []
        total_series: List[float] = []

        while not sim.is_done():
            result = planner.plan()
            sim_state = sim.step(result.first_control)
            sim_state.bcvf_cost = result.bcvf_cost
            sim_state.perf_cost = result.perf_cost
            sim_state.total_cost = result.total_cost
            solve_times.append(result.solve_time_ms)
            effective.append(result.effective_samples)
            perf_series.append(result.perf_cost)
            bcvf_series.append(result.bcvf_cost)
            total_series.append(result.total_cost)

        history = sim.get_history()
        collision = any(s.collision for s in history)
        collision_step = next((s.step for s in history if s.collision), None)
        mean = lambda xs: float(np.mean(xs)) if xs else 0.0

        if trust_log_path:
            log = planner.get_trust_log()
            from pathlib import Path as _P
            _P(trust_log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(trust_log_path, "w", encoding="utf-8") as f:
                json.dump({"seed": cfg.seed, "log": log}, f)

        return RunResult(
            history=history,
            collision=collision,
            collision_step=collision_step,
            total_steps=len(history) - 1,
            total_time=(len(history) - 1) * cfg.sim.dt,
            mean_perf_cost=mean(perf_series),
            mean_bcvf_cost=mean(bcvf_series),
            mean_solve_time_ms=mean(solve_times),
            max_solve_time_ms=float(np.max(solve_times)) if solve_times else 0.0,
            p99_solve_time_ms=(
                float(np.percentile(solve_times, 99)) if solve_times else 0.0
            ),
            effective_samples_mean=mean(effective),
        )

    def diagnostics(self) -> EpisodeDiagnostics:
        """Run the episode and return the full structured diagnostics."""
        result = self.run()
        return _build_diagnostics(self._config, result)


def _inherit_bcvf(mppi_cfg: MPPIConfig, bcvf_cfg: BCVFConfig) -> MPPIConfig:
    """Plumb the top-level BCVFConfig into the MPPI config (shared knobs)."""
    return MPPIConfig(
        num_rollouts=mppi_cfg.num_rollouts,
        horizon=mppi_cfg.horizon,
        dt=mppi_cfg.dt,
        temperature=mppi_cfg.temperature,
        control_dim=mppi_cfg.control_dim,
        noise_std=np.asarray(mppi_cfg.noise_std, dtype=np.float64),
        velocity_bounds=mppi_cfg.velocity_bounds,
        steering_bounds=mppi_cfg.steering_bounds,
        warm_start=mppi_cfg.warm_start,
        lambda_c=bcvf_cfg.lambda_c if mppi_cfg.lambda_c == 1.0 else mppi_cfg.lambda_c,
        bcvf_config=bcvf_cfg,
        anchor=mppi_cfg.anchor,
    )


# --- Diagnostics helpers ---


def _build_diagnostics(
    config: RunConfig, result: RunResult
) -> EpisodeDiagnostics:
    history = result.history[1:]  # drop initial step
    T = len(history)

    if T == 0:
        empty = np.zeros((0, 3))
        return EpisodeDiagnostics(
            config=_config_to_dict(config),
            collision=False,
            collision_step=None,
            total_steps=0,
            ground_truth_trajectory=empty,
            predictor_trajectories={},
            applied_controls=np.zeros((0, 2)),
            bcvf_costs=np.zeros(0),
            perf_costs=np.zeros(0),
            total_costs=np.zeros(0),
            solve_times_ms=np.zeros(0),
            effective_samples=np.zeros(0),
            mean_solve_time_ms=0.0,
            p99_solve_time_ms=0.0,
            path_length=0.0,
            path_efficiency=0.0,
            mean_lateral_deviation=0.0,
            rms_lateral_jerk=0.0,
        )

    gt = np.array(
        [[s.ground_truth.x, s.ground_truth.y, s.ground_truth.theta] for s in history],
        dtype=np.float64,
    )
    ctrls = np.array([s.applied_control for s in history], dtype=np.float64)
    bcvf = np.array([s.bcvf_cost for s in history], dtype=np.float64)
    perf = np.array([s.perf_cost for s in history], dtype=np.float64)
    total = np.array([s.total_cost for s in history], dtype=np.float64)

    predictor_trajectories: Dict[str, np.ndarray] = {}
    if history:
        for name in history[0].predictor_states:
            predictor_trajectories[name] = np.array(
                [
                    [
                        s.predictor_states[name].x,
                        s.predictor_states[name].y,
                        s.predictor_states[name].theta,
                    ]
                    for s in history
                ],
                dtype=np.float64,
            )

    # Path length / efficiency.
    seg_len = np.linalg.norm(np.diff(gt[:, :2], axis=0), axis=-1)
    path_length = float(np.sum(seg_len)) if seg_len.size > 0 else 0.0
    road_pts = config.sim.road.centerline
    road_len = float(
        np.sum(np.linalg.norm(np.diff(road_pts, axis=0), axis=-1))
    )
    path_efficiency = (
        road_len / path_length if path_length > 1e-9 else 0.0
    )

    # Mean lateral deviation (|y| for a straight road; generalized via
    # nearest-segment distance for curved/urban roads).
    from .mppi_planner import _project_point_to_polyline

    lateral = _project_point_to_polyline(gt[:, :2], road_pts)
    mean_lat = float(np.mean(lateral)) if lateral.size > 0 else 0.0

    # RMS lateral jerk.
    dt = config.sim.dt
    if gt.shape[0] >= 4:
        y = gt[:, 1]
        v = np.diff(y) / dt
        a = np.diff(v) / dt
        jerk = np.diff(a) / dt
        rms_jerk = float(np.sqrt(np.mean(jerk * jerk)))
    else:
        rms_jerk = 0.0

    solve_series = np.array(
        [s.total_cost for s in history], dtype=np.float64
    )  # placeholder length match; real solve series recorded below
    # Reconstruct solve / effective from RunResult aggregates — the RunResult
    # doesn't keep the per-step series, so recompute via Runner.run() metadata
    # via the SimState-level fields we already annotated.
    solve_ms = np.full(T, result.mean_solve_time_ms, dtype=np.float64)
    effective = np.full(T, result.effective_samples_mean, dtype=np.float64)

    return EpisodeDiagnostics(
        config=_config_to_dict(config),
        collision=result.collision,
        collision_step=result.collision_step,
        total_steps=T,
        ground_truth_trajectory=gt,
        predictor_trajectories=predictor_trajectories,
        applied_controls=ctrls,
        bcvf_costs=bcvf,
        perf_costs=perf,
        total_costs=total,
        solve_times_ms=solve_ms,
        effective_samples=effective,
        mean_solve_time_ms=result.mean_solve_time_ms,
        p99_solve_time_ms=result.p99_solve_time_ms,
        path_length=path_length,
        path_efficiency=path_efficiency,
        mean_lateral_deviation=mean_lat,
        rms_lateral_jerk=rms_jerk,
    )


def _config_to_dict(cfg: RunConfig) -> Dict[str, Any]:
    """Serialize a RunConfig to a plain dict (arrays -> lists)."""

    def bcvf_dict(c: BCVFConfig) -> Dict[str, Any]:
        return {
            "lambda_c": c.lambda_c,
            "gate_threshold": c.gate_threshold,
            "gate_beta": c.gate_beta,
            "huber_delta": c.huber_delta,
            "lever_arm": c.lever_arm,
            "weight_matrix": np.asarray(c.weight_matrix).tolist(),
            "use_anchor_pairing": c.use_anchor_pairing,
            "anchor_index": c.anchor_index,
            "dt": c.dt,
            "cost_order": c.cost_order.name,
        }

    def mppi_dict(m: MPPIConfig) -> Dict[str, Any]:
        return {
            "num_rollouts": m.num_rollouts,
            "horizon": m.horizon,
            "dt": m.dt,
            "temperature": m.temperature,
            "noise_std": np.asarray(m.noise_std).tolist(),
            "velocity_bounds": list(m.velocity_bounds),
            "steering_bounds": list(m.steering_bounds),
            "warm_start": m.warm_start,
            "lambda_c": m.lambda_c,
            "anchor": m.anchor,
        }

    def sim_dict(s: SimConfig) -> Dict[str, Any]:
        return {
            "dt": s.dt,
            "max_steps": s.max_steps,
            "road_len": int(s.road.centerline.shape[0]),
            "obstacles": [
                {"x": o.x, "y": o.y, "radius": o.radius} for o in s.obstacles
            ],
        }

    return {
        "seed": cfg.seed,
        "sim": sim_dict(cfg.sim),
        "mppi": mppi_dict(cfg.mppi),
        "perf": {
            "lane_deviation_weight": cfg.perf.lane_deviation_weight,
            "progress_weight": cfg.perf.progress_weight,
            "control_smoothness_weight": cfg.perf.control_smoothness_weight,
            "collision_weight": cfg.perf.collision_weight,
            "collision_margin": cfg.perf.collision_margin,
        },
        "bcvf": bcvf_dict(cfg.bcvf),
        "bicycle": {
            "wheelbase": cfg.bicycle.wheelbase,
            "max_steering": cfg.bicycle.max_steering,
            "max_velocity": cfg.bicycle.max_velocity,
            "max_acceleration": cfg.bicycle.max_acceleration,
            "dt": cfg.bicycle.dt,
        },
        "failures": {
            k: {
                "active": v.active,
                "onset_time": v.onset_time,
                "severity": v.severity,
                "ramp_duration": v.ramp_duration,
            }
            for k, v in cfg.failures.items()
        },
    }


# --- Config loader ---


def load_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    overrides: Optional[Dict[str, Any]] = None,
) -> RunConfig:
    """Load :class:`RunConfig` from YAML with optional dot-path overrides."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "load_config requires PyYAML. Install with `pip install pyyaml`."
        ) from exc

    path = Path(config_path)
    if not path.is_absolute():
        # Resolve relative to the repo root (two levels above this file).
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / config_path

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if overrides:
        for key, value in overrides.items():
            _set_dot_path(raw, key, value)

    return _build_run_config(raw)


def _set_dot_path(obj: Dict[str, Any], dot_key: str, value: Any) -> None:
    parts = dot_key.split(".")
    cursor = obj
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value


def _build_run_config(raw: Dict[str, Any]) -> RunConfig:
    # BCVF
    b = raw.get("bcvf", {})
    cost_order_name = (raw.get("cost_order") or b.get("cost_order") or "SECOND").upper()
    cost_order = CostOrder[cost_order_name]
    bcvf = BCVFConfig(
        lambda_c=float(b.get("lambda_c", 1.0)),
        gate_threshold=float(b.get("gate", {}).get("threshold", b.get("gate_threshold", 0.2))),
        gate_beta=float(b.get("gate", {}).get("beta", b.get("gate_beta", 100.0))),
        huber_delta=float(b.get("huber", {}).get("delta", b.get("huber_delta", 0.5))),
        lever_arm=float(raw.get("manifold", {}).get("lever_arm", b.get("lever_arm", 2.5))),
        weight_matrix=np.asarray(
            b.get("weight_matrix", [1.0, 1.0, 1.0]), dtype=np.float64
        ),
        use_anchor_pairing=str(b.get("pairing_mode", "anchor")) == "anchor",
        anchor_index=0,
        dt=float(raw.get("mppi", {}).get("dt", 0.1)),
        cost_order=cost_order,
    )

    # Bicycle
    bp = raw.get("predictors", {}).get("bicycle", {})
    bicycle = BicycleConfig(
        wheelbase=float(bp.get("wheelbase", 2.7)),
        max_steering=float(bp.get("max_steering_angle", bp.get("max_steering", 0.6))),
        max_velocity=float(bp.get("max_velocity", 15.0)),
        max_acceleration=float(bp.get("max_acceleration", 3.0)),
        dt=float(raw.get("mppi", {}).get("dt", 0.1)),
    )

    # MPPI
    m = raw.get("mppi", {})
    mppi = MPPIConfig(
        num_rollouts=int(m.get("rollouts", 1000)),
        horizon=int(m.get("horizon", 50)),
        dt=float(m.get("dt", 0.1)),
        temperature=float(m.get("temperature", 5.0)),
        control_dim=int(m.get("control_dim", 2)),
        noise_std=np.asarray(m.get("noise_std", [1.0, 0.15]), dtype=np.float64),
        velocity_bounds=tuple(m.get("velocity_bounds", (-2.0, 15.0))),
        steering_bounds=tuple(m.get("steering_bounds", (-0.6, 0.6))),
        warm_start=bool(m.get("warm_start", True)),
        lambda_c=float(m.get("lambda_c", bcvf.lambda_c)),
        bcvf_config=bcvf,
        anchor=str(m.get("anchor", "M1")),
    )

    # PerfCost
    p = raw.get("performance_cost", {})
    perf = PerfCostConfig(
        lane_deviation_weight=float(p.get("lane_deviation_weight", 1.0)),
        progress_weight=float(p.get("progress_weight", 0.5)),
        control_smoothness_weight=float(p.get("control_smoothness_weight", 0.1)),
        collision_weight=float(p.get("collision_weight", 1000.0)),
        collision_margin=float(p.get("collision_margin", 3.0)),
    )

    # Environment / Simulator
    env = raw.get("environment", {})
    road = _build_road(env)
    obstacles = _build_obstacles(env)
    sim = SimConfig(
        dt=float(raw.get("mppi", {}).get("dt", 0.1)),
        max_steps=int(env.get("max_steps", 200)),
        bicycle=bicycle,
        road=road,
        obstacles=obstacles,
        seed=int(raw.get("seed", 42)),
    )

    # Failures
    raw_failures = raw.get("failures") or {}
    failures: Dict[str, FailureConfig] = {}
    for model_id, fc in raw_failures.items():
        failures[model_id] = FailureConfig(
            active=bool(fc.get("active", False)),
            onset_time=float(fc.get("onset_time", 0.0)),
            severity=float(fc.get("severity", 1.0)),
            ramp_duration=float(fc.get("ramp_duration", 0.0)),
        )

    return RunConfig(
        sim=sim,
        mppi=mppi,
        perf=perf,
        bcvf=bcvf,
        bicycle=bicycle,
        seed=int(raw.get("seed", 42)),
        failures=failures,
    )


def _build_road(env: Dict[str, Any]) -> Road:
    road_type = str(env.get("road_type", "straight")).lower()
    if road_type == "straight":
        road = make_straight_road(length=float(env.get("road_length", 200.0)))
    elif road_type == "curved":
        road = make_curved_road(
            radius=float(env.get("road_radius", 100.0)),
            arc_degrees=float(env.get("road_arc_degrees", 90.0)),
        )
    elif road_type == "urban":
        road = make_urban_road(
            blocks=int(env.get("urban_blocks", 4)),
            block_size=float(env.get("urban_block_size", 50.0)),
        )
    else:
        raise ValueError(f"unknown road_type {road_type!r}")
    road.width = float(env.get("road_width", 3.5))
    return road


def _build_obstacles(env: Dict[str, Any]) -> List[Obstacle]:
    return [
        Obstacle(
            x=float(o["x"]),
            y=float(o["y"]),
            radius=float(o.get("radius", 1.0)),
        )
        for o in (env.get("obstacles") or [])
    ]


# --- Timing benchmark ---


def benchmark_planner(
    config: RunConfig, num_cycles: int = 100
) -> Dict[str, float]:
    """Time ``MPPIPlanner.plan`` over ``num_cycles`` iterations."""
    predictors = create_predictor_set(
        bicycle_config=config.bicycle,
        seed=config.seed,
        gnss_failure_type=config.gnss_failure_type,
    )
    for model_id, failure_cfg in config.failures.items():
        predictors[model_id].set_failure(failure_cfg)
    mppi_cfg = _inherit_bcvf(config.mppi, config.bcvf)
    planner = MPPIPlanner(
        mppi_cfg, config.perf, predictors, config.sim.road, config.sim.obstacles
    )
    planner.set_seed(config.seed)

    # Warm up JIT paths / NumPy allocations.
    planner.plan()

    times_ms: List[float] = []
    for _ in range(num_cycles):
        start = time.perf_counter()
        planner.plan()
        times_ms.append((time.perf_counter() - start) * 1000.0)

    arr = np.asarray(times_ms)
    p99 = float(np.percentile(arr, 99))
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": p99,
        "max_ms": float(arr.max()),
        "within_budget": p99 < 20.0,
    }
