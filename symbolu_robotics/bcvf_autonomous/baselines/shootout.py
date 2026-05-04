"""Shootout orchestrator — runs every arbitrator across every
characterization family and writes the comparison table.

Output artifacts (in ``output_dir``):

* ``shootout.csv`` — one row per (arbitrator, family, seed) with
  consensus error / attribution hit / false-attribution / wall time
* ``shootout.json`` — aggregated per-(arbitrator, family) summary
* ``shootout_report.md`` — investor-readable comparison table
"""

from __future__ import annotations

import csv
import dataclasses
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..characterization.traces import (
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    TraceBundle,
    generate_trace,
)
from ..core import BCVFConfig, CostOrder
from .anchor import AnchorArbitrator
from .base import Arbitrator
from .bcvf_arbitrator import BCVFArbitrator
from .ekf_arbitrator import EKFArbitrator, EKFConfig
from .majority_vote import MajorityVoteArbitrator


# --------------------------------------------------------------------------- #
# Per-cell evaluation
# --------------------------------------------------------------------------- #


@dataclass
class CellResult:
    arbitrator: str
    family: str
    seed: int
    truth_label: Optional[int]
    consensus_xy_error: float
    attribution_hit_top_half: bool
    false_attribution_max: float    # max attribution score on benign families
    per_tick_us: float


def _ground_truth_trajectory(bundle: TraceBundle) -> np.ndarray:
    """Reconstruct the failure-free baseline trajectory for the family.

    Every characterization family starts from a straight-line
    ``base_velocity`` baseline and layers perturbations on one
    predictor (or all). The ground truth is that baseline.
    """
    H = int(bundle.metadata.get("H", bundle.trajectories.shape[1]))
    dt = float(bundle.metadata.get("dt", 0.1))
    v = float(bundle.metadata.get("base_velocity", 5.0))
    truth = np.zeros((H, 3), dtype=np.float64)
    truth[:, 0] = v * dt * np.arange(H, dtype=np.float64)
    return truth


def _attribution_top_half(
    attribution: np.ndarray, truth_label: Optional[int],
) -> bool:
    """True if the truth predictor sits in the top-half ranking.

    Top half is defined as ``ceil(M / 2)`` — for M=3 that's the top 2,
    for M=4 the top 2, for M=5 the top 3. A more lenient threshold
    than ``M // 2`` so M=3 cells aren't degenerate.

    An arbitrator whose attribution is exactly zero for every
    predictor (e.g. :class:`AnchorArbitrator`) carries no
    information about which predictor failed; we treat that as a
    miss regardless of truth_label, so the anchor floor stays at 0
    on every failure family.
    """
    if truth_label is None:
        return False
    if not np.any(attribution > 0):
        return False
    M = attribution.shape[0]
    ranks_desc = np.argsort(-attribution, kind="stable")
    pos = int(np.where(ranks_desc == truth_label)[0][0]) + 1
    top_k = (M + 1) // 2
    return pos <= top_k


def _eval_cell(
    arbitrator: Arbitrator,
    family: str,
    seed: int,
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
) -> CellResult:
    bundle = generate_trace(family=family, M=M, H=H, dt=dt, seed=seed)
    result = arbitrator.arbitrate(bundle.trajectories)
    gt = _ground_truth_trajectory(bundle)
    err = float(np.linalg.norm(result.consensus[:, :2] - gt[:, :2], axis=-1).mean())
    hit = _attribution_top_half(result.attribution, bundle.truth_label)
    # False-attribution: on benign families (no truth_label) the max
    # attribution score should be small; we record the max so the
    # shootout summary can compute the per-arbitrator false-positive
    # tendency.
    fa_max = (
        float(result.attribution.max()) if bundle.truth_label is None else 0.0
    )
    return CellResult(
        arbitrator=arbitrator.name,
        family=family,
        seed=seed,
        truth_label=bundle.truth_label,
        consensus_xy_error=err,
        attribution_hit_top_half=hit,
        false_attribution_max=fa_max,
        per_tick_us=result.per_tick_us,
    )


# --------------------------------------------------------------------------- #
# Shootout entry point
# --------------------------------------------------------------------------- #


@dataclass
class ShootoutSummary:
    """Aggregated per-(arbitrator, family) view."""

    arbitrator: str
    family: str
    n_seeds: int
    median_consensus_error: float
    attribution_hit_rate: float
    median_false_attribution: float
    median_per_tick_us: float


@dataclass
class ShootoutResult:
    cells: List[CellResult] = field(repr=False, default_factory=list)
    summaries: List[ShootoutSummary] = field(repr=False, default_factory=list)


def run_shootout(
    N: int = 10,
    base_seed: int = 5000,
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
    families: Sequence[str] = (
        "baseline", "constant_bias", "linear_drift",
        "accelerating", "noise_floor", "outlier", "sensor_dropout",
    ),
    arbitrators: Optional[Sequence[Arbitrator]] = None,
    output_dir: Union[str, Path] = "results/baseline_shootout",
    write_artifacts: bool = True,
) -> ShootoutResult:
    """Run every arbitrator across every family at N seeds each."""
    if arbitrators is None:
        bcvf_cfg = BCVFConfig(
            gate_threshold=0.05, gate_beta=400.0, huber_delta=0.5,
            lever_arm=2.5, weight_matrix=np.ones(3, dtype=np.float64),
            use_anchor_pairing=False, anchor_index=0,
            dt=dt, cost_order=CostOrder.SECOND, lambda_c=1.0,
        )
        arbitrators = [
            BCVFArbitrator(bcvf_cfg),
            EKFArbitrator(EKFConfig(dt=dt)),
            MajorityVoteArbitrator(cluster_radius=0.5),
            AnchorArbitrator(anchor_idx=0),
        ]

    cells: List[CellResult] = []
    for arb in arbitrators:
        for fam in families:
            for i in range(N):
                seed = base_seed + i
                cell = _eval_cell(arb, fam, seed, M=M, H=H, dt=dt)
                cells.append(cell)

    # Aggregate per-(arbitrator, family).
    grouped: Dict[Tuple[str, str], List[CellResult]] = defaultdict(list)
    for c in cells:
        grouped[(c.arbitrator, c.family)].append(c)
    summaries: List[ShootoutSummary] = []
    for (arb_name, fam), group in grouped.items():
        errs = np.array([c.consensus_xy_error for c in group])
        hits = np.array([c.attribution_hit_top_half for c in group])
        fas = np.array([c.false_attribution_max for c in group])
        tts = np.array([c.per_tick_us for c in group])
        summaries.append(ShootoutSummary(
            arbitrator=arb_name, family=fam, n_seeds=len(group),
            median_consensus_error=float(np.median(errs)),
            attribution_hit_rate=float(hits.mean()),
            median_false_attribution=float(np.median(fas)),
            median_per_tick_us=float(np.median(tts)),
        ))

    result = ShootoutResult(cells=cells, summaries=summaries)

    if write_artifacts:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        _write_csv(out_path / "shootout.csv", cells)
        _write_json(out_path / "shootout.json", result)
        _write_report_md(out_path / "shootout_report.md", result)

    return result


# --------------------------------------------------------------------------- #
# Artifact writers
# --------------------------------------------------------------------------- #


def _write_csv(path: Path, cells: List[CellResult]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "arbitrator", "family", "seed", "truth_label",
            "consensus_xy_error", "attribution_hit_top_half",
            "false_attribution_max", "per_tick_us",
        ])
        for c in cells:
            w.writerow([
                c.arbitrator, c.family, c.seed,
                c.truth_label if c.truth_label is not None else "",
                f"{c.consensus_xy_error:.6f}",
                int(c.attribution_hit_top_half),
                f"{c.false_attribution_max:.6f}",
                f"{c.per_tick_us:.2f}",
            ])


def _write_json(path: Path, result: ShootoutResult) -> None:
    payload = {
        "summaries": [dataclasses.asdict(s) for s in result.summaries],
        "n_cells": len(result.cells),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _write_report_md(path: Path, result: ShootoutResult) -> None:
    """Investor-readable markdown table grouped by family.

    For each family, one row per arbitrator with consensus error,
    attribution hit rate (failure families) or false-attribution
    median (benign families), and per-tick wall time.
    """
    lines: List[str] = []
    lines.append("# Apples-to-apples Baseline Shootout")
    lines.append("")
    if result.cells:
        n_seeds = result.summaries[0].n_seeds if result.summaries else 0
        lines.append(
            f"N = {n_seeds} seeds per cell  ·  4 arbitrators "
            "(BCVF, EKF, MajorityVote, Anchor) × 7 characterization families."
        )
    lines.append("")
    lines.append("## Headline — failure families (attribution hit rate)")
    lines.append("")
    failure_summaries = [s for s in result.summaries if s.family in FAILURE_FAMILIES]
    families = sorted({s.family for s in failure_summaries})
    arbs = sorted({s.arbitrator for s in failure_summaries})
    lines.append("| family | " + " | ".join(arbs) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(arbs)) + "|")
    by_key = {(s.arbitrator, s.family): s for s in failure_summaries}
    for fam in families:
        cells: List[str] = [f"`{fam}`"]
        for arb in arbs:
            s = by_key.get((arb, fam))
            cells.append(f"{s.attribution_hit_rate:.2f}" if s else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Consensus XY error (median, m) — all families")
    lines.append("")
    summaries = result.summaries
    families_all = sorted({s.family for s in summaries})
    lines.append("| family | " + " | ".join(arbs) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(arbs)) + "|")
    by_key2 = {(s.arbitrator, s.family): s for s in summaries}
    for fam in families_all:
        cells = [f"`{fam}`"]
        for arb in arbs:
            s = by_key2.get((arb, fam))
            cells.append(f"{s.median_consensus_error:.3f}" if s else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## False attribution (median max-attribution on benign families)")
    lines.append("")
    benign_summaries = [s for s in summaries if s.family in NOMINAL_FAMILIES]
    families_b = sorted({s.family for s in benign_summaries})
    lines.append("| family | " + " | ".join(arbs) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(arbs)) + "|")
    by_key3 = {(s.arbitrator, s.family): s for s in benign_summaries}
    for fam in families_b:
        cells = [f"`{fam}`"]
        for arb in arbs:
            s = by_key3.get((arb, fam))
            cells.append(f"{s.median_false_attribution:.3f}" if s else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Per-tick wall time (median µs)")
    lines.append("")
    lines.append("| family | " + " | ".join(arbs) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(arbs)) + "|")
    for fam in families_all:
        cells = [f"`{fam}`"]
        for arb in arbs:
            s = by_key2.get((arb, fam))
            cells.append(f"{s.median_per_tick_us:.1f}" if s else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Reading the table")
    lines.append("")
    lines.append(
        "* **Failure families** (`accelerating`, `outlier`, "
        "`sensor_dropout`): hit rate = fraction of seeds where the "
        "arbitrator ranked the *injected* outlier predictor in the "
        "top half of attribution scores. 1.0 = perfect attribution; "
        "0.0 = the arbitrator never identified the outlier."
    )
    lines.append(
        "* **Benign families** (`baseline`, `constant_bias`, "
        "`linear_drift`, `noise_floor`): false attribution = median "
        "max-across-predictors attribution score. Smaller is better; "
        "the Lemma-1 invariance says BCVF should produce ~0 here."
    )
    lines.append(
        "* **Anchor**: never assigns attribution (always returns "
        "zero). Always-trust-anchor's hit rate is therefore 0.0 by "
        "construction — it's the floor the other three must beat."
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
