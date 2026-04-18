"""Phase 4C — experiment orchestrator + CLI (DESIGN.md §4C).

Runs the full (scenarios × ablation variants × lambda_c sweep × repeats)
matrix, persists each episode's diagnostics as JSON so crashed runs can
resume, feeds results into :mod:`metrics` for aggregation + statistical
comparisons, and emits the DESIGN §4B.6 summary table.

Also exposes a CLI entry point::

    python -m symbolu_robotics.bcvf_autonomous.run_experiments --quick
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .core import BCVFConfig, CostOrder
from .metrics import (
    AggregateMetrics,
    ComparisonResult,
    build_summary_table,
    compare_collision_rates,
    compare_recovery_rates,
    compute_aggregate_metrics,
    compute_alignment_diagnostic,
    compute_episode_metrics,
    compute_early_warning_time,
    mcnemar_exact,
)
from .mppi_planner import MPPIConfig, PerfCostConfig
from .predictors.base import BicycleConfig
from .runner import RunConfig, Runner
from .scenarios import SCENARIOS, scenario_to_run_config


# --- Variant descriptor ---


VARIANT_IDS: Tuple[str, ...] = ("A0", "A1", "A2", "A3")
VARIANT_DIRNAMES = {
    "A0": "A0_baseline",
    "A1": "A1_zeroth",
    "A2": "A2_first",
    "A3": "A3_second_bcvf",
}


def _variant_to_configs(
    variant_id: str,
    base_bcvf: BCVFConfig,
    base_mppi: MPPIConfig,
    lambda_c_override: Optional[float] = None,
) -> Tuple[BCVFConfig, MPPIConfig]:
    """Translate a variant ID to the correct ``(BCVFConfig, MPPIConfig)`` pair.

    A0: ``lambda_c = 0`` (BCVF disabled, no BCVF rollouts).
    A1: ``lambda_c = 1``, ``cost_order = ZEROTH``.
    A2: ``lambda_c = 1``, ``cost_order = FIRST``.
    A3: ``lambda_c = 1`` (or ``lambda_c_override``), ``cost_order = SECOND``.
    """
    bcvf = dataclasses.replace(base_bcvf)
    mppi = dataclasses.replace(base_mppi)

    if variant_id == "A0":
        mppi.lambda_c = 0.0
        bcvf.lambda_c = 0.0
        bcvf.cost_order = CostOrder.SECOND  # value is irrelevant when lambda_c=0
    elif variant_id == "A1":
        mppi.lambda_c = 1.0
        bcvf.lambda_c = 1.0
        bcvf.cost_order = CostOrder.ZEROTH
    elif variant_id == "A2":
        mppi.lambda_c = 1.0
        bcvf.lambda_c = 1.0
        bcvf.cost_order = CostOrder.FIRST
    elif variant_id == "A3":
        lam = lambda_c_override if lambda_c_override is not None else 1.0
        mppi.lambda_c = lam
        bcvf.lambda_c = lam
        bcvf.cost_order = CostOrder.SECOND
    else:
        raise ValueError(f"unknown variant {variant_id!r}; expected one of {VARIANT_IDS}")

    mppi.bcvf_config = bcvf
    return bcvf, mppi


# --- Experiment configuration ---


@dataclass
class ExperimentConfig:
    """Configuration for the full experiment suite (DESIGN §4C.4)."""

    scenarios: List[str] = field(default_factory=lambda: list(SCENARIOS.keys()))
    ablation_variants: List[str] = field(default_factory=lambda: list(VARIANT_IDS))
    lambda_c_sweep_values: List[float] = field(
        default_factory=lambda: [0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
    )
    runs_per_config: int = 100
    base_seed: int = 42
    output_dir: str = "results"
    quick_mode: bool = False

    # Injected at Runner build-time by ExperimentRunner; allows tests to
    # shrink the tuning for fast sweeps without editing code.
    base_bcvf: Optional[BCVFConfig] = None
    base_mppi: Optional[MPPIConfig] = None
    base_perf: Optional[PerfCostConfig] = None
    base_bicycle: Optional[BicycleConfig] = None


@dataclass
class ExperimentResult:
    """Complete output of the experiment suite (DESIGN §4C.4)."""

    ablation_results: Dict[Tuple[str, str], AggregateMetrics]
    sweep_results: Dict[Tuple[str, float], AggregateMetrics]
    summary_table: Dict[str, Dict[str, Dict[str, str]]]
    comparisons: List[ComparisonResult]
    wall_clock_seconds: float
    total_runs: int


# --- Orchestrator ---


def _default_tuning() -> Tuple[BCVFConfig, MPPIConfig, PerfCostConfig, BicycleConfig]:
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
        num_rollouts=256,
        horizon=20,
        noise_std=np.array([1.5, 0.2], dtype=np.float64),
        velocity_bounds=(0.5, 10.0),
        bcvf_config=bcvf,
    )
    # Gate-2 cost-balance experiment: cap per-step squared lane deviation
    # at 10 (d < ~3.16 m, comfortably outside the 3.5 m lane). Prevents
    # J_perf from saturating at 1e4+ under the failing-anchor rollout —
    # without which MPPI's softmax collapses and strips J_BCVF of leverage.
    perf = PerfCostConfig(lane_deviation_cap=10.0)
    return bcvf, mppi, perf, BicycleConfig()


def _apply_quick_mode(cfg: ExperimentConfig) -> ExperimentConfig:
    cfg.scenarios = ["S1_normal_driving", "S6_glass_corridor"]
    cfg.ablation_variants = ["A0", "A3"]
    cfg.runs_per_config = 3
    cfg.lambda_c_sweep_values = []
    return cfg


def _log(msg: str) -> None:
    print(msg, flush=True)


class ExperimentRunner:
    """Orchestrates the DESIGN §4C experiment matrix."""

    def __init__(self, config: ExperimentConfig) -> None:
        self._config = config
        if config.quick_mode:
            _apply_quick_mode(self._config)
        tuning = _default_tuning()
        self._base_bcvf = config.base_bcvf or tuning[0]
        self._base_mppi = config.base_mppi or tuning[1]
        self._base_perf = config.base_perf or tuning[2]
        self._base_bicycle = config.base_bicycle or tuning[3]

    # --- filesystem ---

    def _ablation_dir(self, scenario: str, variant_id: str) -> Path:
        return (
            Path(self._config.output_dir)
            / "ablation"
            / scenario
            / VARIANT_DIRNAMES[variant_id]
        )

    def _sweep_dir(self, scenario: str, lam: float) -> Path:
        return (
            Path(self._config.output_dir)
            / "sweep"
            / scenario
            / f"lambda_{lam:.2f}"
        )

    def _should_skip(self, run_dir: Path, run_index: int) -> bool:
        return (run_dir / f"run_{run_index:03d}.json").exists()

    # --- one run ---

    def _run_one_episode(
        self,
        scenario_name: str,
        bcvf_cfg: BCVFConfig,
        mppi_cfg: MPPIConfig,
        seed: int,
        out_dir: Path,
        run_index: int,
    ) -> compute_episode_metrics.__annotations__["return"]:  # EpisodeMetrics
        run_cfg = scenario_to_run_config(
            SCENARIOS[scenario_name],
            bcvf_cfg,
            mppi_cfg,
            self._base_perf,
            self._base_bicycle,
            seed=seed,
        )
        diag = Runner(run_cfg).diagnostics()

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"run_{run_index:03d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(diag.to_dict(), f)

        return compute_episode_metrics(diag)

    # --- ablation study ---

    def run_ablation_study(self) -> Dict[Tuple[str, str], AggregateMetrics]:
        results: Dict[Tuple[str, str], AggregateMetrics] = {}
        for scenario in self._config.scenarios:
            for variant in self._config.ablation_variants:
                bcvf_cfg, mppi_cfg = _variant_to_configs(
                    variant, self._base_bcvf, self._base_mppi
                )
                run_dir = self._ablation_dir(scenario, variant)
                ems = []
                t0 = time.perf_counter()
                for i in range(self._config.runs_per_config):
                    if self._should_skip(run_dir, i):
                        continue
                    ems.append(
                        self._run_one_episode(
                            scenario, bcvf_cfg, mppi_cfg,
                            seed=self._config.base_seed + i,
                            out_dir=run_dir, run_index=i,
                        )
                    )
                # Re-load any pre-existing runs so aggregation covers the full N.
                ems = self._load_episodes(run_dir, self._config.runs_per_config)
                agg = compute_aggregate_metrics(ems)
                _save_aggregate(run_dir, agg)
                results[(scenario, VARIANT_DIRNAMES[variant])] = agg
                _log(
                    f"[ablation] {scenario} / {VARIANT_DIRNAMES[variant]}: "
                    f"{len(ems)}/{self._config.runs_per_config} runs "
                    f"({time.perf_counter() - t0:.1f}s)"
                )
        return results

    # --- lambda_c sweep ---

    def run_lambda_sweep(self) -> Dict[Tuple[str, float], AggregateMetrics]:
        results: Dict[Tuple[str, float], AggregateMetrics] = {}
        if not self._config.lambda_c_sweep_values:
            return results
        for scenario in self._config.scenarios:
            if scenario == "S1_normal_driving":
                continue  # §4C.3: S1 excluded from sweep (J_BCVF ~ 0)
            for lam in self._config.lambda_c_sweep_values:
                bcvf_cfg, mppi_cfg = _variant_to_configs(
                    "A3", self._base_bcvf, self._base_mppi, lambda_c_override=lam
                )
                run_dir = self._sweep_dir(scenario, lam)
                ems: List = []
                t0 = time.perf_counter()
                for i in range(self._config.runs_per_config):
                    if self._should_skip(run_dir, i):
                        continue
                    ems.append(
                        self._run_one_episode(
                            scenario, bcvf_cfg, mppi_cfg,
                            seed=self._config.base_seed + i,
                            out_dir=run_dir, run_index=i,
                        )
                    )
                ems = self._load_episodes(run_dir, self._config.runs_per_config)
                agg = compute_aggregate_metrics(ems)
                _save_aggregate(run_dir, agg)
                results[(scenario, lam)] = agg
                _log(
                    f"[sweep] {scenario} / lambda_c={lam:.2f}: "
                    f"{len(ems)}/{self._config.runs_per_config} runs "
                    f"({time.perf_counter() - t0:.1f}s)"
                )
        return results

    # --- full suite ---

    def run_all(self, skip_sweep: bool = False, skip_ablation: bool = False) -> ExperimentResult:
        start = time.perf_counter()
        ablation = {} if skip_ablation else self.run_ablation_study()
        sweep = {} if skip_sweep else self.run_lambda_sweep()
        summary = build_summary_table(ablation)
        comparisons: List[ComparisonResult] = []

        # A0 vs A3 comparisons per scenario: collision rate (DESIGN §4C.13)
        # and post-peak recovery rate (B2-smoke-motivated addition — the
        # primary gate-2 metric when collisions are absent on both variants
        # because the failure geometry misses rather than hits).
        for scenario in self._config.scenarios:
            a0_key = (scenario, VARIANT_DIRNAMES["A0"])
            a3_key = (scenario, VARIANT_DIRNAMES["A3"])
            if a0_key in ablation and a3_key in ablation:
                comparisons.append(
                    compare_collision_rates(
                        ablation[a0_key], ablation[a3_key], "A0", "A3"
                    )
                )
                comparisons.append(
                    compare_recovery_rates(
                        ablation[a0_key], ablation[a3_key], "A0", "A3"
                    )
                )

        # Per-seed paired-outcome output for A0-vs-A3 recovery analysis.
        # Re-loads run_NNN.json files (cheap) and builds the McNemar table
        # per scenario. This is what downstream reviewers need to call the
        # gate-2 decision when Fisher's-exact p is borderline.
        paired_by_scenario = self._build_paired_outcomes(ablation)

        # BCVF-recovery alignment diagnostic: per-seed Pearson correlation
        # between A3's BCVF cost time-series and the lookahead-shifted A3-A0
        # lateral gap. Answers "is BCVF actually steering toward safety,
        # or just firing on predictor disagreement?"
        alignment_by_scenario = self._build_alignment_diagnostic()

        wall = time.perf_counter() - start
        total_runs = (
            len(ablation) * self._config.runs_per_config
            + len(sweep) * self._config.runs_per_config
        )

        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "summary_table.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        with open(out_dir / "comparisons.json", "w", encoding="utf-8") as f:
            json.dump([dataclasses.asdict(c) for c in comparisons], f, indent=2)
        with open(out_dir / "experiment_config.json", "w", encoding="utf-8") as f:
            json.dump(_config_to_dict(self._config), f, indent=2)
        with open(out_dir / "timing.json", "w", encoding="utf-8") as f:
            json.dump({"wall_clock_seconds": wall, "total_runs": total_runs}, f, indent=2)
        with open(out_dir / "paired_outcomes.json", "w", encoding="utf-8") as f:
            json.dump(paired_by_scenario, f, indent=2)
        with open(out_dir / "alignment_diagnostic.json", "w", encoding="utf-8") as f:
            json.dump(alignment_by_scenario, f, indent=2)

        return ExperimentResult(
            ablation_results=ablation,
            sweep_results=sweep,
            summary_table=summary,
            comparisons=comparisons,
            wall_clock_seconds=wall,
            total_runs=total_runs,
        )

    # --- helpers ---

    def _build_paired_outcomes(
        self, ablation: Dict[Tuple[str, str], AggregateMetrics]
    ) -> Dict[str, Any]:
        """Construct the per-seed paired-outcome tables needed for the
        McNemar analysis on A0 vs A3 recovery (B2 smoke follow-up).

        For each scenario with both A0 and A3 run, produces:

            {
              scenario_name: {
                "seeds": [s_0, ..., s_{N-1}],
                "A0_recovered":    [bool, ...],
                "A3_recovered":    [bool, ...],
                "A0_final_lateral":[float, ...],
                "A3_final_lateral":[float, ...],
                "discordant": {
                   "a3_wins": [seed_idx where A3 recovered, A0 didn't],
                   "a0_wins": [seed_idx where A0 recovered, A3 didn't],
                   "both_recovered": [...],
                   "both_failed":    [...],
                },
                "mcnemar": {"n_discordant": int, "p_value": float},
              }
            }

        The function is cheap — it re-reads each run's JSON (same data
        _load_episodes already uses) and is idempotent.
        """
        out: Dict[str, Any] = {}
        for scenario in self._config.scenarios:
            a0_dir = self._ablation_dir(scenario, "A0")
            a3_dir = self._ablation_dir(scenario, "A3")
            if not (a0_dir.exists() and a3_dir.exists()):
                continue
            a0_ems = self._load_episodes(a0_dir, self._config.runs_per_config)
            a3_ems = self._load_episodes(a3_dir, self._config.runs_per_config)
            n = min(len(a0_ems), len(a3_ems))
            if n == 0:
                continue
            seeds = [self._config.base_seed + i for i in range(n)]
            a0_rec = [m.post_peak_recovery_s is not None for m in a0_ems[:n]]
            a3_rec = [m.post_peak_recovery_s is not None for m in a3_ems[:n]]
            a0_final = [float(m.final_lateral_deviation) for m in a0_ems[:n]]
            a3_final = [float(m.final_lateral_deviation) for m in a3_ems[:n]]

            a3_wins, a0_wins, both_rec, both_fail = [], [], [], []
            for i, (r0, r3) in enumerate(zip(a0_rec, a3_rec)):
                if r0 and r3:
                    both_rec.append(i)
                elif not r0 and not r3:
                    both_fail.append(i)
                elif r3 and not r0:
                    a3_wins.append(i)
                else:
                    a0_wins.append(i)
            n_disc, p_mcnemar = mcnemar_exact(len(a0_wins), len(a3_wins))

            out[scenario] = {
                "seeds": seeds,
                "A0_recovered": a0_rec,
                "A3_recovered": a3_rec,
                "A0_final_lateral": a0_final,
                "A3_final_lateral": a3_final,
                "discordant": {
                    "a3_wins": a3_wins,
                    "a0_wins": a0_wins,
                    "both_recovered": both_rec,
                    "both_failed": both_fail,
                },
                "mcnemar": {
                    "n_discordant": int(n_disc),
                    "p_value": float(p_mcnemar),
                },
            }
        return out

    def _load_diagnostics(self, run_dir: Path, n: int) -> List:
        """Load raw EpisodeDiagnostics (not the derived EpisodeMetrics).
        Used by the alignment diagnostic, which needs the full
        ground_truth trajectory and bcvf_costs time series."""
        diags: List = []
        for i in range(n):
            path = run_dir / f"run_{i:03d}.json"
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as f:
                diags.append(_diagnostics_from_dict(json.load(f)))
        return diags

    def _build_alignment_diagnostic(self) -> Dict[str, Any]:
        """Run the BCVF-recovery alignment analysis for each scenario
        with both A0 and A3 runs completed."""
        out: Dict[str, Any] = {}
        for scenario in self._config.scenarios:
            a0_dir = self._ablation_dir(scenario, "A0")
            a3_dir = self._ablation_dir(scenario, "A3")
            if not (a0_dir.exists() and a3_dir.exists()):
                continue
            a0_diags = self._load_diagnostics(a0_dir, self._config.runs_per_config)
            a3_diags = self._load_diagnostics(a3_dir, self._config.runs_per_config)
            if not a0_diags or not a3_diags:
                continue
            n = min(len(a0_diags), len(a3_diags))
            out[scenario] = compute_alignment_diagnostic(
                a0_diags[:n], a3_diags[:n]
            )
        return out

    def _load_episodes(self, run_dir: Path, n: int) -> List:
        ems = []
        for i in range(n):
            path = run_dir / f"run_{i:03d}.json"
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            diag = _diagnostics_from_dict(raw)
            ems.append(compute_episode_metrics(diag))
        return ems


# --- (de)serialization helpers ---


def _diagnostics_from_dict(raw: Dict[str, Any]):
    from .runner import EpisodeDiagnostics  # avoid top-level cycle for readers
    return EpisodeDiagnostics(
        config=raw.get("config", {}),
        collision=raw["collision"],
        collision_step=raw.get("collision_step"),
        total_steps=raw["total_steps"],
        ground_truth_trajectory=np.asarray(raw["ground_truth_trajectory"], dtype=np.float64),
        predictor_trajectories={
            k: np.asarray(v, dtype=np.float64)
            for k, v in raw.get("predictor_trajectories", {}).items()
        },
        applied_controls=np.asarray(raw["applied_controls"], dtype=np.float64),
        bcvf_costs=np.asarray(raw["bcvf_costs"], dtype=np.float64),
        perf_costs=np.asarray(raw["perf_costs"], dtype=np.float64),
        total_costs=np.asarray(raw["total_costs"], dtype=np.float64),
        solve_times_ms=np.asarray(raw["solve_times_ms"], dtype=np.float64),
        effective_samples=np.asarray(raw["effective_samples"], dtype=np.float64),
        mean_solve_time_ms=raw["mean_solve_time_ms"],
        p99_solve_time_ms=raw["p99_solve_time_ms"],
        path_length=raw["path_length"],
        path_efficiency=raw["path_efficiency"],
        mean_lateral_deviation=raw.get("mean_lateral_deviation", 0.0),
        rms_lateral_jerk=raw["rms_lateral_jerk"],
    )


def _save_aggregate(run_dir: Path, agg: AggregateMetrics) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    out = dataclasses.asdict(agg)
    # Convert Tuple[Optional[float], Optional[float]] -> list for JSON.
    if out.get("early_warning_time_iqr") is not None:
        out["early_warning_time_iqr"] = list(out["early_warning_time_iqr"])
    with open(run_dir / "aggregate.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def _config_to_dict(cfg: ExperimentConfig) -> Dict[str, Any]:
    return {
        "scenarios": list(cfg.scenarios),
        "ablation_variants": list(cfg.ablation_variants),
        "lambda_c_sweep_values": list(cfg.lambda_c_sweep_values),
        "runs_per_config": cfg.runs_per_config,
        "base_seed": cfg.base_seed,
        "output_dir": cfg.output_dir,
        "quick_mode": cfg.quick_mode,
    }


# --- CLI ---


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BCVF Autonomous — Experiment Runner")
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--scenarios", nargs="+", default=None)
    parser.add_argument("--variants", nargs="+", default=None)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--sweep-only", action="store_true")
    parser.add_argument("--ablation-only", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    cfg = ExperimentConfig(
        output_dir=args.output,
        quick_mode=args.quick,
        base_seed=args.seed,
        runs_per_config=args.runs,
    )
    if args.scenarios:
        cfg.scenarios = args.scenarios
    if args.variants:
        cfg.ablation_variants = args.variants
    if args.quick:
        cfg = _apply_quick_mode(cfg)

    runner = ExperimentRunner(cfg)
    _log("BCVF Autonomous — Experiment Runner")
    _log("=" * 36)
    _log(
        f"Mode: {'quick' if cfg.quick_mode else 'full'} | "
        f"Scenarios: {len(cfg.scenarios)} | "
        f"Variants: {len(cfg.ablation_variants)} | "
        f"Repeats: {cfg.runs_per_config}"
    )
    result = runner.run_all(
        skip_sweep=args.ablation_only,
        skip_ablation=args.sweep_only,
    )
    _log(
        f"DONE. total_runs={result.total_runs} wall={result.wall_clock_seconds:.1f}s  "
        f"-> {cfg.output_dir}/summary_table.json"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
