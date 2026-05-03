"""§6.2 pilot top-level runner.

Iterates a :class:`DatasetAdapter`, runs paired A0 / A3 evaluation
on every scene, computes the headline sign-test, and writes three
artifacts to ``output_dir``:

1. ``paired_comparison.csv`` — per-scene metrics
2. ``fleet_summary.json`` — v0.4 ``FleetSummary`` over A3 episode records
3. ``pilot_report.md`` — human-readable summary

The runner is dataset-agnostic. The first execution runs against
``RealisticNoiseAdapter`` (the documented bridge); swapping in
``NuScenesAdapter`` is a one-line config change once the dataset
is accessible. See ``DESIGN.md`` for full rationale.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from ..analysis import aggregate_fleet
from ..datasets.base import DatasetAdapter
from .scene_evaluator import (
    SceneEvaluatorConfig,
    SceneMetrics,
    evaluate_scene_a0,
    evaluate_scene_a3,
)
from .sign_test import PairedComparisonResult, one_sided_sign_test


@dataclass
class PilotResult:
    """Aggregated output of one pilot execution."""

    n_scenes: int
    n_predictors: int
    paired_comparison: PairedComparisonResult
    per_failure_class: Dict[str, PairedComparisonResult]
    per_failure_class_attribution: Dict[str, float]
    lemma1_negative_control_pass: bool
    lemma1_max_bcvf_total: float
    fleet_summary_dict: Dict[str, Any]
    scene_metrics_a0: List[SceneMetrics] = field(repr=False, default_factory=list)
    scene_metrics_a3: List[SceneMetrics] = field(repr=False, default_factory=list)


def _scenes_with_metric_filter(
    scenes_a0: List[SceneMetrics],
    scenes_a3: List[SceneMetrics],
) -> List[Tuple[SceneMetrics, SceneMetrics, float]]:
    """Pair (A0, A3) scenes by id and compute per-scene delta."""
    by_id_a0 = {m.scene_id: m for m in scenes_a0}
    by_id_a3 = {m.scene_id: m for m in scenes_a3}
    paired = []
    for sid in by_id_a0:
        if sid in by_id_a3:
            a0 = by_id_a0[sid]
            a3 = by_id_a3[sid]
            delta = a0.mean_forecast_xy_error - a3.mean_forecast_xy_error
            paired.append((a0, a3, delta))
    return paired


def _failure_class_breakdown(
    paired: List[Tuple[SceneMetrics, SceneMetrics, float]],
    scenes: List,
) -> Dict[str, List[Tuple[SceneMetrics, SceneMetrics, float]]]:
    by_id = {s.scene_id: s for s in scenes}
    out: Dict[str, List] = defaultdict(list)
    for a0, a3, delta in paired:
        rec = by_id.get(a0.scene_id)
        ftype = (
            rec.failure_metadata.get("type")
            if rec is not None and rec.failure_metadata
            else "unknown"
        )
        out[ftype].append((a0, a3, delta))
    return dict(out)


def run_pilot(
    adapter: DatasetAdapter,
    output_dir: Union[str, Path],
    eval_config: Optional[SceneEvaluatorConfig] = None,
    pilot_label: str = "pilot",
) -> PilotResult:
    """Execute the §6.2 paired pilot end-to-end.

    Args:
        adapter: any concrete :class:`DatasetAdapter`.
        output_dir: directory where artifacts will be written. Created
            if missing.
        eval_config: per-scene evaluator config (BCVF / EMA / V2 knobs).
            Defaults match the §6.1 V1 validated configuration.
        pilot_label: prefix used in the output filenames + report header.

    Returns:
        :class:`PilotResult` with the aggregated comparison stats and
        the per-scene metric lists.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cfg = eval_config or SceneEvaluatorConfig()

    scene_ids = adapter.scene_ids()
    scenes = []
    metrics_a0: List[SceneMetrics] = []
    metrics_a3: List[SceneMetrics] = []
    episode_records = []
    episode_classifications = []
    episode_metadata = []
    lemma1_max = 0.0
    lemma1_pass = True

    for sid in scene_ids:
        scene = adapter.load_scene(sid)
        scenes.append(scene)
        metrics_a0.append(evaluate_scene_a0(scene, cfg))
        m_a3 = evaluate_scene_a3(scene, cfg)
        metrics_a3.append(m_a3)
        if m_a3.episode_record is not None:
            episode_records.append(m_a3.episode_record)
            episode_classifications.append(
                str(scene.failure_metadata.get("type") or "unknown")
            )
            episode_metadata.append(dict(scene.failure_metadata))

        # Lemma-1 negative control hard gate.
        ftype = scene.failure_metadata.get("type")
        if ftype == "constant_bias_sanity":
            lemma1_max = max(lemma1_max, m_a3.max_bcvf_total)
            if m_a3.max_bcvf_total > 1e-3:
                # constant_bias_sanity must NOT register meaningful
                # BCVF cost. The threshold is loose because realistic-
                # noise data has small AR(1) jitter that survives the
                # second derivative; the kernel itself is exact zero
                # under Lemma 1 on noise-free constant bias (verified
                # in the characterization sweep).
                lemma1_pass = False

    paired = _scenes_with_metric_filter(metrics_a0, metrics_a3)
    deltas = [d for (_a0, _a3, d) in paired]
    overall = one_sided_sign_test(deltas)

    per_class = _failure_class_breakdown(paired, scenes)
    per_class_test = {
        ftype: one_sided_sign_test([d for (_a, _b, d) in items])
        for ftype, items in per_class.items()
    }
    per_class_attr = {
        ftype: float(np.mean([a3.attribution_hit_rate for (_, a3, _d) in items]))
        for ftype, items in per_class.items()
    }

    fleet_summary = aggregate_fleet(
        episode_records,
        episode_ids=[m.scene_id for m in metrics_a3 if m.episode_record is not None],
        classifications=episode_classifications,
        metadata=episode_metadata,
    )
    fleet_dict = fleet_summary.to_dict()

    result = PilotResult(
        n_scenes=len(scene_ids),
        n_predictors=metrics_a3[0].M if metrics_a3 else 0,
        paired_comparison=overall,
        per_failure_class=per_class_test,
        per_failure_class_attribution=per_class_attr,
        lemma1_negative_control_pass=lemma1_pass,
        lemma1_max_bcvf_total=lemma1_max,
        fleet_summary_dict=fleet_dict,
        scene_metrics_a0=metrics_a0,
        scene_metrics_a3=metrics_a3,
    )

    _write_paired_csv(out_path / f"{pilot_label}_paired_comparison.csv", paired, scenes)
    _write_fleet_json(out_path / f"{pilot_label}_fleet_summary.json", fleet_dict)
    _write_report_md(
        out_path / f"{pilot_label}_pilot_report.md",
        adapter,
        result,
    )
    return result


def _write_paired_csv(path: Path, paired, scenes) -> None:
    by_id = {s.scene_id: s for s in scenes}
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "scene_id",
            "failure_type",
            "err_A0",
            "err_A3",
            "delta",
            "attribution_hit_rate",
            "mean_bcvf_total",
        ])
        for a0, a3, delta in paired:
            rec = by_id.get(a0.scene_id)
            ftype = (
                rec.failure_metadata.get("type", "unknown")
                if rec is not None and rec.failure_metadata
                else "unknown"
            )
            w.writerow([
                a0.scene_id,
                ftype,
                f"{a0.mean_forecast_xy_error:.6f}",
                f"{a3.mean_forecast_xy_error:.6f}",
                f"{delta:.6f}",
                f"{a3.attribution_hit_rate:.4f}",
                f"{a3.mean_bcvf_total:.6f}",
            ])


def _write_fleet_json(path: Path, fleet_dict: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fleet_dict, f, indent=2)


def _write_report_md(path: Path, adapter, result: PilotResult) -> None:
    overall = result.paired_comparison
    lines = []
    lines.append(f"# §6.2 Pilot Report")
    lines.append("")
    lines.append(f"Adapter: `{type(adapter).__name__}`")
    lines.append(f"Scenes: {result.n_scenes}  ·  Predictors per scene: {result.n_predictors}")
    lines.append("")
    lines.append("## Headline result — paired A0 vs A3 (forecast XY error)")
    lines.append("")
    lines.append(f"- N paired: **{overall.n_paired}**")
    lines.append(
        f"- A3 wins: **{overall.n_a3_wins}**  ·  "
        f"A0 wins: {overall.n_a0_wins}  ·  ties: {overall.n_ties}"
    )
    lines.append(
        f"- Win rate: **{overall.win_rate:.3f}**  "
        f"(95% Wilson CI: {overall.win_rate_ci_low:.3f}–"
        f"{overall.win_rate_ci_high:.3f})"
    )
    lines.append(
        f"- One-sided sign-test p-value: **{overall.p_value_one_sided:.4f}**"
    )
    lines.append("")
    lines.append("## Per-failure-class breakdown")
    lines.append("")
    lines.append("| failure_type | N | A3 wins | A0 wins | win_rate | p-value | attribution_hit |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for ftype, test in sorted(result.per_failure_class.items()):
        attr = result.per_failure_class_attribution.get(ftype, 0.0)
        lines.append(
            f"| {ftype} | {test.n_paired} | {test.n_a3_wins} | "
            f"{test.n_a0_wins} | {test.win_rate:.3f} | "
            f"{test.p_value_one_sided:.4f} | {attr:.3f} |"
        )
    lines.append("")
    lines.append("## Lemma-1 negative control")
    lines.append("")
    lines.append(
        f"- `constant_bias_sanity` max BCVF total observed in A3: "
        f"**{result.lemma1_max_bcvf_total:.6f}**"
    )
    lines.append(
        f"- Negative-control gate "
        f"({'PASS' if result.lemma1_negative_control_pass else 'FAIL'}): "
        "BCVF must not fire on Lemma-1 benign scenes."
    )
    lines.append("")
    lines.append("## Fleet summary highlights")
    lines.append("")
    fs = result.fleet_summary_dict
    lines.append(f"- Total episodes: {fs.get('n_episodes', 0)}")
    lines.append(f"- Total simulator steps: {fs.get('n_total_steps', 0)}")
    lines.append(
        f"- Argmax-flips per step (mean): "
        f"{fs.get('argmax_flips_per_step', {}).get('mean', 0):.4f}"
    )
    lines.append(
        f"- Argmax-flips per step (p99): "
        f"{fs.get('argmax_flips_per_step', {}).get('p99', 0):.4f}"
    )
    lines.append(f"- Near-vetoes detected: {len(fs.get('near_vetoes', []))}")
    lines.append(
        f"- V2 state flips detected: {len(fs.get('v2_state_flips', []))}"
    )
    lines.append("")
    lines.append("## Scope caveats")
    lines.append("")
    lines.append(
        "- This pilot ran the dataset returned by the supplied adapter. "
        "Numerical results are valid for that adapter's data; "
        "external-validity claims (e.g., real automotive sensor data) "
        "require executing the same runner against an adapter that "
        "loads a real dataset."
    )
    lines.append(
        "- Mode A (open-loop forecast comparison) was used. Mode B "
        "(closed-loop simulator) is a follow-on per the pilot plan."
    )
    lines.append(
        "- N paired = number of scenes — small N inflates the sign-test "
        "p-value. The headline bar is win-rate Wilson-CI lower bound > 0.5; "
        "the strict §6.1 protocol requires N ≥ 21 with p < 0.05 on a "
        "responsive failure class for a positive result."
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
