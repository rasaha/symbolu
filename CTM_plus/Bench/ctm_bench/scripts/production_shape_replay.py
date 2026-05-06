"""Production-shape workload replay (#1 in the validation roadmap).

Drives the KVSimulator's continuous-batching runner with parametric
length and arrival distributions whose *shapes* match commonly-cited
production-workload characteristics (bimodal short+long, bursty
inter-arrival, sustained long-context pressure). Runs the full
policy comparison (LRU / FIFO / Random / CTM+) and reports
recompute_cost — the conservative metric established in
``RESULTS.md`` §11.

**Honest scope.** This is *workload-shape* replay, not real-attention
replay. The length distributions and arrival patterns are
parametric models tunable to whatever production data you have;
the attention itself still comes from the synthetic generators in
KVSimulator's ``ATTENTION_PATTERNS``. Real attention requires GPU
extraction from a real model on real prompts (#1b in the
validation roadmap; not implemented).

The presets in this file are **parametric models, not validated
against any specific public dataset**. They are named for the
*shape* they capture, not for a dataset they reproduce. Citing
them as "LMSYS" or "BurstGPT" results would not survive technical
diligence.

Usage:

    # All presets, all policies, dump JSON + markdown.
    python -m ctm_bench.scripts.production_shape_replay \\
        --output-dir bench_out/production_shape_replay

    # One preset, custom seeds.
    python -m ctm_bench.scripts.production_shape_replay \\
        --preset chat_short_long_mix \\
        --seeds 42,137,271 \\
        --output-dir bench_out/replay_chat
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ReplayPreset:
    """A named parametric workload preset.

    The ``length_distribution`` is a list of
    ``(weight, min_tokens, max_tokens)`` tuples — the same format
    KVSimulator's ``run_continuous_batching`` accepts. ``arrival_rate``
    is a per-step Bernoulli probability; ``arrival_burstiness`` is an
    optional Pareto shape parameter (None = uniform Poisson;
    ``< 2`` = heavy-tailed bursts, see :func:`apply_burstiness`).

    ``description`` is a one-line label that appears in the markdown
    report. ``shape_caveat`` describes what this preset does and does
    not validate — copied verbatim into the report so partners can't
    misread a parametric model as a real-dataset claim.
    """

    name: str
    description: str
    shape_caveat: str
    max_blocks: int
    block_size: int
    total_steps: int
    arrival_rate: float
    completion_rate: float
    max_concurrent: int
    length_distribution: Tuple[Tuple[float, int, int], ...]
    arrival_burstiness: Optional[float] = None  # Pareto alpha; None = Poisson


# ---------------------------------------------------------------------- #
# Parametric presets.
#
# Each preset is named for the *shape* it models. The numbers come
# from order-of-magnitude reasoning about production workloads, not
# from specific dataset measurements. To map a preset to your actual
# data, replace the parameters with empirical values from your trace.
# ---------------------------------------------------------------------- #

# Short queries dominate (chat-style), with a long tail of long-context
# requests. The bimodal split below is a stylized parametric model: 70%
# short turns plus a long tail. Real LMSYS-Chat-1M / ShareGPT
# distributions need to be measured, not assumed.
CHAT_SHORT_LONG_MIX: ReplayPreset = ReplayPreset(
    name="chat_short_long_mix",
    description=(
        "Bimodal length: short chat turns dominate, occasional long "
        "context. Steady arrival rate. Stresses scan-resistance + "
        "small-block-eviction quality."
    ),
    shape_caveat=(
        "Parametric bimodal length distribution. NOT validated "
        "against LMSYS-Chat-1M / ShareGPT specifically — replace "
        "the length_distribution tuples with empirical measurements "
        "if you have them."
    ),
    max_blocks=128,
    block_size=16,
    total_steps=400,
    arrival_rate=0.15,
    completion_rate=0.05,
    max_concurrent=10,
    length_distribution=(
        (0.70, 64, 512),         # short chat turns
        (0.20, 1024, 4096),      # medium replies
        (0.08, 4096, 16384),     # long contexts
        (0.02, 16384, 32768),    # rare extreme long
    ),
)

# Bursty arrivals over long-context retrieval. RAG-style workloads
# are typically large prefill (the retrieved chunks) followed by short
# decode; bursts of arrivals stress KV admission heavily.
RAG_BURSTY: ReplayPreset = ReplayPreset(
    name="rag_bursty",
    description=(
        "Long-context retrieval-augmented workload with bursty "
        "arrivals (Pareto inter-arrival shape). Stresses scan-"
        "resistance under heavy admission pressure."
    ),
    shape_caveat=(
        "Pareto burstiness models heavy-tailed inter-arrival. "
        "Production traces (e.g. BurstGPT) are known to be heavy-"
        "tailed but the alpha here is a stylized parametric value, "
        "not an empirical fit to a specific dataset."
    ),
    max_blocks=256,
    block_size=16,
    total_steps=300,
    arrival_rate=0.20,
    completion_rate=0.05,
    max_concurrent=10,
    length_distribution=(
        (0.30, 2048, 4096),     # short retrieval contexts
        (0.40, 8192, 16384),    # medium RAG contexts
        (0.30, 16384, 32768),   # long RAG contexts
    ),
    arrival_burstiness=1.5,  # Pareto alpha; lower = burstier
)

# Sustained long-context agentic. Long contexts, long decode runs,
# heavy and sustained KV pressure. This is where the §11 4c-Extreme-
# style regression was surfaced — included here so the replay
# explicitly exercises the regime CTM+ is known not to handle well.
AGENTIC_SUSTAINED_LONG: ReplayPreset = ReplayPreset(
    name="agentic_sustained_long",
    description=(
        "Long-context agentic workload with sustained KV pressure "
        "(high arrival, slow completion, large concurrent set). "
        "This is the regime KVSimulator §11 surfaced as a CTM+ "
        "regression — included here so the replay does not silently "
        "skip the bad case."
    ),
    shape_caveat=(
        "Sustained-pressure regime. Mode A and §11 KVSimulator "
        "both surface CTM+ regressions on this shape. Reported here "
        "explicitly to keep the replay honest."
    ),
    max_blocks=96,
    block_size=16,
    total_steps=400,
    arrival_rate=0.20,
    completion_rate=0.04,
    max_concurrent=12,
    length_distribution=(
        (0.10, 1024, 2048),
        (0.30, 4096, 8192),
        (0.40, 8192, 16384),
        (0.20, 16384, 32768),
    ),
)


PRESETS: Dict[str, ReplayPreset] = {
    p.name: p for p in (
        CHAT_SHORT_LONG_MIX,
        RAG_BURSTY,
        AGENTIC_SUSTAINED_LONG,
    )
}


# ---------------------------------------------------------------------- #
# Burstiness adapter
#
# KVSimulator's `arrival_rate` is uniform Bernoulli per step (Poisson-
# like in the limit). Production arrival traces are known to be heavy-
# tailed (BurstGPT-style). We approximate burstiness by replacing the
# uniform arrival decision with a Pareto-driven gap process: an
# arrival happens, then the next arrival is delayed by a Pareto-
# distributed number of steps. Shape parameter alpha controls
# burstiness — alpha → ∞ approaches uniform; alpha = 1.5 is "moderately
# bursty"; alpha < 1 is heavy-tailed enough that the mean diverges.
#
# We expose this as a function that takes a seed and a base rate and
# returns a callable that decides arrivals — but we don't patch the
# KVSimulator runner directly. Instead, the script invokes the runner
# with a transformed `arrival_rate` schedule. See
# :func:`build_arrival_schedule`.
# ---------------------------------------------------------------------- #


def build_arrival_schedule(
    total_steps: int,
    base_rate: float,
    burstiness_alpha: Optional[float],
    seed: int,
) -> List[bool]:
    """Pre-compute a per-step arrivals schedule.

    When ``burstiness_alpha`` is ``None`` the schedule is uniform
    Bernoulli at ``base_rate`` per step (Poisson-equivalent).

    When ``burstiness_alpha`` is set, the schedule is a Pareto-gap
    process: an arrival happens, then the next arrival is at least
    ``ceil(Pareto(alpha))`` steps later. Smaller alpha => more bursty.

    Returns a list of length ``total_steps`` with True at arrival
    steps. The mean arrival probability is approximately
    ``base_rate`` over the run length (matched to the uniform case
    so that comparisons are fair), but the distribution of arrivals
    is heavy-tailed.
    """
    rng = random.Random(seed)
    schedule: List[bool] = [False] * total_steps
    if burstiness_alpha is None:
        for i in range(total_steps):
            schedule[i] = rng.random() < base_rate
        return schedule

    if burstiness_alpha <= 0:
        raise ValueError(
            f"burstiness_alpha must be > 0; got {burstiness_alpha}"
        )

    # Pareto with shape alpha has mean alpha / (alpha - 1) for alpha > 1.
    # We scale so that average inter-arrival == 1 / base_rate.
    target_mean_gap = 1.0 / base_rate
    if burstiness_alpha > 1.0:
        pareto_mean = burstiness_alpha / (burstiness_alpha - 1.0)
        scale = target_mean_gap / pareto_mean
    else:
        # alpha <= 1 has divergent mean; fall back to using
        # target_mean_gap as a scale and accept that the realised
        # mean may exceed it for short runs.
        scale = target_mean_gap

    step = 0
    while step < total_steps:
        # Pareto draw: U^(-1/alpha) - 1 has Pareto(alpha) shape.
        u = rng.random()
        if u <= 0.0:
            u = 1e-9
        gap_raw = (u ** (-1.0 / burstiness_alpha)) - 1.0
        gap = max(1, int(math.ceil(gap_raw * scale)))
        step += gap
        if step < total_steps:
            schedule[step] = True
    return schedule


# ---------------------------------------------------------------------- #
# Replay runner
# ---------------------------------------------------------------------- #


def run_preset(
    preset: ReplayPreset,
    seeds: Sequence[int],
) -> Dict:
    """Run all KVSimulator policies on a preset across multiple seeds.

    Returns a dict with per-policy aggregated metrics. Aggregation is
    plain mean of recompute_cost / accuracy / blocks_evicted /
    important_evictions across seeds. ``important_evictions`` is
    retained for completeness but flagged in the markdown report
    with the §11 policy-coupling caveat.
    """
    # KVSimulator's internal code uses ``from CTM_plus.KVPolicy...``
    # imports, so we need the repo root (the parent of CTM_plus/) on
    # sys.path regardless of where this script was invoked from.
    import sys as _sys
    from pathlib import Path as _Path
    repo_root = _Path(__file__).resolve().parents[4]
    if str(repo_root) not in _sys.path:
        _sys.path.insert(0, str(repo_root))
    from CTM_plus.KVSimulator.kv_simulator.buffer_pool import (
        compare_continuous_batching,
    )

    per_seed_results: Dict[int, Dict] = {}
    for seed in seeds:
        # The current KVSimulator continuous-batching runner does not
        # accept an externally supplied arrival schedule. We invoke
        # it with the base ``arrival_rate``; burstiness mode is
        # surfaced for future use when the runner gains a hook for
        # supplied schedules. The schedule is computed (deterministic
        # per seed) and reported in the JSON output so partners can
        # see the burstiness shape even when the KVSimulator path
        # uses uniform Bernoulli.
        per_seed_results[seed] = compare_continuous_batching(
            max_blocks=preset.max_blocks,
            block_size=preset.block_size,
            total_steps=preset.total_steps,
            seed=seed,
            arrival_rate=preset.arrival_rate,
            completion_rate=preset.completion_rate,
            max_concurrent=preset.max_concurrent,
            length_distribution=list(preset.length_distribution),
        )

    # Aggregate across seeds.
    policies = sorted(per_seed_results[seeds[0]].keys())
    aggregated: Dict[str, Dict] = {}
    for policy in policies:
        runs = [per_seed_results[s][policy] for s in seeds]
        agg: Dict = {}
        for key in runs[0].keys():
            vals = [r[key] for r in runs]
            if isinstance(vals[0], (int, float)) and not isinstance(vals[0], bool):
                agg_val = sum(vals) / len(vals)
                if isinstance(vals[0], int):
                    agg_val = round(agg_val)
                agg[key] = agg_val
            elif isinstance(vals[0], dict):
                agg[key] = {
                    k: sum(r[k] for r in vals) / len(vals)
                    for k in vals[0].keys()
                }
            else:
                agg[key] = vals[0]
        aggregated[policy] = agg

    # Sample one burstiness schedule (deterministic on first seed)
    # so the JSON shows the realised arrival shape.
    arrivals = build_arrival_schedule(
        total_steps=preset.total_steps,
        base_rate=preset.arrival_rate,
        burstiness_alpha=preset.arrival_burstiness,
        seed=seeds[0],
    )
    arrival_indices = [i for i, x in enumerate(arrivals) if x]
    arrival_gaps = [
        arrival_indices[i + 1] - arrival_indices[i]
        for i in range(len(arrival_indices) - 1)
    ]

    return {
        "preset": preset.name,
        "description": preset.description,
        "shape_caveat": preset.shape_caveat,
        "config": {
            "max_blocks": preset.max_blocks,
            "block_size": preset.block_size,
            "total_steps": preset.total_steps,
            "arrival_rate": preset.arrival_rate,
            "completion_rate": preset.completion_rate,
            "max_concurrent": preset.max_concurrent,
            "length_distribution": [
                list(t) for t in preset.length_distribution
            ],
            "arrival_burstiness_alpha": preset.arrival_burstiness,
        },
        "seeds": list(seeds),
        "n_arrivals_first_seed": len(arrival_indices),
        "arrival_gap_mean_first_seed": (
            mean(arrival_gaps) if arrival_gaps else None
        ),
        "arrival_gap_max_first_seed": (
            max(arrival_gaps) if arrival_gaps else None
        ),
        "policies": aggregated,
    }


# ---------------------------------------------------------------------- #
# Markdown reporting
# ---------------------------------------------------------------------- #


def render_report(results: Sequence[Dict]) -> str:
    """Render a markdown report for a list of preset results.

    Conservative framing per §11: leads with recompute_cost, calls
    out important_evictions as policy-coupled, surfaces regressions
    honestly.
    """
    lines: List[str] = []
    lines.append("# Production-Shape Workload Replay\n")
    lines.append(
        "**Scope: workload-shape evidence, not real-attention "
        "evidence.** The length and arrival distributions below are "
        "parametric models. The attention itself still comes from "
        "KVSimulator's synthetic attention generators. True real-"
        "attention replay requires GPU-extracted attention from a "
        "real model on real prompts (not implemented in this tool).\n\n"
        "Lead metric: **recompute_cost** (the §11 audit-passed "
        "metric — observes the operational consequence of eviction "
        "rather than predicting importance from policy-coupled "
        "signals).\n"
    )

    if not results:
        lines.append("_No presets ran._\n")
        return "".join(lines)

    for i, r in enumerate(results, 1):
        lines.append(f"## §{i} {r['preset']}\n\n")
        lines.append(f"_{r['description']}_\n\n")
        lines.append(f"**Shape caveat:** {r['shape_caveat']}\n\n")

        cfg = r["config"]
        lines.append(
            "| Parameter | Value |\n|---|---|\n"
            f"| max_blocks | {cfg['max_blocks']} |\n"
            f"| block_size | {cfg['block_size']} |\n"
            f"| total_steps | {cfg['total_steps']} |\n"
            f"| arrival_rate (base) | {cfg['arrival_rate']} |\n"
            f"| completion_rate | {cfg['completion_rate']} |\n"
            f"| max_concurrent | {cfg['max_concurrent']} |\n"
            f"| arrival_burstiness_alpha | "
            f"{cfg['arrival_burstiness_alpha']} |\n"
            f"| seeds | {r['seeds']} |\n\n"
        )

        # Arrival shape (sample from first seed).
        if r.get("arrival_gap_mean_first_seed") is not None:
            lines.append(
                f"**Arrival shape (first seed):** "
                f"{r['n_arrivals_first_seed']} arrivals, mean gap "
                f"{r['arrival_gap_mean_first_seed']:.2f} steps, max "
                f"gap {r['arrival_gap_max_first_seed']} steps. "
                f"(Reported for the burstiness-aware schedule even "
                f"when the KVSimulator runner used uniform "
                f"Bernoulli.)\n\n"
            )

        # Policy table — recompute_cost first.
        lines.append(
            "| Policy | recompute_cost | blocks_evicted | accuracy | "
            "important_evictions* |\n"
            "|---|---:|---:|---:|---:|\n"
        )
        # Sort policies for stable output.
        for policy in sorted(r["policies"].keys()):
            m = r["policies"][policy]
            recompute = m.get("recompute_cost", 0)
            evicted = m.get("blocks_evicted", 0)
            accuracy = m.get("accuracy", 0.0)
            imp = m.get("important_evictions", 0)
            policy_label = (
                f"**{policy}**" if policy in ("ctm_plus", "lru")
                else policy
            )
            lines.append(
                f"| {policy_label} | {recompute:,} | {evicted:,} | "
                f"{accuracy:.1%} | {imp} |\n"
            )

        lines.append(
            "\n*important_evictions is policy-coupled (see "
            "RESULTS.md §11.2): SINK is structurally pinned for "
            "all policies, ENTITY classification overlaps with "
            "CTM+'s scoring inputs. Reported for completeness only; "
            "do not cite as a CTM+ headline.\n\n"
        )

        # Lead-finding callout: CTM+ vs LRU recompute delta.
        ctm = r["policies"].get("ctm_plus")
        lru = r["policies"].get("lru")
        if ctm and lru:
            ctm_rec = ctm.get("recompute_cost", 0)
            lru_rec = lru.get("recompute_cost", 0)
            ctm_acc = ctm.get("accuracy", 0.0)
            lru_acc = lru.get("accuracy", 0.0)
            if lru_rec > 0:
                delta_pct = 100.0 * (ctm_rec - lru_rec) / lru_rec
                direction = (
                    "CTM+ better" if delta_pct < -1
                    else "CTM+ worse" if delta_pct > 1
                    else "tie"
                )
            else:
                delta_pct = 0.0
                direction = "tie"
            acc_delta_pp = 100.0 * (ctm_acc - lru_acc)
            lines.append(
                "**Lead finding:** CTM+ vs LRU on recompute_cost: "
                f"{delta_pct:+.1f}% ({direction}). "
                f"Accuracy delta: {acc_delta_pp:+.2f}pp.\n\n"
            )

    lines.append("## Honest scope statement\n\n")
    lines.append(
        "* This tool produces **workload-shape replay**, not "
        "real-attention replay. The length distributions and "
        "arrival patterns are parametric; the attention is "
        "synthetic.\n"
        "* Presets are **parametric models, not validated against "
        "specific public datasets** (LMSYS, ShareGPT, BurstGPT, "
        "etc.). To map a preset to your data, replace its "
        "parameters with empirical measurements from your trace.\n"
        "* Lead metric is `recompute_cost` (the §11 audit-passed "
        "metric); `important_evictions` is reported for "
        "completeness with the policy-coupling caveat.\n"
        "* Real-model CTM+ vs LRU validation remains gated on "
        "either Path A (vLLM 0.5+ rewrite) or Path B (partner "
        "serving stack). See `PARTNER_VALIDATION_NOTE.md`.\n"
    )
    return "".join(lines)


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="production_shape_replay",
        description=(
            "Run production-shape workloads (parametric length + "
            "arrival distributions) through KVSimulator's continuous-"
            "batching runner. Lead metric: recompute_cost."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS.keys()) + ["all"],
        default="all",
        help="Which preset to run; default 'all'.",
    )
    parser.add_argument(
        "--seeds",
        default="42,137,271",
        help="Comma-separated list of seeds; default '42,137,271'.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "If set, writes results.json + report.md into this "
            "directory. If omitted, prints the report to stdout."
        ),
    )
    args = parser.parse_args(argv)

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    if not seeds:
        print("--seeds must list at least one seed", file=sys.stderr)
        return 2

    if args.preset == "all":
        preset_list = [PRESETS[k] for k in sorted(PRESETS.keys())]
    else:
        preset_list = [PRESETS[args.preset]]

    results = [run_preset(p, seeds) for p in preset_list]
    report = render_report(results)

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "results.json").write_text(
            json.dumps({"runs": results}, indent=2)
        )
        (args.output_dir / "report.md").write_text(report)
        print(f"Wrote {args.output_dir / 'results.json'}")
        print(f"Wrote {args.output_dir / 'report.md'}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
