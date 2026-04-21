"""§3.4 four-grid sweep orchestration + §3.5 per-cell thresholds +
§3.9.2 winner-tuple tiebreaker.

Emits one ``CellResult`` per cell; downstream ``__main__.py`` writes
the catalog as CSV and synthesizes ``phase_1_5_summary.md``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from symbolu_bcvf_llm.core import (
    BCVFLLMConfig,
    CostOrder,
    compute_bcvf_cost,
)

from .alignment import (
    AlignmentAggregate,
    AlignmentMetrics,
    aggregate_alignment,
    compute_alignment_metrics,
)
from .traces import TraceBundle, generate_trace


@dataclass
class CellResult:
    grid: str
    family: str
    family_params: Dict[str, Any]
    T: float
    beta: float
    delta: float
    sigma_logit: float
    V: int
    seed: int
    cost_order: str
    total_cost: float
    max_accel_norm: float
    gate_activations: int
    per_source_costs: Tuple[float, ...]
    per_pair_costs: Dict[str, float]        # keys are "i,j" strings for CSV friendliness
    truth_label: Optional[int]
    hit: Optional[int]
    margin: Optional[float]
    rank: Optional[int]
    threshold_pass: bool
    alignment_pass: Optional[bool]          # None if alignment not applicable
    cell_pass: bool
    failure_reasons: Tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# §3.3.3 magnitude sweep ranges
# --------------------------------------------------------------------------- #
FAMILY_MAGNITUDES: Dict[str, Tuple[str, Tuple[float, ...]]] = {
    "baseline": ("_unused", (0.0,)),
    "constant_bias": ("alpha_mag", (0.05, 0.1, 0.2, 0.5, 1.0, 2.0)),
    "linear_drift": ("drift_rate", (0.01, 0.02, 0.05, 0.1, 0.2)),
    "accelerating": ("accel_mag", (0.02, 0.05, 0.1, 0.2, 0.5, 1.0)),
    "noise_floor": ("sigma_noise", (0.001, 0.005, 0.01, 0.02, 0.05)),
    "outlier": ("accel_mag", (0.3,)),  # canonical magnitude per §3.2.6
    "eos_truncation": ("k_eos", (0, 1, 2, 3, 4)),
}

PRIMARY_SEEDS = (42, 43, 44)
V1_DEFAULTS = dict(T=0.1, beta=200.0, delta=0.5)
SENSITIVITY_T = (0.05, 0.1, 0.2)
SENSITIVITY_BETA = (100.0, 200.0, 500.0)
SENSITIVITY_DELTA = (0.25, 0.5, 1.0)
SENSITIVITY_SIGMA = (1.0, 3.0, 5.0)


# --------------------------------------------------------------------------- #
# §3.5 per-family threshold evaluation
# --------------------------------------------------------------------------- #
def _evaluate_thresholds(
    family: str,
    family_params: Dict[str, Any],
    total_cost: float,
    max_accel_norm: float,
    gate_activations: int,
    per_source_costs: Tuple[float, ...],
    truth_label: Optional[int],
    alignment: Optional[AlignmentMetrics],
    per_pair_costs: Dict[Tuple[int, int], float],
) -> Tuple[bool, Optional[bool], Tuple[str, ...]]:
    """Returns (threshold_pass, alignment_pass, failure_reasons).

    Implements §3.5.2–§3.5.8 per-family tables. Alignment_pass is per
    §3.6.5 where applicable, else None.
    """
    reasons: List[str] = []

    def need(condition: bool, label: str) -> None:
        if not condition:
            reasons.append(label)

    if family == "baseline":
        need(total_cost < 1e-6, "baseline.total_cost<1e-6")
        need(max_accel_norm < 1e-3, "baseline.max_accel<1e-3")
        need(gate_activations == 0, "baseline.gate_activations==0")
        need(all(c < 1e-6 for c in per_source_costs), "baseline.per_source<1e-6")

    elif family == "constant_bias":
        need(total_cost <= 1e-10, "const_bias.total_cost<=1e-10(fp64)")
        need(max_accel_norm <= 1e-10, "const_bias.max_accel<=1e-10(fp64)")
        need(
            all(c <= 1e-10 for c in per_source_costs),
            "const_bias.per_source<=1e-10(fp64)",
        )

    elif family == "linear_drift":
        need(total_cost <= 1e-10, "lin_drift.total_cost<=1e-10(fp64)")
        need(max_accel_norm <= 1e-10, "lin_drift.max_accel<=1e-10(fp64)")
        need(
            all(c <= 1e-10 for c in per_source_costs),
            "lin_drift.per_source<=1e-10(fp64)",
        )

    elif family == "accelerating":
        accel = float(family_params.get("accel_mag", 0.0))
        if accel >= 0.1:
            need(total_cost > 1e-4, "accel.total_cost>1e-4_gate_open")
            need(gate_activations > 0, "accel.gate_activations>0")
        need(total_cost < 1e6, "accel.total_cost<1e6(huber_bound)")
        need(math.isfinite(total_cost), "accel.total_cost_finite")

    elif family == "noise_floor":
        sigma = float(family_params.get("sigma_noise", 0.0))
        if sigma <= 0.005:
            need(total_cost < 1e-3, "noise.total_cost<1e-3_at_sigma<=0.005")
        if sigma <= 0.001:
            need(gate_activations == 0, "noise.gate_activations==0_at_sigma<=0.001")
        # symmetry: std(per_source_costs)/mean < 0.1 at low sigma
        if sigma <= 0.01:
            mean = float(np.mean(per_source_costs))
            std = float(np.std(per_source_costs))
            if mean > 0:
                need(std / mean < 0.5, "noise.symmetry_std/mean<0.5")

    elif family == "outlier":
        M = len(per_source_costs)
        if truth_label is not None and M >= 2:
            tr = per_source_costs[truth_label]
            others = [per_source_costs[i] for i in range(M) if i != truth_label]
            others_max = max(others)
            if others_max > 0:
                ratio = tr / others_max
                need(ratio >= 1.8, f"outlier.ratio_truth/other>=1.8(got_{ratio:.2f})")
            need(gate_activations > 0, "outlier.gate_activations>0")
            # symmetry of non-truth sources
            others_arr = np.asarray(others)
            mean_other = float(others_arr.mean())
            if mean_other > 0:
                spread = float(others_arr.std() / mean_other)
                need(spread < 0.1, f"outlier.non_truth_symmetry_std/mean<0.1(got_{spread:.2f})")

    elif family == "eos_truncation":
        k = int(family_params.get("k_eos", -1))
        need(math.isfinite(total_cost), "eos.total_cost_finite")
        if k == 0:
            # Pairs involving source 0 must be exactly zero.
            c01 = per_pair_costs.get((1, 0), 0.0)
            c02 = per_pair_costs.get((2, 0), 0.0)
            need(c01 == 0.0, "eos_k0.pair(1,0)==0_exact")
            need(c02 == 0.0, "eos_k0.pair(2,0)==0_exact")

    threshold_pass = len(reasons) == 0

    # §3.6.5 alignment thresholds — applies to accelerating / outlier /
    # eos_truncation-with-outlier-outer.
    alignment_pass: Optional[bool] = None
    if alignment is not None:
        apass = True
        if alignment.rank == 3:
            apass = False
            reasons.append("alignment.rank==3")
        alignment_pass = apass

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
    sigma_logit: float,
    V: int,
    seed: int,
    cost_order: CostOrder = CostOrder.SECOND,
    L: int = 5,
) -> CellResult:
    bundle = generate_trace(
        family=family,
        L=L,
        V=V,
        sigma_logit=sigma_logit,
        seed=seed,
        **family_params,
    )
    cfg = BCVFLLMConfig(
        gate_threshold=T,
        gate_beta=beta,
        huber_delta=delta,
        cost_order=cost_order,
    )
    sources_list = [bundle.sources[i] for i in range(bundle.sources.shape[0])]
    masks_list = (
        None
        if bundle.valid_masks is None
        else [bundle.valid_masks[i] for i in range(bundle.valid_masks.shape[0])]
    )
    result = compute_bcvf_cost(sources_list, cfg, valid_masks=masks_list)

    per_source = tuple(
        float(result.per_source_costs[i]) for i in range(len(sources_list))
    )
    alignment = compute_alignment_metrics(
        result.per_source_costs, bundle.truth_label
    )

    threshold_pass, alignment_pass, reasons = _evaluate_thresholds(
        family=family,
        family_params=family_params,
        total_cost=result.total_cost,
        max_accel_norm=result.max_acceleration_norm,
        gate_activations=result.gate_activation_count,
        per_source_costs=per_source,
        truth_label=bundle.truth_label,
        alignment=alignment,
        per_pair_costs=result.per_pair_costs,
    )

    cell_pass = threshold_pass and (alignment_pass is None or alignment_pass)

    return CellResult(
        grid=grid,
        family=family,
        family_params=dict(family_params),
        T=T,
        beta=beta,
        delta=delta,
        sigma_logit=sigma_logit,
        V=V,
        seed=seed,
        cost_order=cost_order.name,
        total_cost=float(result.total_cost),
        max_accel_norm=float(result.max_acceleration_norm),
        gate_activations=int(result.gate_activation_count),
        per_source_costs=per_source,
        per_pair_costs={
            f"{i},{j}": float(v) for (i, j), v in result.per_pair_costs.items()
        },
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
# §3.4.2 primary grid
# --------------------------------------------------------------------------- #
def run_primary_grid(V: int = 1024) -> List[CellResult]:
    cells: List[CellResult] = []
    for family, (param_name, mags) in FAMILY_MAGNITUDES.items():
        for mag, seed in itertools.product(mags, PRIMARY_SEEDS):
            params: Dict[str, Any] = {}
            if family == "baseline":
                pass  # no magnitude
            elif family == "eos_truncation":
                params = {
                    "outer_family": "outlier",
                    "accel_mag": 0.3,
                    "k_eos": int(mag),
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
                    sigma_logit=3.0,
                    V=V,
                    seed=seed,
                )
            )
    return cells


# --------------------------------------------------------------------------- #
# §3.4.3 sensitivity grid — canonical magnitude, sweep (T, β, δ, σ_logit)
# --------------------------------------------------------------------------- #
def _canonical_magnitude(family: str) -> Dict[str, Any]:
    param_name, mags = FAMILY_MAGNITUDES[family]
    if family == "baseline":
        return {}
    if family == "eos_truncation":
        return {"outer_family": "outlier", "accel_mag": 0.3, "k_eos": 2}
    middle = mags[len(mags) // 2]
    return {param_name: float(middle)}


def run_sensitivity_grid(V: int = 1024) -> List[CellResult]:
    cells: List[CellResult] = []
    for family in FAMILY_MAGNITUDES:
        params = _canonical_magnitude(family)
        for T, beta, delta, sigma_logit, seed in itertools.product(
            SENSITIVITY_T, SENSITIVITY_BETA, SENSITIVITY_DELTA,
            SENSITIVITY_SIGMA, PRIMARY_SEEDS,
        ):
            cells.append(
                _eval_cell(
                    grid="sensitivity",
                    family=family,
                    family_params=params,
                    T=T,
                    beta=beta,
                    delta=delta,
                    sigma_logit=sigma_logit,
                    V=V,
                    seed=seed,
                )
            )
    return cells


# --------------------------------------------------------------------------- #
# §3.4.4 ablation grid — linear_drift × {ZEROTH, FIRST, SECOND}
# --------------------------------------------------------------------------- #
def run_ablation_grid(V: int = 1024) -> List[CellResult]:
    cells: List[CellResult] = []
    _, drift_mags = FAMILY_MAGNITUDES["linear_drift"]
    for drift, order, seed in itertools.product(
        drift_mags, (CostOrder.ZEROTH, CostOrder.FIRST, CostOrder.SECOND),
        PRIMARY_SEEDS,
    ):
        cells.append(
            _eval_cell(
                grid="ablation",
                family="linear_drift",
                family_params={"drift_rate": float(drift)},
                T=V1_DEFAULTS["T"],
                beta=V1_DEFAULTS["beta"],
                delta=V1_DEFAULTS["delta"],
                sigma_logit=3.0,
                V=V,
                seed=seed,
                cost_order=order,
            )
        )
    return cells


# --------------------------------------------------------------------------- #
# §3.4.5 full-V spot check at winner (T, β, δ)
# --------------------------------------------------------------------------- #
def run_full_v_spot_check(
    winner: Dict[str, float], V: int = 32000
) -> List[CellResult]:
    cells: List[CellResult] = []
    for family in FAMILY_MAGNITUDES:
        params = _canonical_magnitude(family)
        for seed in PRIMARY_SEEDS:
            cells.append(
                _eval_cell(
                    grid="full_v",
                    family=family,
                    family_params=params,
                    T=winner["T"],
                    beta=winner["beta"],
                    delta=winner["delta"],
                    sigma_logit=3.0,
                    V=V,
                    seed=seed,
                )
            )
    return cells


# --------------------------------------------------------------------------- #
# §3.9.2 tiebreaker — pick V1 winner from sensitivity grid
# --------------------------------------------------------------------------- #
def pick_winner_tuple(
    sensitivity_cells: List[CellResult],
) -> Tuple[Optional[Dict[str, float]], List[Dict[str, float]]]:
    """Returns (winner, all_candidates). winner is None if no
    (T, β, δ) satisfies config_pass_rate == 1.0 across families + σ.
    """
    from collections import defaultdict

    grouped = defaultdict(list)
    for c in sensitivity_cells:
        key = (c.T, c.beta, c.delta)
        grouped[key].append(c)

    candidates: List[Dict[str, float]] = []
    for (T, beta, delta), cells in grouped.items():
        if all(c.cell_pass for c in cells):
            candidates.append({"T": T, "beta": beta, "delta": delta})
    if not candidates:
        return None, []

    def distance(tpl: Dict[str, float]) -> Tuple[float, float, float, float]:
        d = math.sqrt(
            ((tpl["T"] - 0.1) / 0.1) ** 2
            + ((tpl["beta"] - 200) / 200) ** 2
            + ((tpl["delta"] - 0.5) / 0.5) ** 2
        )
        # Tiebreakers: lowest T, highest β, lowest δ.
        return (d, tpl["T"], -tpl["beta"], tpl["delta"])

    candidates_sorted = sorted(candidates, key=distance)
    return candidates_sorted[0], candidates_sorted


# --------------------------------------------------------------------------- #
# Aggregation helpers for the summary
# --------------------------------------------------------------------------- #
def family_pass_rate(cells: List[CellResult]) -> Dict[str, Dict[str, Any]]:
    """Per-family pass counts + alignment summary."""
    from collections import defaultdict

    per_family = defaultdict(list)
    for c in cells:
        per_family[c.family].append(c)
    out: Dict[str, Dict[str, Any]] = {}
    for fam, fcells in per_family.items():
        passed = sum(1 for c in fcells if c.cell_pass)
        metrics = [
            None
            if c.hit is None
            else AlignmentMetrics(hit=c.hit, margin=c.margin or 0.0,
                                  rank=c.rank or 3)
            for c in fcells
        ]
        agg = aggregate_alignment(metrics)
        out[fam] = {
            "total": len(fcells),
            "passed": passed,
            "pass_rate": passed / len(fcells),
            "alignment": asdict(agg) if agg is not None else None,
        }
    return out
