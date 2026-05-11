"""Latency-based Mode B cross-check — harness/timing evidence only.

Takes a directory of Mode B ``vllm_summary.json`` files (produced
by :mod:`ctm_bench.runner_vllm`) and renders a markdown report
of per-seed and per-workload tokens/sec + ms/token, plus an
optional directional cross-check against Mode A's per-workload
predictions.

**This tool reports harness/timing evidence only — not CTM+
performance evidence.** The Mode B runs that fed this tool ran
LRU only, because vLLM 0.5+ removed the public eviction-policy
hook that the CTM+ patch targeted; CTM+ was never installed.
Additionally, batch-mode FCFS execution did not trigger swap, so
the tier-cost path the simulator predicts was not exercised. See
``MODE_B_RUNBOOK.md`` §9 for the architectural details.

What this tool *does* show:

* The harness loaded a real model on a real GPU and produced
  honest wall-clock-per-decode-token data.
* The directional ordering of per-token wall across workloads
  (chat vs RAG, etc.) under real-model LRU.

What this tool does **not** show:

* CTM+ vs LRU on a real model (CTM+ was not running).
* Swap-byte traffic (no preemption, no swap).
* Validation of the simulator's tier-cost model — Mode A
  predicts memory-access cost, Mode B's per-token wall is
  compute-dominated on long contexts. Disagreement in the
  directional ranking is expected and is reported honestly.

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

    @property
    def tokens_per_second(self) -> Optional[float]:
        """Decode tokens per wall-clock second. ``None`` if the
        cell produced no decode tokens or had zero wall-clock."""
        if self.n_decode_tokens <= 0 or self.wall_clock_seconds <= 0:
            return None
        return self.n_decode_tokens / self.wall_clock_seconds


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


# Cells with n_decode_tokens below this floor are treated as
# truncated / setup-dominated outliers and excluded from the
# wall-clock aggregate. The first rag_128k cell on the May 2026
# run completed with n_decode=2 (vLLM truncated 128K prompts to
# its 32K max_seq_len before --max-model-len was wired through);
# 6.2s for 2 tokens = 3 sec/token, completely artifactual.
# 100 is comfortably above truncation cases and well below any
# real workload (chat_32k = 512 decode/seq, rag = 1024 decode/seq).
_DECODE_TOKEN_FLOOR_FOR_AGGREGATE: int = 100


def aggregate_mode_b_by_workload(
    cells: Sequence[ModeBCell],
) -> Dict[str, Dict[str, object]]:
    """Group Mode B cells by workload (collapsing seeds) and
    compute mean per-token wall + min/max for variance.

    Cells with n_decode_tokens below
    :data:`_DECODE_TOKEN_FLOOR_FOR_AGGREGATE` are treated as
    truncated/setup-dominated outliers and excluded; their count
    is reported under ``excluded_cells_count`` so the reader
    knows something was filtered."""
    by_workload: Dict[str, List[ModeBCell]] = {}
    excluded_by_workload: Dict[str, List[ModeBCell]] = {}
    for c in cells:
        if c.policy != "lru":
            continue
        if c.per_token_wall_ms is None:
            continue
        if c.n_decode_tokens < _DECODE_TOKEN_FLOOR_FOR_AGGREGATE:
            excluded_by_workload.setdefault(c.workload, []).append(c)
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
            # Drop empty strings (cells written by the harness
            # before counter_source was a field) so the column
            # doesn't show ",vllm_0_7_no_swaps_observed".
            "counter_sources": sorted({
                c.counter_source for c in group if c.counter_source
            }),
            "seeds": sorted({c.seed for c in group}),
            "excluded_cells_count": len(
                excluded_by_workload.get(workload, [])
            ),
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
    mode_b_cells: Sequence[ModeBCell] = (),
) -> str:
    """Render the cross-check report as markdown.

    ``mode_b_cells`` is optional and used only for the §1
    per-seed table. If omitted, the per-seed table is skipped
    and the report starts with the workload aggregate. Existing
    callers that don't pass it remain valid.
    """
    lines: List[str] = []
    lines.append("# Mode B Latency Cross-Check\n")
    lines.append(
        "**Scope: harness/timing evidence only — not CTM+ "
        "performance evidence.** The Mode B runs feeding this "
        "report ran LRU only, because vLLM 0.5+ removed the "
        "public eviction-policy hook the CTM+ patch targeted, "
        "and batch-mode FCFS execution did not trigger swap. "
        "See `MODE_B_RUNBOOK.md` §9 for the architectural "
        "details. The numbers below show that the harness ran "
        "end-to-end on a real model and produced honest "
        "wall-clock data; they do **not** show CTM+ vs LRU on "
        "a real model.\n\n"
        "Indirect cross-check (§3, when Mode A summary supplied): "
        "Mode B's wall-clock-per-decode-token against Mode A's "
        "`avg_access_latency_ns`. They are not the same metric; "
        "what we compare is **directional ranking**.\n"
    )

    if mode_b_cells:
        lines.append(_render_per_seed_section(mode_b_cells))

    lines.append("## §2 Mode B per-token wall — workload aggregate (LRU)\n")
    if not mode_b_by_workload:
        lines.append("_No Mode B cells found in the input directory._\n")
    else:
        lines.append(
            "| Workload | Seeds | n_decode (each) | Per-token wall (mean) |"
            " Per-token wall (min..max) | counter_source |\n"
            "|---|---:|---|---:|---:|---|\n"
        )
        any_excluded = False
        for workload in sorted(mode_b_by_workload.keys()):
            cell = mode_b_by_workload[workload]
            n_decode = cell["n_decode_tokens_each"]
            per_token_mean = cell["per_token_wall_ms_mean"]
            per_token_lo = cell["per_token_wall_ms_min"]
            per_token_hi = cell["per_token_wall_ms_max"]
            counter_sources = cell["counter_sources"]
            excluded_n = int(cell.get("excluded_cells_count", 0))
            workload_label = workload
            if excluded_n > 0:
                workload_label = f"{workload} (excluded {excluded_n})"
                any_excluded = True
            lines.append(
                f"| {workload_label} "
                f"| {cell['n_seeds']} "
                f"| {n_decode} "
                f"| {per_token_mean:.2f} ms "
                f"| {per_token_lo:.2f}..{per_token_hi:.2f} ms "
                f"| {','.join(counter_sources) or '(none)'} |\n"
            )
        if any_excluded:
            lines.append(
                "\n_Cells where `n_decode_tokens` was below "
                f"{_DECODE_TOKEN_FLOOR_FOR_AGGREGATE} were excluded "
                "from the aggregate as truncated/setup-dominated "
                "outliers (e.g. vLLM truncated a long prompt to "
                "max_seq_len and barely generated). The count is "
                "shown in parentheses._\n"
            )
        lines.append("\n")

    lines.append("## §3 Mode A predicted access latency (LRU)\n")
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
        lines.append("## §4 Directional cross-check\n")
        common = sorted(
            set(mode_a_by_workload.keys()) & set(mode_b_by_workload.keys())
        )
        if not common:
            lines.append(
                "_No workloads appear in both Mode A and Mode B summaries; "
                "directional cross-check skipped._\n"
            )
        else:
            # Pick which Mode A field to rank by. avg_access_latency_ns
            # is the natural choice if populated; fall back to
            # slow_tier_bytes_per_decode_token if all zeros (older
            # multi_seed_summary.json files don't include the latency
            # field — bench_out/round4_multi_seed/multi_seed_summary.json
            # is one such case as of May 2026).
            all_zero_latency = all(
                mode_a_by_workload[w]["avg_access_latency_ns_mean"] == 0.0
                for w in common
            )
            if all_zero_latency:
                mode_a_signal_name = "slow_tier_bytes_per_decode_token_mean"
                mode_a_signal_label = "slow-tier B/tok"
                mode_a_signal_unit = "B/tok"
                fallback_note = (
                    " (Fallback: Mode A `avg_access_latency_ns` was "
                    "zero on all workloads, so we ranked by Mode A's "
                    "`slow_tier_bytes_per_decode_token` instead. This "
                    "captures eviction-pressure ordering, which is "
                    "what Mode A actually models — the simulator does "
                    "not estimate compute cost.)"
                )
            else:
                mode_a_signal_name = "avg_access_latency_ns_mean"
                mode_a_signal_label = "avg_access_latency_ns"
                mode_a_signal_unit = "ns"
                fallback_note = ""

            mode_b_ranked = sorted(
                common,
                key=lambda w: float(
                    mode_b_by_workload[w]["per_token_wall_ms_mean"]
                ),
            )
            mode_a_ranked = sorted(
                common,
                key=lambda w: mode_a_by_workload[w][mode_a_signal_name],
            )
            lines.append(
                "Both rankings are ascending (lowest first):\n\n"
            )
            lines.append(
                f"* **Mode B order** (by per-token wall ms): "
                f"{' < '.join(mode_b_ranked)}\n"
            )
            lines.append(
                f"* **Mode A order** (by {mode_a_signal_label} "
                f"in {mode_a_signal_unit}): {' < '.join(mode_a_ranked)}\n\n"
            )
            if fallback_note:
                lines.append(fallback_note + "\n\n")

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
                    "disagree on relative ordering. Two common reasons:\n\n"
                    "1. **Mode B per-token wall is compute-dominated, "
                    "not memory-dominated.** Mode A's tier model "
                    "captures memory access patterns only — it does "
                    "not estimate compute cost. If a workload's "
                    "decode latency on a real model is dominated by "
                    "the cost of attending to a long KV cache (rather "
                    "than by slow-tier read traffic), Mode A's "
                    "ranking will not match Mode B's. This is "
                    "expected for long-context workloads (e.g. RAG "
                    "at 128K context vs chat at 32K — the 4× longer "
                    "context attends to 4× more KV per decode step, "
                    "regardless of where that KV lives).\n"
                    "2. **Mode A's tier model is mis-calibrated.** "
                    "If two workloads have similar context lengths "
                    "but Mode A predicts opposite ordering from Mode "
                    "B, the simulator's relative weights are wrong "
                    "and need to be reviewed against the data.\n\n"
                    "Inspect the per-workload numbers above; a "
                    "disagreement does not invalidate either side, "
                    "but it does mean the cross-check is **not** "
                    "qualitative validation of the tier model on "
                    "these workloads. To get qualitative validation, "
                    "run the cross-check on workload pairs with "
                    "matched context length where Mode A predicts "
                    "different eviction pressure (so the difference "
                    "in per-token wall, if any, comes from memory "
                    "access not compute).\n"
                )

    lines.append("\n## §5 Honest scope statement\n")
    lines.append(
        "* The numbers above are **harness/timing evidence**: they "
        "show the Mode B harness ran end-to-end on a real GPU and "
        "produced honest per-decode-token wall-clock data on LRU. "
        "They are **not** CTM+ performance evidence: CTM+ was not "
        "installed into vLLM (vLLM 0.5+ removed the public "
        "eviction-policy hook), so no real-model CTM+ vs LRU "
        "comparison exists.\n"
        "* Direct swap-counter cross-check is blocked by vLLM's "
        "batch-mode preemption gap — `engine.generate(prompts=[...])` "
        "with FCFS never preempts, so swap stays at zero. See "
        "MODE_B_RUNBOOK.md §9.\n"
        "* The directional cross-check (§4) is **indirect** — "
        "wall-clock per token includes compute, model forward "
        "passes, and Python overhead in addition to memory access. "
        "Match in directional ranking is qualitative agreement on "
        "ordering; disagreement is expected on long-context "
        "compute-dominated workloads and is reported, not papered "
        "over.\n"
        "* Absolute magnitude calibration (Mode A's "
        "`avg_access_latency_ns` → Mode B's wall-clock-ms-per-token "
        "in some constant ratio) is **not** a valid claim from this "
        "cross-check; the units differ.\n"
    )
    return "".join(lines)


def _render_per_seed_section(cells: Sequence[ModeBCell]) -> str:
    """Render the §1 per-seed table: one row per (workload, seed)
    cell with tokens/sec and ms/token. LRU only — non-LRU cells
    are skipped (CTM+ was never running in the May 2026 sweep)."""
    rows: List[ModeBCell] = sorted(
        (c for c in cells if c.policy == "lru"),
        key=lambda c: (c.workload, c.seed),
    )
    if not rows:
        return (
            "## §1 Mode B per-seed (LRU)\n\n"
            "_No LRU cells found._\n\n"
        )
    lines: List[str] = []
    lines.append("## §1 Mode B per-seed (LRU) — harness/timing evidence\n\n")
    lines.append(
        "One row per (workload, seed). Tokens/sec is the inverse of "
        "the per-token wall and may be dominated by compute on long "
        "contexts; this is real-model timing, not a CTM+ comparison.\n\n"
    )
    lines.append(
        "| Workload | Seed | n_decode | Wall (s) | Per-token (ms) | "
        "Tokens/sec | counter_source |\n"
        "|---|---:|---:|---:|---:|---:|---|\n"
    )
    for c in rows:
        per_token = c.per_token_wall_ms
        tps = c.tokens_per_second
        per_token_str = (
            f"{per_token:.2f}" if per_token is not None else "—"
        )
        tps_str = f"{tps:.2f}" if tps is not None else "—"
        lines.append(
            f"| {c.workload} | {c.seed} | {c.n_decode_tokens} "
            f"| {c.wall_clock_seconds:.2f} | {per_token_str} "
            f"| {tps_str} | {c.counter_source or '(none)'} |\n"
        )
    lines.append("\n")
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
        mode_b_cells=cells,
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
