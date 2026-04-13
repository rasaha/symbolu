#!/usr/bin/env python3
"""
PCAM offline trace replay benchmark (Phase 3).

Drives a ``KVCachePolicy`` through a deterministic event trace and
emits a compact per-run report. Intended for:

- Reproducing a serving incident offline
- Parameter sweeps (run the same trace under different configs)
- Sanity checks after a runtime port change
- Feeding a Phase 4 benchmark harness once one exists

This script is REPLAY-ONLY. It does not execute a real model or a
real runtime. Any "win" numbers it prints describe what PCAM's
policy would have decided on the given trace — not what end-to-end
token throughput or quality would have been. The distinction is
called out in the report output and in the Phase 3 doc.

Usage:

    python benchmarks/pcam_trace_replay.py               # built-in demo trace
    python benchmarks/pcam_trace_replay.py --trace t.json
    python benchmarks/pcam_trace_replay.py --max-blocks 512 --json out.json

If ``--trace`` is omitted, a small deterministic demo trace is used
so the script is self-contained and can run in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam import (  # noqa: E402
    InferencePhase,
    PCAMConfig,
    TierHint,
)
from simulator.pcam._report import emit_json, format_table, section_header  # noqa: E402
from simulator.pcam.trace import EventKind, TraceEvent, replay  # noqa: E402


# ---------------------------------------------------------------------------
# Built-in demo trace
# ---------------------------------------------------------------------------


def build_demo_trace(num_filler: int = 24, num_entity: int = 4) -> List[TraceEvent]:
    """
    A small deterministic trace exercising every PCAM codepath:
    sink admission, filler admission, entity admission, a PREFILL
    → DECODE phase transition, a victim selection under memory
    pressure, and a tier-hint query. No randomness, no RNG, no
    external inputs.
    """
    events: List[TraceEvent] = [
        TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": 1}),
        TraceEvent(EventKind.SET_PHASE, {"seq_id": 1, "phase": "PREFILL"}),
        # Sink block
        TraceEvent(
            EventKind.ENSURE_BLOCK,
            {"block_id": 0, "sequence_id": 1, "positions": [0, 1, 2, 3]},
        ),
    ]
    # Filler blocks (non-sink, low attention)
    for i in range(num_filler):
        bid = 100 + i
        events.append(
            TraceEvent(
                EventKind.ENSURE_BLOCK,
                {"block_id": bid, "sequence_id": 1, "positions": [bid]},
            )
        )
        events.append(
            TraceEvent(
                EventKind.ON_BLOCK_ATTENTION,
                {"block_id": bid, "attention_sum": 0.001, "sequence_id": 1},
            )
        )
    # Entity blocks (non-sink, high attention — exceed adaptive threshold)
    for i in range(num_entity):
        bid = 500 + i
        events.append(
            TraceEvent(
                EventKind.ENSURE_BLOCK,
                {"block_id": bid, "sequence_id": 1, "positions": [bid]},
            )
        )
        for _ in range(15):
            events.append(
                TraceEvent(
                    EventKind.ON_BLOCK_ATTENTION,
                    {"block_id": bid, "attention_sum": 0.9, "sequence_id": 1},
                )
            )
    events.extend(
        [
            TraceEvent(EventKind.SET_PHASE, {"seq_id": 1, "phase": "DECODE"}),
            TraceEvent(EventKind.SELECT_VICTIMS, {"count": num_filler // 4}),
            TraceEvent(
                EventKind.TIER_HINTS,
                {"block_ids": [0] + [500 + i for i in range(num_entity)] + [100, 101]},
            ),
            TraceEvent(EventKind.COMPLETE_SEQUENCE, {"seq_id": 1}),
        ]
    )
    return events


def load_trace_from_json(path: Path) -> List[TraceEvent]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise TypeError(
            f"trace file {path} must contain a JSON list of events, "
            f"got {type(data).__name__}"
        )
    return [TraceEvent.from_dict(e) for e in data]


# ---------------------------------------------------------------------------
# Metrics collection
# ---------------------------------------------------------------------------


def _tier_distribution(
    tier_hint_results: List[Dict[int, TierHint]],
) -> Dict[str, int]:
    """
    Aggregate tier-hint queries across the whole trace. Returns a
    dict keyed by TierHint.value.
    """
    counts = {t.value: 0 for t in TierHint}
    for hints in tier_hint_results:
        for hint in hints.values():
            counts[hint.value] += 1
    return counts


def collect_metrics(config: PCAMConfig, result) -> Dict[str, Any]:
    """
    Build a flat metrics dict from a ReplayResult. Mirrors
    ``KVCachePolicy.get_stats()`` plus a few replay-level aggregates.
    """
    total_victims = sum(len(v) for v in result.victim_lists)
    metrics: Dict[str, Any] = {
        "config.max_blocks": config.max_blocks,
        "config.sink_tokens": config.sink_tokens,
        "config.attention_ema_alpha": config.attention_ema_alpha,
        "events_replayed": result.event_count,
        "select_victims_calls": len(result.victim_lists),
        "tier_hint_calls": len(result.tier_hint_results),
        "complete_sequence_calls": len(result.completed_sequences),
        "total_victims_selected": total_victims,
        "tier_distribution": _tier_distribution(result.tier_hint_results),
    }
    metrics.update(
        {f"policy.{k}": v for k, v in result.final_stats.items()}
    )
    return metrics


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


_DISCLAIMER = (
    "NOTE: This is a REPLAY-ONLY benchmark. It reports what the PCAM "
    "policy would have decided on the given trace. It does not measure "
    "real model throughput, latency, or quality — those require a real "
    "runtime integration (see benchmarks/pcam_vllm_demo.py for the "
    "Phase 2 integration shim)."
)


def render_report(metrics: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(section_header("PCAM Offline Trace Replay"))
    lines.append(_DISCLAIMER)

    config_rows = [
        ("max_blocks", metrics["config.max_blocks"]),
        ("sink_tokens", metrics["config.sink_tokens"]),
        ("attention_ema_alpha", metrics["config.attention_ema_alpha"]),
    ]
    lines.append("\nConfig")
    lines.append(format_table(config_rows, ["key", "value"]))

    run_rows = [
        ("events replayed", metrics["events_replayed"]),
        ("select_victims calls", metrics["select_victims_calls"]),
        ("tier_hints calls", metrics["tier_hint_calls"]),
        ("complete_sequence calls", metrics["complete_sequence_calls"]),
        ("total victims selected", metrics["total_victims_selected"]),
    ]
    lines.append("\nReplay summary")
    lines.append(format_table(run_rows, ["metric", "value"]))

    policy_rows = [
        ("evictions", metrics.get("policy.evictions", 0)),
        ("filler_evictions", metrics.get("policy.filler_evictions", 0)),
        ("total_blocks", metrics.get("policy.total_blocks", 0)),
        ("gpu_blocks", metrics.get("policy.gpu_blocks", 0)),
        ("pinned_blocks", metrics.get("policy.pinned_blocks", 0)),
        ("active_sequences", metrics.get("policy.active_sequences", 0)),
        ("step", metrics.get("policy.step", 0)),
    ]
    lines.append("\nPolicy stats (final)")
    lines.append(format_table(policy_rows, ["metric", "value"]))

    tier_rows = [(k, v) for k, v in metrics["tier_distribution"].items()]
    lines.append("\nTier-hint distribution (across all tier_hints calls)")
    lines.append(format_table(tier_rows, ["tier", "count"]))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline PCAM trace replay benchmark (Phase 3).",
    )
    p.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Path to a JSON trace file (list of TraceEvent dicts). "
             "If omitted, a built-in deterministic demo trace is used.",
    )
    p.add_argument(
        "--max-blocks",
        type=int,
        default=256,
        help="Policy max_blocks (default: 256).",
    )
    p.add_argument(
        "--sink-tokens",
        type=int,
        default=4,
        help="Policy sink_tokens (default: 4).",
    )
    p.add_argument(
        "--json",
        type=Path,
        default=None,
        help="If provided, write the metrics dict to this JSON path.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable report (useful with --json).",
    )
    return p


def run(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point. Accepts an optional argv for programmatic/test
    invocation. Returns an int exit code (0 on success).
    """
    args = build_argparser().parse_args(argv)

    events = (
        load_trace_from_json(args.trace)
        if args.trace is not None
        else build_demo_trace()
    )

    config = PCAMConfig(
        max_blocks=args.max_blocks,
        sink_tokens=args.sink_tokens,
    )
    policy = config.build_policy()
    result = replay(policy, events)
    metrics = collect_metrics(config, result)

    if not args.quiet:
        print(render_report(metrics))

    if args.json is not None:
        emit_json(metrics, args.json)

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
