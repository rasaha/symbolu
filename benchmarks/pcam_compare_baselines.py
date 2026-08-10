#!/usr/bin/env python3
"""
PCAM vs software baselines — replay comparison (Phase 3).

Runs the same deterministic trace through PCAM and a small set of
inline software baselines, then prints a side-by-side summary of
eviction behavior. Intended as a first-order sanity check that
PCAM's four-signal scoring produces measurably different decisions
from naive policies, not as a rigorous end-to-end quality benchmark.

**What this compares**

- PCAM's ``KVCachePolicy`` (via ``simulator.pcam.trace.replay``)
- LRU  — evict least-recently-used block, sink-unaware
- LFU  — evict least-frequently-used block, sink-unaware

**What this DOES NOT claim**

- These are NOT the published LRU / LFU / ARC / H2O / Streaming LLM
  implementations. They are minimal, sink-unaware reference
  heuristics implemented inline in this file. The repo has richer
  baselines at ``simulator/pcam/baselines/`` (``sink_lru.py``,
  ``h2o.py``, ``industry_style.py``) built against the older
  controller API; wiring those into the Phase 1 trace path is a
  follow-up scope, not a Phase 3 deliverable.
- The comparison is REPLAY-ONLY. No model execution, no latency
  measurement, no token-throughput proxy. The metrics are policy
  decisions, not serving outcomes.
- The trace is a small synthetic scenario by default. Real
  workload traces would produce a more representative picture.

The goal is to land a small, honest, readable comparison harness
that a future phase can extend with real baselines and real
traces, not to publish an acquisition-grade benchmark today.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam import PCAMConfig  # noqa: E402
from simulator.pcam._report import emit_json, format_table, section_header  # noqa: E402
from simulator.pcam.trace import EventKind, TraceEvent, replay  # noqa: E402

# Re-use the demo trace builder from the replay script so both
# benchmarks share the same canonical scenario without duplication.
from benchmarks.pcam_trace_replay import build_demo_trace, load_trace_from_json  # noqa: E402


# ===========================================================================
# Inline baselines
# ===========================================================================


class _BaselineBase:
    """
    Common accounting for the inline baselines. Tracks:
      - the set of "live" blocks
      - per-block accumulated attention (for the attention-weighted cost)
      - the set of blocks that would have been sinks under PCAM's
        sink_tokens rule (computed independently from the trace)
    """

    name: str = ""

    def __init__(self, sink_tokens: int) -> None:
        self.sink_tokens = sink_tokens
        self.live: set = set()
        self.attention: Dict[int, float] = {}
        self.sinks: set = set()
        self.metrics: Dict[str, Any] = {
            "evictions": 0,
            "sink_evictions": 0,
            "attention_weighted_cost": 0.0,
        }

    # ---- Per-event hooks ---------------------------------------------------

    def on_ensure(self, block_id: int, positions: List[int]) -> None:
        if any(p < self.sink_tokens for p in positions):
            self.sinks.add(block_id)
        self.live.add(block_id)
        self.attention.setdefault(block_id, 0.0)
        self._admit(block_id)

    def on_attention(self, block_id: int, attention_sum: float) -> None:
        self.attention[block_id] = self.attention.get(block_id, 0.0) + attention_sum
        self.live.add(block_id)
        self._touch(block_id)

    def on_select_victims(self, count: int) -> List[int]:
        victims = self._select(count)
        for v in victims:
            if v in self.sinks:
                self.metrics["sink_evictions"] += 1
            self.metrics["attention_weighted_cost"] += self.attention.get(v, 0.0)
            self.live.discard(v)
        self.metrics["evictions"] += len(victims)
        return victims

    # ---- Subclass hooks ----------------------------------------------------

    def _admit(self, block_id: int) -> None:
        raise NotImplementedError

    def _touch(self, block_id: int) -> None:
        raise NotImplementedError

    def _select(self, count: int) -> List[int]:
        raise NotImplementedError


class LRUBaseline(_BaselineBase):
    """Evict the block whose ``last_access_step`` is smallest."""

    name = "LRU"

    def __init__(self, sink_tokens: int) -> None:
        super().__init__(sink_tokens)
        self._step = 0
        self._last: Dict[int, int] = {}

    def _admit(self, block_id: int) -> None:
        self._step += 1
        self._last[block_id] = self._step

    def _touch(self, block_id: int) -> None:
        self._step += 1
        self._last[block_id] = self._step

    def _select(self, count: int) -> List[int]:
        ordered = sorted(self._last.items(), key=lambda kv: kv[1])
        victims = [bid for bid, _ in ordered[:count]]
        for v in victims:
            self._last.pop(v, None)
        return victims


class LFUBaseline(_BaselineBase):
    """Evict the block whose cumulative access count is smallest."""

    name = "LFU"

    def __init__(self, sink_tokens: int) -> None:
        super().__init__(sink_tokens)
        self._count: Dict[int, int] = {}

    def _admit(self, block_id: int) -> None:
        self._count[block_id] = self._count.get(block_id, 0) + 1

    def _touch(self, block_id: int) -> None:
        self._count[block_id] = self._count.get(block_id, 0) + 1

    def _select(self, count: int) -> List[int]:
        ordered = sorted(self._count.items(), key=lambda kv: kv[1])
        victims = [bid for bid, _ in ordered[:count]]
        for v in victims:
            self._count.pop(v, None)
        return victims


# ===========================================================================
# Phase 4: in-repo baseline adapter
# ===========================================================================
#
# The repo ships richer baselines at simulator/pcam/baselines/:
#   - sink_lru.py:       Sink+LRU — pins first N blocks, LRU otherwise
#   - h2o.py:            H2O — heavy-hitters oracle, attention-mass based
#   - industry_style.py: Combined heuristic with a ghost buffer
#
# These were built for the older ControllerConfig API, not the Phase 1
# TraceEvent stream. InRepoBaselineAdapter translates TraceEvents into
# the older API shape so the compare harness can drive them.
#
# Honesty notes:
#
# - Sink semantics differ slightly. PCAM pins blocks whose ADMISSION
#   positions contain any index < sink_tokens. The in-repo baselines
#   pin the first num_sinks block_ids they see. On the demo trace
#   where the sink block is admitted first, the two agree. On more
#   complex traces where non-sink blocks may be admitted before the
#   sink, they can disagree.
#
# - The "attention" signal is mapped as follows: each
#   on_block_attention event becomes a record_access call with
#   query_block=block_id and attention_scores={block_id: attention_sum}.
#   This is a self-attention interpretation; it preserves "how much
#   attention this block received" but does not capture cross-block
#   query→key structure.
#
# - IndustryStyleController has a warmup / ghost-buffer cooldown and
#   may return empty victim lists on short traces. This is a property
#   of the baseline, not a bug in the adapter.
#
# The wiring is a small deterministic shim; any future richer
# integration (e.g. multi-sequence tracking, cross-block attention
# mass) belongs to a later phase.


class InRepoBaselineAdapter(_BaselineBase):
    """
    Drives an in-repo ``BaselineController`` through the same
    TraceEvent→metric pipeline as the inline LRU/LFU baselines.

    Constructed with a factory callable that returns a fresh
    ``BaselineController`` instance. The factory is deferred so the
    compare harness can report a clear skip if the import fails.
    """

    def __init__(
        self,
        *,
        controller: Any,
        display_name: str,
        sink_tokens: int,
    ) -> None:
        super().__init__(sink_tokens)
        self._controller = controller
        self.name = display_name
        self._last_seq_id: int = 1

    def _admit(self, block_id: int) -> None:
        self._controller.record_access(
            query_block=block_id,
            accessed_blocks=[block_id],
            attention_scores={block_id: 0.0},
            sequence_id=self._last_seq_id,
        )

    def _touch(self, block_id: int) -> None:
        # Caller passed attention via on_attention, which already
        # recorded the attention mass on the live side. We mirror it
        # into the controller here.
        attn = self.attention.get(block_id, 0.0)
        self._controller.record_access(
            query_block=block_id,
            accessed_blocks=[block_id],
            attention_scores={block_id: attn},
            sequence_id=self._last_seq_id,
        )

    def _select(self, count: int) -> List[int]:
        return list(
            self._controller.select_evictions(
                num_to_evict=count,
                sequence_id=self._last_seq_id,
            )
        )

    def set_sequence(self, seq_id: int) -> None:
        """Update the sequence id used in subsequent record_access calls."""
        self._last_seq_id = seq_id


def _try_build_inrepo_adapters(
    *,
    max_blocks: int,
    sink_tokens: int,
) -> Tuple[List[InRepoBaselineAdapter], List[str]]:
    """
    Attempt to build adapters for the three in-repo baselines. Returns
    ``(adapters, skip_reasons)``. If an import fails (e.g. numpy is
    missing), the corresponding adapter is omitted and the reason is
    surfaced in the returned ``skip_reasons`` list.
    """
    adapters: List[InRepoBaselineAdapter] = []
    skip_reasons: List[str] = []

    try:
        from simulator.pcam.baselines.base import ControllerConfig
    except Exception as exc:
        skip_reasons.append(
            f"in-repo baselines unavailable: {type(exc).__name__}: {exc}"
        )
        return adapters, skip_reasons

    # num_sinks=1 on traces where the sink block is admitted first.
    # The configured sink_tokens value drives PCAM's per-position
    # sink detection; the in-repo baseline uses block-id order.
    cfg = ControllerConfig(
        cache_capacity=max_blocks,
        num_sinks=1,
        recent_window=16,
        top_k=4,
    )

    targets = [
        ("simulator.pcam.baselines.sink_lru", "SinkLRUController", "SinkLRU (in-repo)"),
        ("simulator.pcam.baselines.h2o", "H2OController", "H2O (in-repo)"),
        ("simulator.pcam.baselines.industry_style", "IndustryStyleController",
         "IndustryStyle (in-repo)"),
    ]
    for module_path, class_name, display in targets:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            controller = cls(cfg)
        except Exception as exc:
            skip_reasons.append(
                f"{display}: {type(exc).__name__}: {exc}"
            )
            continue
        adapters.append(
            InRepoBaselineAdapter(
                controller=controller,
                display_name=display,
                sink_tokens=sink_tokens,
            )
        )
    return adapters, skip_reasons


# ===========================================================================
# Replay drivers
# ===========================================================================


def run_baseline(
    events: List[TraceEvent],
    baseline: _BaselineBase,
) -> Dict[str, Any]:
    """
    Drive a baseline through a trace. Updates the baseline's
    current-sequence id on ``register_sequence`` events so the
    in-repo adapter can scope ``record_access`` correctly; the
    naive inline baselines ignore that hook. Ignores tier_hints
    and set_phase events.
    """
    for event in events:
        if event.kind is EventKind.REGISTER_SEQUENCE:
            # The in-repo adapter scopes record_access by sequence_id.
            # The inline LRU/LFU baselines don't track sequences and
            # don't need this hook, but the adapter does.
            if hasattr(baseline, "set_sequence"):
                baseline.set_sequence(int(event.args["seq_id"]))
        elif event.kind is EventKind.ENSURE_BLOCK:
            baseline.on_ensure(
                int(event.args["block_id"]),
                list(event.args["positions"]),
            )
        elif event.kind is EventKind.ON_BLOCK_ATTENTION:
            baseline.on_attention(
                int(event.args["block_id"]),
                float(event.args["attention_sum"]),
            )
        elif event.kind is EventKind.SELECT_VICTIMS:
            baseline.on_select_victims(int(event.args["count"]))
        # set_phase, complete_sequence, tier_hints are no-ops for
        # all baselines — they don't consume phase or tier hints.
    return {
        "policy": baseline.name,
        **baseline.metrics,
        "live_blocks": len(baseline.live),
        "live_sinks_remaining": len(baseline.sinks & baseline.live),
    }


def run_pcam(events: List[TraceEvent], config: PCAMConfig) -> Dict[str, Any]:
    """
    Drive PCAM's ``KVCachePolicy`` through the same trace via
    ``simulator.pcam.trace.replay`` and collect the same metric shape
    the baselines produce.
    """
    policy = config.build_policy()

    # Replay the trace, then compute the comparable metrics directly
    # from the policy's state + the trace's attention events.
    per_block_attention: Dict[int, float] = {}
    pcam_sinks: set = set()
    for event in events:
        if event.kind is EventKind.ENSURE_BLOCK:
            bid = int(event.args["block_id"])
            if any(p < config.sink_tokens for p in event.args["positions"]):
                pcam_sinks.add(bid)
        elif event.kind is EventKind.ON_BLOCK_ATTENTION:
            bid = int(event.args["block_id"])
            per_block_attention[bid] = per_block_attention.get(bid, 0.0) + float(
                event.args["attention_sum"]
            )

    result = replay(policy, events)

    # Compute the sink-eviction / attention-weighted cost from the
    # recorded victim lists, matching the baseline metric shape.
    sink_evictions = 0
    attention_weighted_cost = 0.0
    total_victims = 0
    for victims in result.victim_lists:
        for v in victims:
            total_victims += 1
            if v in pcam_sinks:
                sink_evictions += 1
            attention_weighted_cost += per_block_attention.get(v, 0.0)

    return {
        "policy": "PCAM",
        "evictions": total_victims,
        "sink_evictions": sink_evictions,
        "attention_weighted_cost": attention_weighted_cost,
        "live_blocks": len(policy.gpu_blocks),
        "live_sinks_remaining": len(pcam_sinks & policy.gpu_blocks),
    }


# ===========================================================================
# Report
# ===========================================================================


_DISCLAIMER = (
    "NOTE: REPLAY-ONLY comparison against minimal inline LRU and LFU "
    "baselines. These are NOT the published LRU/LFU/ARC/H2O/Streaming LLM "
    "implementations. Metrics reflect policy decisions on a synthetic "
    "trace, not model throughput or serving quality. See "
    "Project_documentation/simulator/simulator/pcam/docs/PHASE3_BENCHMARKS.md for the full caveat list."
)


def render_report(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(section_header("PCAM vs Baselines — Replay Comparison"))
    lines.append(_DISCLAIMER)

    headers = [
        "policy",
        "source",
        "evictions",
        "sink_evictions",
        "attn_weighted_cost",
        "live_blocks",
        "live_sinks",
    ]
    table = [
        [
            row["policy"],
            row.get("source", "?"),
            row["evictions"],
            row["sink_evictions"],
            f"{row['attention_weighted_cost']:.4f}",
            row["live_blocks"],
            row["live_sinks_remaining"],
        ]
        for row in rows
    ]
    lines.append("")
    lines.append(format_table(table, headers))
    lines.append("")
    lines.append("Source tags:")
    lines.append("  runtime  = PCAM KVCachePolicy via simulator.pcam.trace.replay")
    lines.append("  inline   = minimal LRU/LFU heuristic implemented in this file")
    lines.append("  in-repo  = adapted from simulator/pcam/baselines/ via InRepoBaselineAdapter")
    lines.append("")
    lines.append("Lower sink_evictions and lower attn_weighted_cost are better.")
    lines.append(
        "PCAM is expected to show zero sink_evictions by construction "
        "(sink blocks are pinned and excluded from select_victims)."
    )
    return "\n".join(lines) + "\n"


# ===========================================================================
# CLI
# ===========================================================================


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PCAM vs software baselines replay comparison "
                    "(Phase 3 inline + Phase 4 in-repo adapter).",
    )
    p.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Path to a JSON trace file. If omitted, use the built-in "
             "deterministic demo trace from pcam_trace_replay.",
    )
    p.add_argument(
        "--max-blocks", type=int, default=256,
        help="PCAM max_blocks (default: 256).",
    )
    p.add_argument(
        "--sink-tokens", type=int, default=4,
        help="sink_tokens threshold (default: 4). Applied consistently "
             "across PCAM and the inline baselines so the sink_evictions "
             "metric is apples-to-apples.",
    )
    p.add_argument(
        "--include-inrepo-baselines", action="store_true", default=False,
        help="Include the in-repo baselines from simulator/pcam/baselines/ "
             "(SinkLRU, H2O, IndustryStyle) via the Phase 4 adapter. "
             "Off by default; the Phase 3 default output continues to "
             "show only PCAM + inline LRU/LFU.",
    )
    p.add_argument(
        "--json",
        type=Path,
        default=None,
        help="If provided, write the per-policy metric rows to this "
             "JSON file.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable report.",
    )
    return p


def run(argv: Optional[List[str]] = None) -> int:
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

    pcam_row = run_pcam(events, config)
    lru_row = run_baseline(events, LRUBaseline(sink_tokens=args.sink_tokens))
    lfu_row = run_baseline(events, LFUBaseline(sink_tokens=args.sink_tokens))
    rows = [pcam_row, lru_row, lfu_row]

    # Source-tag each row so the report can distinguish inline from in-repo.
    pcam_row["source"] = "runtime"
    lru_row["source"] = "inline"
    lfu_row["source"] = "inline"

    skip_reasons: List[str] = []
    if args.include_inrepo_baselines:
        adapters, skip_reasons = _try_build_inrepo_adapters(
            max_blocks=args.max_blocks,
            sink_tokens=args.sink_tokens,
        )
        for adapter in adapters:
            row = run_baseline(events, adapter)
            row["source"] = "in-repo"
            rows.append(row)

    if not args.quiet:
        print(render_report(rows))
        if skip_reasons:
            print("\nSkipped in-repo baselines:")
            for reason in skip_reasons:
                print(f"  - {reason}")

    if args.json is not None:
        emit_json({"rows": rows, "skipped": skip_reasons, "config": {
            "max_blocks": config.max_blocks,
            "sink_tokens": config.sink_tokens,
        }}, args.json)

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
