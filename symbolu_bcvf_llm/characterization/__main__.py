"""CLI entry: ``python -m symbolu_bcvf_llm.characterization``.

Runs the four §3.4 grids in the §3.4.7 execution order, writes
``docs/experiments/phase_1_5_results.csv`` and
``docs/experiments/phase_1_5_summary.md``, and prints the §3.9.5
classification.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List

from .sweep import (
    CellResult,
    FAMILY_MAGNITUDES,
    V1_DEFAULTS,
    family_pass_rate,
    pick_winner_tuple,
    run_ablation_grid,
    run_full_v_spot_check,
    run_primary_grid,
    run_sensitivity_grid,
)


CSV_FIELDS = [
    "grid", "family", "family_params", "T", "beta", "delta",
    "sigma_logit", "V", "seed", "cost_order",
    "total_cost", "max_accel_norm", "gate_activations",
    "per_source_costs", "per_pair_costs",
    "truth_label", "hit", "margin", "rank",
    "threshold_pass", "alignment_pass", "cell_pass",
    "failure_reasons",
]


def _write_csv(cells: List[CellResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for c in cells:
            writer.writerow({
                "grid": c.grid,
                "family": c.family,
                "family_params": json.dumps(c.family_params, sort_keys=True),
                "T": c.T,
                "beta": c.beta,
                "delta": c.delta,
                "sigma_logit": c.sigma_logit,
                "V": c.V,
                "seed": c.seed,
                "cost_order": c.cost_order,
                "total_cost": c.total_cost,
                "max_accel_norm": c.max_accel_norm,
                "gate_activations": c.gate_activations,
                "per_source_costs": json.dumps(list(c.per_source_costs)),
                "per_pair_costs": json.dumps(c.per_pair_costs, sort_keys=True),
                "truth_label": c.truth_label,
                "hit": c.hit,
                "margin": c.margin,
                "rank": c.rank,
                "threshold_pass": c.threshold_pass,
                "alignment_pass": c.alignment_pass,
                "cell_pass": c.cell_pass,
                "failure_reasons": ";".join(c.failure_reasons),
            })


def _classify(
    primary: List[CellResult],
    sensitivity: List[CellResult],
    ablation: List[CellResult],
    full_v: List[CellResult],
    winner: Dict[str, float] | None,
) -> str:
    # §3.4.4 ablation expectation: SECOND cells all pass linear_drift.
    ablation_second_pass = all(
        c.cell_pass for c in ablation if c.cost_order == "SECOND"
    )
    primary_all = all(c.cell_pass for c in primary)
    full_v_all = all(c.cell_pass for c in full_v) if full_v else False
    if not ablation_second_pass or any(
        c.cell_pass is False and c.cost_order == "SECOND"
        and c.family == "linear_drift"
        for c in ablation
    ):
        return "STRUCTURAL_FAILURE"
    if primary_all and winner is not None and full_v_all:
        return "PASS"
    if winner is not None and full_v_all and not primary_all:
        return "SCALE_MISMATCH_FIXED"
    if winner is None:
        return "STRUCTURAL_FAILURE"
    return "VOCAB_SCALE_MISMATCH_FIXED"


def _summarize(
    primary: List[CellResult],
    sensitivity: List[CellResult],
    ablation: List[CellResult],
    full_v: List[CellResult],
    winner: Dict[str, float] | None,
    candidates: List[Dict[str, float]],
    classification: str,
    out_path: Path,
) -> None:
    lines: List[str] = []
    lines.append("# Phase 1.5 Summary — §3 BCVF LLM Characterization\n")
    lines.append(f"**Classification:** `{classification}`\n")
    if winner is not None:
        lines.append(
            f"**Winner tuple:** `T={winner['T']}, beta={winner['beta']}, "
            f"delta={winner['delta']}`\n"
        )
    else:
        lines.append("**Winner tuple:** *none — no sensitivity cell passed all "
                     "families × σ.*\n")

    lines.append("\n## Grid counts\n")
    lines.append(f"- Primary: {len(primary)} cells "
                 f"({sum(c.cell_pass for c in primary)} pass)")
    lines.append(f"- Sensitivity: {len(sensitivity)} cells "
                 f"({sum(c.cell_pass for c in sensitivity)} pass)")
    lines.append(f"- Ablation: {len(ablation)} cells")
    lines.append(f"- Full-V spot check: {len(full_v)} cells "
                 f"({sum(c.cell_pass for c in full_v)} pass)\n")

    lines.append("\n## §3.4.4 Ablation — empirical Lemma-1 confirmation\n")
    lines.append("| cost_order | linear_drift pass/total |")
    lines.append("|---|---|")
    for order in ("ZEROTH", "FIRST", "SECOND"):
        filt = [c for c in ablation if c.cost_order == order]
        total = len(filt)
        passed = sum(c.cell_pass for c in filt)
        lines.append(f"| {order} | {passed}/{total} |")
    lines.append("")
    lines.append("**Expected per §2.8.3/§2.6.4:** `SECOND` should pass all "
                 "cells (Lemma-1-respecting); `FIRST` should fail on "
                 "`drift_rate > 0` cells (confirming the Lemma-1 violation "
                 "warning is empirical); `ZEROTH` fails when the gate is "
                 "open.\n")

    lines.append("\n## §3.4.2 Primary grid — per-family pass rate at V1 defaults\n")
    lines.append("| Family | Pass rate | Notes |")
    lines.append("|---|---|---|")
    pf = family_pass_rate(primary)
    for fam in FAMILY_MAGNITUDES:
        entry = pf.get(fam, {"total": 0, "passed": 0, "pass_rate": 0.0,
                             "alignment": None})
        align = entry.get("alignment")
        if align is None:
            note = "—"
        else:
            note = (f"hit_rate={align['hit_rate']:.2f}, "
                    f"margin_mean={align['margin_mean']:.2f}")
        lines.append(
            f"| {fam} | {entry['passed']}/{entry['total']} "
            f"= {entry['pass_rate']:.2%} | {note} |"
        )

    lines.append("\n## §3.4.5 Full-V spot check (winner at V=32000)\n")
    if full_v:
        pf_full = family_pass_rate(full_v)
        lines.append("| Family | Pass rate |")
        lines.append("|---|---|")
        for fam in FAMILY_MAGNITUDES:
            e = pf_full.get(fam, {"total": 0, "passed": 0, "pass_rate": 0.0})
            lines.append(
                f"| {fam} | {e['passed']}/{e['total']} = {e['pass_rate']:.2%} |"
            )
    else:
        lines.append("*Not run (no winner).*")
    lines.append("")

    lines.append("\n## §3.9.2 Tiebreaker candidates\n")
    if candidates:
        lines.append(f"{len(candidates)} configurations pass the sensitivity "
                     "grid. Top 5 by Euclidean distance to V1 defaults:\n")
        lines.append("| rank | T | beta | delta |")
        lines.append("|---|---|---|---|")
        for i, c in enumerate(candidates[:5]):
            lines.append(f"| {i+1} | {c['T']} | {c['beta']} | {c['delta']} |")
    else:
        lines.append("*No candidate passed all families × σ_logit.*")
    lines.append("")

    lines.append("\n## Recommendation\n")
    if classification == "PASS":
        lines.append(
            f"`UNLOCK §4 AT (T={winner['T']}, β={winner['beta']}, "
            f"δ={winner['delta']})` — §3.4.1–§3.4.5 all green, §2.6 "
            "invariances empirically confirmed via §3.4.4 ablation, §3.5 "
            "thresholds met, §3.6 alignment met."
        )
    elif classification == "SCALE_MISMATCH_FIXED":
        lines.append(
            f"`UNLOCK §4 AT (T={winner['T']}, β={winner['beta']}, "
            f"δ={winner['delta']})` — V1 defaults did not pass primary, but "
            "the sensitivity winner survived full-V. Update §2.5 defaults "
            "to the winner tuple before proceeding."
        )
    elif classification == "VOCAB_SCALE_MISMATCH_FIXED":
        lines.append(
            "`FALLBACK PENDING` — sensitivity winner failed at V=32000; "
            "expand sensitivity grid directly at V=32000 and re-pick."
        )
    else:
        lines.append(
            "`HALT` — no (T, β, δ) passes all families or §2.6 C2 fails "
            "under SECOND. §0.6 stop rule #4 triggers; return to §2 math."
        )
    lines.append("")

    # Enumerate any §3.2.3 linear_drift SECOND failures (should be none).
    lin_drift_second_fails = [
        c for c in primary + sensitivity + full_v
        if c.family == "linear_drift" and c.cost_order == "SECOND"
        and not c.cell_pass
    ]
    if lin_drift_second_fails:
        lines.append("\n### ⚠ §2.6 C2 violations under SECOND (blocker)\n")
        for c in lin_drift_second_fails[:10]:
            lines.append(
                f"- {c.grid}/{c.family} drift_rate="
                f"{c.family_params.get('drift_rate')} σ={c.sigma_logit} "
                f"seed={c.seed} → total_cost={c.total_cost:.3e}, "
                f"reasons={c.failure_reasons}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="§3 Phase 1.5 BCVF LLM characterization sweep"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "docs" / "experiments",
        help="directory for phase_1_5_results.csv and phase_1_5_summary.md",
    )
    parser.add_argument(
        "--fast-V", type=int, default=1024,
        help="vocab size for primary/sensitivity/ablation grids",
    )
    parser.add_argument(
        "--full-V", type=int, default=32000,
        help="vocab size for full-V spot check",
    )
    parser.add_argument(
        "--skip-full-v", action="store_true",
        help="skip the V=32000 spot-check grid (for fast iteration)",
    )
    args = parser.parse_args(argv)

    print("§3.4.4 ablation grid ...", flush=True)
    ablation = run_ablation_grid(V=args.fast_V)
    ab_second_fails = [
        c for c in ablation if c.cost_order == "SECOND" and not c.cell_pass
    ]
    if ab_second_fails:
        print(
            "  ⚠ SECOND failures in ablation — Lemma 1 C2 violated "
            f"({len(ab_second_fails)} cells). Halting."
        )
        primary: List[CellResult] = []
        sensitivity: List[CellResult] = []
        full_v: List[CellResult] = []
        winner = None
        candidates: List[Dict[str, float]] = []
    else:
        print(f"  SECOND {sum(c.cell_pass for c in ablation if c.cost_order == 'SECOND')}/"
              f"{sum(1 for c in ablation if c.cost_order == 'SECOND')} pass")
        print(f"  FIRST {sum(c.cell_pass for c in ablation if c.cost_order == 'FIRST')}/"
              f"{sum(1 for c in ablation if c.cost_order == 'FIRST')} pass "
              "(expected to fail on drift_rate>0)")

        print("§3.4.2 primary grid ...", flush=True)
        primary = run_primary_grid(V=args.fast_V)
        print(f"  {sum(c.cell_pass for c in primary)}/{len(primary)} pass")

        print("§3.4.3 sensitivity grid ...", flush=True)
        sensitivity = run_sensitivity_grid(V=args.fast_V)
        print(f"  {sum(c.cell_pass for c in sensitivity)}/{len(sensitivity)} pass")

        winner, candidates = pick_winner_tuple(sensitivity)
        if winner is None:
            print("  no winner tuple found")
            full_v = []
        elif args.skip_full_v:
            print(f"  winner = {winner}; skipping full-V spot check")
            full_v = []
        else:
            print(f"  winner = {winner}")
            print("§3.4.5 full-V spot check ...", flush=True)
            full_v = run_full_v_spot_check(winner, V=args.full_V)
            print(f"  {sum(c.cell_pass for c in full_v)}/{len(full_v)} pass")

    all_cells = ablation + primary + sensitivity + full_v
    csv_path = args.out_dir / "phase_1_5_results.csv"
    md_path = args.out_dir / "phase_1_5_summary.md"
    _write_csv(all_cells, csv_path)
    classification = _classify(primary, sensitivity, ablation, full_v, winner)
    _summarize(primary, sensitivity, ablation, full_v, winner, candidates,
               classification, md_path)

    print(f"\nClassification: {classification}")
    print(f"Results: {csv_path}")
    print(f"Summary: {md_path}")
    return 0 if classification in ("PASS", "SCALE_MISMATCH_FIXED",
                                   "VOCAB_SCALE_MISMATCH_FIXED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
