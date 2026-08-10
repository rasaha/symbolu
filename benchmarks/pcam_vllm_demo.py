#!/usr/bin/env python3
"""
PCAM vLLM-facing demo (Phase 3).

A small, runnable demo that exercises the Phase 2 integration
surface (``simulator.pcam.integrations.vllm.PCAMEvictor``) in a
vLLM-shaped workflow without requiring the ``vllm`` package to be
installed. Intended as the seed artifact for an
acquisition-facing or partner-facing demo — not a benchmark.

What it shows
-------------
1. A ``PCAMEvictor`` instance built from a ``PCAMConfig``
2. Sequence registration with a phase (PREFILL → DECODE)
3. Block admission, each paired with a "fake" block object mimicking
   ``vllm.block.PhysicalTokenBlock``'s shape
4. Attention events driving the underlying scoring
5. Victim selection both as bare IDs and as the tracked block
   objects (via ``select_victims_as_blocks``)
6. Tier-hint queries for placement decisions
7. A final metrics snapshot via ``PolicyMetrics``

Honesty notes
-------------
- This demo does NOT execute a real model or a real vLLM runtime.
  The "attention events" are hand-written, not extracted from a
  real forward pass. Any throughput or quality numbers would
  require a real model; this demo produces neither.
- The "vLLM block object" here is a tiny dataclass. A real
  integration would track ``vllm.block.PhysicalTokenBlock``
  instances via the same ``admit_block(..., vllm_block=...)``
  slot.
- Running the demo with ``--real-vllm`` is supported in principle
  (the flag is documented and parsed) but currently errors out
  with an explicit "vLLM runtime path not yet implemented" message
  if the ``vllm`` package is present. That path is Phase 4 work,
  not Phase 3, and is deliberately not stubbed with fake numbers.

Usage
-----

    # Synthetic walkthrough, zero external dependencies
    python benchmarks/pcam_vllm_demo.py

    # Attempt the real-vLLM path (currently fails clean — see above)
    python benchmarks/pcam_vllm_demo.py --real-vllm

    # Emit a JSON transcript of the walkthrough for a demo page
    python benchmarks/pcam_vllm_demo.py --json out.json
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam import (  # noqa: E402
    InferencePhase,
    PCAMConfig,
    PolicyMetrics,
    TierHint,
)
from simulator.pcam._report import emit_json, format_table, section_header  # noqa: E402
from simulator.pcam.integrations.vllm import PCAMEvictor  # noqa: E402
from simulator.pcam.trace import replay  # noqa: E402

# vllm_bridge does NOT import vllm at module load. It is safe to import
# here whether or not vllm is installed; the actual vllm import happens
# lazily inside generate_with_derived_trace / ensure_vllm_available.
from benchmarks.vllm_bridge import (  # noqa: E402
    DerivedRunResult,
    VLLMBridgeUnavailable,
    ensure_vllm_available,
    generate_with_derived_trace,
)

# Phase 3 used a separate RealVLLMNotAvailable exception. Phase 4 routes
# everything through VLLMBridgeUnavailable so there's one failure class.
# The alias keeps Phase 3 test imports working without churn.
RealVLLMNotAvailable = VLLMBridgeUnavailable


# ---------------------------------------------------------------------------
# Fake vLLM block object
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FakeVLLMBlock:
    """
    Stand-in for ``vllm.block.PhysicalTokenBlock``. The demo tracks
    one of these per admitted block so ``select_victims_as_blocks``
    has something to return that is not a bare integer. The shape
    is intentionally minimal — real vLLM block objects have more
    fields, but the adapter only needs opaque identity.
    """

    block_id: int
    sequence_id: int
    num_tokens: int

    def __repr__(self) -> str:
        return (
            f"FakeBlock(id={self.block_id}, seq={self.sequence_id}, "
            f"tokens={self.num_tokens})"
        )


# ---------------------------------------------------------------------------
# Synthetic walkthrough
# ---------------------------------------------------------------------------


def _log(transcript: List[Dict[str, Any]], stage: str, **fields: Any) -> None:
    entry = {"stage": stage, **fields}
    transcript.append(entry)


def run_synthetic_walkthrough(
    max_blocks: int = 128,
    sink_tokens: int = 4,
) -> Dict[str, Any]:
    """
    Drive a ``PCAMEvictor`` through a vLLM-shaped workflow. Returns
    a transcript dict containing the per-stage events and the final
    metrics snapshot. This is deterministic — the same inputs
    always produce the same transcript, which makes it safe to
    diff in code review.
    """
    transcript: List[Dict[str, Any]] = []

    cfg = PCAMConfig(max_blocks=max_blocks, sink_tokens=sink_tokens)
    evictor = PCAMEvictor.from_config(cfg)
    _log(
        transcript,
        "init",
        max_blocks=cfg.max_blocks,
        sink_tokens=cfg.sink_tokens,
    )

    # ---- 1. Register a sequence with PREFILL phase ------------------------
    seq_id = 42
    evictor.register_sequence(seq_id=seq_id, phase=InferencePhase.PREFILL)
    _log(transcript, "register_sequence", seq_id=seq_id, phase="PREFILL")

    # ---- 2. Admit a sink block --------------------------------------------
    sink_block = _FakeVLLMBlock(block_id=0, sequence_id=seq_id, num_tokens=4)
    evictor.admit_block(
        block_id=sink_block.block_id,
        sequence_id=seq_id,
        positions=[0, 1, 2, 3],  # hits the sink threshold
        vllm_block=sink_block,
    )
    _log(transcript, "admit_sink_block", block_id=0, is_sink=True)

    # ---- 3. Admit 24 filler blocks with low attention ----------------------
    filler_blocks: List[_FakeVLLMBlock] = []
    for i in range(24):
        blk = _FakeVLLMBlock(
            block_id=100 + i, sequence_id=seq_id, num_tokens=16,
        )
        evictor.admit_block(
            block_id=blk.block_id,
            sequence_id=seq_id,
            positions=[100 + i],  # non-sink positions
            vllm_block=blk,
        )
        filler_blocks.append(blk)
    _log(transcript, "admit_filler_blocks", count=len(filler_blocks))

    # Apply weak attention to the filler blocks.
    for blk in filler_blocks:
        evictor.on_attention(
            block_id=blk.block_id,
            attention_sum=0.001,
            sequence_id=seq_id,
        )
    _log(transcript, "attention_filler", per_block=0.001, count=len(filler_blocks))

    # ---- 4. Admit a handful of entity blocks with strong attention --------
    entity_blocks: List[_FakeVLLMBlock] = []
    for i in range(4):
        blk = _FakeVLLMBlock(
            block_id=500 + i, sequence_id=seq_id, num_tokens=16,
        )
        evictor.admit_block(
            block_id=blk.block_id,
            sequence_id=seq_id,
            positions=[500 + i],
            vllm_block=blk,
        )
        entity_blocks.append(blk)
    _log(transcript, "admit_entity_blocks", count=len(entity_blocks))

    for blk in entity_blocks:
        for _ in range(15):
            evictor.on_attention(
                block_id=blk.block_id,
                attention_sum=0.9,
                sequence_id=seq_id,
            )
    _log(
        transcript,
        "attention_entity",
        per_block_total=15 * 0.9,
        count=len(entity_blocks),
    )

    # ---- 5. Transition to DECODE ------------------------------------------
    evictor.set_phase(seq_id, InferencePhase.DECODE)
    _log(transcript, "set_phase", seq_id=seq_id, phase="DECODE")

    # ---- 6. Request victims under memory pressure -------------------------
    victim_ids = evictor.select_victims(count=6)
    victim_blocks = [
        evictor.policy.blocks.get(bid) for bid in victim_ids
    ]  # for reporting; the adapter's method is select_victims_as_blocks
    _log(
        transcript,
        "select_victims",
        requested=6,
        returned_ids=list(victim_ids),
        num_returned=len(victim_ids),
    )

    # ---- 7. Tier hints for a mix of blocks --------------------------------
    probe_ids = [0] + [500 + i for i in range(4)] + [100, 101, 9999]
    hints = evictor.tier_hints(probe_ids)
    _log(
        transcript,
        "tier_hints",
        probe_ids=probe_ids,
        hints={bid: h.value for bid, h in hints.items()},
    )

    # ---- 8. Final metrics snapshot ----------------------------------------
    metrics = PolicyMetrics(evictor.policy).snapshot()
    _log(transcript, "final_stats", **metrics)

    return {
        "transcript": transcript,
        "final_stats": metrics,
        "victim_ids": list(victim_ids),
        "tier_hints": {bid: h.value for bid, h in hints.items()},
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def render_report(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(section_header("PCAM vLLM Demo — Synthetic Walkthrough"))
    lines.append(
        "NOTE: This is a SYNTHETIC demo. Attention events are "
        "hand-written, not extracted from a real model forward pass. "
        "No throughput, latency, or quality numbers are reported."
    )

    lines.append("\nTranscript")
    transcript_rows = [(i, e["stage"]) for i, e in enumerate(result["transcript"])]
    lines.append(format_table(transcript_rows, ["#", "stage"]))

    lines.append("\nVictim IDs selected under pressure")
    if result["victim_ids"]:
        lines.append("  " + ", ".join(str(v) for v in result["victim_ids"]))
    else:
        lines.append("  (none)")

    lines.append("\nTier hints")
    tier_rows = [(bid, hint) for bid, hint in result["tier_hints"].items()]
    lines.append(format_table(tier_rows, ["block_id", "tier"]))

    lines.append("\nFinal policy stats")
    stats_rows = [(k, v) for k, v in result["final_stats"].items()]
    lines.append(format_table(stats_rows, ["metric", "value"]))

    lines.append("")
    lines.append(
        "For a real vLLM integration, subclass vllm.core.evictor.Evictor "
        "and forward each abstract method to this same PCAMEvictor "
        "instance. See the docstring of "
        "simulator/pcam/integrations/vllm.py for the reference bridge."
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _attempt_real_vllm_path() -> None:
    """
    Thin importability probe for the real-vLLM path. Preserved from
    Phase 3 as a named entry point so existing tests that assert on
    the fail-clean behavior without vllm installed continue to work.
    Delegates to ``benchmarks.vllm_bridge.ensure_vllm_available``,
    which raises ``VLLMBridgeUnavailable`` (aliased as
    ``RealVLLMNotAvailable``) with an actionable hint.
    """
    ensure_vllm_available()


def run_real_vllm_path(
    *,
    model: str,
    prompts: List[str],
    max_tokens: int,
    block_size: int,
    max_blocks: int,
    sink_tokens: int,
    dtype: Optional[str] = None,
    trust_remote_code: bool = False,
) -> Dict[str, Any]:
    """
    Execute a real vLLM ``LLM.generate`` run, derive a ``TraceEvent``
    list from the observed sequence shapes, and replay that trace
    through ``KVCachePolicy``.

    Returns a dict that mirrors the synthetic-walkthrough result
    shape (plus an extra ``mode`` key so a downstream consumer can
    always tell which path produced the numbers). Raises
    ``VLLMBridgeUnavailable`` on any missing-dependency or
    model-load failure — never silently falls back to the synthetic
    path.

    See ``benchmarks/vllm_bridge.py`` for the shadow-mode
    honesty-notes: this path runs a real model on real inputs but
    does not patch vLLM's internal evictor, so the numbers
    describe "what PCAM would have decided on the observed
    workload", not "what PCAM did while driving vLLM's allocator".
    """
    run_result: DerivedRunResult = generate_with_derived_trace(
        model=model,
        prompts=prompts,
        max_tokens=max_tokens,
        block_size=block_size,
        sink_tokens=sink_tokens,
        dtype=dtype,
        trust_remote_code=trust_remote_code,
    )

    cfg = PCAMConfig(max_blocks=max_blocks, sink_tokens=sink_tokens)
    policy = cfg.build_policy()
    replay_result = replay(policy, run_result.trace)

    final_stats = PolicyMetrics(policy).snapshot()
    tier_hints_all: Dict[int, str] = {}
    for hints in replay_result.tier_hint_results:
        for bid, hint in hints.items():
            tier_hints_all[bid] = hint.value

    return {
        "mode": "real-vllm-shadow",
        "vllm_run": run_result.summary(),
        "config": {
            "max_blocks": cfg.max_blocks,
            "sink_tokens": cfg.sink_tokens,
        },
        "trace_events": len(run_result.trace),
        "victim_ids": [bid for lst in replay_result.victim_lists for bid in lst],
        "tier_hints": tier_hints_all,
        "final_stats": final_stats,
    }


def render_real_report(result: Dict[str, Any]) -> str:
    """Human-readable report for a real-vLLM shadow-mode run."""
    lines: List[str] = []
    lines.append(section_header("PCAM vLLM Demo — REAL vLLM (Shadow Mode)"))
    lines.append(
        "NOTE: vLLM ran a real model on real inputs. The PCAM numbers "
        "below describe what PCAM's policy would have decided on the "
        "observed workload. vLLM's own eviction was NOT replaced — "
        "this is shadow mode, not active control. See "
        "benchmarks/vllm_bridge.py and "
        "Project_documentation/simulator/simulator/pcam/docs/PHASE4_REAL_RUNTIME.md for the caveats."
    )

    vllm_run = result["vllm_run"]
    vllm_rows = [
        ("model", vllm_run["model"]),
        ("block_size", vllm_run["block_size"]),
        ("num_prompts", vllm_run["num_prompts"]),
        ("total_prompt_tokens", vllm_run["total_prompt_tokens"]),
        ("total_completion_tokens", vllm_run["total_completion_tokens"]),
        ("derived events", vllm_run["derived_events"]),
    ]
    lines.append("\nvLLM run")
    lines.append(format_table(vllm_rows, ["metric", "value"]))

    lines.append(f"\nVictim IDs selected during replay: {len(result['victim_ids'])}")
    if result["victim_ids"][:16]:
        lines.append("  first 16: " + ", ".join(str(v) for v in result["victim_ids"][:16]))

    if result["tier_hints"]:
        tier_rows = [(k, v) for k, v in list(result["tier_hints"].items())[:20]]
        lines.append("\nTier hints (first 20)")
        lines.append(format_table(tier_rows, ["block_id", "tier"]))

    stats_rows = [(k, v) for k, v in result["final_stats"].items()]
    lines.append("\nFinal policy stats")
    lines.append(format_table(stats_rows, ["metric", "value"]))
    return "\n".join(lines) + "\n"


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PCAM vLLM-facing demo — synthetic walkthrough "
                    "(default) or real-vLLM shadow mode (--real-vllm).",
    )
    p.add_argument(
        "--max-blocks", type=int, default=128,
        help="PCAMConfig max_blocks (default: 128).",
    )
    p.add_argument(
        "--sink-tokens", type=int, default=4,
        help="PCAMConfig sink_tokens (default: 4).",
    )
    p.add_argument(
        "--real-vllm", action="store_true",
        help="Run a real vllm.LLM.generate() call, derive a TraceEvent "
             "list from the observed sequence shapes, and replay it "
             "through KVCachePolicy (shadow mode). Requires a vllm "
             "install and a GPU. Fails clean via VLLMBridgeUnavailable "
             "if vllm is absent.",
    )
    p.add_argument(
        "--model", type=str, default="facebook/opt-125m",
        help="Model name passed to vllm.LLM(...) when --real-vllm is set "
             "(default: facebook/opt-125m — small enough to fit on most "
             "GPUs for a smoke test).",
    )
    p.add_argument(
        "--prompt", action="append", default=None,
        help="Prompt to generate against. Repeat to pass multiple "
             "prompts. If omitted when --real-vllm is set, a small "
             "default prompt list is used.",
    )
    p.add_argument(
        "--max-tokens", type=int, default=64,
        help="Max completion tokens per prompt under --real-vllm "
             "(default: 64).",
    )
    p.add_argument(
        "--block-size", type=int, default=16,
        help="Block size used to derive admissions under --real-vllm "
             "(default: 16).",
    )
    p.add_argument(
        "--dtype", type=str, default=None,
        help="Optional vllm dtype override (e.g. float16, bfloat16).",
    )
    p.add_argument(
        "--trust-remote-code", action="store_true",
        help="Pass trust_remote_code=True to vllm.LLM. Required for "
             "some custom architectures.",
    )
    p.add_argument(
        "--json", type=Path, default=None,
        help="If provided, write the transcript / real-run result to "
             "this JSON file.",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress the human-readable report.",
    )
    return p


_DEFAULT_REAL_PROMPTS: List[str] = [
    "Explain the PCAM project in two sentences.",
    "Write a one-line summary of vLLM's paged attention.",
    "Name three kinds of cache eviction algorithms.",
]


def run(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.real_vllm:
        prompts = args.prompt if args.prompt else list(_DEFAULT_REAL_PROMPTS)
        try:
            real_result = run_real_vllm_path(
                model=args.model,
                prompts=prompts,
                max_tokens=args.max_tokens,
                block_size=args.block_size,
                max_blocks=args.max_blocks,
                sink_tokens=args.sink_tokens,
                dtype=args.dtype,
                trust_remote_code=args.trust_remote_code,
            )
        except VLLMBridgeUnavailable as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        if not args.quiet:
            print(render_real_report(real_result))
        if args.json is not None:
            emit_json(real_result, args.json)
        return 0

    result = run_synthetic_walkthrough(
        max_blocks=args.max_blocks,
        sink_tokens=args.sink_tokens,
    )

    if not args.quiet:
        print(render_report(result))

    if args.json is not None:
        emit_json(result, args.json)

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
