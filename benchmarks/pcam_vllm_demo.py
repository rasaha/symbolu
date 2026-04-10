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


class RealVLLMNotAvailable(RuntimeError):
    """Raised when --real-vllm is requested but the path is not implemented."""


def _attempt_real_vllm_path() -> None:
    """
    Stub for the future real-vLLM execution path. Deliberately does
    not silently fall back to the synthetic path — a demo user who
    asked for the real path should get a clear, actionable error
    rather than wondering whether the numbers they're looking at
    came from a real model or a hand-written trace.
    """
    try:
        import vllm  # noqa: F401
    except ImportError as exc:
        raise RealVLLMNotAvailable(
            "--real-vllm requires the vllm package to be installed "
            "(pip install vllm). The synthetic demo path is the "
            "default and does not require vllm."
        ) from exc
    raise RealVLLMNotAvailable(
        "--real-vllm is not yet wired up. The Phase 3 demo ships only "
        "the synthetic walkthrough. Wiring a real vLLM model + PCAM "
        "eviction is Phase 4 work. Run without --real-vllm for the "
        "current demo."
    )


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PCAM vLLM-facing demo (Phase 3 synthetic walkthrough).",
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
        help="Attempt the real-vLLM execution path. Not yet implemented; "
             "fails with an explicit error rather than silently falling "
             "back to the synthetic demo.",
    )
    p.add_argument(
        "--json", type=Path, default=None,
        help="If provided, write the demo transcript to this JSON file.",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress the human-readable report.",
    )
    return p


def run(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.real_vllm:
        try:
            _attempt_real_vllm_path()
        except RealVLLMNotAvailable as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

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
