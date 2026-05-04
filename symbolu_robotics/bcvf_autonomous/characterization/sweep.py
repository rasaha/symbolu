"""Characterization sweep — per-family thresholds + parameter-grid
runner + winner-tuple selection.

Each cell of the sweep evaluates one (family, magnitude, parameter
tuple, seed) combination. The cell records the kernel's total cost,
per-predictor cost, gate activations, alignment metrics, and a
boolean ``cell_pass`` that requires both the threshold check (per
family table in §4 of the design doc) and the alignment check
(where applicable) to hold.

Three grids:

* ``run_primary_grid`` — every family × magnitude grid × seeds.
* ``run_sensitivity_grid`` — canonical magnitude × (T, β, δ) sweep.
* ``run_ablation_grid`` — ``linear_drift`` × ``CostOrder`` to
  confirm only ``SECOND`` rejects linear drift (a regression check
  on the BCVF kernel's order-of-derivative claim).

``pick_winner_tuple`` selects (T, β, δ) from the sensitivity grid
that satisfies every cell's pass criterion, prefers the cell closest
to the V1 defaults, and tiebreaks by lowest T → highest β → lowest
δ to match the LLM tiebreaker convention.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from ..core import BCVFConfig, CostOrder, compute_bcvf_cost
from ..observables.kernel_per_step import compute_bcvf_per_step
from .alignment import (
    AlignmentMetrics,
    aggregate_alignment,
    compute_alignment_metrics,
)
from .stats import (
    CERTIFICATION_FLOOR,
    WILSON_Z_95,
    wilson_ci,
)
from .traces import (
    ADVERSARIAL_FAMILIES,
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    TraceBundle,
    generate_trace,
)


# --------------------------------------------------------------------------- #
# Sweep configuration
# --------------------------------------------------------------------------- #

FAMILY_MAGNITUDES: Dict[str, Tuple[str, Tuple[float, ...]]] = {
    "baseline": ("_unused", (0.0,)),
    "constant_bias": ("bias", (0.1, 0.5, 1.0, 2.0)),
    "linear_drift": ("drift_rate", (0.01, 0.05, 0.1, 0.2)),
    "accelerating": ("accel_mag", (0.1, 0.3, 0.5, 1.0)),
    "noise_floor": ("sigma_noise", (0.005, 0.01, 0.02, 0.05)),
    "outlier": ("accel_mag", (1.0,)),  # canonical magnitude
    "sensor_dropout": ("k_dropout", (5, 15, 25, 35)),
    # Cybersecurity-grade adversarial input — the magnitudes span the
    # full stealth→transition→loud arc relative to the V1 default gate
    # threshold T=0.05. Stealth (0.005, 0.01) keeps the gate closed
    # most ticks → BCVF is invisible-to-the-attack → consensus is
    # biased ≈ ``bias × weight_attacker`` → planner-level harm is real.
    # Loud (0.5) opens the gate every tick → kernel detects via the
    # gate-noise interaction. The transition magnitude (0.05) sits
    # exactly at the gate threshold and surfaces the kernel's
    # detection-onset behaviour. See DESIGN.md §3.5 + §4.8 for the
    # acceptance criterion + the UN ECE R155 cybersecurity scope.
    "adversarial_consistent_bias": ("bias", (0.005, 0.01, 0.05, 0.5)),
}

# Primary-grid seeds. 60 deterministic seeds give 22 configs × 60
# seeds = 1320 cells per ``run_primary_grid`` invocation. The audit
# flagged the prior 3-seed-per-cell coverage as too narrow for a
# certification-grade statistical bound — at the threshold-edge
# magnitudes (e.g. ``accelerating`` at ``accel_mag = 0.3``) a single
# kernel regression can flip a 3-of-3 pass into a 0-of-3 fail
# without the suite catching it. 60 seeds + a per-config Wilson 95%
# CI lower-bound floor (see ``stats.CERTIFICATION_FLOOR``) ties the
# regression suite to a stated statistical bound.
PRIMARY_SEEDS: Tuple[int, ...] = tuple(range(42, 102))

# Three-seed legacy tuple kept for callers that explicitly want the
# prior smoke-grade smoke run; no internal call site uses it.
LEGACY_PRIMARY_SEEDS: Tuple[int, ...] = (42, 43, 44)

V1_DEFAULTS = {"T": 0.2, "beta": 100.0, "delta": 0.5}
SENSITIVITY_T = (0.1, 0.2, 0.5)
SENSITIVITY_BETA = (50.0, 100.0, 200.0)
SENSITIVITY_DELTA = (0.25, 0.5, 1.0)
# Sensitivity / ablation grids stay at 3 seeds — those grids exist
# to validate the (T, β, δ) cube, not to certify per-config pass-rate
# bounds. Tying them to the 60-seed primary cadence would push the
# default test suite past its time budget without buying additional
# certification signal.
SENSITIVITY_SEEDS: Tuple[int, ...] = (42, 43, 44)
ABLATION_SEEDS: Tuple[int, ...] = (42, 43, 44)


# --------------------------------------------------------------------------- #
# Cell record
# --------------------------------------------------------------------------- #


@dataclass
class CellResult:
    """One sweep cell — kernel output + threshold / alignment verdicts."""

    grid: str
    family: str
    family_params: Dict[str, Any]
    T: float
    beta: float
    delta: float
    seed: int
    cost_order: str
    M: int
    H: int
    total_cost: float
    max_acceleration_norm: float
    gate_activations: int
    per_predictor_costs: Tuple[float, ...]
    per_pair_costs: Dict[str, float]
    truth_label: Optional[int]
    hit: Optional[int]
    margin: Optional[float]
    rank: Optional[int]
    threshold_pass: bool
    alignment_pass: Optional[bool]
    cell_pass: bool
    failure_reasons: Tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Per-family threshold tables
# --------------------------------------------------------------------------- #


def _evaluate_thresholds(
    family: str,
    family_params: Dict[str, Any],
    total_cost: float,
    max_accel: float,
    gate_activations: int,
    per_predictor_costs: Tuple[float, ...],
    truth_label: Optional[int],
    alignment: Optional[AlignmentMetrics],
    per_pair_costs: Dict[Tuple[int, int], float],
) -> Tuple[bool, Optional[bool], Tuple[str, ...]]:
    """Evaluate the per-family acceptance table (DESIGN.md §4).

    Returns ``(threshold_pass, alignment_pass, reasons)``. The
    ``reasons`` tuple lists every gate that failed — a SOTIF
    auditor can read it directly.
    """
    reasons: List[str] = []

    def need(condition: bool, label: str) -> None:
        if not condition:
            reasons.append(label)

    if family == "baseline":
        need(total_cost < 1e-6, "baseline.total_cost<1e-6")
        need(max_accel < 1e-6, "baseline.max_accel<1e-6")
        need(gate_activations == 0, "baseline.gate_activations==0")
        need(
            all(c < 1e-6 for c in per_predictor_costs),
            "baseline.per_predictor<1e-6",
        )

    elif family == "constant_bias":
        need(total_cost <= 1e-9, "const_bias.total_cost<=1e-9(fp64)")
        need(max_accel <= 1e-9, "const_bias.max_accel<=1e-9(fp64)")
        need(
            all(c <= 1e-9 for c in per_predictor_costs),
            "const_bias.per_predictor<=1e-9(fp64)",
        )

    elif family == "linear_drift":
        need(total_cost <= 1e-9, "lin_drift.total_cost<=1e-9(fp64)")
        need(max_accel <= 1e-9, "lin_drift.max_accel<=1e-9(fp64)")
        need(
            all(c <= 1e-9 for c in per_predictor_costs),
            "lin_drift.per_predictor<=1e-9(fp64)",
        )

    elif family == "accelerating":
        accel = float(family_params.get("accel_mag", 0.0))
        if accel >= 0.3:
            need(total_cost > 1e-3, "accel.total_cost>1e-3_gate_open")
            need(gate_activations > 0, "accel.gate_activations>0")
        need(math.isfinite(total_cost), "accel.total_cost_finite")
        need(total_cost < 1e8, "accel.total_cost<1e8(huber_bound)")

    elif family == "noise_floor":
        sigma = float(family_params.get("sigma_noise", 0.0))
        if sigma <= 0.01:
            need(total_cost < 1e-2, "noise.total_cost<1e-2_at_sigma<=0.01")
        if sigma <= 0.005:
            # Symmetry: every predictor should attract a similar share
            # of cost. std/mean < 0.5 is a generous bound that catches
            # asymmetry without false-positiving on near-zero costs.
            arr = np.asarray(per_predictor_costs, dtype=np.float64)
            m = float(arr.mean())
            if m > 1e-9:
                spread = float(arr.std() / m)
                need(spread < 0.5, f"noise.symmetry_std/mean<0.5(got_{spread:.2f})")

    elif family == "outlier":
        M = len(per_predictor_costs)
        if truth_label is not None and M >= 2:
            tr = per_predictor_costs[truth_label]
            others = [
                per_predictor_costs[i] for i in range(M) if i != truth_label
            ]
            others_max = max(others)
            if others_max > 0:
                ratio = tr / others_max
                need(
                    ratio >= 1.5,
                    f"outlier.ratio_truth/other>=1.5(got_{ratio:.2f})",
                )
            need(gate_activations > 0, "outlier.gate_activations>0")
            need(total_cost > 1e-3, "outlier.total_cost>1e-3")

    elif family == "sensor_dropout":
        k = int(family_params.get("k_dropout", -1))
        need(math.isfinite(total_cost), "dropout.total_cost_finite")
        # The dropped predictor stops moving at k_dropout; the others
        # continue. Disagreement velocity grows linearly thereafter so
        # the second derivative includes an impulse-shaped acceleration
        # at the boundary that should fire the gate.
        if 0 <= k < int(family_params.get("H", 50)) - 5:
            need(gate_activations > 0, "dropout.gate_activations>0")
            need(total_cost > 1e-3, "dropout.total_cost>1e-3")

    elif family == "adversarial_consistent_bias":
        # Cybersecurity-grade attack — see DESIGN.md §3.5 / §4.8.
        # Per-cell pass criterion is deliberately permissive: the
        # family's purpose is to expose the kernel's *behaviour* across
        # the stealth → transition → loud bias regime, not to gate the
        # kernel's correctness. The reviewer-facing evidence is the
        # per-config Wilson stats (cost percentiles + gate-activation
        # rate per magnitude) rendered into the auditor markdown by
        # ``GridSummary.to_markdown_report``; per-cell pass simply
        # asserts the kernel is bounded + dimensionally well-behaved.
        need(math.isfinite(total_cost), "adversarial.total_cost_finite")
        need(total_cost < 1e8, "adversarial.total_cost<1e8(huber_bound)")
        bias = float(family_params.get("bias", 0.0))
        # Stealth regime — bias well below the V1 default gate threshold
        # T = 0.05 — must keep BCVF below an order of magnitude of the
        # noise-floor cost. Pinned at total_cost < 5.0 (~10x the
        # noise-only floor at sigma=0.01) so a kernel that suddenly
        # over-reacts on stealth bias trips the gate.
        if bias <= 0.01:
            need(total_cost < 5.0, "adversarial.stealth_total_cost<5.0")

    threshold_pass = len(reasons) == 0

    # Alignment check is family-aware: outlier requires a strict hit;
    # accelerating accepts hit or rank-2-with-positive-margin; sensor
    # dropout only requires "not last" because outer-family signal can
    # legitimately dominate (a heavily accelerating predictor wrapped
    # by dropout on a different one is a real test of the kernel
    # picking the bigger problem first, not a regression).
    alignment_pass: Optional[bool] = None
    if alignment is not None:
        if family == "outlier":
            apass = alignment.hit == 1
            crit = "rank==1"
        elif family == "sensor_dropout":
            apass = alignment.rank < len(per_predictor_costs)
            crit = f"rank<{len(per_predictor_costs)}"
        else:
            apass = alignment.hit == 1 or (
                alignment.rank <= 2 and alignment.margin >= 1.0
            )
            crit = "rank==1_or_(rank<=2_and_margin>=1)"
        if not apass:
            reasons.append(
                f"alignment.{crit}_violated"
                f"(rank={alignment.rank}_margin={alignment.margin:.2f})"
            )
        alignment_pass = bool(apass)

    return threshold_pass, alignment_pass, tuple(reasons)


# --------------------------------------------------------------------------- #
# Cell evaluation
# --------------------------------------------------------------------------- #


def _eval_cell(
    grid: str,
    family: str,
    family_params: Dict[str, Any],
    T: float,
    beta: float,
    delta: float,
    seed: int,
    cost_order: CostOrder = CostOrder.SECOND,
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
) -> CellResult:
    bundle = generate_trace(
        family=family,
        M=M,
        H=H,
        dt=dt,
        seed=seed,
        **family_params,
    )
    cfg = BCVFConfig(
        lambda_c=1.0,
        gate_threshold=T,
        gate_beta=beta,
        huber_delta=delta,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=False,
        anchor_index=0,
        dt=dt,
        cost_order=cost_order,
    )
    trajs = bundle.trajectories
    aggregate = compute_bcvf_cost([trajs[m] for m in range(trajs.shape[0])], cfg)
    breakdown = compute_bcvf_per_step(trajs, cfg)
    per_predictor = breakdown.per_step_per_predictor.sum(axis=1)
    per_pred_tuple = tuple(float(c) for c in per_predictor)
    alignment = compute_alignment_metrics(per_predictor, bundle.truth_label)

    # Build a (i, j) → cost dict from the aggregate kernel so the
    # CellResult parallels the LLM CellResult shape (sensible for
    # CSV serialization).
    per_pair_str = {
        f"{i},{j}": float(v) for (i, j), v in aggregate.per_pair_costs.items()
    }

    threshold_pass, alignment_pass, reasons = _evaluate_thresholds(
        family=family,
        family_params={**family_params, "H": H},
        total_cost=aggregate.total_cost,
        max_accel=aggregate.max_acceleration_norm,
        gate_activations=aggregate.gate_activation_count,
        per_predictor_costs=per_pred_tuple,
        truth_label=bundle.truth_label,
        alignment=alignment,
        per_pair_costs=aggregate.per_pair_costs,
    )

    cell_pass = threshold_pass and (
        alignment_pass is None or alignment_pass
    )

    return CellResult(
        grid=grid,
        family=family,
        family_params=dict(family_params),
        T=T,
        beta=beta,
        delta=delta,
        seed=seed,
        cost_order=cost_order.name,
        M=M,
        H=H,
        total_cost=float(aggregate.total_cost),
        max_acceleration_norm=float(aggregate.max_acceleration_norm),
        gate_activations=int(aggregate.gate_activation_count),
        per_predictor_costs=per_pred_tuple,
        per_pair_costs=per_pair_str,
        truth_label=bundle.truth_label,
        hit=None if alignment is None else alignment.hit,
        margin=None if alignment is None else alignment.margin,
        rank=None if alignment is None else alignment.rank,
        threshold_pass=threshold_pass,
        alignment_pass=alignment_pass,
        cell_pass=cell_pass,
        failure_reasons=reasons,
    )


# --------------------------------------------------------------------------- #
# Grid runners
# --------------------------------------------------------------------------- #


def _canonical_magnitude(family: str) -> Dict[str, Any]:
    param_name, mags = FAMILY_MAGNITUDES[family]
    if family == "baseline":
        return {}
    if family == "sensor_dropout":
        return {
            "outer_family": "outlier",
            "accel_mag": 1.0,
            "k_dropout": int(mags[len(mags) // 2]),
            "dropped_predictor": 2,
        }
    middle = mags[len(mags) // 2]
    return {param_name: float(middle)}


def run_primary_grid(
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
    seeds: Tuple[int, ...] = PRIMARY_SEEDS,
) -> List[CellResult]:
    """Every family × magnitude × seed at the V1 default (T, β, δ)."""
    cells: List[CellResult] = []
    for family, (param_name, mags) in FAMILY_MAGNITUDES.items():
        for mag, seed in itertools.product(mags, seeds):
            params: Dict[str, Any] = {}
            if family == "baseline":
                pass
            elif family == "sensor_dropout":
                params = {
                    "outer_family": "outlier",
                    "accel_mag": 1.0,
                    "k_dropout": int(mag),
                    "dropped_predictor": 2,
                }
            else:
                params = {param_name: float(mag)}
            cells.append(
                _eval_cell(
                    grid="primary",
                    family=family,
                    family_params=params,
                    T=V1_DEFAULTS["T"],
                    beta=V1_DEFAULTS["beta"],
                    delta=V1_DEFAULTS["delta"],
                    seed=seed,
                    M=M,
                    H=H,
                    dt=dt,
                )
            )
    return cells


def run_sensitivity_grid(
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
    seeds: Tuple[int, ...] = SENSITIVITY_SEEDS,
) -> List[CellResult]:
    """Canonical magnitude × (T, β, δ) sweep."""
    cells: List[CellResult] = []
    for family in FAMILY_MAGNITUDES:
        params = _canonical_magnitude(family)
        for T, beta, delta, seed in itertools.product(
            SENSITIVITY_T, SENSITIVITY_BETA, SENSITIVITY_DELTA, seeds
        ):
            cells.append(
                _eval_cell(
                    grid="sensitivity",
                    family=family,
                    family_params=params,
                    T=T,
                    beta=beta,
                    delta=delta,
                    seed=seed,
                    M=M,
                    H=H,
                    dt=dt,
                )
            )
    return cells


def run_ablation_grid(
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
    seeds: Tuple[int, ...] = ABLATION_SEEDS,
) -> List[CellResult]:
    """``linear_drift`` × cost-order ablation.

    Confirms that ``ZEROTH`` and ``FIRST`` orders fire on linear
    drift while ``SECOND`` rejects it — the kernel's order-of-
    derivative claim distilled into a regression test.
    """
    cells: List[CellResult] = []
    _, mags = FAMILY_MAGNITUDES["linear_drift"]
    orders = (CostOrder.ZEROTH, CostOrder.FIRST, CostOrder.SECOND)
    for drift, order, seed in itertools.product(mags, orders, seeds):
        cells.append(
            _eval_cell(
                grid="ablation",
                family="linear_drift",
                family_params={"drift_rate": float(drift)},
                T=V1_DEFAULTS["T"],
                beta=V1_DEFAULTS["beta"],
                delta=V1_DEFAULTS["delta"],
                seed=seed,
                cost_order=order,
                M=M,
                H=H,
                dt=dt,
            )
        )
    return cells


# --------------------------------------------------------------------------- #
# Winner selection + summary
# --------------------------------------------------------------------------- #


def pick_winner_tuple(
    sensitivity_cells: List[CellResult],
) -> Tuple[Optional[Dict[str, float]], List[Dict[str, float]]]:
    """Pick (T, β, δ) where every cell passes; tiebreak toward V1 defaults."""
    grouped: Dict[Tuple[float, float, float], List[CellResult]] = defaultdict(
        list
    )
    for c in sensitivity_cells:
        grouped[(c.T, c.beta, c.delta)].append(c)

    candidates: List[Dict[str, float]] = []
    for (T, beta, delta), cells in grouped.items():
        if all(c.cell_pass for c in cells):
            candidates.append({"T": T, "beta": beta, "delta": delta})
    if not candidates:
        return None, []

    def distance(tpl: Dict[str, float]) -> Tuple[float, float, float, float]:
        d = math.sqrt(
            ((tpl["T"] - V1_DEFAULTS["T"]) / V1_DEFAULTS["T"]) ** 2
            + ((tpl["beta"] - V1_DEFAULTS["beta"]) / V1_DEFAULTS["beta"]) ** 2
            + ((tpl["delta"] - V1_DEFAULTS["delta"]) / V1_DEFAULTS["delta"]) ** 2
        )
        return (d, tpl["T"], -tpl["beta"], tpl["delta"])

    candidates_sorted = sorted(candidates, key=distance)
    return candidates_sorted[0], candidates_sorted


@dataclass
class PerConfigPassStat:
    """Pass-rate tally + Wilson 95% CI for one (family, magnitude) cell.

    A "config" here is the natural grouping the audit asked for: every
    combination of family and family-parameter magnitude that appears
    in the primary grid. ``magnitude_label`` is a stable string key
    suitable for CSV / JSON output and table headers (e.g.
    ``"accelerating[accel_mag=0.3]"`` or ``"baseline"``).
    """

    family: str
    magnitude_label: str
    family_params: Dict[str, Any]
    n: int
    passed: int
    pass_rate: float
    ci_low: float
    ci_high: float
    meets_certification_floor: bool


def _magnitude_label(family: str, family_params: Dict[str, Any]) -> str:
    """Stable string key for (family, magnitude) suitable for grouping.

    For families with a scalar magnitude parameter (e.g. ``constant_bias``
    with ``bias=0.5``) we emit ``"family[param=value]"`` so two cells
    with different magnitudes always carry distinct labels — a
    pre-fix special case for ``outlier`` collapsed every magnitude to
    just ``"outlier"``, which silently merged distinct configs into
    one Wilson-CI group when the outlier magnitude tuple was extended.
    ``baseline`` is keyed by family name (no magnitude parameter is
    defined for it). ``sensor_dropout`` is keyed by ``k_dropout``
    since the outer family + dropped-predictor are fixed across the
    primary grid.
    """
    if family == "baseline":
        return "baseline"
    if family == "sensor_dropout":
        k = family_params.get("k_dropout", "?")
        return f"sensor_dropout[k_dropout={k}]"
    # Every other family carries a single scalar magnitude under
    # ``FAMILY_MAGNITUDES``: constant_bias, linear_drift, accelerating,
    # noise_floor, and outlier (all use a named param + a magnitude
    # tuple). Distinct magnitudes therefore always yield distinct
    # labels.
    name, _ = FAMILY_MAGNITUDES.get(family, (None, ()))
    if name and name in family_params:
        return f"{family}[{name}={family_params[name]}]"
    # Fallback: serialise the params dict deterministically.
    items = ",".join(f"{k}={v}" for k, v in sorted(family_params.items()))
    return f"{family}[{items}]" if items else family


def per_config_pass_stats(
    cells: List[CellResult],
    z: float = WILSON_Z_95,
    certification_floor: float = CERTIFICATION_FLOOR,
) -> List[PerConfigPassStat]:
    """Aggregate sweep cells into per-(family, magnitude) pass tallies
    with Wilson confidence intervals.

    The Wilson 95% CI is computed at each config independently —
    ``ci_low`` is the per-config lower bound a SOTIF auditor would
    quote ("with 95% confidence the true pass rate at this magnitude
    is at least X"). ``meets_certification_floor`` is the per-config
    boolean the regression suite asserts on; ``False`` means the cell
    is the regression hot-spot.
    """
    grouped: Dict[Tuple[str, str], List[CellResult]] = defaultdict(list)
    for c in cells:
        key = (c.family, _magnitude_label(c.family, c.family_params))
        grouped[key].append(c)

    out: List[PerConfigPassStat] = []
    for (family, label), group in grouped.items():
        n = len(group)
        passed = sum(1 for c in group if c.cell_pass)
        rate = passed / n if n else 0.0
        ci_low, ci_high = wilson_ci(passed, n, z=z)
        out.append(PerConfigPassStat(
            family=family,
            magnitude_label=label,
            family_params=dict(group[0].family_params),
            n=n,
            passed=passed,
            pass_rate=rate,
            ci_low=ci_low,
            ci_high=ci_high,
            meets_certification_floor=ci_low >= certification_floor,
        ))
    # Stable ordering: family group, then magnitude label. Keeps CSV /
    # markdown rendering deterministic across runs.
    out.sort(key=lambda s: (s.family, s.magnitude_label))
    return out


def family_pass_rate(cells: List[CellResult]) -> Dict[str, Dict[str, Any]]:
    """Per-family pass tally with alignment summary."""
    per_family: Dict[str, List[CellResult]] = defaultdict(list)
    for c in cells:
        per_family[c.family].append(c)

    out: Dict[str, Dict[str, Any]] = {}
    for fam, fcells in per_family.items():
        passed = sum(1 for c in fcells if c.cell_pass)
        metrics = [
            None
            if c.hit is None
            else AlignmentMetrics(
                hit=c.hit, margin=c.margin or 0.0, rank=c.rank or 0
            )
            for c in fcells
        ]
        agg = aggregate_alignment(metrics)
        out[fam] = {
            "total": len(fcells),
            "passed": passed,
            "pass_rate": passed / len(fcells) if fcells else 0.0,
            "alignment": asdict(agg) if agg is not None else None,
        }
    return out


def split_nominal_failure(
    cells: List[CellResult],
) -> Tuple[List[CellResult], List[CellResult]]:
    """Split cells by family polarity — useful for SOTIF FP/FN tallies.

    Returns ``(nominal, failure)``. Adversarial-family cells are
    intentionally not in either bucket; consume them via
    :func:`split_polarity` if the cybersecurity-tier rate matters.
    """
    nominal = [c for c in cells if c.family in NOMINAL_FAMILIES]
    failure = [c for c in cells if c.family in FAILURE_FAMILIES]
    return nominal, failure


def split_polarity(
    cells: List[CellResult],
) -> Tuple[List[CellResult], List[CellResult], List[CellResult]]:
    """Split cells across all three polarity buckets — nominal /
    failure / adversarial. Used by :func:`summarize_grid` to compute
    the cybersecurity-tier pass rate alongside the SOTIF FP/FN rates.
    """
    nominal = [c for c in cells if c.family in NOMINAL_FAMILIES]
    failure = [c for c in cells if c.family in FAILURE_FAMILIES]
    adversarial = [c for c in cells if c.family in ADVERSARIAL_FAMILIES]
    return nominal, failure, adversarial


def summarize_grid(
    cells: List[CellResult],
    z: float = WILSON_Z_95,
    certification_floor: float = CERTIFICATION_FLOOR,
) -> "GridSummary":
    """Top-level grid summary: per-family pass rates + FP / FN counts.

    Also exposes per-(family, magnitude) Wilson confidence intervals so
    a SOTIF audit can quote a per-config statistical bound rather than
    a point estimate. The returned :class:`GridSummary` carries:

    * ``per_config`` — list of :class:`PerConfigPassStat` (one per
      config) with ``family``, ``magnitude_label``, ``n``, ``passed``,
      ``pass_rate``, ``ci_low``, ``ci_high``, ``meets_certification_floor``.
    * ``min_ci_lower_bound`` — the worst per-config CI lower bound
      across the grid (the "weakest cell" gauge).
    * ``cells_below_certification_floor`` — labels of any configs whose
      CI lower bound undershoots ``certification_floor``.
    * ``certification_floor`` and ``wilson_z`` — the bound and z-score
      in effect for this summary.

    Auditor-facing artifacts: :meth:`GridSummary.to_csv` and
    :meth:`GridSummary.to_markdown_report` emit frozen deliverables
    suitable for a SOTIF / ISO 26262 documentation pack.
    ``to_dict()`` produces a JSON-friendly view with the same shape
    callers used to read off the legacy dict return.
    """
    nominal, failure, adversarial = split_polarity(cells)
    config_stats = per_config_pass_stats(
        cells, z=z, certification_floor=certification_floor,
    )
    min_ci_lower = (
        min(s.ci_low for s in config_stats) if config_stats else 0.0
    )
    below_floor = [
        s.magnitude_label for s in config_stats
        if not s.meets_certification_floor
    ]
    fpr = (
        sum(1 for c in nominal if not c.cell_pass) / len(nominal)
        if nominal else 0.0
    )
    fnr = (
        sum(1 for c in failure if not c.cell_pass) / len(failure)
        if failure else 0.0
    )
    adv_pass_rate = (
        sum(1 for c in adversarial if c.cell_pass) / len(adversarial)
        if adversarial else 1.0
    )
    return GridSummary(
        n_cells=len(cells),
        per_family=family_pass_rate(cells),
        false_positive_rate=fpr,
        false_negative_rate=fnr,
        adversarial_pass_rate=adv_pass_rate,
        per_config=list(config_stats),
        min_ci_lower_bound=min_ci_lower,
        cells_below_certification_floor=below_floor,
        certification_floor=certification_floor,
        wilson_z=z,
    )


@dataclass
class GridSummary:
    """Top-level grid summary — per-family pass rates, per-config
    Wilson CIs, and the certification-floor verdict.

    Auditor-facing writers:

    * :meth:`to_csv` — one row per (family, magnitude) config.
    * :meth:`to_markdown_report` — regulator-friendly layout with
      headline gate, per-config table, per-family roll-up,
      methodology block, and a failed-config section.
    * :meth:`to_dict` — JSON-friendly view; matches the shape of
      the legacy ``summarize_grid`` dict return so existing
      consumers can read ``GridSummary.to_dict()["per_config"]``
      unchanged.
    """

    n_cells: int
    per_family: Dict[str, Dict[str, Any]]
    false_positive_rate: float
    false_negative_rate: float
    adversarial_pass_rate: float
    per_config: List[PerConfigPassStat]
    min_ci_lower_bound: float
    cells_below_certification_floor: List[str]
    certification_floor: float
    wilson_z: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cells": int(self.n_cells),
            "per_family": dict(self.per_family),
            "false_positive_rate": float(self.false_positive_rate),
            "false_negative_rate": float(self.false_negative_rate),
            "adversarial_pass_rate": float(self.adversarial_pass_rate),
            "per_config": [asdict(s) for s in self.per_config],
            "min_ci_lower_bound": float(self.min_ci_lower_bound),
            "cells_below_certification_floor": list(
                self.cells_below_certification_floor
            ),
            "certification_floor": float(self.certification_floor),
            "wilson_z": float(self.wilson_z),
        }

    def to_csv(self, path: "Union[str, Path]") -> "Path":
        """Write the per-config CSV to ``path``. Returns the Path."""
        from .reports import write_grid_csv
        return write_grid_csv(self, path)

    def to_markdown_report(
        self,
        path: "Union[str, Path]",
        *,
        title: str = "BCVF Characterization Grid — Certification Report",
        grid_label: str = "primary",
        generated_at: "Optional[datetime]" = None,
    ) -> "Path":
        """Write the regulator-friendly markdown report to ``path``."""
        from .reports import write_grid_markdown
        return write_grid_markdown(
            self,
            path,
            title=title,
            grid_label=grid_label,
            generated_at=generated_at,
        )
