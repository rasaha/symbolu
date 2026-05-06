"""Latency-based Mode B cross-check (option C from Mode B disposition).

Takes a directory of Mode B ``vllm_summary.json`` files (produced
by :mod:`ctm_bench.runner_vllm`) and cross-references their
wall-clock timings against Mode A's per-workload predictions.

**Why latency rather than swap counts.** vLLM's swap mechanism
only engages under preemption pressure, which our batch-mode
runner does not create (default FCFS scheduler, no priority
mix, all prompts submitted at once via ``engine.generate(...)``).
See ``MODE_B_RUNBOOK.md`` §9 "vLLM batch-mode swap-engagement
gap" for the architectural details. Direct swap-byte cross-check
is therefore not achievable today; **per-decode-token wall-clock
latency** is the data Mode B *can* produce under batch mode and
is what this tool cross-references.

The cross-check is **indirect**: Mode A predicts
``avg_access_latency_ns`` per cache access; Mode B reports
wall-clock seconds per decode token. They are not the same
quantity. What we *can* compare is the **directional ranking**
between workloads: if Mode A predicts workload X has higher
average access latency than workload Y, Mode B should also show
higher per-token wall time for X than Y. Match in directional
ranking validates the tier model qualitatively.

Usage:

    python -m ctm_bench.scripts.latency_cross_check \\
        --mode-b-dir /workspace/lru_validation \\
        --mode-a-summary bench_out/round4_multi_seed/multi_seed_summary.json \\
        --output /workspace/lru_validation/cross_check.md

If ``--output`` is omitted, the report is printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class ModeBCell:
    """One Mode B run, distilled from a ``vllm_summary.json`` file."""

    workload: str
    policy: str
    seed: int
    n_decode_tokens: int
    wall_clock_seconds: float
    counter_source: str
    slow_tier_bytes_per_decode_token: float
    source_path: str

    @property
    def per_token_wall_ms(self) -> Optional[float]:
        """Wall-clock seconds per decode token, in milliseconds.
        ``None`` if no decode tokens were produced (the cell ran
        but vLLM truncated the prompt or generated nothing)."""
        if self.n_decode_tokens <= 0:
            return None
        return (self.wall_clock_seconds * 1000.0) / self.n_decode_tokens


@dataclass(frozen=True)
class ModeAPrediction:
    """One Mode A cell's prediction relevant to the cross-check."""

    workload: str
    policy: str
    seed: int
    avg_access_latency_ns: float
    slow_tier_bytes_per_decode_token: float
    n_decode_tokens: int


def load_mode_b_cells(mode_b_dir: Path) -> List[ModeBCell]:
    """Walk a directory tree looking for ``vllm_summary.json``
    files and load each cell. Tolerates extra files / nested
    directories; ignores files that don't have the expected
    schema."""
    cells: List[ModeBCell] = []
    for path in sorted(mode_b_dir.rglob("vllm_summary.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for cell in data.get("cells", []):
            try:
                cells.append(
                    ModeBCell(
                        workload=cell["workload_name"],
                        policy=cell["policy_name"],
                        seed=int(cell.get("seed", -1)),
                        n_decode_tokens=int(cell.get("n_decode_tokens", 0)),
                        wall_clock_seconds=float(
                            cell.get("wall_clock_seconds", 0.0)
                        ),
                        counter_source=cell.get("counter_source", ""),
                        slow_tier_bytes_per_decode_token=float(
                            cell.get("slow_tier_bytes_per_decode_token", 0.0)
                        ),
                        source_path=str(path),
                    )
                )
            except (KeyError, ValueError, TypeError):
                # Schema doesn't match — skip; don't pretend.
                continue
    return cells


def load_mode_a_predictions(summary_path: Path) -> List[ModeAPrediction]:
    """Load Mode A predictions from a multi-seed summary JSON
    (the output of one of the bench_out/round*_*/multi_*.json
    files). Tolerates missing fields."""
    if not summary_path.exists():
        return []
    with open(summary_path) as f:
        data = json.load(f)
    out: List[ModeAPrediction] = []
    cells = data.get("cells", [])
    for cell in cells:
        try:
            out.append(
                ModeAPrediction(
                    workload=cell.get("workload", cell.get("workload_name", "")),
                    policy=cell.get("policy", cell.get("policy_name", "")),
                    seed=int(cell.get("seed", -1)),
                    avg_access_latency_ns=float(
                        cell.get("avg_access_latency_ns", 0.0)
                    ),
                    slow_tier_bytes_per_decode_token=float(
                        cell.get("slow_tier_bytes_per_decode_token", 0.0)
                    ),
                    n_decode_tokens=int(cell.get("n_decode_tokens", 0)),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return out


def aggregate_mode_b_by_workload(
    cells: Sequence[ModeBCell],
) -> Dict[str, Dict[str, object]]:
    """Group Mode B cells by workload (collapsing seeds) and
    compute mean per-token wall + min/max for variance."""
    by_workload: Dict[str, List[ModeBCell]] = {}
    for c in cells:
        if c.policy != "lru":
            continue
        if c.per_token_wall_ms is None:
            continue
        by_workload.setdefault(c.workload, []).append(c)

    out: Dict[str, Dict[str, object]] = {}
    for workload, group in by_workload.items():
        per_token_walls = [
            c.per_token_wall_ms for c in group
            if c.per_token_wall_ms is not None
        ]
        if not per_token_walls:
            continue
        # Casting to satisfy the type checker; per_token_wall_ms is
        # not None here by construction (filtered above).
        walls_ms: List[float] = [float(v) for v in per_token_walls]
        out[workload] = {
            "n_seeds": len(group),
            "n_decode_tokens_each": [c.n_decode_tokens for c in group],
            "wall_clock_seconds_each": [c.wall_clock_seconds for c in group],
            "per_token_wall_ms_mean": mean(walls_ms),
            "per_token_wall_ms_min": min(walls_ms),
            "per_token_wall_ms_max": max(walls_ms),
            "counter_sources": sorted({c.counter_source for c in group}),
            "seeds": sorted({c.seed for c in group}),
        }
    return out


def aggregate_mode_a_by_workload(
    predictions: Sequence[ModeAPrediction],
) -> Dict[str, Dict[str, float]]:
    """Group Mode A predictions by workload (LRU only) and
    compute mean avg_access_latency_ns + slow_tier_B/tok."""
    by_workload: Dict[str, List[ModeAPrediction]] = {}
    for p in predictions:
        if p.policy != "lru":
            continue
        by_workload.setdefault(p.workload, []).append(p)
    out: Dict[str, Dict[str, float]] = {}
    for workload, group in by_workload.items():
        out[workload] = {
            "n_seeds": len(group),
            "avg_access_latency_ns_mean": mean(
                p.avg_access_latency_ns for p in group
            ),
            "slow_tier_bytes_per_decode_token_mean": mean(
                p.slow_tier_bytes_per_decode_token for p in group
            ),
        }
    return out


def render_report(
    mode_b_by_workload: Mapping[str, Mapping[str, object]],
    mode_a_by_workload: Mapping[str, Mapping[str, float]],
) -> str:
    """Render the cross-check report as markdown."""
    lines: List[str] = []
    lines.append("# Mode B Latency Cross-Check\n")
    lines.append(
        "Indirect cross-check: Mode B's wall-clock-per-decode-token "
        "(measurable) against Mode A's `avg_access_latency_ns` "
        "(predicted). Same metric this is *not*; what we cross-check "
        "is **directional ranking** — does Mode B's per-token wall "
        "rank workloads in the same order Mode A predicts?\n"
    )
    lines.append("## §1 Mode B per-token wall (LRU)\n")
    if not mode_b_by_workload:
        lines.append("_No Mode B cells found in the input directory._\n")
    else:
        lines.append(
            "| Workload | Seeds | n_decode (each) | Per-token wall (mean) |"
            " Per-token wall (min..max) | counter_source |\n"
            "|---|---:|---|---:|---:|---|\n"
        )
        for workload in sorted(mode_b_by_workload.keys()):
            cell = mode_b_by_workload[workload]
            n_decode = cell["n_decode_tokens_each"]
            per_token_mean = cell["per_token_wall_ms_mean"]
            per_token_lo = cell["per_token_wall_ms_min"]
            per_token_hi = cell["per_token_wall_ms_max"]
            counter_sources = cell["counter_sources"]
            lines.append(
                f"| {workload} "
                f"| {cell['n_seeds']} "
                f"| {n_decode} "
                f"| {per_token_mean:.2f} ms "
                f"| {per_token_lo:.2f}..{per_token_hi:.2f} ms "
                f"| {','.join(counter_sources)} |\n"
            )
        lines.append("\n")

    lines.append("## §2 Mode A predicted access latency (LRU)\n")
    if not mode_a_by_workload:
        lines.append(
            "_No Mode A predictions loaded — pass `--mode-a-summary`._\n"
        )
    else:
        lines.append(
            "| Workload | Seeds | Mean avg_access_latency_ns | "
            "Mean slow_tier B/tok |\n"
            "|---|---:|---:|---:|\n"
        )
        for workload in sorted(mode_a_by_workload.keys()):
            cell = mode_a_by_workload[workload]
            lines.append(
                f"| {workload} "
                f"| {int(cell['n_seeds'])} "
                f"| {cell['avg_access_latency_ns_mean']:,.0f} ns "
                f"| {cell['slow_tier_bytes_per_decode_token_mean']:,.0f} B |\n"
            )
        lines.append("\n")

    # Directional cross-check (only if we have both).
    if mode_a_by_workload and mode_b_by_workload:
        lines.append("## §3 Directional cross-check\n")
        common = sorted(
            set(mode_a_by_workload.keys()) & set(mode_b_by_workload.keys())
        )
        if not common:
            lines.append(
                "_No workloads appear in both Mode A and Mode B summaries; "
                "directional cross-check skipped._\n"
            )
        else:
            mode_b_ranked = sorted(
                common,
                key=lambda w: float(
                    mode_b_by_workload[w]["per_token_wall_ms_mean"]
                ),
            )
            mode_a_ranked = sorted(
                common,
                key=lambda w: mode_a_by_workload[w][
                    "avg_access_latency_ns_mean"
                ],
            )
            lines.append(
                "Both rankings are ascending (lowest latency first):\n\n"
            )
            lines.append(f"* **Mode B order:** {' < '.join(mode_b_ranked)}\n")
            lines.append(f"* **Mode A order:** {' < '.join(mode_a_ranked)}\n\n")
            if mode_b_ranked == mode_a_ranked:
                lines.append(
                    "**✅ Rankings match.** Mode A's tier model "
                    "directionally agrees with Mode B's measured "
                    "per-token wall — the workloads Mode A predicts "
                    "as slower are also slower under real-model vLLM. "
                    "This is qualitative validation that Mode A's "
                    "tier-cost model captures the right relative "
                    "ordering, even if absolute numbers can't be "
                    "directly compared.\n"
                )
            else:
                lines.append(
                    "**⚠ Rankings differ.** Mode A and Mode B "
                    "disagree on which workload is slower. This is a "
                    "real finding worth investigating — either the "
                    "Mode A tier model's relative weights are wrong, "
                    "or the Mode B per-token wall is dominated by "
                    "compute rather than memory access (so the "
                    "comparison is invalid for these workloads). "
                    "Inspect the per-workload numbers above and "
                    "decide.\n"
                )

    lines.append("\n## §4 Honest scope statement\n")
    lines.append(
        "* This cross-check is **indirect** — wall-clock latency "
        "includes compute, model forward passes, and Python overhead "
        "in addition to memory access. Direct swap-counter "
        "cross-check is blocked by vLLM's batch-mode preemption gap "
        "(see MODE_B_RUNBOOK.md §9).\n"
        "* Match in **directional ranking** validates that Mode A's "
        "tier model captures the right qualitative ordering. "
        "Disagreement is informative — flag, don't paper over.\n"
        "* Absolute magnitude calibration (Mode A's "
        "`avg_access_latency_ns` → Mode B's wall-clock-ms-per-token "
        "in some constant ratio) is **not** a valid claim from this "
        "cross-check; the units differ.\n"
    )
    return "".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="latency_cross_check",
        description=(
            "Cross-check Mode B per-decode-token wall against Mode A "
            "avg_access_latency_ns predictions (directional ranking)."
        ),
    )
    parser.add_argument(
        "--mode-b-dir",
        type=Path,
        required=True,
        help=(
            "Directory containing Mode B vllm_summary.json files "
            "(searched recursively)."
        ),
    )
    parser.add_argument(
        "--mode-a-summary",
        type=Path,
        default=None,
        help=(
            "Path to a Mode A multi-seed summary JSON "
            "(e.g. bench_out/round4_multi_seed/multi_seed_summary.json). "
            "If omitted, only the Mode B half of the report is rendered."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this path. If omitted, prints to stdout.",
    )
    args = parser.parse_args(argv)

    cells = load_mode_b_cells(args.mode_b_dir)
    if not cells:
        print(
            f"No vllm_summary.json files found under {args.mode_b_dir}",
            file=sys.stderr,
        )

    predictions = (
        load_mode_a_predictions(args.mode_a_summary)
        if args.mode_a_summary
        else []
    )

    report = render_report(
        aggregate_mode_b_by_workload(cells),
        aggregate_mode_a_by_workload(predictions),
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"Wrote {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
