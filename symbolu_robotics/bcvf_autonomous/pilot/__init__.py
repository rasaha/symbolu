"""§6.2 real-sensor pilot — executable harness for the paired
A0 / A3 comparison.

Dataset-agnostic: feeds any :class:`DatasetAdapter` through the V1
(or V2) trust pipeline, computes forecast-error and attribution
metrics per scene, runs a one-sided sign test on per-scene deltas,
aggregates a fleet-level :class:`FleetSummary`, and writes three
artifacts to disk:

* ``{label}_paired_comparison.csv`` — per-scene metrics
* ``{label}_fleet_summary.json`` — v0.4 fleet analysis output
* ``{label}_pilot_report.md`` — human-readable report

Usage:

    from symbolu_robotics.bcvf_autonomous.datasets.synthetic_realistic import (
        RealisticNoiseAdapter,
    )
    from symbolu_robotics.bcvf_autonomous.pilot import run_pilot

    result = run_pilot(
        adapter=RealisticNoiseAdapter(),
        output_dir="results/phase_6_2_pilot",
        pilot_label="phase_6_2_pre_pilot",
    )
    print(result.paired_comparison)

See ``DESIGN.md`` for the full design + acceptance criteria.
"""

from __future__ import annotations

from .runner import PilotResult, run_pilot
from .scene_evaluator import (
    SceneEvaluatorConfig,
    SceneMetrics,
    evaluate_scene_a0,
    evaluate_scene_a3,
)
from .sign_test import PairedComparisonResult, one_sided_sign_test

__all__ = [
    "PairedComparisonResult",
    "PilotResult",
    "SceneEvaluatorConfig",
    "SceneMetrics",
    "evaluate_scene_a0",
    "evaluate_scene_a3",
    "one_sided_sign_test",
    "run_pilot",
]
