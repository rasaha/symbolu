"""§6.5 latency benchmark — per-``plan()`` wall-clock latency across
(M, K, H) combinations.

Outputs a Markdown table to `docs/experiments/phase_6_5_latency.md`
(or stdout with --no-write), with mean / p50 / p95 / p99 / max in
milliseconds per cell, plus pass/fail indicators against three
integration-tier budgets:

    automotive       10 Hz → 100.0 ms
    industrial robot 50 Hz →  20.0 ms
    drone           100 Hz →  10.0 ms

Sweep (reduced from the §6.5 design-doc spec for CI-friendliness):
    M  ∈ {3, 4}            (predictor count)
    K  ∈ {128, 256, 512}   (MPPI rollouts)
    H  ∈ {10, 20, 50}      (planning horizon)

All other planner config fixed to the V1 validated defaults
(T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor pairing).

Typical wall time on a laptop CPU (no GPU): ~2-5 min for the full
sweep at 50 cycles per cell. Seed-reproducible.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from ..core import BCVFConfig, CostOrder
from ..mppi_planner import MPPIConfig, MPPIPlanner, PerfCostConfig
from ..predictors import create_predictor_set
from ..simulator import make_straight_road


# ---------- latency tier budgets (ms) ----------
TIER_BUDGETS_MS = {
    "automotive (10 Hz)": 100.0,
    "industrial (50 Hz)": 20.0,
    "drone (100 Hz)": 10.0,
}


# ---------- sweep grid ----------
DEFAULT_M_VALUES = [3, 4]
DEFAULT_K_VALUES = [128, 256, 512]
DEFAULT_H_VALUES = [10, 20, 50]
DEFAULT_WARMUP = 5
DEFAULT_CYCLES = 50
DEFAULT_SEED = 42


def _build_planner(
    m: int, k: int, h: int, seed: int
) -> MPPIPlanner:
    """Construct a planner with M predictors, K rollouts, H horizon,
    and V1 validated consumer config."""
    predictors = create_predictor_set(seed=seed)
    if m == 3:
        # Drop M4 (the failing-anchor predictor in S3 scenarios) to
        # get an M=3 subset that still represents a realistic stack.
        predictors = {k_: v for k_, v in predictors.items() if k_ != "M4"}
    elif m == 4:
        pass  # all four
    else:
        raise ValueError(
            f"M={m} not supported by create_predictor_set subset path"
        )

    bcvf_cfg = BCVFConfig(
        gate_threshold=0.05,
        gate_beta=400.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3),
        use_anchor_pairing=False,
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )
    mppi_cfg = MPPIConfig(
        num_rollouts=k,
        horizon=h,
        dt=0.1,
        temperature=5.0,
        noise_std=np.array([1.5, 0.2], dtype=np.float64),
        velocity_bounds=(0.5, 10.0),
        steering_bounds=(-0.6, 0.6),
        warm_start=True,
        lambda_c=1.0,
        bcvf_config=bcvf_cfg,
        anchor=next(iter(predictors)),
    )
    road = make_straight_road(length=200.0)
    planner = MPPIPlanner(
        mppi_cfg, PerfCostConfig(), predictors, road, []
    )
    planner.set_seed(seed)
    planner.set_ema_alpha(0.05)
    planner.set_deadband_k_sigma(2.0)
    return planner


def _time_planner(
    planner: MPPIPlanner, warmup: int, cycles: int
) -> Dict[str, float]:
    """Warm up, then time ``cycles`` plan() calls. Returns ms stats."""
    for _ in range(warmup):
        planner.plan()
    times_ms: List[float] = []
    for _ in range(cycles):
        start = time.perf_counter()
        planner.plan()
        times_ms.append((time.perf_counter() - start) * 1000.0)
    arr = np.asarray(times_ms)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "max_ms": float(arr.max()),
    }


def _run_sweep(
    m_values: List[int],
    k_values: List[int],
    h_values: List[int],
    warmup: int,
    cycles: int,
    seed: int,
) -> List[Dict]:
    rows: List[Dict] = []
    for m in m_values:
        for k in k_values:
            for h in h_values:
                sys.stdout.write(
                    f"  M={m}, K={k:4d}, H={h:2d} ..."
                )
                sys.stdout.flush()
                planner = _build_planner(m, k, h, seed)
                stats = _time_planner(planner, warmup, cycles)
                row = {"M": m, "K": k, "H": h, **stats}
                rows.append(row)
                sys.stdout.write(
                    f" p50={stats['p50_ms']:6.1f} ms, "
                    f"p99={stats['p99_ms']:6.1f} ms, "
                    f"max={stats['max_ms']:6.1f} ms\n"
                )
    return rows


def _format_markdown(
    rows: List[Dict], seed: int, warmup: int, cycles: int
) -> str:
    lines: List[str] = []
    lines.append("# §6.5 Latency Benchmark — Results")
    lines.append("")
    lines.append(
        "Per-``plan()`` wall-clock latency across (M, K, H) combinations, "
        "V1 validated consumer config."
    )
    lines.append("")
    lines.append(
        f"- Warmup: {warmup} calls; cycles measured: {cycles}"
    )
    lines.append(f"- Seed: {seed}")
    lines.append(
        f"- Config: T=0.05, β=400, EMA α=0.05, deadband k=2σ, "
        f"non-anchor pairing"
    )
    lines.append("")
    lines.append("## Raw results")
    lines.append("")
    lines.append(
        "| M | K | H | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|"
    )
    for r in rows:
        lines.append(
            f"| {r['M']} | {r['K']} | {r['H']} | "
            f"{r['mean_ms']:.1f} | {r['p50_ms']:.1f} | "
            f"{r['p95_ms']:.1f} | {r['p99_ms']:.1f} | "
            f"{r['max_ms']:.1f} |"
        )
    lines.append("")
    lines.append("## Pass / fail against integration-tier budgets")
    lines.append("")
    lines.append(
        "Green (✅) = p99 ≤ budget. Red (❌) = p99 > budget. "
        "p99 is the conservative read; p50 gives a sense of typical "
        "case."
    )
    lines.append("")
    for tier, budget in TIER_BUDGETS_MS.items():
        lines.append(f"### {tier} — budget {budget:.0f} ms")
        lines.append("")
        lines.append("| M | K | H | p99 (ms) | vs budget |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            status = "✅" if r["p99_ms"] <= budget else "❌"
            lines.append(
                f"| {r['M']} | {r['K']} | {r['H']} | "
                f"{r['p99_ms']:.1f} | {status} |"
            )
        lines.append("")
    lines.append("## Recommended operating point per tier")
    lines.append("")
    lines.append(
        "Largest (M, K, H) combination that stays under each budget at "
        "p99:"
    )
    lines.append("")
    lines.append("| Tier | Largest configuration | p99 headroom |")
    lines.append("|---|---|---|")
    for tier, budget in TIER_BUDGETS_MS.items():
        passing = [r for r in rows if r["p99_ms"] <= budget]
        if not passing:
            lines.append(f"| {tier} | (none passing) | — |")
            continue
        # Largest = maximize K×H, tiebreak by M
        passing.sort(
            key=lambda r: (r["K"] * r["H"], r["M"]), reverse=True
        )
        best = passing[0]
        lines.append(
            f"| {tier} | M={best['M']}, K={best['K']}, H={best['H']} | "
            f"{budget - best['p99_ms']:.1f} ms below budget |"
        )
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(
        "Run ``python -m symbolu_robotics.bcvf_autonomous.benchmarks.latency`` "
        "to reproduce. Warm-up / cycle counts and the sweep grid are "
        "CLI-tunable. Results will vary with CPU model; run on the "
        "integrator's target compute substrate for actionable numbers."
    )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=str,
        default="docs/experiments/phase_6_5_latency.md",
        help="Markdown output path (relative to repo root).",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Print to stdout, don't write the file.",
    )
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--m", type=int, nargs="+", default=DEFAULT_M_VALUES
    )
    parser.add_argument(
        "--k", type=int, nargs="+", default=DEFAULT_K_VALUES
    )
    parser.add_argument(
        "--h", type=int, nargs="+", default=DEFAULT_H_VALUES
    )
    args = parser.parse_args(argv)

    print("§6.5 latency sweep:")
    print(f"  M × K × H = {args.m} × {args.k} × {args.h}")
    print(f"  warmup={args.warmup}, cycles={args.cycles}, seed={args.seed}")
    print()

    t0 = time.perf_counter()
    rows = _run_sweep(
        args.m, args.k, args.h, args.warmup, args.cycles, args.seed
    )
    wall = time.perf_counter() - t0
    print()
    print(f"Sweep wall time: {wall:.1f} s ({len(rows)} cells)")

    md = _format_markdown(rows, args.seed, args.warmup, args.cycles)
    if args.no_write:
        print()
        print(md)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md)
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
