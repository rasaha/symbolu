"""BCVF Autonomous characterization sweep — public API.

A regression suite that proves the BCVF kernel detects each canonical
sensor-failure class while staying quiet on each canonical nominal
class. Seven families:

  baseline, constant_bias, linear_drift, accelerating, noise_floor,
  outlier, sensor_dropout

Three grids:

  primary       — every family × magnitude × seed at V1 defaults
  sensitivity   — canonical magnitude × (T, β, δ) sweep
  ablation      — linear_drift × cost-order (ZEROTH / FIRST / SECOND)

Per-family threshold tables in ``sweep._evaluate_thresholds`` mirror
the BCVF LLM characterization tables. Outlier-attribution metrics
(hit / margin / rank) live in ``alignment``.

Usage:

    from symbolu_robotics.bcvf_autonomous.characterization import (
        run_primary_grid, summarize_grid,
    )

    cells = run_primary_grid()
    summary = summarize_grid(cells)
    print(summary["false_positive_rate"], summary["false_negative_rate"])
"""

from __future__ import annotations

from .alignment import (
    AlignmentAggregate,
    AlignmentMetrics,
    aggregate_alignment,
    compute_alignment_metrics,
)
from .stats import (
    CERTIFICATION_FLOOR,
    WILSON_Z_95,
    wilson_ci,
    wilson_lower_bound,
)
from .sweep import (
    ABLATION_SEEDS,
    FAMILY_MAGNITUDES,
    LEGACY_PRIMARY_SEEDS,
    PRIMARY_SEEDS,
    SENSITIVITY_BETA,
    SENSITIVITY_DELTA,
    SENSITIVITY_SEEDS,
    SENSITIVITY_T,
    V1_DEFAULTS,
    CellResult,
    PerConfigPassStat,
    family_pass_rate,
    per_config_pass_stats,
    pick_winner_tuple,
    run_ablation_grid,
    run_primary_grid,
    run_sensitivity_grid,
    split_nominal_failure,
    summarize_grid,
)
from .traces import (
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    TraceBundle,
    generate_trace,
)

__all__ = [
    "ABLATION_SEEDS",
    "AlignmentAggregate",
    "AlignmentMetrics",
    "CERTIFICATION_FLOOR",
    "CellResult",
    "FAILURE_FAMILIES",
    "FAMILY_MAGNITUDES",
    "LEGACY_PRIMARY_SEEDS",
    "NOMINAL_FAMILIES",
    "PerConfigPassStat",
    "PRIMARY_SEEDS",
    "SENSITIVITY_BETA",
    "SENSITIVITY_DELTA",
    "SENSITIVITY_SEEDS",
    "SENSITIVITY_T",
    "TraceBundle",
    "V1_DEFAULTS",
    "WILSON_Z_95",
    "aggregate_alignment",
    "compute_alignment_metrics",
    "family_pass_rate",
    "generate_trace",
    "per_config_pass_stats",
    "pick_winner_tuple",
    "run_ablation_grid",
    "run_primary_grid",
    "run_sensitivity_grid",
    "split_nominal_failure",
    "summarize_grid",
    "wilson_ci",
    "wilson_lower_bound",
]
